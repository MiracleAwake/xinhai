from .configuration import weight_arguments
from pathlib import Path
import os
from .service import MemoryService
from .memory import OllamaMemoryProvider
from .retrieval.embedding import SentenceTransformerProvider
from .configuration import ConfigManager
from .governance import operations_for
TOOLS={'remember':'Store a candidate memory.','confirm':'Confirm a candidate.','auto_recall':'Detect and recall relevant memories.','recall':'Recall bounded active memories.','recall_evidence':'Recall modality-neutral evidence.','recall_structured':'Recall OCR structured facts.','compare_structured':'Compare structured image states.','config_status':'Read active runtime configuration metadata.','config_history':'List valid configuration versions.','config_diff':'Compare two valid configuration versions.','checkpoint':'Persist context state.','history':'List records.','forget':'Mark obsolete.'}
MAINTENANCE_TOOLS = {
    'rebuild_vectors': 'Recompute a page of vectors for the specified branch.',
    'rebuild_summary': 'Create a candidate summary from an original record.',
    'supersede': 'Confirm a candidate as the replacement for an active memory.',
    'cover_memory': 'Link a derived summary to source record ranges.',
    'verify_memory': 'Record a verification conclusion and its evidence.',
    'memory_provenance': 'Read revision, source coverage, and verification history.',
}
TOOLS.update(MAINTENANCE_TOOLS)
class MemoryMCPAdapter:
 def __init__(self,service,config_manager=None):self.service,self.config_manager=service,config_manager
 def call(self,name,arguments):
  if name=='remember':
   arguments.pop('adapter',None)
   return self.service.remember(arguments.pop('text'),**arguments).__dict__
  if name=='confirm':return self.service.confirm(arguments['record_id'])
  if name=='auto_recall':return self.service.auto_recall(arguments.pop('text'),**arguments)
  if name=='recall':return self.service.recall(arguments.pop('query'),**arguments)
  if name=='recall_evidence':return self.service.recall_evidence(arguments.pop('query'),**arguments)
  if name=='recall_structured':return self.service.recall_structured(**arguments)
  if name=='compare_structured':return self.service.compare_structured(**arguments)
  if name=='config_status':
   current=self.config_manager.current() if self.config_manager else None
   return {'configured': current is not None, 'version': current.get('version') if current else None, 'config_id': current.get('config_id') if current else None, 'scope': current.get('scope') if current else None, 'validation_status': current.get('validation_status') if current else None}
  if name=='config_history': return self.config_manager.history() if self.config_manager else []
  if name=='config_diff': return self.config_manager.diff(arguments['older'], arguments['newer']) if self.config_manager else {}
  if name=='checkpoint':return self.service.checkpoint(**arguments)
  if name=='history':return self.service.history(**arguments)
  if name=='forget':return self.service.forget(arguments['record_id'],arguments['reason'])
  raise KeyError(name)
def build_adapter(db_path,layers_path=None,markdown_root=None,config_root=None):
 if markdown_root and layers_path is None:
  default_layers=Path(__file__).resolve().parents[2]/'config'/'memory_layers.yaml'
  layers_path=default_layers if default_layers.exists() else None
 provider = OllamaMemoryProvider(model=os.environ.get('XINHAI_OLLAMA_MODEL','qwen2.5vl:3b'), host=os.environ.get('XINHAI_OLLAMA_HOST','http://127.0.0.1:11434')) if os.environ.get('XINHAI_MODEL_PROVIDER','').lower()=='ollama' else None
 embedding = SentenceTransformerProvider(os.environ.get('XINHAI_EMBEDDING_MODEL','BAAI/bge-m3')) if os.environ.get('XINHAI_EMBEDDING_PROVIDER','').lower()=='sentence-transformers' else None
 config_manager=ConfigManager(config_root) if config_root else None
 return MemoryMCPAdapter(MemoryService(db_path,layers_path=layers_path,markdown_root=markdown_root,model_provider=provider,embedding_provider=embedding,config_manager=config_manager),config_manager)
