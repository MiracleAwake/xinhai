import hashlib, math
class HashEmbeddingProvider:
 def __init__(self,dimensions=8): self.dimensions=dimensions
 def embed(self,texts):
  out=[]
  for text in texts:
   raw=hashlib.sha256(text.encode()).digest(); vals=[raw[i]/255-0.5 for i in range(self.dimensions)]; norm=math.sqrt(sum(x*x for x in vals)) or 1; out.append([x/norm for x in vals])
  return out

class SentenceTransformerProvider:
 """Optional real embedding provider; imports heavy dependencies lazily."""
 def __init__(self,model_name='BAAI/bge-m3',**kwargs):
  from sentence_transformers import SentenceTransformer
  self.model_name=model_name; self.model=SentenceTransformer(model_name,**kwargs); self.dimensions=self.model.get_embedding_dimension()
 def embed(self,texts):
  return self.model.encode(list(texts),normalize_embeddings=True).tolist()
