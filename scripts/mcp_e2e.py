import asyncio, os, sys, json, ast
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
def parse_tool_json(result):
 text=''.join(getattr(x,'text','') for x in (result.content or []))
 try:return json.loads(text)
 except json.JSONDecodeError:
  start=min([i for i in (text.find('{'),text.find('[')) if i>=0],default=-1)
  if start<0:
   try:return ast.literal_eval(text)
   except Exception: raise
  try:return json.loads(text[start:])
  except json.JSONDecodeError:return ast.literal_eval(text[start:])
async def main():
 root=Path(__file__).parents[1]; db=Path(os.environ.get('TEMP','.'))/'xinhai-mcp-branch-e2e.sqlite'
 if db.exists(): db.unlink()
 env={**os.environ,'PYTHONPATH':str(root/'src'),'XINHAI_ROOT':str(root),'XINHAI_DB':str(db),'XINHAI_LAYERS':str(root/'config/memory_layers.yaml'),'XINHAI_MARKDOWN_ROOT':str(root/'data/e2e-memory')}
 params=StdioServerParameters(command=sys.executable,args=['-m','xinhai.mcp_server'],env=env)
 async with stdio_client(params) as (read,write):
  async with ClientSession(read,write) as client:
   await client.initialize(); names={t.name for t in (await client.list_tools()).tools}; assert {'remember','confirm','recall','checkpoint','history','forget'}<=names
   ids=[]
   for branch in ['GO2','GO3']:
    saved=await client.call_tool('remember',{'text':f'Codex {branch} 分支记忆','user_confirmed':True,'agent_id':'codex','workspace_id':'deepsea','branch_id':branch,'session_id':f's-{branch}','thread_id':f't-{branch}'})
    ids.append(parse_tool_json(saved)['record']['id'])
   for branch in ['GO2','GO3']:
    found=await client.call_tool('recall',{'query':'分支记忆','limit':5,'agent_id':'codex','workspace_id':'deepsea','branch_id':branch})
    rows=parse_tool_json(found) if found.content else {}; rows=rows if isinstance(rows,list) else [rows]
    assert len(rows)==1 and rows[0]['branch_id']==branch
   print('MCP branch e2e passed:', sorted(names), ids)
asyncio.run(main())
