from dataclasses import dataclass
from .pipeline import Evidence
import ast, math, struct
@dataclass(frozen=True)
class VectorStatus:
 available: bool
 reason: str
class EmbeddingProvider:
 def embed(self,texts): raise NotImplementedError
class UnavailableEmbedding(EmbeddingProvider):
 def embed(self,texts): raise RuntimeError('embedding provider unavailable')
class VectorRetriever:
 def __init__(self,provider=None,store=None): self.provider=provider; self.store=store; self.status=VectorStatus(bool(provider and store),'configured' if provider and store else 'no embedding provider configured')
 def retrieve(self,plan):
  if not self.provider or not self.store:return []
  try:q=self.provider.embed([plan.query])[0]; qn=math.sqrt(sum(x*x for x in q)) or 1
  except Exception:return []
  out=[]
  for row in self.store.conn.execute('SELECT r.*,v.embedding FROM record_vectors v JOIN records r ON r.id=v.record_id WHERE r.status=?',('active',)):
   try:
    raw=row['embedding']; v=list(struct.unpack('<'+'f'*(len(raw)//4),raw)) if isinstance(raw,bytes) else ast.literal_eval(raw)
    if len(q)!=len(v): continue
    dot=sum(a*b for a,b in zip(q,v)); vn=math.sqrt(sum(x*x for x in v)) or 1; score=dot/(qn*vn)
   except Exception:continue
   out.append(Evidence(row['id'],row['text'],score,row['source_id'],row['modality'] or 'text',row['asset_ref']))
  return sorted(out,key=lambda x:x.score,reverse=True)
