import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
import os

import pytest

from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import MemoryMCPAdapter
from xinhai.service import MemoryService


def test_worker_does_not_claim_completed_job_from_stale_queue_snapshot(tmp_path):
    first_active = Event()
    second_done = Event()

    class PausedProvider:
        def extract(self, text):
            first_active.set()
            assert second_done.wait(timeout=10)
            return {"summary": text}

    path = tmp_path / "stale-queue.sqlite"
    first = MemoryService(path, model_provider=PausedProvider())
    second = MemoryService(path)
    identity = {"workspace_id": "simulation", "agent_id": "codex"}
    try:
        with TestClient(create_app(MemoryMCPAdapter(first))) as client:
            create_app(MemoryMCPAdapter(second))
            for branch in ("first", "second"):
                response = client.post("/imports", json={
                    **identity, "branch_id": branch, "session_id": branch,
                    "client_type": "codex", "filename": "synthetic.txt", "content": branch,
                })
                response.raise_for_status()
                client.post(f"/imports/{response.json()['id']}/start", params=identity).raise_for_status()

            with ThreadPoolExecutor(1) as pool:
                pending = pool.submit(first.run_import_queue)
                try:
                    assert first_active.wait(timeout=10)
                    other, = second.run_import_queue()
                    assert other["status"] == "completed"
                finally:
                    second_done.set()
                result, = pending.result(timeout=10)
            assert result["status"] == "completed" and result["id"] != other["id"]
    finally:
        first.close()
        second.close()


def test_seven_concurrent_archives_before_summary(tmp_path):
    calls = []
    class Provider:
        def extract(self, text):
            calls.append(text)
            return {'summary': text}

    service = MemoryService(tmp_path / 'seven.sqlite', model_provider=Provider())
    client = TestClient(create_app(MemoryMCPAdapter(service)))
    ready = Barrier(7)
    sample = (Path(__file__).parent / 'fixtures/codex_rehearsal_long_output.txt').read_text(encoding='utf8')

    def submit(index):
        identity = {'workspace_id': 'simulation', 'agent_id': (['codex']*3 + ['vega']*2 + ['gwen']*2)[index]}
        branch = f'branch-{index}'
        original = branch + '\n' + sample
        ready.wait(timeout=10)
        response = client.post('/imports', json={
            **identity, 'branch_id': branch, 'session_id': branch, 'client_type': 'codex',
            'filename': 'synthetic.txt', 'content': original,
        })
        response.raise_for_status()
        route = '/imports/' + response.json()['id']
        client.post(route + '/start', params=identity).raise_for_status()
        assert client.get(route + '/original', params=identity).json()['content'] == original
        return identity, branch, route, original

    try:
        with ThreadPoolExecutor(7) as pool:
            jobs = list(pool.map(submit, range(7)))
        assert not calls
        assert len({job[2] for job in jobs}) == 7
        assert all(client.get(route, params=identity).json()['queue_state'] == 'queued'
                   for identity, _, route, _ in jobs)
        results = service.run_import_queue()
        assert len(results) == 7 and all(r['status'] == 'completed' for r in results)
        assert len(calls) == 49
        for identity, branch, route, original in jobs:
            drafts = client.get(route + '/drafts', params=identity).json()
            assert ''.join(draft['summary'] for draft in drafts) == original
            rows = client.get('/memories', params={**identity, 'branch_id': branch}).json()
            assert [row['text'] for row in rows] == [original]
    finally:
        service.close()


