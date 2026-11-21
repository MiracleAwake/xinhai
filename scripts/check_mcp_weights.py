"""Real stdio contract check; all writes stay inside a temporary directory."""
import asyncio, json, os, sys, tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from xinhai.configuration import ConfigManager

async def main():
    root=Path(__file__).parents[1]
    with tempfile.TemporaryDirectory(prefix='xinhai-weights-') as tmp:
        folder=Path(tmp); manager=ConfigManager(folder/'versions')
        manager.activate(manager.stage({'retrieval':{'weights':{'text':3,'vector':1}}},version='v1'))
        env={**os.environ,'PYTHONPATH':str(root/'src'),'XINHAI_DB':str(folder/'memory.sqlite'),
             'XINHAI_ROOT':str(root),'XINHAI_MARKDOWN_ROOT':str(folder/'markdown'),
             'XINHAI_CONFIG_ROOT':str(folder/'versions'),'XINHAI_EMBEDDING_PROVIDER':'','XINHAI_MODEL_PROVIDER':''}
        async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','xinhai.mcp_server'],env=env)) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                identity = {'agent_id':'codex-probe','workspace_id':'acceptance','branch_id':'A'}
                saved = await client.call_tool('remember',{
                    'text':'完成权重契约测试','user_confirmed':True,**identity})
                assert not saved.isError
                record_id = json.loads(saved.content[0].text)['record']['id']
                same = await client.call_tool('recall',{'query':'权重契约',**identity})
                assert not same.isError and json.loads(same.content[0].text)['id'] == record_id
                other = await client.call_tool('recall',{
                    'query':'权重契约',**identity,'branch_id':'B'})
                assert not other.isError and not other.content
                for name in ('recall','recall_evidence'):
                    for extra,source in (({},'config'),({'text_weight':1,'vector_weight':4},'request')):
                        result=await client.call_tool(name,{'query':'权重契约','branch_id':'A',**extra})
                        assert not result.isError
                        text=''.join(item.text for item in result.content if hasattr(item,'text'))
                        assert source in text and 'weight_source' in text
                    bad=await client.call_tool(name,{'query':'权重契约','text_weight':1})
                    assert bad.isError
        print('MCP weights contract passed; temporary files cleaned on exit')

if __name__=='__main__': asyncio.run(main())
