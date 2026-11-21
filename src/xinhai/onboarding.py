"""Local prototype onboarding: immutable archives and confirmed layer rules."""
import hashlib
import json
import uuid
import sqlite3
import time
from pathlib import Path
from contextlib import closing
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from .adapters.session_export import STRUCTURED_FORMATS, parse_import_messages

def check_snapshot(connection):
    if [row[0] for row in connection.execute('PRAGMA quick_check')] != ['ok']:
        raise RuntimeError('import snapshot integrity check failed')
    connection.execute('SELECT id FROM records LIMIT 1').fetchone()

def snapshot_before_import(store, snapshot_id):
    """Capture committed SQLite data, including committed WAL pages."""
    if not store.path.is_file():
        raise RuntimeError('import requires a file-backed memory database')
    folder = store.path.parent / 'import-snapshots'
    folder.mkdir(exist_ok=True)
    path = folder / f'{snapshot_id}.sqlite'
    temporary = folder / f'.{snapshot_id}.{uuid.uuid4().hex}.tmp'
    with temporary.open('xb'):
        pass
    try:
        target = sqlite3.connect(temporary)
        try:
            store.conn.backup(target)
            check_snapshot(target)
        finally:
            target.close()
        temporary.rename(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path

class LayerIn(BaseModel):
    workspace_id:str; agent_id:str; name:str=Field(min_length=1)
    description:str=Field(min_length=1); prompt:str=''
    tags:list[str]=[]; keywords:list[str]=[]

class ImportIn(BaseModel):
    workspace_id:str; agent_id:str; branch_id:str; session_id:str
    client_type:str; filename:str; content:str
    format:str='text'

def router_for(service):
    router=APIRouter(); conn=service.store.conn
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS custom_layers_v1(id TEXT PRIMARY KEY,workspace_id TEXT,agent_id TEXT,status TEXT,payload TEXT);
    CREATE TABLE IF NOT EXISTS session_imports_v1(id TEXT PRIMARY KEY,workspace_id TEXT,agent_id TEXT,branch_id TEXT,digest TEXT,content TEXT,payload TEXT,status TEXT,error TEXT,record_id TEXT,UNIQUE(workspace_id,agent_id,branch_id,digest));
    CREATE TABLE IF NOT EXISTS import_drafts_v1(job_id TEXT,start_offset INTEGER,end_offset INTEGER,payload TEXT,PRIMARY KEY(job_id,start_offset));
    CREATE TABLE IF NOT EXISTS import_messages_v1(job_id TEXT,message_index INTEGER,payload TEXT,PRIMARY KEY(job_id,message_index));
    CREATE TABLE IF NOT EXISTS import_queue_v1(job_id TEXT PRIMARY KEY,state TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_failed_segments_v1(job_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_leases_v1(job_id TEXT PRIMARY KEY,owner TEXT,expires REAL,attempts INTEGER NOT NULL DEFAULT 0);
    ''')

    @router.post('/layers')
    def create_layer(body:LayerIn):
        lid=uuid.uuid4().hex
        with service.store.lock, conn:
            conn.execute('INSERT INTO custom_layers_v1 VALUES (?,?,?,?,?)',(lid,body.workspace_id,body.agent_id,'draft',body.model_dump_json()))
        return {'id':lid,'status':'draft',**body.model_dump()}

    @router.get('/layers')
    def layers(workspace_id:str,agent_id:str):
        rows=conn.execute('SELECT * FROM custom_layers_v1 WHERE workspace_id=? AND agent_id=?',(workspace_id,agent_id))
        return [{'id':r['id'],'status':r['status'],**json.loads(r['payload'])} for r in rows]

    @router.post('/layers/install-defaults')
    def install_defaults(workspace_id:str,agent_id:str):
        from .memory.layers import LayerRegistry
        from pathlib import Path
        registry=LayerRegistry(Path(__file__).parents[2]/'config'/'memory_layers.yaml')
        with service.store.lock, conn:
            for key,layer in registry.layers.items():
                lid=hashlib.sha256(f'{workspace_id}:{agent_id}:{key}'.encode()).hexdigest()
                payload={'workspace_id':workspace_id,'agent_id':agent_id,'name':layer['name'],'description':layer['description'],
                         'prompt':'','tags':[],'keywords':[],'template_id':key,'version':1}
                conn.execute('INSERT OR IGNORE INTO custom_layers_v1 VALUES (?,?,?,?,?)',(lid,workspace_id,agent_id,'draft',json.dumps(payload,ensure_ascii=False)))
        return layers(workspace_id,agent_id)

    @router.post('/layers/{layer_id}/confirm')
    def confirm_layer(layer_id:str,workspace_id:str,agent_id:str):
        with service.store.lock, conn:
            cursor=conn.execute("UPDATE custom_layers_v1 SET status='active' WHERE id=? AND workspace_id=? AND agent_id=?",(layer_id,workspace_id,agent_id))
            if not cursor.rowcount: raise HTTPException(404,'layer not found')
        return {'id':layer_id,'status':'active'}

    @router.post('/imports')
    def archive(body:ImportIn):
        # Preserve content verbatim before any secretary or classification step.
        digest=hashlib.sha256(body.content.encode('utf-8')).hexdigest()
        job_id=uuid.uuid4().hex
        with service.store.lock, conn:
            existing=conn.execute('SELECT id,status FROM session_imports_v1 WHERE workspace_id=? AND agent_id=? AND branch_id=? AND digest=?',(body.workspace_id,body.agent_id,body.branch_id,digest)).fetchone()
            if existing:
                return dict(existing)
            try:
                snapshot_before_import(service.store,job_id)
            except (OSError, sqlite3.Error, RuntimeError):
                raise HTTPException(503,'import snapshot failed; archive was not written')
            conn.execute('INSERT OR IGNORE INTO session_imports_v1 VALUES (?,?,?,?,?,?,?,?,?,?)',
                         (job_id,body.workspace_id,body.agent_id,body.branch_id,digest,body.content,body.model_dump_json(exclude={'content'}),'archived',None,None))
            row=conn.execute('SELECT id,status FROM session_imports_v1 WHERE workspace_id=? AND agent_id=? AND branch_id=? AND digest=?',(body.workspace_id,body.agent_id,body.branch_id,digest)).fetchone()
            return dict(row)

    @router.get('/imports')
    def imports(workspace_id:str,agent_id:str):
        with service.store.lock:
            rows=conn.execute('SELECT id FROM session_imports_v1 WHERE workspace_id=? AND agent_id=?',(workspace_id,agent_id)).fetchall()
        return [progress(r['id'],workspace_id,agent_id) for r in rows]

    def job(job_id,workspace_id,agent_id):
        with service.store.lock:
            row=conn.execute('SELECT * FROM session_imports_v1 WHERE id=? AND workspace_id=? AND agent_id=?',(job_id,workspace_id,agent_id)).fetchone()
        if not row: raise HTTPException(404,'import not found')
        return dict(row)

    @router.get('/imports/{job_id}')
    def progress(job_id:str,workspace_id:str,agent_id:str):
        with service.store.lock:
            r=job(job_id,workspace_id,agent_id)
            result={k:r[k] for k in ('id','status','error','record_id','digest')}
            failed=conn.execute('SELECT payload FROM import_failed_segments_v1 WHERE job_id=?',(job_id,)).fetchone()
            result['failed_segment']=json.loads(failed['payload']) if failed and r['status']=='failed' else None
            queued=conn.execute('SELECT state FROM import_queue_v1 WHERE job_id=?',(job_id,)).fetchone()
            result['queue_state']=queued['state'] if queued else None
            result['segments_done']=conn.execute('SELECT count(*) FROM import_drafts_v1 WHERE job_id=?',(job_id,)).fetchone()[0]
        result['segments_total']=(len(r['content'])+499)//500
        meta=json.loads(r['payload'])
        if meta.get('format') in STRUCTURED_FORMATS:
            try:
                from .adapters.session_export import summary_segments
                result['segments_total']=len(summary_segments(parse_import_messages(r['content'],meta['client_type'],meta['format'])))
            except ValueError: result['segments_total']=None
        return result

    @router.get('/imports/{job_id}/drafts')
    def drafts(job_id:str,workspace_id:str,agent_id:str):
        job(job_id,workspace_id,agent_id)
        return [dict(source_id=job_id,start_offset=r['start_offset'],end_offset=r['end_offset'],**json.loads(r['payload'])) for r in conn.execute('SELECT * FROM import_drafts_v1 WHERE job_id=? ORDER BY start_offset',(job_id,))]

    @router.get('/imports/{job_id}/messages')
    def imported_messages(job_id:str,workspace_id:str,agent_id:str):
        job(job_id,workspace_id,agent_id)
        return [dict(source_id=job_id,**json.loads(r['payload'])) for r in conn.execute('SELECT payload FROM import_messages_v1 WHERE job_id=? ORDER BY message_index',(job_id,))]

    @router.post('/imports/{job_id}/drafts/{offset}/confirm')
    def confirm_draft(job_id:str,offset:int,workspace_id:str,agent_id:str):
        from .governance import add_relation
        with service.store.lock, conn:
            conn.execute('UPDATE session_imports_v1 SET status=status WHERE id=? AND workspace_id=? AND agent_id=?',
                         (job_id,workspace_id,agent_id))
            archived=job(job_id,workspace_id,agent_id)
            row=conn.execute('SELECT payload,start_offset,end_offset FROM import_drafts_v1 WHERE job_id=? AND start_offset=?',(job_id,offset)).fetchone()
            if not row: raise HTTPException(404,'draft not found')
            draft=json.loads(row['payload'])
            if not draft.get('record_id'):
                record=service.store._remember(commit=False,text=draft['summary'],status='active',kind='派生摘要',
                    workspace_id=workspace_id,agent_id=agent_id,branch_id=archived['branch_id'],
                    session_id=json.loads(archived['payload'])['session_id'],source_id=job_id,
                    tags=draft['tags']+['derived_summary'],idempotency_key=f'draft:{job_id}:{offset}')
                draft.update(status='confirmed',record_id=record['id'])
                conn.execute('UPDATE import_drafts_v1 SET payload=? WHERE job_id=? AND start_offset=?',(json.dumps(draft,ensure_ascii=False),job_id,offset))
                conn.execute("INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES (?,?,?,datetime('now'),?)",('import_draft_confirm',record['id'],agent_id,json.dumps({'source_id':job_id,'source':draft['source'],'layer_ids':draft['layer_ids'],'is_verified':False},ensure_ascii=False)))
            coverage={'target_type':'import',**draft['source']}
            if coverage['offset_basis']=='archive_text':
                coverage.update(start=row['start_offset'],end=row['end_offset'])
            add_relation(conn,draft['record_id'],'covers',job_id,coverage)
            return draft

    @router.get('/layers/{layer_id}/document')
    def layer_document(layer_id:str,workspace_id:str,agent_id:str,branch_id:str|None=None):
        if not any(x['id']==layer_id for x in layers(workspace_id,agent_id)): raise HTTPException(404,'layer not found')
        sections=[]
        query = ('SELECT d.job_id,d.payload FROM import_drafts_v1 d '
                 'JOIN session_imports_v1 j ON j.id=d.job_id WHERE j.workspace_id=? AND j.agent_id=?')
        params = (workspace_id, agent_id)
        if branch_id is not None:
            query += ' AND j.branch_id=?'
            params += (branch_id,)
        for row in conn.execute(query, params):
            draft=json.loads(row['payload'])
            if draft['status']=='confirmed' and layer_id in draft['layer_ids']:
                sections.append({'source_id':row['job_id'],**draft})
        return {'layer_id':layer_id,'sections':sections}

    @router.get('/imports/{job_id}/original')
    def original(job_id:str,workspace_id:str,agent_id:str):
        r=job(job_id,workspace_id,agent_id)
        return {'content':r['content'],'digest':r['digest'],'source_id':r['id']}

    class LeaseLost(Exception):
        pass

    def renew(job_id, owner):
        now = time.time()
        cursor = conn.execute(
            'UPDATE import_leases_v1 SET expires=? WHERE job_id=? AND owner=? AND expires>?',
            (now+1800, job_id, owner, now))
        if not cursor.rowcount:
            raise LeaseLost()

    def process(job_id:str,workspace_id:str,agent_id:str,owner:str):
        with service.store.lock:
            r=job(job_id,workspace_id,agent_id)
            if r['status']=='completed': return progress(job_id,workspace_id,agent_id)
            snapshot = service.store.path.parent / 'import-snapshots' / f'{job_id}.sqlite'
            try:
                if snapshot.exists():
                    with closing(sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro', uri=True)) as backup:
                        check_snapshot(backup)
                else:
                    snapshot_before_import(service.store,job_id)
            except (OSError, sqlite3.Error, RuntimeError):
                with conn:
                    renew(job_id,owner)
                    conn.execute("UPDATE session_imports_v1 SET status='failed',error=? WHERE id=?",('SnapshotFailed',job_id))
                return progress(job_id,workspace_id,agent_id)
            failed_segment=None
            try:
                meta=json.loads(r['payload'])
                messages=None
                if meta.get('format') in STRUCTURED_FORMATS:
                    messages=parse_import_messages(r['content'],meta['client_type'],meta['format'])
                    from .adapters.session_export import screen_messages
                    with conn:
                        renew(job_id,owner)
                        for message in screen_messages(messages):
                            conn.execute('INSERT OR IGNORE INTO import_messages_v1 VALUES (?,?,?)',(job_id,message['message_index'],json.dumps(message,ensure_ascii=False)))
                elif meta.get('format','text')!='text':
                    raise ValueError('unsupported session format')
                rules=layers(workspace_id,agent_id)
                record_text=r['content']
                if meta.get('format') in {'codex-session-jsonl', 'codex-exec-jsonl'}:
                    record_text='\n'.join(m['text'] for m in screen_messages(messages)
                                          if m['screen_status'] not in {'duplicate','transient'})
                selected=next((x for x in rules if x['status']=='active' and any(k and k in record_text for k in x['keywords'])),None)
                tags=(selected['tags'] if selected else [])+['session_import']
                with conn:
                    renew(job_id,owner)
                    record=service.store.remember(text=record_text,status='candidate',source_id=job_id,
                        source_path=meta['filename'],workspace_id=workspace_id,agent_id=agent_id,
                        branch_id=r['branch_id'],session_id=meta['session_id'],client_type=meta['client_type'],
                        layer_id=selected['id'] if selected else None,tags=tags,idempotency_key='import:'+job_id)
                with conn:
                    renew(job_id,owner)
                    conn.execute('UPDATE session_imports_v1 SET record_id=?,status=? WHERE id=?',(record['id'],'processing',job_id))
                segments=[(start,r['content'][start:start+500],{'offset_basis':'archive_text'}) for start in range(0,len(r['content']),500)]
                if messages is not None:
                    from .adapters.session_export import summary_segments
                    segments=summary_segments(messages)
                for start,segment,source in segments:
                    if conn.execute('SELECT 1 FROM import_drafts_v1 WHERE job_id=? AND start_offset=?',(job_id,start)).fetchone(): continue
                    failed_segment={'start_offset':start,'end_offset':start+len(segment),'source':source}
                    matched=[x for x in rules if x['status']=='active' and any(k and k in segment for k in x['keywords'])]
                    draft={'summary':segment,'summary_kind':'verbatim_excerpt','uncertainty':'unknown',
                           'layer_ids':[x['id'] for x in matched], 'tags':list(dict.fromkeys(t for x in matched for t in x['tags'])),
                           'status':'draft','is_verified':False,'source':source}
                    if service.secretary.provider:
                        candidate=service.secretary.provider.extract(segment)
                        if not isinstance(candidate.get('summary'),str) or not isinstance(candidate.get('uncertainty','unknown'),str): raise ValueError('invalid draft')
                        draft.update(summary=candidate['summary'],summary_kind='model_draft',uncertainty=candidate.get('uncertainty','unknown'))
                    with conn:
                        renew(job_id,owner)
                        conn.execute('INSERT INTO import_drafts_v1 VALUES (?,?,?,?)',(job_id,start,start+len(segment),json.dumps(draft,ensure_ascii=False)))
                    failed_segment=None
                with conn:
                    renew(job_id,owner)
                    conn.execute("UPDATE session_imports_v1 SET status='completed',error=NULL,record_id=? WHERE id=?",(record['id'],job_id))
                    conn.execute('DELETE FROM import_failed_segments_v1 WHERE job_id=?',(job_id,))
            except LeaseLost:
                raise
            except Exception as exc:
                with conn:
                    renew(job_id,owner)
                    conn.execute("UPDATE session_imports_v1 SET status='failed',error=? WHERE id=?",(type(exc).__name__,job_id))
                    conn.execute('DELETE FROM import_failed_segments_v1 WHERE job_id=?',(job_id,))
                    if failed_segment is not None:
                        conn.execute('INSERT INTO import_failed_segments_v1 VALUES (?,?)',(job_id,json.dumps(failed_segment)))
            return progress(job_id,workspace_id,agent_id)

    @router.post('/imports/{job_id}/start',status_code=202)
    def start(job_id:str,workspace_id:str,agent_id:str,background_tasks:BackgroundTasks):
        job(job_id,workspace_id,agent_id)
        with service.store.lock, conn:
            import time
            lease=conn.execute('SELECT expires FROM import_leases_v1 WHERE job_id=?',(job_id,)).fetchone()
            if lease and lease['expires']>time.time(): raise HTTPException(409,'import is already leased')
            conn.execute("INSERT INTO import_queue_v1 VALUES (?,'queued') ON CONFLICT(job_id) DO UPDATE SET state='queued'",(job_id,))
        return {'id':job_id,'status':'queued','durable_queue':True,'execution':'local_worker'}
    def claim(job_id, *, queued_only=False):
        owner=uuid.uuid4().hex
        now=time.time()
        with service.store.lock, conn:
            cursor=conn.execute(
                'INSERT INTO import_leases_v1 SELECT ?,?,?,1 '
                'WHERE NOT ? OR EXISTS(SELECT 1 FROM import_queue_v1 '
                "WHERE job_id=? AND state IN ('queued','processing')) "
                'ON CONFLICT(job_id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires,'
                'attempts=attempts+1 WHERE expires<=?',(job_id,owner,now+1800,queued_only,job_id,now))
            return owner if cursor.rowcount else None

    def release(job_id,owner):
        with service.store.lock, conn:
            conn.execute('UPDATE import_leases_v1 SET expires=0 WHERE job_id=? AND owner=?',(job_id,owner))

    @router.post('/imports/{job_id}/process')
    def process_now(job_id:str,workspace_id:str,agent_id:str):
        job(job_id,workspace_id,agent_id)
        owner=claim(job_id)
        if owner is None:
            raise HTTPException(409,'import is already leased')
        try:
            return process(job_id,workspace_id,agent_id,owner)
        except LeaseLost:
            raise HTTPException(409,'import lease expired or was reassigned') from None
        finally:
            release(job_id,owner)

    def drain():
        results=[]
        for row in conn.execute("SELECT q.job_id,j.workspace_id,j.agent_id FROM import_queue_v1 q JOIN session_imports_v1 j ON j.id=q.job_id WHERE q.state IN ('queued','processing')").fetchall():
            owner=claim(row['job_id'], queued_only=True)
            if owner is None: continue
            with service.store.lock, conn:
                conn.execute("UPDATE import_queue_v1 SET state='processing' WHERE job_id=?",(row['job_id'],))
            try:
                result=process(row['job_id'],row['workspace_id'],row['agent_id'],owner)
            except LeaseLost:
                continue
            with conn:
                conn.execute('UPDATE import_queue_v1 SET state=? WHERE job_id=? AND EXISTS(SELECT 1 FROM import_leases_v1 WHERE job_id=? AND owner=?)',(result['status'],row['job_id'],row['job_id'],owner))
            release(row['job_id'],owner)
            results.append(result)
        return results
    service.run_import_queue=drain
    return router
