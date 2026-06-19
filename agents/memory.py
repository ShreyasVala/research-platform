# agents/memory.py
# Saves the full state of each research job to a JSON file on disk.
#
# WHY THIS EXISTS:
# AI models have a "context window" — a limit on how much text they can
# hold in memory at once. A long research job generates thousands of tokens.
# Without saving to disk, if the context fills up or the program crashes,
# everything is lost. This file is your project's "notebook" — the plan
# gets written down before anything can go wrong.

import json
import asyncio
from datetime import datetime
from pathlib import Path
from config import get_settings

settings = get_settings()


class ResearchState:
    """All data for one research job. One instance per user query."""

    def __init__(self, job_id: str, query: str):
        self.job_id = job_id          # short unique ID, e.g. "a3f9b2c1"
        self.query = query            # the original user question
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.status = "planning"      # planning → running → synthesizing → done / failed
        self.plan = []                # list of sub-tasks the supervisor creates
        self.worker_results = []      # findings from each worker as they finish
        self.final_report = ""        # the finished report
        self.error = ""               # error message if something went wrong

    def to_dict(self) -> dict:
        # Converts to a plain dictionary so json.dumps() can save it
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchState":
        # Rebuilds a ResearchState object from a saved dictionary
        obj = cls.__new__(cls)
        obj.__dict__.update(d)
        return obj


class MemoryManager:
    """Saves and loads ResearchState objects as JSON files."""

    def __init__(self):
        self.state_dir = Path(settings.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Lock prevents two workers writing the same file at the same time
        self._lock = asyncio.Lock()

    def _path(self, job_id: str) -> Path:
        # Each job gets its own file: state/a3f9b2c1.json
        return self.state_dir / f"{job_id}.json"

    async def save(self, state: ResearchState) -> None:
        state.updated_at = datetime.utcnow().isoformat()
        async with self._lock:
            self._path(state.job_id).write_text(
                json.dumps(state.to_dict(), indent=2),
                encoding="utf-8"
            )

    async def load(self, job_id: str) -> ResearchState | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ResearchState.from_dict(data)

    async def update_status(self, job_id: str, status: str, **kwargs) -> None:
        """Load → update fields → save back. Used to change status mid-pipeline."""
        state = await self.load(job_id)
        if state:
            state.status = status
            for key, value in kwargs.items():
                setattr(state, key, value)
            await self.save(state)

    async def append_worker_result(self, job_id: str, result: dict) -> None:
        """Adds one worker's findings to the job's result list."""
        state = await self.load(job_id)
        if state:
            state.worker_results.append(result)
            await self.save(state)

    async def list_jobs(self) -> list[dict]:
        """Returns a summary of all jobs ever run."""
        jobs = []
        for p in self.state_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text())
                jobs.append({
                    "job_id": data["job_id"],
                    "query": data["query"],
                    "status": data["status"],
                    "created_at": data["created_at"],
                })
            except Exception:
                pass  # skip any corrupted files
        return sorted(jobs, key=lambda x: x["created_at"], reverse=True)