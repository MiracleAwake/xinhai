from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.service import MemoryService
from xinhai.mcp_server import MemoryMCPAdapter

def test_codex_jsonl_archive_and_source_lines(tmp_path):
    import json

    service = MemoryService(tmp_path / 'codex.sqlite')
    try:
        client = TestClient(create_app(MemoryMCPAdapter(service)))
        identity = {'workspace_id': 'w', 'agent_id': 'a'}
        item = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
            'id': 'event-1', 'content': [{'type': 'input_text', 'text': '合成消息'}]}}
        content = '\n'.join(map(json.dumps, [
            {'type': 'session_meta'}, item, item,
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'developer',
                'content': [{'type': 'input_text', 'text': '内部元数据'}]}},
        ]))
        job_id = client.post('/imports', json={
            **identity, 'branch_id': 'A', 'session_id': 's', 'client_type': 'codex',
            'format': 'codex-session-jsonl', 'filename': 'synthetic.jsonl', 'content': content,
        }).json()['id']
        route = f'/imports/{job_id}'
        result = client.post(route + '/process', params=identity).json()
        assert result['status'] == 'completed' and result['segments_total'] == 1
        drafts = client.get(route + '/drafts', params=identity).json()
        assert drafts[0]['summary'] == '合成消息' and drafts[0]['source']['source_line'] == 2
        approved = client.post(
            route + f"/drafts/{drafts[0]['start_offset']}/confirm", params=identity,
        ).json()
        assert approved['status'] == 'confirmed'
        query = {**identity, 'q': '合成消息', 'branch_id': 'A'}
        evidence = client.get('/memories/evidence', params=query).json()
        assert any(row['record_id'] == approved['record_id'] and row['source_ref'] == job_id
                   for row in evidence)
        assert client.get('/memories/evidence', params={**query, 'branch_id': 'B'}).json() == []
        assert service.store.history(record_id=result['record_id'])[0]['text'] == '合成消息'
        assert client.get(route + '/original', params=identity).json()['content'] == content
    finally:
        service.close()

def test_reassigned_lease_rejects_old_model_output(tmp_path):
    import sqlite3
    import time
    from contextlib import closing

    path = tmp_path / 'lease.sqlite'
    service = MemoryService(path)
    try:
        client = TestClient(create_app(MemoryMCPAdapter(service)))
        identity = {'workspace_id': 'w', 'agent_id': 'a'}
        job_id = client.post('/imports', json={
            **identity, 'branch_id': 'A', 'session_id': 's', 'client_type': 'codex',
            'filename': 'synthetic.txt', 'content': '合成会话原文',
        }).json()['id']

        class Provider:
            def extract(self, text):
                with closing(sqlite3.connect(path)) as other, other:
                    other.execute(
                        'UPDATE import_leases_v1 SET owner=?, expires=? WHERE job_id=?',
                        ('new-worker', time.time()+60, job_id))
                return {'summary': '旧进程草稿'}

        service.secretary.provider = Provider()
        response = client.post(f'/imports/{job_id}/process', params=identity)
        assert response.status_code == 409
        assert client.get(f'/imports/{job_id}/drafts', params=identity).json() == []
        assert client.get(f'/imports/{job_id}', params=identity).json()['status'] == 'processing'
        with service.store.conn:
            service.store.conn.execute('UPDATE import_leases_v1 SET expires=0 WHERE job_id=?', (job_id,))
        service.secretary.provider = None
        assert client.post(f'/imports/{job_id}/process', params=identity).json()['status'] == 'completed'
        assert len(client.get(f'/imports/{job_id}/drafts', params=identity).json()) == 1
    finally:
        service.close()

def test_snapshot_failure_leaves_existing_memory_intact(tmp_path):
    service = MemoryService(tmp_path / 'memory.sqlite')
    try:
        record = service.store.remember(text='已有记忆', status='active')
        client = TestClient(create_app(MemoryMCPAdapter(service)))
        (tmp_path / 'import-snapshots').write_text('blocks directory creation', encoding='utf-8')
        identity = {'workspace_id': 'w', 'agent_id': 'a'}
        response = client.post('/imports', json={
            **identity, 'branch_id': 'A', 'session_id': 's', 'client_type': 'codex',
            'filename': 'synthetic.txt', 'content': '待导入测试文本',
        })
        assert response.status_code == 503
        assert client.get('/imports', params=identity).json() == []
        assert service.store.history() == [record]
    finally:
        service.close()

