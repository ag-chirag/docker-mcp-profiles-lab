"""A second MCP client: list tools and make a deterministic example call."""

import argparse
import asyncio
import json
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def explore(profile: str):
    server = StdioServerParameters(
        command=str(ROOT / "scripts/gateway.sh"), args=[profile]
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=60)
        ) as session:
            await session.initialize()
            print(
                "Tools:", ", ".join(t.name for t in (await session.list_tools()).tools)
            )
            if profile == "web":
                result = await session.call_tool(
                    "page_outline", {"html": "<h1>Docker</h1><h2>Profiles</h2>"}
                )
            else:
                result = await session.call_tool("order_summary", {"region": "west"})
            print(json.dumps(result.model_dump(mode="json"), indent=2))
            if result.isError:
                raise RuntimeError("Example tool call failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["web", "backend"])
    asyncio.run(explore(parser.parse_args().profile))
