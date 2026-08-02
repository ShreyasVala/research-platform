# Multi-Agent Research Platform

I built this project to explore a simple question: instead of asking one model
to handle an entire research request, what if a supervisor could split the work
between several focused agents and combine their findings at the end?

The result is a FastAPI backend that turns a query into 2-4 independent tasks.
Workers handle web searches or uploaded documents in parallel, then the
supervisor produces one structured report from their results.

## How it works

1. A research request is sent to `POST /research`.
2. The supervisor creates a plan with 2-4 independent tasks.
3. Worker agents run those tasks concurrently with `asyncio`.
4. Search workers use Tavily, while document workers can read PDF, TXT,
   Markdown, and CSV files.
5. Worker results are saved as they finish, including failures.
6. The supervisor combines the successful results into a final report.

The API returns a job ID immediately, so progress and reports can be requested
separately instead of keeping one HTTP request open for the full research run.

## Project structure

```text
api/          FastAPI routes
agents/       Supervisor, workers, and job state
tools/        Search, document, and storage helpers
mcp_servers/  MCP search and document servers
tests/        API, persistence, validation, and storage tests
```

Job state is stored in JSON files so an in-progress job does not depend only on
memory. Uploaded files and reports can use local folders during development or
a private S3 bucket when the application is run on AWS.

## Tech used

- Python, FastAPI, and `asyncio`
- OpenAI and Tavily APIs
- Model Context Protocol (MCP)
- PyMuPDF for PDF text extraction
- Docker and Docker Compose
- AWS S3 integration and an EC2/CloudWatch deployment setup
- pytest and GitHub Actions

## Run it locally

Create the environment and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your OpenAI and Tavily keys to `.env`, then start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

The interactive API page is available at `http://localhost:8000/docs`.

You can also run the backend with Docker:

```powershell
docker compose up --build
```

The `.env` file is ignored by both Git and Docker, so local API keys are not
added to the repository or image.

## Using S3

Local storage is the default. To use S3, attach an IAM role to the EC2 instance
and update these values in `.env`:

```text
STORAGE_BACKEND=s3
AWS_REGION=us-east-1
S3_BUCKET=your-private-bucket
S3_PREFIX=research-platform
```

The application stores uploaded documents under `uploads/` and generated
reports under `reports/` inside the configured prefix. AWS access keys are not
needed in the project when EC2 uses an IAM role.

The manual EC2, IAM, S3, and CloudWatch steps are in
[`docs/aws-deployment.md`](docs/aws-deployment.md).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

There are 18 tests covering the API, job persistence, filename validation,
worker state, local storage, and mocked S3 operations. The same suite runs on
pushes and pull requests through GitHub Actions.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check the API and active storage mode |
| `POST` | `/upload` | Upload a supported document |
| `POST` | `/research` | Start a research job |
| `GET` | `/status/{job_id}` | Check job progress |
| `GET` | `/report/{job_id}` | Get the final report and storage location |
| `GET` | `/jobs` | List saved jobs |

## Current status

The backend, Docker setup, S3 integration, and automated tests are complete.
The AWS deployment steps are prepared in the repository; the EC2 instance can
be started when a live demonstration is needed.
