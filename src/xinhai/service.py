from .store import MemoryStore
from .memory import MemorySecretary, LayerRegistry, MarkdownWriter, MemoryGatekeeper
from .retrieval import search
from .retrieval.pipeline import QueryPlanner, QueryPlan, Evidence, Fusion, KeywordReranker
from .retrieval.vector import VectorRetriever
from .retrieval.vector_store import VectorStore
from .memory.recall_detector import detect
from .memory.ocr_parser import parse_firewall_rules
import json, os
class MemoryService:
 def __init__(self,db_path,*,layers_path=None,markdown_root=None,model_provider=None,embedding_provider=None,config_manager=None):
  if markdown_root and not layers_path:
   raise ValueError('markdown_root requires layers_path=memory_layers.yaml')
  self.store=MemoryStore(db_path); self.layers=LayerRegistry(layers_path) if layers_path else None; self.writer=MarkdownWriter(markdown_root) if markdown_root else None; self.secretary=MemorySecretary(self.store,provider=model_provider); self.gatekeeper=MemoryGatekeeper(self.store); self.vector_store=VectorStore(self.store.conn,embedding_provider) if embedding_provider else None; self.config_manager=config_manager
 def remember(self,text,**kwargs):
  result=self.secretary.process(text,**kwargs)
  if result.record and kwargs.get('modality')=='image' and kwargs.get('ocr_text'):
   facts=parse_firewall_rules(kwargs['ocr_text'])
   if facts:
    with self.store.conn:
     self.store.conn.execute("INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES (?,?,?,?,?)",('ocr_structured_fact',result.record['id'],'ocr-parser',__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),json.dumps({'facts':facts},ensure_ascii=False)))
  if self.vector_store and result.record:
   result.record['vector_status']=self.retry_vector(result.record['id'])
  return result
 def retry_vector(self,record_id):
  rows=self.store.history(record_id=record_id)
  if not rows: raise KeyError(record_id)
  if not self.vector_store: return 'disabled'
  status='ready'; error=None
  try: self.vector_store.add(record_id,rows[0]['text'])
  except Exception as exc:
   status='pending'; error=type(exc).__name__
  with self.store.conn:
   self.store.conn.execute("INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES (?,?,?,datetime('now'),?)",('vector_index',record_id,'vector-worker',json.dumps({'status':status,'error_type':error})))
  return status
 def auto_recall(self,text,**kwargs):
  decision=detect(text)
  if not decision.should_recall:return {'decision':decision.__dict__,'records':[]}
  if len(decision.query)<=4 and not kwargs.get('limit'): kwargs['limit']=3
  records=self.recall(decision.query,**kwargs)
  if not records:
   terms=[x for x in decision.query.replace('，',' ').replace('。',' ').replace('的',' ').split() if len(x)>=2]
   if kwargs.get('branch_id'): terms.append(str(kwargs['branch_id']))
   merged=[]
   for term in terms: merged.extend(self.recall(term,**kwargs))
   seen=set(); records=[r for r in merged if not (r['id'] in seen or seen.add(r['id']))]
  return {'decision':decision.__dict__,'records':records}
 def confirm(self,record_id):
  rows=self.store.history(record_id=record_id)
  if not rows:raise KeyError(record_id)
  record=rows[0]
  if record['status']=='candidate':
   with self.store.conn:self.store.conn.execute("UPDATE records SET status='active' WHERE id=?",(record_id,))
   record=self.store.history(record_id=record_id)[0]
  if self.writer and self.layers and record.get('layer_id'):self.writer.append(layer=self.layers.get(record['layer_id']),record=record,summary=record['text'],tags=json.loads(record['tags_json']))
  return record
 def recall(self,query,**kwargs):
  if 'expand_source' not in kwargs and self.config_manager:
   kwargs['expand_source']=self.config_manager.runtime_options().get('retrieval.expand_source', False)
  route=QueryPlanner().route_weights(query)
  configured=self.config_manager.runtime_options() if self.config_manager else {}
  weights=kwargs.get('weights',configured.get('retrieval.weights'))
  if weights is not None:
   import math
   if not isinstance(weights,dict) or set(weights)!={'text','vector'} or any(type(weights[k]) not in (int,float) or not math.isfinite(weights[k]) or weights[k]<=0 for k in ('text','vector')):
    raise ValueError('weights must contain positive finite text and vector numbers')
   route={**route,'text':float(weights['text']),'vector':float(weights['vector'])}
  weight_source='request' if kwargs.get('weights') is not None else ('config' if weights is not None else 'query_route')
  quality={}
  matches={}
  keys={'scope','layer_id','tag','session_id','thread_id','since','until','include_obsolete','limit','agent_id','workspace_id','branch_id','task_id','source_id','modality'}; c=search(self.store,query,**{k:v for k,v in kwargs.items() if k in keys}); c=self.gatekeeper.filter(c,allowed_scopes=kwargs.get('allowed_scopes'),required_tags=kwargs.get('required_tags'))
  for row in c: matches[row['id']]={'kind':'literal_query','terms':[query]}
  if not c and len(query)>=2:
   variants=[x for x in query.replace('，',' ').replace('。',' ').split() if len(x)>=2]
   merged=[]; seen=set()
   for term in variants:
    for row in search(self.store,term,**{k:v for k,v in kwargs.items() if k in keys}):
     matches.setdefault(row['id'],{'kind':'term_fallback','terms':[]})['terms'].append(term)
     if row['id'] not in seen: merged.append(row); seen.add(row['id'])
   c=self.gatekeeper.filter(merged,allowed_scopes=kwargs.get('allowed_scopes'),required_tags=kwargs.get('required_tags'))
  if self.vector_store:
   plan=QueryPlan(query,filters=kwargs)
   text_ev=[Evidence(r['id'],r['text'],0.0,r.get('source_id'),r.get('modality') or 'text',r.get('asset_ref')) for r in c]
   vec=VectorRetriever(self.vector_store.provider,self.store).retrieve(plan)
   eligibility_kwargs={k:v for k,v in kwargs.items() if k in keys}; candidate_cap=max(int(kwargs.get('limit',10)),int(os.environ.get('XINHAI_VECTOR_CANDIDATE_LIMIT','1000'))); eligibility_kwargs['limit']=candidate_cap
   eligible=search(self.store,'',**eligibility_kwargs); eligible=self.gatekeeper.filter(eligible,allowed_scopes=kwargs.get('allowed_scopes'),required_tags=kwargs.get('required_tags'))
   allowed={r['id'] for r in eligible}; vec=[x for x in vec if x.record_id in allowed]
   text_ids={x.record_id for x in text_ev}
   review_below=float(os.environ.get('XINHAI_VECTOR_REVIEW_BELOW','0.55'))
   import math
   if not math.isfinite(review_below) or not -1<=review_below<=1: raise ValueError('XINHAI_VECTOR_REVIEW_BELOW must be between -1 and 1')
   threshold=os.environ.get('XINHAI_VECTOR_MIN_SIMILARITY')
   if threshold is not None:
    import math
    threshold=float(threshold)
    if not math.isfinite(threshold) or not -1<=threshold<=1: raise ValueError('XINHAI_VECTOR_MIN_SIMILARITY must be between -1 and 1')
    vec=[x for x in vec if x.score>=threshold]
   for item in vec:
    quality[item.record_id]={'vector_similarity':item.score,'quality_status':'needs_verification' if item.score<review_below else 'candidate','quality_reason':'low_similarity' if item.score<review_below else 'similarity_is_not_verification','retrieval_channels':['text','vector'] if item.record_id in text_ids else ['vector']}
   for rid in text_ids:
    if rid not in quality: quality[rid]={'vector_similarity':None,'quality_status':'candidate','quality_reason':'literal_match_is_not_verification','retrieval_channels':['text']}
   fused=Fusion(weights=[route['text'],route['vector']]).merge([text_ev,vec])
   for item in vec:
    if item.record_id in matches:
     matches[item.record_id]['channels']=['text','vector']
    else:
     matches[item.record_id]={'kind':'vector','terms':[],'channels':['vector']}
   by={x.record_id:x for x in text_ev+vec}; ordered=[by[i] for i,_ in fused]
   # Preserve weighted RRF order across distinct records. Fine ranking is only
   # safe within equal-score groups; do not let keyword hits erase route weight.
   c=[next(r for r in (c+eligible) if r['id']==x.record_id) for x in ordered][:int(kwargs.get('limit',10))]
  for row in c: row['route_reason']=route['reason']; row['route_weights']={'text':route['text'],'vector':route['vector']}
  if kwargs.get('expand_source'):
   ids={r.get('source_id') for r in c if r.get('source_id')}
   expanded=[]
   for sid in ids: expanded.extend(search(self.store,'',source_id=sid,include_obsolete=kwargs.get('include_obsolete',False),limit=kwargs.get('limit',10),agent_id=kwargs.get('agent_id'),workspace_id=kwargs.get('workspace_id'),branch_id=kwargs.get('branch_id'),session_id=kwargs.get('session_id'),thread_id=kwargs.get('thread_id'),task_id=kwargs.get('task_id'),scope=kwargs.get('scope'),modality=kwargs.get('modality')))
   c=self.gatekeeper.filter(expanded,allowed_scopes=kwargs.get('allowed_scopes'),required_tags=kwargs.get('required_tags'))
  for row in c: row['route_reason']=route['reason']; row['route_weights']={'text':route['text'],'vector':route['vector']}
  for row in c:
   row['weight_source']=weight_source
   row['match_reason']={**matches.get(row['id'],{'kind':'source_context' if kwargs.get('expand_source') else 'vector','terms':[]}), 'structured_state_verified':False}
   row['match_reason'].setdefault('channels',['source_context'] if row['match_reason']['kind']=='source_context' else ['text'])
   row.update(quality.get(row['id'],{'vector_similarity':None,'quality_status':'needs_verification' if kwargs.get('expand_source') else 'candidate','quality_reason':'source_context' if kwargs.get('expand_source') else 'literal_match_is_not_verification','retrieval_channels':['source_context'] if kwargs.get('expand_source') else ['text']}))
   row['context_status']='sufficient' if len((row.get('text') or '').strip())>=12 and (row.get('source_id') or row.get('source_path')) else ('insufficient' if len((row.get('text') or '').strip())<12 else 'unknown')
  return c
 def checkpoint(self,**kwargs):return self.store.checkpoint(**kwargs)
 def list_checkpoints(self,**kwargs):return self.store.list_checkpoints(**kwargs)
 def history(self,**kwargs):return self.store.history(**kwargs)
 def recall_structured(self,*,enabled=None,action=None,direction=None,branch_id=None,workspace_id=None,agent_id=None,limit=20):
  rows=[]
  for r in self.store.conn.execute("SELECT a.record_id,a.details_json,r.* FROM audit_events a JOIN records r ON r.id=a.record_id WHERE a.action='ocr_structured_fact' ORDER BY a.created_at DESC LIMIT ?",(limit*5,)):
   if branch_id is not None and r['branch_id']!=branch_id: continue
   if workspace_id is not None and r['workspace_id']!=workspace_id: continue
   if agent_id is not None and r['agent_id']!=agent_id: continue
   facts=json.loads(r['details_json']).get('facts',[])
   matched=[f for f in facts if (enabled is None or f.get('enabled')==enabled) and (action is None or f.get('action')==action) and (direction is None or f.get('direction')==direction)]
   if matched:
    d=dict(r); d['structured_facts']=matched; rows.append(d)
   if len(rows)>=limit: break
  return rows
 def compare_structured(self,*,rule_name=None,action=None,direction=None,branch_id=None,workspace_id=None,agent_id=None,limit=100):
  rows=self.recall_structured(action=action,direction=direction,branch_id=branch_id,workspace_id=workspace_id,agent_id=agent_id,limit=limit)
  groups={}
  for row in rows:
   for fact in row.get('structured_facts',[]):
    if rule_name and fact.get('rule_name')!=rule_name: continue
    groups.setdefault(fact.get('rule_name','unknown'),{}).setdefault('enabled_true' if fact.get('enabled') else 'enabled_false',[]).append({'record_id':row['record_id'],'asset_ref':row.get('asset_ref'),'branch_id':row.get('branch_id'),'evidence':fact.get('evidence')})
  return groups
 def recall_evidence(self,query,**kwargs):
  """Return a modality-neutral evidence envelope for text/image/mixed records."""
  rows=self.recall(query,**kwargs); out=[]
  for r in rows:
   facts=[]
   for a in self.store.conn.execute("SELECT details_json FROM audit_events WHERE action='ocr_structured_fact' AND record_id=? ORDER BY created_at DESC LIMIT 1",(r['id'],)):
    facts=json.loads(a['details_json']).get('facts',[])
   out.append({'record_id':r['id'],'text':r.get('text',''),'modality':r.get('modality') or 'text','asset_ref':r.get('asset_ref'),'source_ref':r.get('source_id') or r.get('source_path'),'ocr_text':r.get('ocr_text'),'visual_summary':r.get('visual_summary'),'structured_facts':facts,'score':r.get('vector_similarity'),'quality_status':r.get('quality_status'),'context_status':r.get('context_status'),'route_reason':r.get('route_reason'),'branch_id':r.get('branch_id'),'workspace_id':r.get('workspace_id')})
   draft=None
   audit=self.store.conn.execute("SELECT details_json FROM audit_events WHERE action='secretary_model' AND record_id=? ORDER BY id DESC LIMIT 1",(r['id'],)).fetchone()
   if audit:
    try: draft=json.loads(audit['details_json'])
    except (ValueError, TypeError): pass
   out[-1]['secretary_evidence']={'uncertainty':draft.get('uncertainty','unknown') if draft else 'unknown',
     'summary':draft.get('summary') if draft else None,'provider':draft.get('provider') if draft else None,
     'result':draft.get('result','unknown') if draft else 'unknown','is_verified':False}
   out[-1]['match_reason']=r.get('match_reason')
   out[-1]['route_weights']=r.get('route_weights')
   out[-1]['weight_source']=r.get('weight_source')
  return out
 def forget(self,record_id,reason):return self.store.forget(record_id,reason)
 def close(self):
  """Release the SQLite connection; callers should use this in tests and shutdown hooks."""
  self.store.close()
