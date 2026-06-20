# tests/test_memory.py
# Tests for the memory/state management system.
# These tests run completely offline — no LLM, no internet needed.

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

# We need to set STATE_DIR to a temp folder so tests don't
# mess with your real state/ folder
os.environ["STATE_DIR"] = tempfile.mkdtemp()

from agents.memory import MemoryManager, ResearchState


@pytest.fixture
def memory():
    """Creates a fresh MemoryManager for each test."""
    return MemoryManager()


@pytest.mark.asyncio
async def test_save_and_load(memory):
    """Test that saving and loading a state works correctly."""
    state = ResearchState("test123", "What is Python?")
    await memory.save(state)

    loaded = await memory.load("test123")
    assert loaded is not None
    assert loaded.job_id == "test123"
    assert loaded.query == "What is Python?"
    assert loaded.status == "planning"


@pytest.mark.asyncio
async def test_update_status(memory):
    """Test that status updates are saved correctly."""
    state = ResearchState("test456", "Test query")
    await memory.save(state)

    await memory.update_status("test456", "running")

    loaded = await memory.load("test456")
    assert loaded.status == "running"


@pytest.mark.asyncio
async def test_append_worker_result(memory):
    """Test that worker results are appended correctly."""
    state = ResearchState("test789", "Test query")
    await memory.save(state)

    result = {
        "worker_id": "test789-w0",
        "summary": "Test summary",
        "status": "done"
    }
    await memory.append_worker_result("test789", result)

    loaded = await memory.load("test789")
    assert len(loaded.worker_results) == 1
    assert loaded.worker_results[0]["worker_id"] == "test789-w0"


@pytest.mark.asyncio
async def test_load_nonexistent_job(memory):
    """Test that loading a job that doesn't exist returns None."""
    result = await memory.load("doesnotexist")
    assert result is None


@pytest.mark.asyncio
async def test_list_jobs(memory):
    """Test that listing jobs returns all saved jobs."""
    state1 = ResearchState("listtest1", "Query one")
    state2 = ResearchState("listtest2", "Query two")
    await memory.save(state1)
    await memory.save(state2)

    jobs = await memory.list_jobs()
    job_ids = [j["job_id"] for j in jobs]
    assert "listtest1" in job_ids
    assert "listtest2" in job_ids