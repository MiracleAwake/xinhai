import sqlite3
from dataclasses import dataclass
@dataclass(frozen=True)
class VectorIndexStatus:
 available: bool; reason: str
class SQLiteVecIndex:
 def __init__(self,conn):
  self.conn=conn; self.status=self._load()
 def _load(self):
  try:
   import sqlite_vec
   self.conn.enable_load_extension(True); self.conn.load_extension(sqlite_vec.loadable_path()); self.conn.enable_load_extension(False)
   return VectorIndexStatus(True,'sqlite-vec loaded')
  except Exception as e:return VectorIndexStatus(False,str(e))
 def ensure_table(self,dimensions:int):
  if not self.status.available: return False
  self.conn.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS record_vectors USING vec0(record_id TEXT PRIMARY KEY, embedding float[{dimensions}])'); self.conn.commit(); return True
