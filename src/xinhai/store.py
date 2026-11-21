import json, sqlite3, uuid, threading
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
SCHEMA='''PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY,scope TEXT NOT NULL,kind TEXT NOT NULL,speaker TEXT NOT NULL,ts TEXT NOT NULL,ingested_at TEXT NOT NULL,text TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',obsolete_reason TEXT,source_path TEXT,session_id TEXT,thread_id TEXT,turn INTEGER,idempotency_key TEXT UNIQUE,tags_json TEXT NOT NULL DEFAULT '[]'); CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(id UNINDEXED,text,tags); CREATE TABLE IF NOT EXISTS tags(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,kind TEXT NOT NULL DEFAULT 'agent'); CREATE TABLE IF NOT EXISTS record_tags(record_id TEXT,tag_id INTEGER,PRIMARY KEY(record_id,tag_id)); CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT,record_id TEXT,actor TEXT,created_at TEXT,details_json TEXT); CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY,session_id TEXT,thread_id TEXT,created_at TEXT,goal TEXT,confirmed_facts_json TEXT,decisions_json TEXT,completed_json TEXT,pending_json TEXT,unknown_json TEXT,next_step TEXT,source_range_json TEXT); CREATE TABLE IF NOT EXISTS memory_layers(id TEXT PRIMARY KEY,name TEXT,description TEXT,scope TEXT,markdown_path TEXT); CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,source_type TEXT,path TEXT,session_id TEXT,turn_start INTEGER,turn_end INTEGER,content_hash TEXT); CREATE TABLE IF NOT EXISTS relations(from_id TEXT,relation TEXT,to_id TEXT,metadata_json TEXT,PRIMARY KEY(from_id,relation,to_id));'''
class MemoryStore:
 def __init__(self,path):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(self.path,check_same_thread=False,timeout=30); self.lock=threading.RLock(); self.conn.row_factory=sqlite3.Row; self.conn.executescript(SCHEMA); cols={r[1] for r in self.conn.execute('PRAGMA table_info(records)')};
  for n in ['layer_id','source_id','event_id','client_type','event_kind','unmapped_json','agent_id','workspace_id','branch_id','task_id','modality','asset_ref','ocr_text','visual_summary']:
   if n not in cols:self.conn.execute(f'ALTER TABLE records ADD COLUMN {n} TEXT')
  self.conn.commit()
 def remember(self,**kw):
  with self.lock: return self._remember(**kw)
 def _remember(self,*,commit=True,**kw):
  text=kw['text']; tags=kw.get('tags') or []; key=kw.get('idempotency_key');
  if key:
   old=self.conn.execute('SELECT * FROM records WHERE idempotency_key=?',(key,)).fetchone()
   if old:return dict(old)
  rid=uuid.uuid4().hex; row=(rid,kw.get('scope','personal'),kw.get('kind','事实'),kw.get('speaker','我'),kw.get('ts') or now(),now(),text,kw.get('status','active'),None,kw.get('source_path'),kw.get('session_id'),kw.get('thread_id'),kw.get('turn'),key,json.dumps(tags,ensure_ascii=False),kw.get('layer_id'),kw.get('source_id'),kw.get('event_id'),kw.get('client_type'),kw.get('event_kind'),json.dumps(kw.get('unmapped') or [],ensure_ascii=False), kw.get('agent_id'), kw.get('workspace_id'), kw.get('branch_id'), kw.get('task_id'))
  with (self.conn if commit else nullcontext()):
   self.conn.execute('INSERT INTO records (id,scope,kind,speaker,ts,ingested_at,text,status,obsolete_reason,source_path,session_id,thread_id,turn,idempotency_key,tags_json,layer_id,source_id,event_id,client_type,event_kind,unmapped_json,agent_id,workspace_id,branch_id,task_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',row); self.conn.execute('INSERT INTO records_fts(id,text,tags) VALUES (?,?,?)',(rid,text,' '.join(tags)))
   if any(kw.get(k) is not None for k in ('modality','asset_ref','ocr_text','visual_summary')):
    self.conn.execute('UPDATE records SET modality=?,asset_ref=?,ocr_text=?,visual_summary=? WHERE id=?',(kw.get('modality','text'),kw.get('asset_ref'),kw.get('ocr_text'),kw.get('visual_summary'),rid))
   for tag in tags:self.conn.execute('INSERT OR IGNORE INTO tags(name) VALUES (?)',(tag,)); tid=self.conn.execute('SELECT id FROM tags WHERE name=?',(tag,)).fetchone()[0]; self.conn.execute('INSERT OR IGNORE INTO record_tags VALUES (?,?)',(rid,tid))
   self.conn.execute("INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES ('remember',?,'system',?, '{}')",(rid,now()))
  return dict(self.conn.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone())
 def history(self,record_id=None,status=None,scope=None,limit=50,branch_id=None,layer_id=None,tag=None,agent_id=None,workspace_id=None):
  c=[];a=[]
  for k,v in [('id',record_id),('status',status),('scope',scope),('branch_id',branch_id),('layer_id',layer_id),('agent_id',agent_id),('workspace_id',workspace_id)]:
   if v:c.append(k+'=?');a.append(v)
  if tag is not None:
   c.append('EXISTS (SELECT 1 FROM json_each(records.tags_json) WHERE value=?)'); a.append(tag)
  w=(' WHERE '+' AND '.join(c)) if c else ''; return [dict(x) for x in self.conn.execute('SELECT * FROM records'+w+' ORDER BY ts DESC LIMIT ?',(*a,limit)).fetchall()]
 def forget(self,record_id,reason):
  with self.conn:self.conn.execute("UPDATE records SET status='obsolete',obsolete_reason=? WHERE id=?",(reason,record_id))
  r=self.conn.execute('SELECT * FROM records WHERE id=?',(record_id,)).fetchone();
  if not r:raise KeyError(record_id)
  return dict(r)
 def checkpoint(self,**kw):
  cid=uuid.uuid4().hex; vals=[cid,kw['session_id'],kw.get('thread_id'),now(),kw.get('goal',''),kw.get('confirmed_facts',[]),kw.get('decisions',[]),kw.get('completed',[]),kw.get('pending',[]),kw.get('unknown',[]),kw.get('next_step'),kw.get('source_range',{})]
  with self.conn:self.conn.execute('INSERT INTO checkpoints VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(vals[0],vals[1],vals[2],vals[3],vals[4],*[json.dumps(x,ensure_ascii=False) for x in vals[5:10]],vals[10],json.dumps(vals[11],ensure_ascii=False)))
  return self.load_checkpoint(cid)
 def load_checkpoint(self,cid):
  r=self.conn.execute('SELECT * FROM checkpoints WHERE id=?',(cid,)).fetchone();
  if not r:raise KeyError(cid)
  return self._decode_checkpoint(r)
 def list_checkpoints(self,session_id,thread_id=None,limit=50):
  sql='SELECT * FROM checkpoints WHERE session_id=?'
  args=[session_id]
  if thread_id is not None:
   sql+=' AND thread_id=?'
   args.append(thread_id)
  sql+=' ORDER BY created_at DESC, rowid DESC LIMIT ?'
  return [self._decode_checkpoint(row) for row in self.conn.execute(sql,(*args,limit))]
 @staticmethod
 def _decode_checkpoint(r):
  d=dict(r)
  for k in ['confirmed_facts_json','decisions_json','completed_json','pending_json','unknown_json','source_range_json']:d[k[:-5]]=json.loads(d.pop(k))
  return d
 def close(self):self.conn.close()
