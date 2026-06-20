# mcp_servers/search_server.py
# A standalone MCP server that exposes web_search as an MCP tool.
#
# HOW MCP SERVERS WORK:
# This file runs as a SEPARATE PROCESS from your main app.
# It communicates via stdio (standard input/output) — text in, text out.
# Any MCP client connects to this process and can call the tools it exposes.
# The MCP SDK handles all the protocol details — you just define tools.

import sys
import os
import asyncio
import json

# Add project root to path so we can import config and tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from config import get_settings

settings = get_settings()

# Create the MCP server — give it a name clients will see
app = Server("research-search-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    Tells MCP clients what tools this server provides.
    Clients call this first to discover available tools.
    """
    return [
        Tool(
            name="web_search",
            description=(
                "Search the web for current information on any topic. "
                "Returns titles, URLs, and content excerpts from relevant pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """
    Called when an MCP client wants to execute a tool.
    Receives the tool name and arguments, returns results.
    """
    if name != "web_search":
        raise ValueError(f"Unknown tool: {name}")

    query = arguments["query"]
    max_results = arguments.get("max_results", settings.max_search_results)

    # Use real Tavily search if key is configured, otherwise mock
    if settings.tavily_api_key.startswith("tvly-"):
        result = await _tavily_search(query, max_results)
    else:
        result = _mock_search(query, max_results)

    # MCP requires results wrapped in TextContent objects
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _tavily_search(query: str, max_results: int) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "query": query,
            "answer": data.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "excerpt": r.get("content", ""),
                }
                for r in data.get("results", [])
            ],
        }


def _mock_search(query: str, max_results: int) -> dict:
    return {
        "query": query,
        "answer": "[MOCK] Add tvly- key to .env for real results",
        "results": [
            {
                "title": f"Mock result {i+1} for: {query}",
                "url": f"https://example.com/{i+1}",
                "excerpt": f"Mock content about {query}",
            }
            for i in range(min(max_results, 3))
        ],
    }


async def main():
    # stdio_server handles the MCP protocol communication
    # Your server reads from stdin, writes to stdout
    # The MCP client on the other end does the same
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())