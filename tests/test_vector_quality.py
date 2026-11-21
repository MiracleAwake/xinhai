from xinhai.service import MemoryService
def test_firewall_ocr_parser_extracts_only_explicit_rows():
    from xinhai.memory import parse_firewall_rules
    rows=parse_firewall_rules('Block Ollama outbound (prevent auto model download) True Block Outbound\nBlock Ollama App outbound False Block Outbound')
    assert len(rows)==2 and rows[0]['enabled'] is True and rows[1]['enabled'] is False
def test_image_write_audits_structured_ocr(tmp_path):
    s=MemoryService(tmp_path/'ocr-audit.sqlite')
    try:
        r=s.remember('防火墙截图',user_confirmed=True,modality='image',ocr_text='Block Ollama outbound True Block Outbound',branch_id='A')
        a=s.store.conn.execute("SELECT details_json FROM audit_events WHERE action='ocr_structured_fact' AND record_id=?",(r.record['id'],)).fetchone()
        assert a and 'enabled' in a['details_json']
    finally: s.close()
def test_structured_fact_recall_uses_audit_state(tmp_path):
    s=MemoryService(tmp_path/'structured-recall.sqlite')
    try:
        s.remember('截图A',user_confirmed=True,modality='image',ocr_text='Block Ollama outbound True Block Outbound',branch_id='A')
        s.remember('截图B',user_confirmed=True,modality='image',ocr_text='Block Ollama outbound False Block Outbound',branch_id='B')
        assert len(s.recall_structured(enabled=True,branch_id='A'))==1
        assert len(s.recall_structured(enabled=True,branch_id='B'))==0
        assert len(s.recall_structured(enabled=False,branch_id='B'))==1
    finally: s.close()
def test_compare_structured_groups_true_false_by_rule(tmp_path):
    s=MemoryService(tmp_path/'compare.sqlite')
    try:
        s.remember('图片A记录',user_confirmed=True,modality='image',ocr_text='Block Ollama outbound True Block Outbound',branch_id='A',asset_ref='a.png')
        s.remember('图片B记录',user_confirmed=True,modality='image',ocr_text='Block Ollama outbound False Block Outbound',branch_id='B',asset_ref='b.png')
        g=s.compare_structured()
        assert len(g['Block Ollama outbound']['enabled_true'])==1 and len(g['Block Ollama outbound']['enabled_false'])==1
    finally: s.close()
def test_recall_evidence_unifies_image_and_structured_fact(tmp_path):
    s=MemoryService(tmp_path/'evidence.sqlite')
    try:
        s.remember('图片证据',user_confirmed=True,modality='image',asset_ref='a.png',ocr_text='Block Ollama outbound True Block Outbound',visual_summary='防火墙表格',source_id='src-a',branch_id='A')
        e=s.recall_evidence('防火墙表格',modality='image',branch_id='A')
        assert e and e[0]['modality']=='image' and e[0]['asset_ref']=='a.png' and e[0]['structured_facts'][0]['enabled'] is True
    finally: s.close()
def test_visual_result_schema_normalizes_scalars():
    from xinhai.memory.model_provider import normalize_visual_result
    out=normalize_visual_result({'ocr':'一行','keywords':'Ollama','uncertainty':'路径可能不完整','visual_summary':None})
    assert out['ocr']==['一行'] and out['keywords']==['Ollama'] and out['uncertainty']==['路径可能不完整'] and out['visual_summary']==''
class FixedEmbedding:
    dimensions=2
    def embed(self,texts): return [[0.,1.] if t in {'今天午饭','精确词'} else [1.,0.] for t in texts]
def test_similarity_filter_preserves_text_and_relevant_vector(tmp_path,monkeypatch):
    monkeypatch.setenv('XINHAI_VECTOR_MIN_SIMILARITY','0.8'); s=MemoryService(tmp_path/'quality.sqlite',embedding_provider=FixedEmbedding())
    try:
        for text in ['数据库锁释义','今天午饭','精确词']: s.remember(text,user_confirmed=True,branch_id='A')
        rows=s.recall('锁库语义',branch_id='A'); assert [r['text'] for r in rows]==['数据库锁释义']
        assert '精确词' in [r['text'] for r in s.recall('精确词',branch_id='A')]; assert not s.recall('锁库语义',branch_id='B')
        monkeypatch.delenv('XINHAI_VECTOR_MIN_SIMILARITY'); assert len(s.recall('锁库语义',branch_id='A'))==3
    finally: s.close()
def test_soft_gate_keeps_low_similarity_without_claiming_verification(tmp_path,monkeypatch):
    monkeypatch.delenv('XINHAI_VECTOR_MIN_SIMILARITY',raising=False); monkeypatch.setenv('XINHAI_VECTOR_REVIEW_BELOW','0.55'); s=MemoryService(tmp_path/'soft.sqlite',embedding_provider=FixedEmbedding())
    try:
        s.remember('数据库锁释义',user_confirmed=True,branch_id='A'); s.remember('今天午饭',user_confirmed=True,branch_id='A')
        rows={r['text']:r for r in s.recall('锁库语义',branch_id='A')}; assert rows['今天午饭']['quality_status']=='needs_verification'; assert rows['今天午饭']['vector_similarity']==0.0; assert rows['数据库锁释义']['quality_status']=='candidate'; assert not s.recall('锁库语义',branch_id='B')
    finally: s.close()
def test_context_status_is_only_a_signal(tmp_path,monkeypatch):
    monkeypatch.delenv('XINHAI_VECTOR_MIN_SIMILARITY',raising=False); s=MemoryService(tmp_path/'context.sqlite')
    try:
        s.store.remember(text='短句',status='active',branch_id='A'); s.store.remember(text='这是一条有足够上下文的记录',status='active',branch_id='A',source_id='src-1')
        rows=s.recall('',branch_id='A',limit=10); by={r['text']:r for r in rows}; assert by['短句']['context_status']=='insufficient'; assert by['这是一条有足够上下文的记录']['context_status']=='sufficient'; assert all(r['status']=='active' for r in rows)
    finally: s.close()
def test_image_query_falls_back_to_terms(tmp_path):
    s=MemoryService(tmp_path/'image-query.sqlite')
    try:
        s.store.remember(text='Ollama 防火墙规则',status='active',modality='image',source_id='img-1')
        rows=s.recall('Ollama 防火墙',modality='image')
        assert rows and rows[0]['source_id']=='img-1'
    finally: s.close()
def test_secretary_and_recall_support_multimodal_fields(tmp_path):
    s=MemoryService(tmp_path/'mm-contract.sqlite')
    try:
        r=s.remember('图片记录',user_confirmed=True,branch_id='A',modality='image',asset_ref='asset://a',ocr_text='关闭网络规则',visual_summary='Ollama 出站防火墙')
        assert r.record['modality']=='image' and r.record['asset_ref']=='asset://a'
        rows=s.recall('关闭网络规则',modality='image',branch_id='A')
        assert rows and rows[0]['ocr_text']=='关闭网络规则'
    finally: s.close()
