"""Simple test to verify DDGS API behavior."""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ddgs import DDGS
import time

def test_ddgs_direct():
    """Test DDGS directly without async wrapper."""
    print("Testing DDGS directly...")

    ddgs = DDGS()
    query = "What is artificial intelligence?"

    print(f"Query: {query}")
    print("Calling ddgs.text()...")

    start = time.time()
    try:
        # Test if ddgs.text returns a generator
        results_gen = ddgs.text(query, max_results=5)
        print(f"Type of results: {type(results_gen)}")

        # Convert to list
        results = list(results_gen)
        duration = time.time() - start

        print(f"Duration: {duration:.2f}s")
        print(f"Raw result count: {len(results)}")

        if results:
            print(f"\nFirst result structure:")
            print(f"Keys: {results[0].keys() if isinstance(results[0], dict) else 'Not a dict'}")
            print(f"First result: {results[0]}")

            # Check for expected fields
            if isinstance(results[0], dict):
                print(f"\nField check:")
                print(f"  'href' in result: {'href' in results[0]}")
                print(f"  'title' in result: {'title' in results[0]}")
                print(f"  'body' in result: {'body' in results[0]}")
        else:
            print("No results returned!")

    except Exception as e:
        duration = time.time() - start
        print(f"Error after {duration:.2f}s: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_ddgs_direct()
