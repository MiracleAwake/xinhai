from pathlib import Path
from xinhai import MemoryStore

def test_remember_idempotent_and_history(tmp_path: Path):
    s = MemoryStore(tmp_path / "x.sqlite")
    first = s.remember(text="保留这条原话", tags=["项目:心海"], idempotency_key="a")
    second = s.remember(text="保留这条原话", tags=["项目:心海"], idempotency_key="a")
    assert first["id"] == second["id"]
    assert s.history()[0]["text"] == "保留这条原话"

def test_forget_keeps_original(tmp_path: Path):
    s = MemoryStore(tmp_path / "x.sqlite")
    row = s.remember(text="旧决定")
    changed = s.forget(row["id"], "被新决定替代")
    assert changed["status"] == "obsolete"
    assert changed["text"] == "旧决定"
from pathlib import Path
from xinhai import MemoryStore
from xinhai.retrieval import search

def test_recall_excludes_obsolete_by_default(tmp_path: Path):
    s = MemoryStore(tmp_path / "x.sqlite")
    old = s.remember(text="旧方案 使用 SQLite", tags=["方案"])
    s.forget(old["id"], "被新方案替代")
    s.remember(text="新方案 使用 MySQL", tags=["方案"])
    result = search(s, "方案")
    assert [x["text"] for x in result] == ["新方案 使用 MySQL"]
    assert len(search(s, "方案", include_obsolete=True)) == 2
from pathlib import Path
from xinhai import MemoryStore

