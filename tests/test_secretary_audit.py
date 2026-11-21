import json
from xinhai.service import MemoryService


def test_uncertainty_survives_database_reopen(tmp_path):
    class Provider:
        def extract(self, text):
            return {'summary':'测试完成，结果待复核','memory_layer':'核心记忆节点',
                    'tags':[], 'action':'待确认','uncertainty':'缺少独立复核'}
    path=tmp_path/'audit.sqlite'
    service=MemoryService(path, model_provider=Provider())
    original='完成接口测试，结果还需要独立复核。'
    result=service.remember(original, source_id='source-a', branch_id='A')
    rid=result.record['id']
    service.close()
    service=MemoryService(path)
    row=service.store.conn.execute("SELECT details_json FROM audit_events WHERE action='secretary_model' AND record_id=?",(rid,)).fetchone()
    audit=json.loads(row[0])
    assert audit['uncertainty']=='缺少独立复核'
    assert audit['draft']['memory_layer']=='核心记忆节点'
    assert audit['final_layer']=='worklog' and audit['is_verified'] is False
    assert audit['source_id']=='source-a'
    assert service.store.history(record_id=rid)[0]['text']==original
    service.confirm(rid)
    evidence=service.recall_evidence('接口测试', branch_id='A')[0]
    assert evidence['secretary_evidence']['uncertainty']=='缺少独立复核'
    assert evidence['secretary_evidence']['is_verified'] is False
    assert service.recall_evidence('接口测试', branch_id='B')==[]
    legacy=service.store.remember(text='旧记录兼容测试', branch_id='A')
    assert service.recall_evidence('旧记录兼容测试',branch_id='A')[0]['secretary_evidence']['uncertainty']=='unknown'
    service.close()
