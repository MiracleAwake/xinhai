from xinhai.service import MemoryService
from xinhai.mcp_server import MemoryMCPAdapter
from xinhai.api import create_app
from fastapi.testclient import TestClient

def test_review_list_combines_filters_and_exact_tags(tmp_path):
    s=MemoryService(tmp_path/'list.sqlite')
    a=s.store.remember(text='候选原文',branch_id='A',status='candidate',layer_id='worklog',tags=['review'])
    s.store.remember(text='其他分支',branch_id='B',status='candidate',layer_id='worklog',tags=['review'])
    s.store.remember(text='不同标签',branch_id='A',status='candidate',layer_id='worklog',tags=['review-extra'])
    client=TestClient(create_app(MemoryMCPAdapter(s)))
    rows=client.get('/memories',params={'branch_id':'A','status':'candidate','layer_id':'worklog','tag':'review'}).json()
    assert [r['id'] for r in rows]==[a['id']]
    assert rows[0]['text']=='候选原文'
    s.close()
