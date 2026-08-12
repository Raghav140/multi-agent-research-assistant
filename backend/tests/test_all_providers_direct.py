"""Test all providers directly without circuit breaker."""

import sys
import os
import asyncio
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.providers.search.duckduckgo_provider import DuckDuckGoProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.providers.papers.arxiv_provider import ArxivProvider

async def test_all_providers():
    """Test all providers directly without circuit breaker."""

    print("=" * 60)
    print("Testing DuckDuckGo Provider")
    print("=" * 60)

    try:
        ddg_provider = DuckDuckGoProvider(timeout=30)
        ddg_results = await ddg_provider.search(query="What is artificial intelligence?", num_results=5, request_id="test_ddg")
        print(f"DuckDuckGo: {len(ddg_results)} results")
        if ddg_results:
            for i, r in enumerate(ddg_results[:2]):
                print(f"  {i+1}. {r.get('title', 'N/A')[:50]}")
    except Exception as e:
        print(f"DuckDuckGo Error: {type(e).__name__}: {str(e)}")

    print("\n" + "=" * 60)
    print("Testing Wikipedia Provider")
    print("=" * 60)

    try:
        wiki_provider = WikipediaProvider(timeout=30)
        wiki_results = await wiki_provider.search(query="What is artificial intelligence?", num_results=5, request_id="test_wiki")
        print(f"Wikipedia: {len(wiki_results)} results")
        if wiki_results:
            for i, r in enumerate(wiki_results[:2]):
                print(f"  {i+1}. {r.get('title', 'N/A')[:50]}")
    except Exception as e:
        print(f"Wikipedia Error: {type(e).__name__}: {str(e)}")

    print("\n" + "=" * 60)
    print("Testing arXiv Provider")
    print("=" * 60)

    try:
        arxiv_provider = ArxivProvider(timeout=30)
        arxiv_results = await arxiv_provider.search(query="quantum computing", max_results=5, request_id="test_arxiv")
        print(f"arXiv: {len(arxiv_results)} results")
        if arxiv_results:
            for i, r in enumerate(arxiv_results[:2]):
                print(f"  {i+1}. {r.get('title', 'N/A')[:50]}")
    except Exception as e:
        print(f"arXiv Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_all_providers())
