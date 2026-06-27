import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

async def debug_keys():
    keys = settings.OPENROUTER_API_KEYS
    print("Configured OpenRouter API keys count:", len(keys))
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": "Say hello in one word."}],
        "temperature": 0.0
    }
    
    for i, key in enumerate(keys):
        print(f"\n--- Testing Key {i+1}: {key[:12]}... ---")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/agrigpt",
            "X-Title": "AgriGPT"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                print(f"Status Code: {res.status_code}")
                print(f"Response: {res.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_keys())
