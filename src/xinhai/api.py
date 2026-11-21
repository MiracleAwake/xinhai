from .configuration import weight_arguments
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .runtime import adapter_from_env
from .errors import XinhaiError, RecordNotFound
class RememberIn(BaseModel): text:str; user_confirmed:bool=False; agent_id:str|None=None; workspace_id:str|None=None; branch_id:str|None=None; session_id:str|None=None; thread_id:str|None=None; task_id:str|None=None; source_id:str|None=None; modality:str='text'; asset_ref:str|None=None; ocr_text:str|None=None; visual_summary:str|None=None
class ConfirmIn(BaseModel): record_id:str
class ForgetIn(BaseModel): record_id:str; reason:str
class CheckpointIn(BaseModel): session_id:str; thread_id:str|None=None; goal:str=''; pending:list[str]=[]; unknown:list[str]=[]; next_step:str|None=None
class AutoRecallIn(BaseModel): text:str; agent_id:str|None=None; workspace_id:str|None=None; branch_id:str|None=None; session_id:str|None=None; thread_id:str|None=None; task_id:str|None=None; scope:str|None=None
def create_app(adapter=None):
 app=FastAPI(title='Xinhai Memory API',version='0.1.0'); adapter=adapter or adapter_from_env()
 from .onboarding import router_for
 from fastapi.middleware.cors import CORSMiddleware
 import os
 origins=[v.strip() for v in os.environ.get('XINHAI_CORS_ORIGINS','').split(',') if v.strip() and v.strip()!='*']
 if origins: app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST'],allow_headers=['Content-Type'])
 app.include_router(router_for(adapter.service))
 from .governance import router_for as governance_router
 app.include_router(governance_router(adapter.service))
 @app.exception_handler(XinhaiError)
 async def xinhai_error(request:Request,exc:XinhaiError): return JSONResponse(status_code=exc.status_code,content=exc.envelope(request.headers.get('x-request-id')))
 @app.get('/health')
 def health(): return {'status':'ok','service':'xinhai-memory'}
 @app.get('/config/current')
 def config_current(): return adapter.call('config_status',{})
 @app.get('/config/history')
 def config_history(): return adapter.call('config_history',{})
 @app.get('/config/diff')
 def config_diff(older:str,newer:str): return adapter.call('config_diff',{'older':older,'newer':newer})
 @app.post('/memories')
 def remember(body:RememberIn): return adapter.call('remember',body.model_dump())
 @app.post('/memories/confirm')
 def confirm(body:ConfirmIn):
  try:return adapter.call('confirm',body.model_dump())
  except KeyError as e:raise RecordNotFound(e.args[0])
 @app.post('/memories/auto-recall')
 def auto_recall(body: AutoRecallIn): return adapter.service.auto_recall(**body.model_dump())
 @app.get('/memories/search')
 def recall(q:str,limit:int=10,layer_id:str|None=None,scope:str|None=None,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,modality:str|None=None,source_id:str|None=None,expand_source:bool|None=None,text_weight:float|None=None,vector_weight:float|None=None):return adapter.call('recall',{'query':q,'limit':limit,'layer_id':layer_id,'scope':scope,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,'modality':modality,'source_id':source_id,**({'expand_source':expand_source} if expand_source is not None else {}),**weight_arguments(text_weight,vector_weight)})
 @app.get('/memories')
 def history(limit:int=50,branch_id:str|None=None,status:str|None=None,layer_id:str|None=None,tag:str|None=None,agent_id:str|None=None,workspace_id:str|None=None,scope:str|None=None):return adapter.call('history',{'limit':limit,'branch_id':branch_id,'status':status,'layer_id':layer_id,'tag':tag,'agent_id':agent_id,'workspace_id':workspace_id,'scope':scope})
 @app.post('/memories/forget')
 def forget(body:ForgetIn):
  try:return adapter.call('forget',body.model_dump())
  except KeyError as e:raise RecordNotFound(e.args[0])
 @app.post('/checkpoints')
 def checkpoint(body:CheckpointIn):return adapter.call('checkpoint',body.model_dump())
 @app.get('/checkpoints')
 def list_checkpoints(session_id:str=Query(min_length=1),thread_id:str|None=None,limit:int=Query(default=50,ge=1,le=200)):
  return adapter.service.list_checkpoints(session_id=session_id,thread_id=thread_id,limit=limit)
 @app.get('/memories/structured')
 def structured(enabled:bool|None=None,action:str|None=None,direction:str|None=None,branch_id:str|None=None,workspace_id:str|None=None,agent_id:str|None=None,limit:int=20): return adapter.call('recall_structured',{'enabled':enabled,'action':action,'direction':direction,'branch_id':branch_id,'workspace_id':workspace_id,'agent_id':agent_id,'limit':limit})
 @app.get('/memories/structured/compare')
 def structured_compare(rule_name:str|None=None,action:str|None=None,direction:str|None=None,branch_id:str|None=None,workspace_id:str|None=None,agent_id:str|None=None,limit:int=100): return adapter.call('compare_structured',{'rule_name':rule_name,'action':action,'direction':direction,'branch_id':branch_id,'workspace_id':workspace_id,'agent_id':agent_id,'limit':limit})
 @app.get('/memories/evidence')
 def evidence(q:str,limit:int=10,scope:str|None=None,modality:str|None=None,source_id:str|None=None,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,expand_source:bool|None=None,text_weight:float|None=None,vector_weight:float|None=None): return adapter.call('recall_evidence',{'query':q,'limit':limit,'scope':scope,'modality':modality,'source_id':source_id,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,**({'expand_source':expand_source} if expand_source is not None else {}),**weight_arguments(text_weight,vector_weight)})
 return app
app=create_app()
