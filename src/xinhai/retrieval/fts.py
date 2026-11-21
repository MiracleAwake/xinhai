from ..store import MemoryStore
def search(store:MemoryStore,query:str,*,scope=None,layer_id=None,tag=None,session_id=None,thread_id=None,since=None,until=None,include_obsolete=False,limit=10,agent_id=None,workspace_id=None,branch_id=None,task_id=None,source_id=None,modality=None):
 f=[];a=[]
 for k,v in [('scope',scope),('layer_id',layer_id),('session_id',session_id),('thread_id',thread_id),('agent_id',agent_id),('workspace_id',workspace_id),('branch_id',branch_id),('task_id',task_id),('source_id',source_id),('modality',modality)]:
  if v:f.append('r.'+k+'=?');a.append(v)
 if since:f.append('r.ts>=?');a.append(since)
 if until:f.append('r.ts<=?');a.append(until)
 j=''
 if tag:j=' JOIN record_tags rt ON rt.record_id=r.id JOIN tags tg ON tg.id=rt.tag_id';f.append('tg.name=?');a.append(tag)
 if not include_obsolete:f.append("r.status='active'")
 w=(' AND '.join(f)+' AND ') if f else ''
 return [dict(x) for x in store.conn.execute(f'SELECT DISTINCT r.* FROM records r{j} WHERE {w}(r.text LIKE ? OR COALESCE(r.ocr_text,\'\') LIKE ? OR COALESCE(r.visual_summary,\'\') LIKE ?) ORDER BY r.ts DESC LIMIT ?',(*a,'%'+query+'%','%'+query+'%','%'+query+'%',limit)).fetchall()]
