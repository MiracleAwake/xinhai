from dataclasses import dataclass, field
import re
@dataclass(frozen=True)
class QueryPlan:
 query:str; rewritten:list[str]=field(default_factory=list); scopes:list[str]=field(default_factory=list); modalities:list[str]=field(default_factory=lambda:['text']); filters:dict=field(default_factory=dict)
@dataclass(frozen=True)
class Evidence:
 record_id:str; text:str; score:float=0.0; source_ref:str|None=None; modality:str='text'; asset_ref:str|None=None
class QueryPlanner:
 def plan(self,query:str,**filters):
  q=re.sub(r'\s+',' ',query.strip()); base=re.sub(r'^(还记得|之前|上次|以前|我们定的|我们之前的)','',q).strip() or q; variants=[]
  for v in [q,base]:
   if v and v not in variants:variants.append(v)
  return QueryPlan(q,variants,[filters['scope']] if filters.get('scope') else [],filters.get('modalities',['text']),filters)
 def route_weights(self,query):
  """Choose explainable text/vector weights for a query shape."""
  if re.search(r'(?:[A-Za-z]:\\|/|\.py\b|\.md\b|错误码|error|exception|sqlite|GO-[A-Z]+-\w+)',query,re.I): return {'text':2.0,'vector':1.0,'reason':'exact_term'}
  if len(query)>=12 and not re.search(r'\d{3,}',query): return {'text':1.0,'vector':2.0,'reason':'semantic'}
  return {'text':1.0,'vector':1.0,'reason':'balanced'}
class Fusion:
 def __init__(self,weights=None): self.weights=weights or []
 def merge(self,sets):
  scores={}
  for index,rs in enumerate(sets):
   weight=self.weights[index] if index<len(self.weights) else 1.0
   for rank,item in enumerate(rs,1):scores[item.record_id]=scores.get(item.record_id,0)+weight/(60+rank)
  return sorted(scores.items(),key=lambda x:x[1],reverse=True)
class HybridRetriever:
 def __init__(self,retrievers,fusion=None,reranker=None,min_score=None):self.retrievers=retrievers;self.fusion=fusion or Fusion();self.reranker=reranker;self.min_score=min_score
 def retrieve(self,plan):
  sets=[r.retrieve(plan) for r in self.retrievers]; samples={x.record_id:x for rs in sets for x in rs}; out=[Evidence(rid,samples[rid].text,score,samples[rid].source_ref,samples[rid].modality,samples[rid].asset_ref) for rid,score in self.fusion.merge(sets)]
  if self.min_score is not None: out=[x for x in out if x.score>=self.min_score]
  return self.reranker.rank(plan.query,out) if self.reranker else out
class Reranker:
 def rank(self,query,candidates):return candidates
class KeywordReranker(Reranker):
 def rank(self,query,candidates):
  terms=[x for x in re.findall(r'[\w\u4e00-\u9fff]+',query) if x]
  return sorted(candidates,key=lambda e:(sum(t in e.text for t in terms),e.score),reverse=True)
class ContextBuilder:
 def pack(self,candidates,budget):return candidates[:budget]
