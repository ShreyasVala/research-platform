# agents/supervisor.py
# The Supervisor Agent — coordinates the entire research pipeline.
#
# WHAT IT DOES IN ORDER:
# 1. Receives the user's research question
# 2. Asks an LLM to break it into 2-4 specific sub-tasks (the "plan")
# 3. Saves the plan to disk BEFORE anything else happens
# 4. Spawns multiple Worker Agents to run those tasks in parallel
# 5. Waits for all workers to finish and saves their results
# 6. Asks the LLM to combine all findings into one final report

import json
import uuid
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from config import get_settings
from agents.memory import MemoryManager, ResearchState
from agents.worker import WorkerAgent
from tools.storage import save_report_text
import logging

# Set up logging for this module
logger = logging.getLogger(__name__)

settings = get_settings()
memory = MemoryManager()


class SupervisorAgent:

    PLAN_PROMPT = """You are a senior research director.
Given a research query, output a JSON research plan.
Output ONLY raw JSON — no markdown, no code fences, no explanation before or after.

Format:
{
  "tasks": [
    {
      "id": "t1",
      "type": "search",
      "description": "What this task investigates",
      "search_queries": ["specific query 1", "specific query 2"],
      "priority": 1
    }
  ]
}

Rules:
- 2 to 4 tasks total
- Each task must be fully independent (they run simultaneously)
- search_queries: 1-3 specific, focused queries per task
- priority 1 tasks run before priority 2 tasks
- Only use type "document" if a document filename is provided"""

    SYNTHESIS_PROMPT = """You are a senior research analyst.
You have received findings from multiple specialist researchers working in parallel.
Synthesize everything into one coherent research report.

Structure:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points)
3. Detailed Analysis (paragraphs per sub-topic)
4. Sources and References (all URLs)
5. Limitations (what this research couldn't cover)

Be specific. Cite sources inline. Use professional language."""

    def __init__(self):
        self.client = settings.make_llm_client()
        self.model = settings.supervisor_model

    async def run_research(self, query: str, document_name: str | None = None) -> str:
        """
        Starts a research job. Returns a job_id immediately.
        The actual work runs in the background — caller polls /status/{id}.
        """
        # Generate a short random ID for this job
        job_id = str(uuid.uuid4())[:8]

        # Create and save initial state BEFORE doing anything
        state = ResearchState(job_id, query)
        await memory.save(state)

        # asyncio.create_task starts the pipeline WITHOUT waiting for it.
        # This lets the API return the job_id instantly while work continues.
        asyncio.create_task(self._pipeline(job_id, query, document_name))
        return job_id

    async def _pipeline(self, job_id: str, query: str, document_name: str | None):
        try:
            logger.info(f"Job {job_id} started — query: {query[:50]}")
            await memory.update_status(job_id, "planning")

            logger.info(f"Job {job_id} — creating research plan")
            plan = await self._plan(query, document_name)
            logger.info(f"Job {job_id} — plan created with {len(plan['tasks'])} tasks")

            state = await memory.load(job_id)
            state.plan = plan["tasks"]
            state.status = "running"
            await memory.save(state)

            await self._execute_workers(job_id, plan["tasks"])
            logger.info(f"Job {job_id} — all workers complete")

            await memory.update_status(job_id, "synthesizing")
            logger.info(f"Job {job_id} — synthesizing report")
            state = await memory.load(job_id)
            report = await self._synthesize(query, state.worker_results)
            report_location = await asyncio.to_thread(
                save_report_text,
                job_id,
                query,
                report,
            )

            await memory.update_status(
                job_id,
                "done",
                final_report=report,
                report_location=report_location,
            )
            logger.info(f"Job {job_id} — done")

        except Exception as e:
            logger.error(f"Job {job_id} — failed: {e}")
            await memory.update_status(job_id, "failed", error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _plan(self, query: str, document_name: str | None) -> dict:
        """Asks the LLM to generate a research plan as JSON."""
        doc_hint = f"\nA document is available for analysis: {document_name}" \
                   if document_name else ""

        messages = [
            {"role": "system", "content": self.PLAN_PROMPT},
            {"role": "user", "content": f"Research query: {query}{doc_hint}"},
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,   # very low = consistent JSON output
            max_tokens=600,
        )

        raw = response.choices[0].message.content.strip()

        # LLMs sometimes wrap JSON in ```json ... ``` — strip those if present
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        plan = json.loads(raw)
        if document_name:
            for task in plan.get("tasks", []):
                if task.get("type") == "document":
                    task["document_name"] = document_name
        return plan

    async def _execute_workers(self, job_id: str, tasks: list):
        """Groups tasks by priority, runs each group in parallel."""
        # Group tasks: {1: [task_a, task_b], 2: [task_c]}
        by_priority: dict[int, list] = {}
        for task in tasks:
            p = task.get("priority", 1)
            by_priority.setdefault(p, []).append(task)

        # Process each priority level — all tasks in same level run simultaneously
        for priority in sorted(by_priority.keys()):
            group = by_priority[priority]

            # Semaphore = "allow maximum N workers running at the same time"
            # Prevents sending too many simultaneous LLM API requests
            semaphore = asyncio.Semaphore(settings.max_concurrent_workers)

            async def run_one(task, idx):
                async with semaphore:
                    worker = WorkerAgent(
                        worker_id=f"{job_id}-w{idx}",
                        job_id=job_id,
                    )
                    result = await worker.run(task)
                    # Save each result as it completes, not all at the end
                    await memory.append_worker_result(job_id, result)
                    return result

            # Start ALL workers in this priority group simultaneously
            # return_exceptions=True = if one worker fails, others keep running
            results = await asyncio.gather(
                *[run_one(task, i) for i, task in enumerate(group)],
                return_exceptions=True,
            )
            for idx, (task, result) in enumerate(zip(group, results)):
                if isinstance(result, Exception):
                    await memory.append_worker_result(job_id, {
                        "worker_id": f"{job_id}-w{idx}-failed",
                        "task": task,
                        "tool_results": [],
                        "summary": "",
                        "status": "failed",
                        "error": str(result),
                    })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _synthesize(self, query: str, worker_results: list) -> str:
        """Combines all worker summaries into a final report."""
        # Build a readable block of all worker findings
        summaries = "\n\n---\n\n".join(
            f"Researcher {r['worker_id']} investigated: {r['task']['description']}\n\n"
            f"{r['summary']}"
            for r in worker_results
            if r.get("status") == "done"
        )

        messages = [
            {"role": "system", "content": self.SYNTHESIS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original research query: {query}\n\n"
                    f"Findings from all researchers:\n{summaries[:8000]}\n\n"
                    "Write the final research report:"
                ),
            },
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()
