# mcp_servers/document_server.py
# MCP server exposing document reading tools.
# Lets any MCP client read PDFs and text files from the uploads/ folder.

import sys
import os
import asyncio
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from config import get_settings

settings = get_settings()
app = Server("research-document-server")

SUPPORTED = {".pdf", ".txt", ".md", ".csv"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_documents",
            description="List all documents available in the uploads folder.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="read_document",
            description=(
                "Read and extract text from an uploaded document. "
                "Supports PDF, TXT, MD, and CSV files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file in the uploads folder",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default 8000)",
                        "default": 8000,
                    },
                },
                "required": ["filename"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "list_documents":
        return await _list_documents()
    elif name == "read_document":
        return await _read_document(
            arguments["filename"],
            arguments.get("max_chars", 8000)
        )
    raise ValueError(f"Unknown tool: {name}")


async def _list_documents():
    uploads = Path(settings.uploads_dir)
    if not uploads.exists():
        result = {"files": [], "message": "Uploads folder is empty"}
    else:
        files = [
            {
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "type": f.suffix,
            }
            for f in uploads.iterdir()
            if f.suffix.lower() in SUPPORTED
        ]
        result = {"files": files, "count": len(files)}
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _read_document(filename: str, max_chars: int):
    path = Path(settings.uploads_dir) / filename

    if not path.exists():
        result = {"error": f"File not found: {filename}"}
        return [TextContent(type="text", text=json.dumps(result))]

    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            import fitz
            doc = fitz.open(str(path))
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        else:
            text = path.read_text(encoding="utf-8", errors="replace")

        truncated = len(text) > max_chars
        result = {
            "filename": filename,
            "content": text[:max_chars],
            "truncated": truncated,
            "char_count": min(len(text), max_chars),
        }
    except Exception as e:
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())