def test_layer_and_tags(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite')
    row=s.remember(text='记录经验', layer_id='lesson', tags=['错误','项目:心海'])
    assert row['layer_id']=='lesson'
    assert s.conn.execute('SELECT count(*) FROM tags').fetchone()[0]==2
    assert s.conn.execute('SELECT count(*) FROM audit_events').fetchone()[0]==1
from pathlib import Path
from xinhai import MemoryStore
from xinhai.retrieval import search

def test_recall_filters(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite')
    s.remember(text='日志里的方案', layer_id='worklog', session_id='s1', tags=['项目:心海'])
    s.remember(text='经验里的方案', layer_id='lesson', session_id='s2', tags=['项目:其他'])
    assert [r['text'] for r in search(s,'方案',layer_id='worklog',tag='项目:心海',session_id='s1')] == ['日志里的方案']

def test_checkpoint_roundtrip(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite')
    row=s.checkpoint(session_id='s1', goal='恢复任务', confirmed_facts=['事实'], decisions=['决定'], completed=['已做'], pending=['待做'], unknown=['结果未知'], next_step='继续')
    assert row['goal']=='恢复任务' and row['unknown']==['结果未知'] and row['next_step']=='继续'
from pathlib import Path
from xinhai import MemoryStore
from xinhai.memory import MemorySecretary
from xinhai.service import MemoryService
from xinhai.memory import split_text
def test_embedding_provider_import_is_lazy():
 from xinhai.retrieval.embedding import SentenceTransformerProvider
 assert SentenceTransformerProvider.__name__=='SentenceTransformerProvider'
def test_vector_store_accepts_hash_provider(tmp_path):
 from xinhai.retrieval.embedding import HashEmbeddingProvider
 from xinhai.retrieval.vector_store import VectorStore
 from xinhai.store import MemoryStore
 st=MemoryStore(tmp_path/'vectors.sqlite'); p=HashEmbeddingProvider(4); v=VectorStore(st.conn,p); rec=st.remember(text='向量测试')
 v.add(rec['id'],rec['text']); assert st.conn.execute('SELECT count(*) FROM record_vectors').fetchone()[0]==1; st.close()
def test_vector_retriever_reads_sqlite_vectors(tmp_path):
 from xinhai.retrieval.embedding import HashEmbeddingProvider
 from xinhai.retrieval.vector_store import VectorStore
 from xinhai.retrieval.vector import VectorRetriever
 from xinhai.retrieval.pipeline import QueryPlan
 from xinhai.store import MemoryStore
 st=MemoryStore(tmp_path/'vr.sqlite'); p=HashEmbeddingProvider(4); rec=st.remember(text='向量召回测试',status='active'); VectorStore(st.conn,p).add(rec['id'],rec['text'])
 out=VectorRetriever(p,st).retrieve(QueryPlan('向量召回测试')); assert out and out[0].record_id==rec['id']; st.close()
def test_hybrid_retriever_fuses_vector_and_text(tmp_path):
 from xinhai.retrieval.embedding import HashEmbeddingProvider
 from xinhai.retrieval.vector_store import VectorStore
 from xinhai.retrieval.vector import VectorRetriever
 from xinhai.retrieval.pipeline import QueryPlan, HybridRetriever, Evidence
 from xinhai.store import MemoryStore
 class TextStub:
  def retrieve(self,plan): return [Evidence('text-id','文本证据',0.8,modality='text')]
 st=MemoryStore(tmp_path/'hybrid.sqlite'); p=HashEmbeddingProvider(4); rec=st.remember(text='向量证据',status='active'); VectorStore(st.conn,p).add(rec['id'],rec['text'])
 out=HybridRetriever([TextStub(),VectorRetriever(p,st)]).retrieve(QueryPlan('向量证据'))
 assert {x.record_id for x in out}=={'text-id',rec['id']}; st.close()
def test_fusion_accepts_route_weights():
 from xinhai.retrieval.pipeline import Fusion, Evidence
 out=Fusion(weights=[1.0,2.0]).merge([[Evidence('a','a')],[Evidence('b','b')]])
 assert out[0][0]=='b'
def test_recall_detector_normalizes_reference_suffix():
 from xinhai.memory.recall_detector import detect
 d=detect('接着上次那条分支A的验收句子')
 assert d.should_recall and '验收句子' not in d.query and d.query.startswith('那条分支A')
def test_auto_recall_keyword_fallback(tmp_path):
 s=MemoryService(tmp_path/'auto.sqlite'); s.store.remember(text='分支A 验收通过',status='active',branch_id='A')
 out=s.auto_recall('接着上次 分支A 验收',branch_id='A')
 assert out['decision']['should_recall'] and out['records']; s.close()
def test_auto_recall_uses_explicit_branch_id_as_fallback(tmp_path):
 s=MemoryService(tmp_path/'auto-branch.sqlite'); s.store.remember(text='Cursor验收 GO-CURSOR-A：只属于分支A',status='active',branch_id='GO-CURSOR-A')
 out=s.auto_recall('接着上次那条分支A的验收句子',branch_id='GO-CURSOR-A')
 assert out['records'] and out['records'][0]['branch_id']=='GO-CURSOR-A'; s.close()
def test_keyword_reranker_boosts_exact_evidence():
 from xinhai.retrieval.pipeline import KeywordReranker, Evidence
 out=KeywordReranker().rank('SQLite 锁',[Evidence('a','防火墙规则',.9),Evidence('b','SQLite 写入锁',.2)])
 assert out[0].record_id=='b'
def test_hybrid_supports_rerank_and_low_quality_filter():
 from xinhai.retrieval.pipeline import HybridRetriever, Evidence, QueryPlan, KeywordReranker
 class R:
  def __init__(self,rows): self.rows=rows
  def retrieve(self,plan): return self.rows
 out=HybridRetriever([R([Evidence('a','无关',.01),Evidence('b','SQLite 锁',.8)])],reranker=KeywordReranker(),min_score=.01).retrieve(QueryPlan('SQLite 锁'))
 assert out[0].record_id=='b'
def test_query_planner_routes_exact_and_semantic_queries():
 from xinhai.retrieval.pipeline import QueryPlanner
 p=QueryPlanner(); assert p.route_weights('sqlite OperationalError') ['text']==2.0
 assert p.route_weights('请回忆我们之前如何设计长期记忆分层') ['vector']==2.0
def test_chinese_chunker_preserves_bounds():
 text='第一段。第二段！第三段？' * 100
 chunks=split_text(text,max_chars=80,overlap=10)
 assert chunks and all(len(x)<=80 for x in chunks)
 assert ''.join(chunks).replace('第一段。','').replace('第二段！','').replace('第三段？','') is not None
import pytest
def test_markdown_requires_layers(tmp_path):
 with pytest.raises(ValueError, match='markdown_root requires layers_path'):
  MemoryService(tmp_path/'x.sqlite', markdown_root=tmp_path/'memory')
class FakeModelProvider:
 def extract(self,text,**kwargs): return {'summary':'模型摘要','memory_layer':'工作日志','tags':['模型测试'],'action':'记录'}
def test_service_optional_model_provider(tmp_path):
 s=MemoryService(tmp_path/'model.sqlite',model_provider=FakeModelProvider())
 r=s.remember('完成一次模型接入测试')
 assert r.layer_id=='worklog' and r.summary=='模型摘要' and '模型测试' in r.tags
class MisleadingLayerProvider:
 def extract(self,text,**kwargs): return {'summary':'模型摘要','memory_layer':'核心记忆节点','tags':['模型测试'],'action':'记录','uncertainty':'无'}
def test_model_layer_is_draft_and_rules_remain_authoritative(tmp_path):
 s=MemoryService(tmp_path/'misleading.sqlite',model_provider=MisleadingLayerProvider())
 r=s.remember('完成一次接口回归测试，pytest 通过')
 assert r.layer_id=='worklog' and r.summary=='模型摘要'
class InvalidModelProvider:
 def extract(self,text,**kwargs): return {'summary':'坏格式','memory_layer':'工作日志','action':'记录','tags':'not-list','uncertainty':None}
def test_invalid_model_output_falls_back(tmp_path):
 s=MemoryService(tmp_path/'invalid.sqlite',model_provider=InvalidModelProvider())
 r=s.remember('完成一次测试验证')
 assert r.layer_id=='worklog' and r.summary.startswith('完成一次')
class LongModelProvider:
 def extract(self,text,**kwargs): return {'summary':'长'*400,'memory_layer':'工作日志','tags':[],'action':'记录','uncertainty':''}
def test_model_summary_is_bounded_and_noise_rejected(tmp_path):
 s=MemoryService(tmp_path/'long.sqlite',model_provider=LongModelProvider())
 r=s.remember('完成长文本测试')
 assert len(r.summary)<=240
 assert s.remember('好的').decision=='rejected'
def test_versioned_config_activation_and_rollback(tmp_path):
 from xinhai.configuration import ConfigManager
 m=ConfigManager(tmp_path/'config')
 first=m.stage({'retrieval': {'weights': {'text': 1.0, 'vector': 1.0}}}, version='v1', author='test', reason='baseline')
 m.activate(first)
 second=m.stage({'retrieval': {'weights': {'text': 2.0, 'vector': 1.0}}, 'secret_setting':'new-secret'}, version='v2', author='test', reason='tune')
 m.activate(second)
 assert m.current()['version']=='v2'
 assert m.rollback('v1')['version']=='v1'
 assert m.current()['version']=='v1'
 assert {x['version'] for x in m.history()} >= {'v1','v2'}
 assert m.diff('v1','v2')['retrieval']['to']['weights']['text']==2.0
 assert m.diff('v1','v2')['secret_setting']=={'from': '[REDACTED]', 'to': '[REDACTED]'}
 assert m.runtime_options()['retrieval.weights']=={'text': 1.0, 'vector': 1.0}
 bad=dict(second); bad['config']={'drop_original_text': True}; bad['checksum']=m.checksum({k: bad[k] for k in bad if k not in {'checksum','validation_status'}})
 import pytest
 with pytest.raises(ValueError): m.activate(bad)
def test_runtime_config_status_is_read_only(tmp_path):
 from xinhai.configuration import ConfigManager
 from xinhai.mcp_server import build_adapter
 from xinhai.api import create_app
 from fastapi.testclient import TestClient
 m=ConfigManager(tmp_path/'versions')
 m.activate(m.stage({'retrieval': {'weights': {'text': 1.0, 'vector': 1.0}}}, version='v1', reason='test'))
 a=build_adapter(tmp_path/'x.sqlite',None,tmp_path/'memory',tmp_path/'versions')
 c=TestClient(create_app(a)); assert c.get('/config/current').json()['version']=='v1'; assert c.get('/config/history').json()[0]['version']=='v1'; assert c.get('/config/diff',params={'older':'v1','newer':'v1'}).json()=={}
 assert a.call('config_status',{})['validation_status']=='valid'
def test_process_long_creates_bounded_candidates(tmp_path):
 s=MemoryService(tmp_path/'chunks.sqlite')
 results=s.secretary.process_long('完成第一项测试。' * 100,max_chars=40)
 assert len(results)>1 and all(x.record and x.decision=='candidate' for x in results)
def test_write_chain_source_confirm_and_obsolete(tmp_path):
 layers=Path('config/memory_layers.yaml').resolve()
 s=MemoryService(tmp_path/'chain.sqlite',layers_path=layers,markdown_root=tmp_path/'md')
 rows=s.secretary.process_long('完成第一项工作。完成第二项验证。',max_chars=12,branch_id='B1')
 sources={r.record['source_id'] for r in rows}; assert len(sources)==1
 first=rows[0].record['id']; active=s.confirm(first); assert active['status']=='active'
 again=s.confirm(first); assert again['status']=='active'
 files=list((tmp_path/'md').rglob('*.md')); assert len(files)==1 and first in files[0].read_text(encoding='utf-8')
 obsolete=s.forget(first,'测试废弃'); assert obsolete['status']=='obsolete' and obsolete['text']
 s.close()
def test_recall_can_expand_source(tmp_path):
 s=MemoryService(tmp_path/'expand.sqlite')
 rows=s.secretary.process_long('第一片包含目标词。第二片是同一来源上下文。',max_chars=12,user_confirmed=True)
 found=s.recall('目标词',expand_source=True,limit=10)
 assert len({r['source_id'] for r in found})==1 and len(found)>=2
 s.close()
def test_multimodal_metadata_preserves_text_record(tmp_path):
 s=MemoryService(tmp_path/'multi.sqlite')
 r=s.store.remember(text='图片中的测试结果',modality='image',asset_ref='asset://demo/1',ocr_text='测试结果',visual_summary='终端截图')
 assert r['text']=='图片中的测试结果' and r['modality']=='image' and r['asset_ref']=='asset://demo/1'
 s.close()
def test_recall_modality_filter(tmp_path):
 s=MemoryService(tmp_path/'modality.sqlite')
 s.store.remember(text='共同关键词文本',modality='text')
 s.store.remember(text='共同关键词图片',modality='image')
 assert all(r['modality']=='image' for r in s.recall('共同关键词',modality='image'))
 s.close()

def test_secretary_rejects_noise(tmp_path: Path):
    result=MemorySecretary(MemoryStore(tmp_path/'x.sqlite')).process('好的')
    assert result.decision=='rejected' and result.record is None
    for text in ('正在重连 1/5', '工具调用进度：已运行命令。'):
        result=MemorySecretary(MemoryStore(tmp_path/f'{len(text)}.sqlite')).process(text)
        assert result.decision=='rejected' and result.record is None

def test_secretary_classifies_candidate(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite')
    result=MemorySecretary(s).process('这次测试失败，原因是路径错误，已经修复', session_id='s1')
    assert result.decision=='candidate' and result.layer_id=='lesson'
    assert result.record['status']=='candidate'
from pathlib import Path
from xinhai import MemoryStore
from xinhai.memory import MemorySecretary, LayerRegistry, MarkdownWriter

def test_layers_load_and_markdown_idempotent(tmp_path: Path):
    config=Path(__file__).parents[1]/'config'/'memory_layers.yaml'
    registry=LayerRegistry(config)
    assert registry.get('lesson')['name']=='经验教训库'
    s=MemoryStore(tmp_path/'x.sqlite')
    result=MemorySecretary(s).process('测试失败，原因是路径错误', session_id='s1', user_confirmed=True)
    writer=MarkdownWriter(tmp_path/'memory')
    target=writer.append(layer=registry.get(result.layer_id), record=result.record, summary=result.summary, tags=result.tags)
    writer.append(layer=registry.get(result.layer_id), record=result.record, summary=result.summary, tags=result.tags)
    assert target.exists() and target.read_text(encoding='utf-8').count('<!-- xinhai-record:' + result.record['id'] + ' -->')==1
from pathlib import Path
from xinhai import MemoryStore
from xinhai.memory import MemoryGatekeeper

def test_gatekeeper_filters_and_audits(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite')
    a=s.remember(text='可用记忆', scope='personal', tags=['ok'])
    b=s.remember(text='废弃记忆', scope='personal', tags=['ok'])
    s.forget(b['id'], '测试')
    b=s.history(record_id=b['id'])[0]
    out=MemoryGatekeeper(s).filter([a,b], required_tags={'ok'})
    assert [x['text'] for x in out]==['可用记忆']
    assert s.conn.execute("SELECT count(*) FROM audit_events WHERE actor='gatekeeper'").fetchone()[0]==2
from pathlib import Path
from xinhai import MemoryService

def test_service_confirm_and_recall(tmp_path: Path):
    root=tmp_path/'root'; (root/'config').mkdir(parents=True); (root/'config'/'memory_layers.yaml').write_text('layers:\n  - id: lesson\n    name: 经验教训库\n    description: x\n    scope: workspace\n    markdown_path: 经验教训库\n',encoding='utf8')
    s=MemoryService(root/'x.sqlite',layers_path=root/'config'/'memory_layers.yaml',markdown_root=root/'memory')
    result=s.remember('测试失败，原因是路径错误',user_confirmed=False)
    assert result.decision=='candidate'
    row=s.confirm(result.record['id'])
    assert row['status']=='active'
    assert s.recall('路径', layer_id='lesson')
    assert list((root/'memory').rglob('*.md'))
from pathlib import Path
from xinhai.mcp_server import MemoryMCPAdapter, TOOLS
from xinhai import MemoryService

def test_mcp_adapter_contract(tmp_path: Path):
    root=tmp_path/'root'; (root/'config').mkdir(parents=True); (root/'config'/'memory_layers.yaml').write_text('layers:\n  - id: node\n    name: 核心记忆节点\n    description: x\n    scope: personal\n    markdown_path: 核心记忆节点\n',encoding='utf8')
    a=MemoryMCPAdapter(MemoryService(root/'x.sqlite',layers_path=root/'config'/'memory_layers.yaml',markdown_root=root/'memory'))
    result=a.call('remember', {'text':'重要记忆', 'user_confirmed':False})
    assert result['decision']=='candidate'
    assert set(TOOLS)=={'remember','confirm','auto_recall','recall','recall_evidence','recall_structured','compare_structured','config_status','config_history','config_diff','checkpoint','history','forget','rebuild_vectors','rebuild_summary','supersede','cover_memory','verify_memory','memory_provenance'}
from pathlib import Path
from xinhai.adapters import HarnessAdapter, CursorAdapter, CodexAdapter, WorkBuddyAdapter

def test_adapters_normalize_and_flag_unknown():
    for adapter in [HarnessAdapter(), CursorAdapter(), CodexAdapter(), WorkBuddyAdapter()]:
        event=adapter.normalize({'event_id':'e1','speaker':'user','event_kind':'message','text':'hello','future_field':1})
        assert event.client_type==adapter.capabilities.client_type
        assert 'future_field' in event.unmapped
        assert adapter.denormalize(event)['event_id']=='e1'
from pathlib import Path
from xinhai import MemoryStore
from xinhai.adapters import CodexAdapter
from xinhai.memory import MemorySecretary

def test_secretary_accepts_internal_event(tmp_path: Path):
    s=MemoryStore(tmp_path/'x.sqlite'); event=CodexAdapter().normalize({'event_id':'e1','event_kind':'message','speaker':'user','text':'记住这个项目决定','session_id':'s1'})
    result=MemorySecretary(s).process_event(event)
    assert result.record['session_id']=='s1' and 'event:message' in result.tags
from xinhai.adapters.events import DSHAdapter

def test_dsh_event_mapping():
    e=DSHAdapter().normalize({'type':'compaction/summary','id':'c1','session_id':'s1','payload':{'summary':'保留目标和未决项','seq':12}})
    assert e.client_type=='dsh' and e.event_kind=='compaction' and e.session_id=='s1'
from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import build_adapter

def test_http_contract(tmp_path):
    adapter=build_adapter(tmp_path/'x.sqlite', None, tmp_path/'memory')
    client=TestClient(create_app(adapter))
    assert client.get('/health').json()['status']=='ok'
    saved=client.post('/memories',json={'text':'HTTP 测试记忆'}).json(); rid=saved['record']['id']
    assert saved['decision']=='candidate'
    assert client.post('/memories/confirm',json={'record_id':rid}).json()['status']=='active'
    assert client.get('/memories/search',params={'q':'HTTP'}).status_code==200
    assert client.post('/memories/forget',json={'record_id':rid,'reason':'test'}).status_code==200
from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import build_adapter

def test_http_checkpoint(tmp_path):
 a=build_adapter(tmp_path/'x.sqlite',None,tmp_path/'memory'); c=TestClient(create_app(a)); r=c.post('/checkpoints',json={'session_id':'s1','goal':'继续任务','pending':['待做'],'unknown':['结果未知']}); assert r.status_code==200 and r.json()['goal']=='继续任务'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xinhai import MemoryStore

def test_family_concurrent_writes_keep_identity(tmp_path: Path):
    s=MemoryStore(tmp_path/'family.sqlite')
    family=['hixin','vega','gwen','pulan','doubao','zia']
    def write(agent):
        return s.remember(text=f'{agent} 的并发记忆', speaker=agent, client_type=agent, session_id=f's-{agent}', thread_id=f't-{agent}', layer_id='node', tags=[f'agent:{agent}'])
    with ThreadPoolExecutor(max_workers=len(family)) as pool: rows=list(pool.map(write,family))
    assert len({r['id'] for r in rows})==6
    got=s.history(limit=20)
    assert {r['client_type'] for r in got}==set(family)
    assert {r['session_id'] for r in got}=={f's-{x}' for x in family}
    assert all(f'{r["client_type"]} 的并发记忆'==r['text'] for r in got)
from pathlib import Path
from xinhai import MemoryStore, MemoryService

def test_branch_recall_isolation(tmp_path: Path):
 s=MemoryStore(tmp_path/'x.sqlite')
 s.remember(text='分支A秘密',agent_id='zia',workspace_id='w',branch_id='A',session_id='sa')
 s.remember(text='分支B秘密',agent_id='zia',workspace_id='w',branch_id='B',session_id='sb')
 from xinhai.retrieval import search
 assert [x['text'] for x in search(s,'秘密',branch_id='A')]==['分支A秘密']
 assert [x['text'] for x in search(s,'秘密',branch_id='B')]==['分支B秘密']
from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import build_adapter

def test_http_error_contract(tmp_path):
 c=TestClient(create_app(build_adapter(tmp_path/'x.sqlite',None,tmp_path/'m')))
 r=c.post('/memories/confirm',json={'record_id':'missing'},headers={'x-request-id':'req-1'})
 assert r.status_code==404 and r.json()['ok'] is False and r.json()['error']['code']=='RECORD_NOT_FOUND' and r.json()['error']['request_id']=='req-1'
from xinhai.memory.recall_detector import detect

def test_recall_detector():
 assert detect('还记得我们上次定的方案吗').should_recall
 assert not detect('帮我写一个函数').should_recall
from xinhai.retrieval.pipeline import QueryPlanner, Fusion

def test_query_plan_and_rrf():
 p=QueryPlanner().plan('之前的决定',scope='personal',modalities=['text','image']); assert p.modalities==['text','image']
 assert Fusion().merge([[type('E',(),{'record_id':'a'})(),type('E',(),{'record_id':'b'})()],[type('E',(),{'record_id':'b'})()]])[0][0]=='b'
from pathlib import Path
from xinhai import MemoryStore
from xinhai.retrieval.pipeline import QueryPlanner, ContextBuilder
from xinhai.retrieval.text import TextRetriever

def test_text_pipeline(tmp_path:Path):
 s=MemoryStore(tmp_path/'x.sqlite'); s.remember(text='RAG 文本记忆',agent_id='zia',branch_id='A')
 plan=QueryPlanner().plan('文本记忆',agent_id='zia',branch_id='A',limit=5)
 evidence=TextRetriever(s).retrieve(plan); packed=ContextBuilder().pack(evidence,2)
 assert packed and packed[0].text=='RAG 文本记忆' and packed[0].modality=='text'
from pathlib import Path
from xinhai import MemoryStore
from xinhai.retrieval.pipeline import QueryPlanner, HybridRetriever
from xinhai.retrieval.text import TextRetriever

def test_hybrid_rrf_text_route(tmp_path:Path):
 s=MemoryStore(tmp_path/'x.sqlite'); s.remember(text='融合检索内容')
 p=QueryPlanner().plan('融合检索',limit=5); out=HybridRetriever([TextRetriever(s),TextRetriever(s)]).retrieve(p)
 assert len(out)==1 and out[0].text=='融合检索内容' and out[0].score>0
from xinhai.retrieval.vector import VectorRetriever
from xinhai.retrieval.pipeline import QueryPlanner

def test_vector_retriever_explicit_degradation():
 r=VectorRetriever(); assert not r.status.available and r.retrieve(QueryPlanner().plan('test'))==[]
from xinhai.retrieval.pipeline import QueryPlanner

def test_query_planner_rewrites_and_dedupes():
 p=QueryPlanner().plan('  还记得  上次的决定  '); assert p.rewritten[0].startswith('还记得') and '上次的决定' in p.rewritten
from fastapi.testclient import TestClient
from xinhai.api import create_app
from xinhai.mcp_server import build_adapter

def test_auto_recall_http(tmp_path):
 a=build_adapter(tmp_path/'x.sqlite',None,tmp_path/'m'); c=TestClient(create_app(a)); assert c.post('/memories/auto-recall',json={'text':'帮我写函数'}).json()['records']==[]
import sqlite3
from xinhai.retrieval.sqlite_vec import SQLiteVecIndex

def test_sqlite_vec_probe():
 s=SQLiteVecIndex(sqlite3.connect(':memory:')); assert s.status.available
 assert s.ensure_table(3)
from xinhai.retrieval.embedding import HashEmbeddingProvider

def test_hash_embedding_is_explicit_and_stable():
 p=HashEmbeddingProvider(4); assert p.embed(['abc'])==p.embed(['abc']) and len(p.embed(['abc'])[0])==4
