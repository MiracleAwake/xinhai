"""Answer modern discovery probes explicitly on the legacy MCP transport."""
import json
import sys
from io import TextIOWrapper

import anyio
from mcp.server.stdio import stdio_server


async def run_legacy_stdio(server):
    stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"))
    stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
    output_lock = anyio.Lock()

    class Output:
        async def write(self, line):
            async with output_lock:
                await stdout.write(line)
                await stdout.flush()

        async def flush(self):
            pass

    output = Output()

    async def requests():
        async for line in stdin:
            try:
                message = json.loads(line)
            except ValueError:
                yield line
                continue
            if (
                isinstance(message, dict)
                and message.get("jsonrpc") == "2.0"
                and message.get("method") == "server/discover"
                and type(message.get("id")) in (str, int)
            ):
                await output.write(json.dumps({
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": "Method not found: server/discover"},
                }) + "\n")
                continue
            yield line

    async with stdio_server(stdin=requests(), stdout=output) as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())
