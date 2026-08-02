# tests/test_api.py
# Tests every FastAPI endpoint.
# Uses httpx to make real HTTP requests to the running app.
# Mocks LLM calls so tests run without using an API key.

import pytest
import asyncio
import os
import tempfile

# Use temp dirs so tests don't touch real data
os.environ["STATE_DIR"] = tempfile.mkdtemp()
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp()
os.environ["REPORTS_DIR"] = tempfile.mkdtemp()

from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from api.main import app


@pytest.fixture
async def client():
    """Creates a test client that talks directly to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint should always return ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_start_research_empty_query(client):
    """Empty query should return 400 error."""
    response = await client.post("/research", json={"query": ""})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_start_research_valid_query(client):
    """Valid query should return a job_id immediately."""
    # Mock the supervisor so we don't actually run LLM calls during tests
    with patch("api.main.supervisor.run_research", new_callable=AsyncMock) as mock:
        mock.return_value = "testjob1"

        response = await client.post(
            "/research",
            json={"query": "What is machine learning?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] == "testjob1"


@pytest.mark.asyncio
async def test_status_not_found(client):
    """Status for nonexistent job should return 404."""
    response = await client.get("/status/doesnotexist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_report_not_found(client):
    """Report for nonexistent job should return 404."""
    response = await client.get("/report/doesnotexist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_jobs_list(client):
    """Jobs endpoint should return a list."""
    response = await client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


@pytest.mark.asyncio
async def test_upload_unsupported_type(client):
    """Uploading an unsupported file type should return 400."""
    response = await client.post(
        "/upload",
        files={"file": ("test.exe", b"fake content", "application/octet-stream")}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_path_traversal(client):
    """Uploaded filenames must stay inside the uploads folder."""
    response = await client.post(
        "/upload",
        files={"file": ("../evil.txt", b"bad path", "text/plain")}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_txt_file(client):
    """Uploading a valid .txt file should succeed."""
    response = await client.post(
        "/upload",
        files={"file": ("test.txt", b"Hello world content", "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
