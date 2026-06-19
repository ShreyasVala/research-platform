# agents/worker.py
# A single Worker Agent. Gets one specific research task,
# calls tools to gather data, then asks the LLM to summarize findings.
#
# Multiple workers run at the SAME TIME (in parallel) for one research job.
# Worker 1 might search the web while Worker 2 reads a document simultaneously.
# This is what makes multi-agent faster than asking one AI everything sequentially.

import json
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from config import get_settings
from tools.search_tool import web_search
from tools.document_tool import read_document

settings = get_settings()


class WorkerAgent:

    # The "personality" of every worker — tells the LLM how to behave
    SYSTEM_PROMPT = """You are a specialist research assistant.
You receive a specific research task and the raw results from search tools.
Your job: write a clear, factual 3-5 paragraph summary of what you found.
Always include source URLs when available. Be specific, not vague.
If the tool results are mock/fake data, say so clearly."""

    def __init__(self, worker_id: str, job_id: str):
        self.worker_id = worker_id    # e.g. "a3f9-w0", "a3f9-w1"
        self.job_id = job_id
        # This returns an AsyncOpenAI client pointed at Ollama or OpenAI
        # depending on what LLM_PROVIDER is set to in .env
        self.client = settings.make_llm_client()
        self.model = settings.worker_model

    async def run(self, task: dict) -> dict:
        """
        Runs one research task. A task looks like:
        {
          "type": "search",
          "description": "Research the benefits of MCP protocol",
          "search_queries": ["MCP protocol benefits", "model context protocol uses"]
        }
        Returns a dict with the task, raw tool data, LLM summary, and status.
        """
        # Step 1: Call tools to gather raw information
        tool_results = await self._gather_tool_results(task)

        # Step 2: Ask the LLM to read the raw data and write a summary
        summary = await self._summarize(task["description"], tool_results)

        return {
            "worker_id": self.worker_id,
            "task": task,
            "tool_results": tool_results,
            "summary": summary,
            "status": "done",
        }

    async def _gather_tool_results(self, task: dict) -> list:
        """Calls the right tool(s) based on task type."""
        results = []
        task_type = task.get("type", "search")

        if task_type == "search":
            # Run up to 3 search queries simultaneously using asyncio.gather
            # asyncio.gather = "start all these tasks at once, wait for all to finish"
            queries = task.get("search_queries", [task["description"]])
            search_coroutines = [
                web_search(q, settings.max_search_results)
                for q in queries[:3]  # cap at 3 queries per worker
            ]
            raw = await asyncio.gather(*search_coroutines, return_exceptions=True)
            for r in raw:
                if not isinstance(r, Exception):  # skip failed searches
                    results.append(r)

        elif task_type == "document":
            doc_name = task.get("document_name", "")
            if doc_name:
                doc = await read_document(doc_name)
                results.append(doc)

        return results

    # @retry decorator: if this function raises an exception, automatically
    # try again up to 3 times. Wait 1s before retry 2, 2s before retry 3.
    # This handles temporary Ollama timeouts or network hiccups gracefully.
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _summarize(self, task_description: str, tool_results: list) -> str:
        """Sends tool results to the LLM and gets a written summary back."""

        # Convert results to a string. Cap at 6000 chars so we don't overflow
        # the model's context window (it can only read so much at once)
        context = json.dumps(tool_results, indent=2)[:6000]

        # messages is the conversation we send to the LLM
        # "system" = instructions/personality
        # "user" = the actual request
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research task: {task_description}\n\n"
                    f"Here is the raw data from my research tools:\n{context}\n\n"
                    "Please write your research summary:"
                ),
            },
        ]

        # This is the actual call to the LLM (Ollama or OpenAI)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,    # 0 = deterministic/focused, 1 = creative/random
            max_tokens=800,     # max length of the response
        )

        # The response object has a nested structure — dig in to get the text
        return response.choices[0].message.content.strip()