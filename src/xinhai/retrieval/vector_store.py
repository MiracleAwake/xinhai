from .sqlite_vec import SQLiteVecIndex
class VectorStore:
 def __init__(self,conn,provider): self.conn=conn; self.provider=provider; self.index=SQLiteVecIndex(conn); self.index.ensure_table(provider.dimensions)
 def add(self,record_id,text):
  vector=self.provider.embed([text])[0]
  with self.conn:
   self.conn.execute('DELETE FROM record_vectors WHERE record_id=?',(record_id,))
   self.conn.execute('INSERT INTO record_vectors(record_id,embedding) VALUES (?,?)',(record_id, str(vector)))
