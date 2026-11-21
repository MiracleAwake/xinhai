from dataclasses import dataclass
from ..domain.events import InternalEvent
from ..store import MemoryStore
from .chunker import split_text
import uuid
import re
@dataclass(frozen=True)
class SecretaryResult:
    decision: str; layer_id: str|None; summary: str; tags: list[str]; record: dict|None
NOISE={"嗯","好的","好","收到","谢谢","然后呢","明白","正在重连","工具调用进度","已运行命令"}
def is_noise(text: str) -> bool:
 clean = re.sub(r'\s+', ' ', text.strip())
 if not clean or clean in NOISE:
  return True
 # Progress suffixes and tool-status prefixes are transient UI events.
 if re.fullmatch(r'正在重连\s*\d+\s*/\s*\d+', clean):
  return True
 if clean.startswith('工具调用进度') or clean.startswith('工具调用进度：'):
  return True
 return False
RULES={"lesson":("错误","失败","教训","修复","踩坑","原因","问题","误判","冲突","截断","改为","导致"),"worklog":("任务","完成","测试","验证","待办","实现","接入","回归","基线","评估","报告","修复了","通过"),"guide":("规则","约定","必须","不要","工作风格","以后","唯一真相","区分","保留","配置修改","回滚","不确定"),"node":("记住","重要","喜欢","感谢","家人","情感","想法","搭档","小家","好久不见","名字","重逢","希望成为"),"tool":("脚本","工具","命令","代码","依赖","复用","解析器","加载脚本","stress.py",".ps1","mcp_e2e","向量脚本")}
class MemorySecretary:
 def __init__(self,store,provider=None): self.store,self.provider=store,provider
 def process(self,text,*,speaker='我',session_id=None,thread_id=None,user_confirmed=False,event_kind='message',raw_ref=None,event_id=None,client_type=None,unmapped=None, agent_id=None, workspace_id=None, branch_id=None, task_id=None, source_id=None, tags=None, modality='text', asset_ref=None, ocr_text=None, visual_summary=None):
  clean=text.strip()
  if is_noise(clean) or len(clean)<3:return SecretaryResult('rejected',None,'',[],None)
  model_result=None
  model_audit='disabled'
  if self.provider:
   try:
    candidate=self.provider.extract(clean)
    allowed={'工作日志':'worklog','工作指南':'guide','核心记忆节点':'node','经验教训库':'lesson','工具库':'tool'}
    ml=candidate.get('memory_layer'); action=candidate.get('action')
    if (ml in allowed and action in {'记录','忽略','待确认'}
        and isinstance(candidate.get('summary'),str)
        and isinstance(candidate.get('tags',[]),list)
        and isinstance(candidate.get('uncertainty',''),str)):
     model_result=candidate; model_audit='accepted'
    else:
     model_audit='invalid_output'
   except Exception as exc:
    model_audit='provider_error:'+type(exc).__name__
    model_result=None
  scores={l:sum(w in clean for w in ws) for l,ws in RULES.items()}; layer=max(scores,key=scores.get)
  if model_result:
   # The model is a drafting aid only.  Layer assignment stays deterministic so
   # a fluent but unsupported model label cannot move a record across archives.
   # Its summary/tags are retained below, while rule evidence remains authoritative.
   pass
  if scores[layer]==0: layer='worklog' if speaker=='工具' else 'node'
  decision='active' if user_confirmed else 'candidate'; tags=list(tags or []) + [f'layer:{layer}',f'event:{event_kind}']
  if model_result and model_result.get('tags'):
   tags += [str(t) for t in model_result['tags'][:5]]
  if 'DeepSea' in clean or '心海' in clean: tags.append('project:心海')
  if '错误' in clean or '失败' in clean: tags.append('type:lesson')
  summary=(model_result.get('summary') if model_result else None) or (clean if len(clean)<=240 else clean[:237]+'...')
  if len(summary)>240: summary=summary[:237]+'...'
  record=self.store.remember(text=clean,speaker=speaker,session_id=session_id,thread_id=thread_id,layer_id=layer,tags=tags,status=decision,source_path=raw_ref,source_id=source_id,event_id=event_id,client_type=client_type,event_kind=event_kind,unmapped=unmapped, agent_id=agent_id, workspace_id=workspace_id, branch_id=branch_id, task_id=task_id,modality=modality,asset_ref=asset_ref,ocr_text=ocr_text,visual_summary=visual_summary)
  with self.store.conn:
   draft_audit={'result':model_audit,'provider':type(self.provider).__name__ if self.provider else None,
                'draft':model_result,'final_layer':layer,'summary':summary,
                'uncertainty':model_result.get('uncertainty','unknown') if model_result else 'unknown',
                'source_id':source_id,'source_path':raw_ref,'is_verified':False}
   self.store.conn.execute("INSERT INTO audit_events(action,record_id,actor,created_at,details_json) VALUES (?,?,?,?,?)",('secretary_model',record['id'],'memory-secretary',__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),__import__('json').dumps(draft_audit,ensure_ascii=False)))
  return SecretaryResult(decision,layer,summary,tags,record)
 def process_event(self,event:InternalEvent,*,user_confirmed=False):
  if event.event_kind in {'tool_result','compaction','system'} and not event.text:return SecretaryResult('rejected',None,'',[],None)
  return self.process(event.text or '',speaker=event.speaker,session_id=event.session_id,thread_id=event.thread_id,user_confirmed=user_confirmed,event_kind=event.event_kind,raw_ref=event.raw_ref,event_id=event.event_id,client_type=event.client_type,unmapped=list(event.unmapped),agent_id=event.agent_id,workspace_id=event.workspace_id,branch_id=event.branch_id,task_id=event.task_id)
 def process_long(self,text,*,max_chars=500,**kwargs):
  """Process long text in bounded chunks without replacing the original text."""
  chunks=split_text(text,max_chars=max_chars)
  source_id=kwargs.pop('source_id',None) or ('chunkset:'+uuid.uuid4().hex)
  results=[]
  for index,chunk in enumerate(chunks):
   tags=list(kwargs.get('tags') or []) + [f'chunk:{index+1}/{len(chunks)}']
   results.append(self.process(chunk,source_id=source_id,tags=tags,**kwargs))
  return results