@pytest.mark.parametrize('shared_layer', [False, True])
def test_three_branch_layers_and_originals(tmp_path, shared_layer):
    fixture = Path(__file__).parent / 'fixtures' / 'codex_rehearsal_long_output.txt'
    long_output = fixture.read_text(encoding='utf-8')
    ready = Barrier(3)
    path = tmp_path / 'three-branches.sqlite'
    services = []
    jobs = []

    class Provider:
        def __init__(self):
            self.first = True

        def extract(self, text):
            if self.first:
                self.first = False
                ready.wait(timeout=10)
            return {'summary': text}

    try:
        for index in range(3):
            service = MemoryService(path, model_provider=Provider())
            services.append(service)
            client = TestClient(create_app(MemoryMCPAdapter(service)))
            identity = {'workspace_id': 'simulation', 'agent_id': 'shared' if shared_layer else f'agent-{index}'}
            marker = f'SYNTHETIC-BRANCH-{index}'
            branch = f'branch-{index}'
            if shared_layer and index:
                layer_id = jobs[0][2]
            else:
                layer = client.post('/layers', json={
                **identity, 'name': '工作日志', 'description': '合成回执',
                    'keywords': ['SYNTHETIC-BRANCH-' if shared_layer else marker],
                    'tags': [marker],
                })
                layer.raise_for_status()
                layer_id = layer.json()['id']
                client.post(f'/layers/{layer_id}/confirm', params=identity).raise_for_status()
            transcript = f'{marker}\n{long_output}\n{marker}-END'
            content = '\n'.join(map(json.dumps, [
                {'type': 'session_meta'},
                {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': transcript}]}},
            ]))
            result = client.post('/imports', json={
                **identity, 'branch_id': branch, 'session_id': branch, 'client_type': 'codex',
                'format': 'codex-session-jsonl', 'filename': 'synthetic.jsonl', 'content': content,
            })
            result.raise_for_status()
            jobs.append((client, identity, layer_id, result.json()['id'], transcript, content, branch))

        assert len({job[2] for job in jobs}) == (1 if shared_layer else 3)
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending = [pool.submit(client.post, f'/imports/{job_id}/process', params=identity)
                       for client, identity, _, job_id, *_ in jobs]
            assert all(future.result(timeout=20).json()['status'] == 'completed' for future in pending)

        for index, (client, identity, layer_id, job_id, transcript, content, branch) in enumerate(jobs):
            route = f'/imports/{job_id}'
            assert client.get(route + '/original', params=identity).json()['content'] == content
            drafts = client.get(route + '/drafts', params=identity).json()
            assert ''.join(draft['summary'] for draft in drafts) == transcript
            for draft in drafts:
                source = draft['source']
                assert source['source_line'] == 2
                assert transcript[source['message_start']:source['message_end']] == draft['summary']
            assert drafts[0]['layer_ids'] == [layer_id]
            approved = client.post(route + '/drafts/0/confirm', params=identity).json()
            assert approved['status'] == 'confirmed'
            assert approved['is_verified'] is False
            sections = client.get(f'/layers/{layer_id}/document', params={**identity, 'branch_id': branch}).json()['sections']
            assert {(s['source_id'], s['record_id']) for s in sections} == {(job_id, approved['record_id'])}
            other_identity = {**identity, 'agent_id': 'other'} if shared_layer else jobs[(index + 1) % 3][1]
            assert client.get(route + '/original', params=other_identity).status_code == 404
            assert client.get(f'/layers/{layer_id}/document', params=other_identity).status_code == 404
            query = {**identity, 'branch_id': branch, 'q': f'SYNTHETIC-BRANCH-{index}'}
            assert [row['record_id'] for row in client.get('/memories/evidence', params=query).json()] == [approved['record_id']]
            query['branch_id'] = jobs[(index + 1) % 3][-1]
            assert client.get('/memories/evidence', params=query).json() == []
        if shared_layer:
            client, identity, layer_id, *_ = jobs[0]
            route = f'/layers/{layer_id}/document'
            sections = client.get(route, params=identity).json()['sections']
            assert {s['source_id'] for s in sections} == {job[3] for job in jobs}
            assert client.get(route, params={**identity, 'branch_id': 'absent'}).json()['sections'] == []
    finally:
        for service in services:
            service.close()


@pytest.mark.parametrize('large_branch', [
    False,
    pytest.param(True, marks=pytest.mark.skipif(
        os.environ.get('XINHAI_REHEARSAL_SCALE') != '1',
        reason='opt-in scale rehearsal based on the largest copied archive',
    )),
])
def test_long_codex_output_concurrent_branches_and_timeout_retry(tmp_path, large_branch):
    long_output = (Path(__file__).parent / 'fixtures' / 'codex_rehearsal_long_output.txt').read_text(encoding='utf-8')
    barrier = Barrier(2)
    other_finished = Event()

    class Provider:
        def __init__(self, fail):
            self.fail = fail
            self.calls = 0

        def extract(self, text):
            self.calls += 1
            if self.calls == 1:
                # Large archives parse and index before reaching the provider.
                barrier.wait(timeout=60 if large_branch else 10)
            if self.calls == 2 and self.fail:
                if not large_branch and not other_finished.wait(timeout=10):
                    raise RuntimeError('other branch stalled while model was waiting')
                raise TimeoutError()
            return {'summary': text}

    path = tmp_path / 'rehearsal.sqlite'
    services = [MemoryService(path, model_provider=Provider(i == 0)) for i in range(2)]
    identity = {'workspace_id': 'simulation', 'agent_id': 'codex'}
    jobs = []
    try:
        for i, service in enumerate(services):
            client = TestClient(create_app(MemoryMCPAdapter(service)))
            branch = f'branch-{i}'
            transcript = f'分支标记 {branch}\n' + long_output
            if large_branch and i == 1:
                transcript += '合成归档内容' * (33_220_000 // len('合成归档内容'))
            content = '\n'.join(json.dumps(item, ensure_ascii=False) for item in (
                {'type': 'session_meta'},
                {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': transcript}]}},
            ))
            result = client.post('/imports', json={
                **identity, 'session_id': branch, 'branch_id': branch, 'client_type': 'codex',
                'format': 'codex-session-jsonl', 'filename': 'simulation.jsonl', 'content': content,
            })
            result.raise_for_status()
            jobs.append((client, '/imports/' + result.json()['id'], transcript, content))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(c.post, route + '/process', params=identity) for c, route, _, _ in jobs]
            try:
                passed = futures[1].result(timeout=180 if large_branch else 10).json()
            finally:
                other_finished.set()
            failed = futures[0].result(timeout=20).json()
        assert failed['error'] == 'TimeoutError' and failed['segments_done'] == 1
        assert failed['failed_segment']['source']['message_start'] == 500
        assert passed['status'] == 'completed'

        for i, (client, route, transcript, content) in enumerate(jobs):
            status = client.post(route + '/process', params=identity).json()
            assert status['status'] == 'completed'
            assert status['failed_segment'] is None
            drafts = client.get(route + '/drafts', params=identity).json()
            assert ''.join(draft['summary'] for draft in drafts) == transcript
            assert len(drafts) == status['segments_total'] == status['segments_done']
            assert services[i].secretary.provider.calls == len(drafts) + (i == 0)
            assert client.get(route + '/original', params=identity).json()['content'] == content
            rows = client.get('/memories', params={**identity, 'branch_id': f'branch-{i}'}).json()
            assert [row['id'] for row in rows] == [status['record_id']]
    finally:
        for service in services:
            service.close()
