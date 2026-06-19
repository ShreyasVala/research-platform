# tools/search_tool.py
# A single async function that searches the web.
# Worker agents call this like any normal Python function.
# Falls back to mock data if no Tavily key is set — so you can
# develop and test offline without using any API credits.

import httpx
from config import get_settings

settings = get_settings()


async def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web. Returns a dict with:
    - 'answer': a short AI-generated summary of results
    - 'results': list of {title, url, excerpt} dicts
    """
    if settings.tavily_api_key.startswith("tvly-"):
        return await _real_search(query, max_results)
    return _mock_search(query, max_results)


async def _real_search(query: str, max_results: int) -> dict:
    # httpx is like the requests library but works with async/await
    # 'async with' opens a connection, uses it, then closes it cleanly
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
        response.raise_for_status()  # crash loudly if API returns an error
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
    """Returns fake data when no Tavily key is configured."""
    return {
        "query": query,
        "answer": "[MOCK] Add your tvly- key to .env for real search results.",
        "results": [
            {
                "title": f"Mock result {i + 1} for: {query}",
                "url": f"https://example.com/{i + 1}",
                "excerpt": f"This is mock content about '{query}'. Result {i + 1}.",
            }
            for i in range(min(max_results, 3))
        ],
    }