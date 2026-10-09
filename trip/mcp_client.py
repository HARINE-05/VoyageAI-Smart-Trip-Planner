import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _batch(calls):
    params = StdioServerParameters(command=sys.executable,
                                  args=[str(Path(__file__).resolve().parents[1] / 'mcp_server.py')])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            results = []
            for name, arguments in calls:
                result = await session.call_tool(name, arguments=arguments)
                if result.isError:
                    raise RuntimeError(f'MCP tool {name} failed. Check inputs and network access.')
                data = getattr(result, 'structuredContent', None)
                if data is None:
                    data = json.loads(next(c.text for c in result.content if c.type == 'text'))
                results.append(data)
            return results

def call_batch(calls):
    return asyncio.run(asyncio.wait_for(_batch(calls), timeout=90))
