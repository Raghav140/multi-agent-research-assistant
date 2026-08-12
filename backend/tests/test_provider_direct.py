"""Test provider directly without circuit breaker."""

import sys
import os
import asyncio
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.providers.search.duckduckgo_provider import DuckDuckGoProvider

async def test_provider_direct():
    """Test DuckDuckGo provider directly without circuit breaker."""
    print("Testing DuckDuckGo provider directly...")

    provider = DuckDuckGoProvider(timeout=30)
    query = "What is artificial intelligence?"

    print(f"Query: {query}")
    print("Calling provider.search()...")

    try:
        results = await provider.search(query=query, num_results=5, request_id="test_direct")
        print(f"Result count: {len(results)}")

        if results:
            print(f"\nFirst 3 results:")
            for i, r in enumerate(results[:3]):
                print(f"  {i+1}. {r.get('title', 'N/A')[:60]}")
                print(f"     URL: {r.get('url', 'N/A')[:60]}")
                print(f"     Score: {r.get('domain_score', 0)}")
        else:
            print("No results returned!")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_provider_direct())