def create_server(adapter):
 from mcp.server.fastmcp import FastMCP
 from typing import Literal
 server=FastMCP('xinhai-memory')
 operations=operations_for(adapter.service)
 for name, description in MAINTENANCE_TOOLS.items():
  if name != 'memory_provenance':
   server.tool(name=name, description=description)(operations[name])
 @server.tool(description=MAINTENANCE_TOOLS['memory_provenance'])
 def memory_provenance(record_id:str,workspace_id:str,agent_id:str,branch_id:str,
                       scope:Literal['personal','workspace','garden']='personal',limit:int=50)->dict:
  if not 1 <= limit <= 200:
   raise ValueError('limit must be between 1 and 200')
  return operations['memory_provenance'](record_id,workspace_id,agent_id,branch_id,scope,limit)
 @server.tool()
 def remember(text:str,user_confirmed:bool=False,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,source_id:str|None=None,modality:str='text',asset_ref:str|None=None,ocr_text:str|None=None,visual_summary:str|None=None)->dict:
  return adapter.call('remember',{'text':text,'user_confirmed':user_confirmed,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,'source_id':source_id,'modality':modality,'asset_ref':asset_ref,'ocr_text':ocr_text,'visual_summary':visual_summary})
 @server.tool()
 def confirm(record_id:str)->dict:return adapter.call('confirm',{'record_id':record_id})
 @server.tool()
 def auto_recall(text:str,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,scope:str|None=None)->dict:return adapter.call('auto_recall',{'text':text,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,'scope':scope})
 @server.tool()
 def recall(query:str,limit:int=10,scope:str|None=None,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,modality:str|None=None,source_id:str|None=None,expand_source:bool|None=None,text_weight:float|None=None,vector_weight:float|None=None)->list:return adapter.call('recall',{'query':query,'limit':limit,'scope':scope,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,'modality':modality,'source_id':source_id,**({'expand_source':expand_source} if expand_source is not None else {}),**weight_arguments(text_weight,vector_weight)})
 @server.tool()
 def recall_evidence(query:str,limit:int=10,scope:str|None=None,agent_id:str|None=None,workspace_id:str|None=None,branch_id:str|None=None,session_id:str|None=None,thread_id:str|None=None,task_id:str|None=None,modality:str|None=None,source_id:str|None=None,expand_source:bool|None=None,text_weight:float|None=None,vector_weight:float|None=None)->list:return adapter.call('recall_evidence',{'query':query,'limit':limit,'scope':scope,'agent_id':agent_id,'workspace_id':workspace_id,'branch_id':branch_id,'session_id':session_id,'thread_id':thread_id,'task_id':task_id,'modality':modality,'source_id':source_id,**({'expand_source':expand_source} if expand_source is not None else {}),**weight_arguments(text_weight,vector_weight)})
 @server.tool()
 def recall_structured(enabled:bool|None=None,action:str|None=None,direction:str|None=None,branch_id:str|None=None,workspace_id:str|None=None,agent_id:str|None=None,limit:int=20)->list:return adapter.call('recall_structured',{'enabled':enabled,'action':action,'direction':direction,'branch_id':branch_id,'workspace_id':workspace_id,'agent_id':agent_id,'limit':limit})
 @server.tool()
 def compare_structured(rule_name:str|None=None,action:str|None=None,direction:str|None=None,branch_id:str|None=None,workspace_id:str|None=None,agent_id:str|None=None,limit:int=100)->dict:return adapter.call('compare_structured',{'rule_name':rule_name,'action':action,'direction':direction,'branch_id':branch_id,'workspace_id':workspace_id,'agent_id':agent_id,'limit':limit})
 @server.tool()
 def config_status()->dict:return adapter.call('config_status',{})
 @server.tool()
 def config_history()->list:return adapter.call('config_history',{})
 @server.tool()
 def config_diff(older:str,newer:str)->dict:return adapter.call('config_diff',{'older':older,'newer':newer})
 @server.tool()
 def checkpoint(session_id:str,goal:str='',pending:list[str]|None=None,unknown:list[str]|None=None)->dict:return adapter.call('checkpoint',{'session_id':session_id,'goal':goal,'pending':pending or [],'unknown':unknown or []})
 @server.tool()
 def history(limit:int=50)->list:return adapter.call('history',{'limit':limit})
 @server.tool()
 def forget(record_id:str,reason:str)->dict:return adapter.call('forget',{'record_id':record_id,'reason':reason})
 return server
def main():
 root=Path(os.environ.get('XINHAI_ROOT',Path(__file__).resolve().parents[2])); adapter=build_adapter(Path(os.environ.get('XINHAI_DB',root/'data/xinhai.sqlite')),Path(os.environ.get('XINHAI_LAYERS',root/'config/memory_layers.yaml')),Path(os.environ.get('XINHAI_MARKDOWN_ROOT',root/'记忆库')),Path(os.environ.get('XINHAI_CONFIG_ROOT',root/'config'/'versions')));
 import anyio
 from .mcp_stdio import run_legacy_stdio
 try: anyio.run(run_legacy_stdio,create_server(adapter)._mcp_server)
 finally: adapter.service.close()
if __name__=='__main__':main()
