from xinhai.service import MemoryService

def test_term_match_does_not_verify_requested_state(tmp_path):
    s=MemoryService(tmp_path/'match.sqlite')
    s.remember('规则截图记录',user_confirmed=True,branch_id='A',modality='image',
               ocr_text='Block Ollama outbound False Block Outbound')
    row=s.recall_evidence('True Block Outbound',branch_id='A')[0]
    reason=row['match_reason']
    assert reason['kind']=='term_fallback'
    assert reason['terms']==['Block','Outbound']
    assert reason['structured_state_verified'] is False
    assert row['structured_facts'][0]['enabled'] is False
    assert s.recall_evidence('True Block Outbound',branch_id='B')==[]
    assert s.recall_evidence('规则截图记录',branch_id='A')[0]['match_reason']['kind']=='literal_query'
    s.close()

def test_filtered_vector_has_no_participating_score(tmp_path,monkeypatch):
    class Provider:
        dimensions=2
        def embed(self,texts):
            return [[0.,1.] if '旧备份' in t else [1.,0.] for t in texts]
    monkeypatch.setenv('XINHAI_VECTOR_MIN_SIMILARITY','0.5')
    s=MemoryService(tmp_path/'filtered.sqlite',embedding_provider=Provider())
    s.remember('网络规则旧备份',user_confirmed=True,branch_id='A')
    row=s.recall('网络规则',branch_id='A')[0]
    assert row['match_reason']['channels']==row['retrieval_channels']==['text']
    assert row['vector_similarity'] is None
    assert s.recall_evidence('网络规则',branch_id='A')[0]['score'] is None
    s.close()

def test_hybrid_match_channels_preserve_literal_reason(tmp_path):
    class Provider:
        dimensions=2
        def embed(self,texts): return [[1.,0.] for _ in texts]
    s=MemoryService(tmp_path/'hybrid.sqlite',embedding_provider=Provider())
    s.remember('数据库锁定记录',user_confirmed=True,branch_id='A')
    s.remember('含目标词的测试记录',user_confirmed=True,branch_id='A')
    rows={r['text']:r for r in s.recall_evidence('目标词',branch_id='A')}
    literal=rows['含目标词的测试记录']['match_reason']
    vector=rows['数据库锁定记录']['match_reason']
    assert literal['kind']=='literal_query' and literal['terms']==['目标词']
    assert literal['channels']==['text','vector']
    assert vector['kind']=='vector' and vector['terms']==[] and vector['channels']==['vector']
    assert not vector['structured_state_verified']
    assert s.recall_evidence('目标词',branch_id='B')==[]
    s.close()
