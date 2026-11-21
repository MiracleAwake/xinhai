from fastapi.testclient import TestClient

from xinhai.api import create_app
from xinhai.mcp_server import MemoryMCPAdapter
from xinhai.service import MemoryService


def test_checkpoint_history_filters_session_and_thread(tmp_path):
    service = MemoryService(tmp_path / 'checkpoints.sqlite')
    try:
        client = TestClient(create_app(MemoryMCPAdapter(service)))
        for session, thread, goal in [('a', 'x', 'first'), ('b', 'x', 'other'), ('a', 'y', 'latest')]:
            response = client.post('/checkpoints', json={
                'session_id': session, 'thread_id': thread, 'goal': goal, 'pending': ['review'],
            })
            assert response.status_code == 200
        assert client.get('/checkpoints').status_code == 422
        rows = client.get('/checkpoints', params={'session_id': 'a'}).json()
        assert [row['goal'] for row in rows] == ['latest', 'first']
        assert rows[0]['pending'] == ['review']
        rows = client.get('/checkpoints', params={'session_id': 'a', 'thread_id': 'x'}).json()
        assert [row['goal'] for row in rows] == ['first']
    finally:
        service.close()
