import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import MemoryMCPAdapter
from xinhai.service import MemoryService


def test_worker_resumes_after_process_is_killed(tmp_path):
    path = tmp_path / 'crash.sqlite'
    marker = tmp_path / 'second-segment'
    service = MemoryService(path)
    child = None
    try:
        client = TestClient(create_app(MemoryMCPAdapter(service)))
        identity = {'workspace_id': 'test', 'agent_id': 'test'}
        original = 'a' * 500 + 'b' * 500
        job_id = client.post('/imports', json={
            **identity, 'branch_id': 'test', 'session_id': 'test',
            'client_type': 'codex', 'filename': 'synthetic.txt', 'content': original,
        }).json()['id']
        route = f'/imports/{job_id}'
        assert client.post(route + '/start', params=identity).status_code == 202
        code = """
import sys, time
from pathlib import Path
from xinhai.onboarding import router_for
from xinhai.service import MemoryService
class Provider:
    def extract(self, text):
        if text.startswith('b'):
            Path(sys.argv[2]).touch()
            time.sleep(60)
        return {'summary': 'saved by first worker'}
s = MemoryService(sys.argv[1], model_provider=Provider())
router_for(s)
s.run_import_queue()
"""
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src')}
        child = subprocess.Popen([sys.executable, '-c', code, str(path), str(marker)], env=env)
        deadline = time.monotonic() + 10
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists()
        child.kill()
        child.wait(timeout=5)
        assert client.get(route, params=identity).json()['segments_done'] == 1
        assert service.run_import_queue() == []
        # Simulate elapsed lease time without waiting for the production TTL.
        with service.store.conn:
            service.store.conn.execute('UPDATE import_leases_v1 SET expires=0 WHERE job_id=?', (job_id,))
        assert service.run_import_queue()[0]['status'] == 'completed'
        drafts = client.get(route + '/drafts', params=identity).json()
        assert [draft['summary'] for draft in drafts] == ['saved by first worker', 'b' * 500]
        assert client.get(route + '/original', params=identity).json()['content'] == original
        assert (tmp_path / 'import-snapshots' / f'{job_id}.sqlite').is_file()
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        service.close()
