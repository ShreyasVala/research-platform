# Multi-Agent Research Platform

An AI-powered research system that uses multiple specialized agents working 
in parallel to gather, analyze, and synthesize information on any topic.

## Architecture

- **Supervisor Agent** — receives a query, creates a research plan, 
  coordinates workers, synthesizes the final report
- **Worker Agents** — run in parallel, each handling one specific 
  research sub-task (web search, document analysis)
- **MCP Servers** — standardized tool servers for web search (Tavily) 
  and document parsing (PyMuPDF)
- **FastAPI backend** — exposes HTTP endpoints for job management
- **File-backed memory** — persists research state across context limits

## Tech Stack

Python · FastAPI · MCP (Model Context Protocol) · Ollama · OpenAI · 
Tavily · PyMuPDF · Docker · asyncio

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/YOURUSERNAME/research-platform.git
cd research-platform
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt

# 2. Install Ollama and pull a model (free local LLM)
# Download from ollama.com
ollama pull llama3.2

# 3. Configure environment
cp .env.example .env
# Edit .env — add your Tavily API key

# 4. Run a research job
python test_local.py "What are the benefits of multi-agent AI systems?"

# 5. Or start the API server
uvicorn api.main:app --reload --port 8000
# Visit http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /research | Start a research job |
| GET | /status/{job_id} | Poll job progress |
| GET | /report/{job_id} | Get finished report |
| GET | /jobs | List all jobs |
| POST | /upload | Upload a document |
| GET | /health | Check server config |

## How it works

1. User sends a query to POST /research
2. Supervisor Agent uses an LLM to break it into 2-4 independent sub-tasks
3. Worker Agents run those tasks **simultaneously** using asyncio
4. Each worker calls MCP tool servers to search the web or read documents
5. Workers save findings to disk as they complete
6. Supervisor synthesizes all findings into a final structured report
7. User retrieves the report from GET /report/{job_id}

