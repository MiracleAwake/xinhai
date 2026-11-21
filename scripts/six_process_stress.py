import multiprocessing as mp, tempfile, pathlib, json, shutil, time
from xinhai.service import MemoryService

def worker(args):
 db,b=args; s=MemoryService(db)
 try:
  for i in range(10): s.store.remember(text=f'{b} process record {i}',status='active',branch_id=b,agent_id=b.split('-')[0],workspace_id='proc')
  return {'branch':b,'ok':True}
 except Exception as e:return {'branch':b,'ok':False,'error':repr(e)}
 finally:s.close()

def main():
 root=pathlib.Path(tempfile.mkdtemp(prefix='xinhai-proc-')); db=root/'shared.sqlite'; branches=['codex-GO2','codex-GO3','cursor-A','cursor-B','dsh-A','workbuddy-A']; t=time.perf_counter()
 try:
  with mp.get_context('spawn').Pool(6) as pool: results=pool.map(worker,[(str(db),b) for b in branches])
  s=MemoryService(db); counts={b:len(s.recall('process record',branch_id=b,limit=100)) for b in branches}; s.close(); print(json.dumps({'processes':6,'writes':60,'elapsed_s':round(time.perf_counter()-t,3),'workers':results,'counts':counts,'complete':all(x==10 for x in counts.values())},ensure_ascii=False))
 finally: shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__': main()