def test_import_preserves_noise_and_layer_requires_confirmation(tmp_path):
    s=MemoryService(tmp_path/'i.sqlite'); c=TestClient(create_app(MemoryMCPAdapter(s)))
    identity={'workspace_id':'w','agent_id':'a'}
    layer=c.post('/layers',json={**identity,'name':'回忆录','description':'歌曲评价','keywords':['歌曲'],'tags':['音乐']}).json()
    assert layer['status']=='draft'
    assert c.post('/layers/'+layer['id']+'/confirm',params=identity).json()['status']=='active'
    content='好的\n歌曲的评价\n收到\n'
    body={**identity,'branch_id':'A','session_id':'s','client_type':'generic','filename':'session.txt','content':content}
    result=c.post('/imports',json=body).json(); jid=result['id']
    import sqlite3
    from contextlib import closing
    snapshot=tmp_path/'import-snapshots'/f'{jid}.sqlite'
    with closing(sqlite3.connect(snapshot)) as backup:
        assert backup.execute('SELECT count(*) FROM custom_layers_v1').fetchone()[0]==1
        assert backup.execute('SELECT count(*) FROM session_imports_v1').fetchone()[0]==0
    good_snapshot = snapshot.read_bytes()
    snapshot.write_bytes(b'corrupt test snapshot')
    failure = c.post(f'/imports/{jid}/process', params=identity).json()
    assert failure['status']=='failed' and failure['error']=='SnapshotFailed'
    assert failure['record_id'] is None and failure['segments_done']==0
    assert c.get(f'/imports/{jid}/original', params=identity).json()['content']==content
    assert snapshot.read_bytes()==b'corrupt test snapshot'
    snapshot.write_bytes(good_snapshot)
    assert c.post('/imports',json=body).json()['id']==jid
    assert c.get(f'/imports/{jid}/original',params=identity).json()['content']==content
    assert c.get(f'/imports/{jid}/original',params={**identity,'agent_id':'b'}).status_code==404
    result=c.post(f'/imports/{jid}/process',params=identity).json()
    assert result['status']=='completed'
    record=s.store.history(record_id=result['record_id'])[0]
    assert record['text']==content and record['layer_id']==layer['id']
    assert c.post(f'/imports/{jid}/process',params=identity).json()==result
    drafts=c.get(f'/imports/{jid}/drafts',params=identity).json()
    assert drafts[0]['summary']==content and drafts[0]['summary_kind']=='verbatim_excerpt'
    assert drafts[0]['start_offset']==0 and drafts[0]['end_offset']==len(content)
    assert drafts[0]['layer_ids']==[layer['id']] and drafts[0]['is_verified'] is False
    assert result['segments_done']==result['segments_total']==1
    assert c.post(f'/imports/{jid}/start',params=identity).status_code==202
    approved=c.post(f'/imports/{jid}/drafts/0/confirm',params=identity).json()
    assert approved['status']=='confirmed' and approved['is_verified'] is False
    assert c.post(f'/imports/{jid}/drafts/0/confirm',params=identity).json()['record_id']==approved['record_id']
    coverage, = c.get(f"/memory-maintenance/{approved['record_id']}",params={**identity,'branch_id':'A'}).json()['relations']
    assert coverage['type']=='covers' and coverage['to_id']==jid
    assert coverage['metadata']=={'target_type':'import','offset_basis':'archive_text','start':0,'end':len(content)}
    document=c.get('/layers/'+layer['id']+'/document',params=identity).json()
    assert document['sections'][0]['source_id']==jid
    assert c.get('/layers/'+layer['id']+'/document',params={**identity,'agent_id':'b'}).status_code==404
    defaults=c.post('/layers/install-defaults',params=identity).json()
    assert len(defaults)==6 and all(x['status']=='draft' for x in defaults if x['id']!=layer['id'])
    assert len(c.post('/layers/install-defaults',params=identity).json())==6
    assert list(snapshot.parent.glob('*.sqlite'))==[snapshot]
    s.close()

def test_queued_import_survives_restart(tmp_path):
    path=tmp_path/'restart.sqlite'
    s=MemoryService(path); c=TestClient(create_app(MemoryMCPAdapter(s)))
    identity={'workspace_id':'w','agent_id':'a'}
    body={**identity,'branch_id':'A','session_id':'s','client_type':'codex','filename':'export.txt','content':'完整原文\n好的'}
    jid=c.post('/imports',json=body).json()['id']
    snapshot = tmp_path / 'import-snapshots' / f'{jid}.sqlite'
    snapshot.unlink()  # Simulate an archive created before snapshot support.
    assert c.post(f'/imports/{jid}/start',params=identity).json()['durable_queue']
    import time
    with s.store.conn:
        s.store.conn.execute('INSERT INTO import_leases_v1 VALUES (?,?,?,1)',(jid,'old-worker',time.time()+100))
    assert s.run_import_queue()==[]
    assert c.post(f'/imports/{jid}/start',params=identity).status_code==409
    assert c.post(f'/imports/{jid}/process',params=identity).status_code==409
    with s.store.conn:
        s.store.conn.execute('UPDATE import_leases_v1 SET expires=0 WHERE job_id=?',(jid,))
    s.close()
    s=MemoryService(path); c=TestClient(create_app(MemoryMCPAdapter(s)))
    results=s.run_import_queue()
    assert results[0]['status']=='completed'
    assert snapshot.is_file()
    assert s.run_import_queue()==[]
    assert c.get(f'/imports/{jid}/original',params=identity).json()['content']==body['content']
    s.close()
