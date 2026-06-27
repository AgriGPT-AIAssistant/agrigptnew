import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import ai_service

async def verify_routing():
    # Initialize RAG pipeline so it doesn't fail
    ai_service.initialize()
    
    test_queries = {
        # In-scope
        "What are the best farming practices for growing wheat?": True,
        "How much fertilizer should I use for cotton in Warangal?": True,
        "What is the pest control management for tomato?": True,
        "Will it rain in Hyderabad tomorrow?": True,
        # Out-of-scope (should be rejected)
        "Give code for merge sort": False,
        "Write a Java class for bubble sort": False,
        "What is Python programming?": False,
        "Explain SQL database indexes": False,
        "Can you write a bubble sort in C++?": False,
        "Who is the current Prime Minister of India?": False,
        "Can you help me build a website with HTML and CSS?": False
    }

    print("\n--- Verifying Routing Decisions ---\n")
    all_passed = True
    for query, expected_in_scope in test_queries.items():
        try:
            route_res = await ai_service._route(query)
            actual_in_scope = route_res["in_scope"]
            passed = (actual_in_scope == expected_in_scope)
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
            print(f"[{status}] Query: '{query}'")
            print(f"       Expected in_scope: {expected_in_scope} | Actual: {actual_in_scope}")
            print(f"       Tools matched: {[k for k, v in route_res.items() if v and k.startswith('use_')]}")
            print(f"       City: {route_res.get('city_name')}\n")
        except Exception as e:
            print(f"[ERROR] Query: '{query}' failed with: {e}\n")
            all_passed = False

    if all_passed:
        print("SUCCESS: All routing verification tests passed!")
    else:
        print("FAILURE: Some routing verification tests failed.")

if __name__ == "__main__":
    asyncio.run(verify_routing())
