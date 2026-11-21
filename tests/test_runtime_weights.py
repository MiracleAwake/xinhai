from xinhai.service import MemoryService
from xinhai.configuration import ConfigManager
import pytest

def test_configuration_weights_change_order_and_request_overrides(tmp_path):
    class Provider:
        dimensions=2
        def embed(self,texts):
            return [[0.,1.] if '目标词' in t and t!='目标词' else [1.,0.] for t in texts]
    m=ConfigManager(tmp_path/'versions')
    m.activate(m.stage({'retrieval':{'weights':{'text':10.,'vector':1.}}},version='v1'))
    s=MemoryService(tmp_path/'w.sqlite',embedding_provider=Provider(),config_manager=m)
    s.remember('目标词字面记录',user_confirmed=True,branch_id='A')
    s.remember('另一条语义记录',user_confirmed=True,branch_id='A')
    rows=s.recall_evidence('目标词',branch_id='A')
    assert rows[0]['text']=='目标词字面记录' and rows[0]['weight_source']=='config'
    rows=s.recall_evidence('目标词',branch_id='A',weights={'text':1.,'vector':100.})
    assert rows[0]['text']=='另一条语义记录' and rows[0]['weight_source']=='request'
    assert not s.recall('目标词',branch_id='B')
    from xinhai.mcp_server import MemoryMCPAdapter
    from xinhai.api import create_app
    from fastapi.testclient import TestClient
    client=TestClient(create_app(MemoryMCPAdapter(s)))
    rows=client.get('/memories/evidence',params={'q':'目标词','branch_id':'A','text_weight':1,'vector_weight':100}).json()
    assert rows[0]['text']=='另一条语义记录' and rows[0]['weight_source']=='request'
    assert client.get('/memories/evidence',params={'q':'目标词','branch_id':'A'}).json()[0]['weight_source']=='config'
    for params in ({'text_weight':1},{'text_weight':-1,'vector_weight':1}):
        response=client.get('/memories/evidence',params={'q':'目标词',**params})
        assert response.status_code==422 and response.json()['error']['code']=='INVALID_WEIGHTS'
    with pytest.raises(ValueError): s.recall('目标词',weights={'text':float('nan'),'vector':1})
    s.close()
