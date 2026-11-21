from .pipeline import Evidence
from .fts import search
class TextRetriever:
 def __init__(self,store): self.store=store
 def retrieve(self,plan):
  seen={}
  for query in plan.rewritten or [plan.query]:
   rows=search(self.store,query,**{k:v for k,v in plan.filters.items() if k in {'scope','layer_id','tag','session_id','thread_id','since','until','include_obsolete','limit','agent_id','workspace_id','branch_id','task_id'}})
   for r in rows: seen[r['id']]=Evidence(record_id=r['id'],text=r['text'],score=1.0,source_ref=r.get('source_path') or r.get('session_id'),modality='text')
  return list(seen.values())
