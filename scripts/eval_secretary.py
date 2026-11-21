import argparse, json, requests, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from xinhai.service import MemoryService

LAYERS={'worklog':'工作日志','guide':'工作指南','node':'核心记忆节点','lesson':'经验教训库','tool':'工具库'}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--mode',choices=['rule','ollama'],default='rule'); ap.add_argument('--output'); a=ap.parse_args()
 cases=json.loads(Path(a.dataset).read_text(encoding='utf-8'))['cases']; rows=[]
 for c in cases:
  if a.mode=='rule':
   s=MemoryService(':memory:'); r=s.secretary.process(c['text']); got='reject' if r.decision=='rejected' else LAYERS.get(r.layer_id,r.layer_id); s.close(); rows.append({**c,'got':got,'valid':True,'match':got==c['expected']})
  else:
   prompt='Return JSON only with keys summary,memory_layer,tags,action,uncertainty. memory_layer must be one of 工作日志,工作指南,核心记忆节点,经验教训库,工具库,unknown; action must be 记录,忽略,待确认. Do not invent. Content: '+c['text']
   try:
    obj=requests.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen2.5vl:3b','stream':False,'format':'json','messages':[{'role':'user','content':prompt}]},timeout=90).json()['message']['content']; obj=json.loads(obj); valid=isinstance(obj.get('summary'),str) and isinstance(obj.get('tags'),list) and obj.get('memory_layer') in ['工作日志','工作指南','核心记忆节点','经验教训库','工具库','unknown']; rows.append({**c,'output':obj,'valid':valid,'match':obj.get('memory_layer')==c['expected']})
   except Exception as e: rows.append({**c,'valid':False,'error':type(e).__name__,'match':False})
 report={'dataset':a.dataset,'mode':a.mode,'total':len(rows),'schema_valid':sum(x.get('valid',False) for x in rows),'layer_match':sum(x.get('match',False) for x in rows),'rows':rows}
 report['schema_rate']=report['schema_valid']/len(rows) if rows else 0; report['layer_accuracy']=report['layer_match']/len(rows) if rows else 0
 out=Path(a.output) if a.output else Path(a.dataset).with_name(Path(a.dataset).stem+'_'+a.mode+'_report.json'); out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'output':str(out),'schema_rate':report['schema_rate'],'layer_accuracy':report['layer_accuracy']},ensure_ascii=False))
if __name__=='__main__': main()
