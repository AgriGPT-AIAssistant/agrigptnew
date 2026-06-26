import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

async def list_models():
    api_key = settings.OPENROUTER_API_KEYS[1] if len(settings.OPENROUTER_API_KEYS) > 1 else settings.OPENROUTER_API_KEYS[0]
    print(f"Using API Key: {api_key[:10]}...")
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 200:
            models = res.json().get("data", [])
            print("Found", len(models), "models.")
            free_models = [m for m in models if "free" in m.get("id", "")]
            print("\nFree Models:")
            for m in free_models:
                print(f" - {m.get('id')} ({m.get('name')})")
            
            llama_models = [m for m in models if "llama" in m.get("id", "").lower()]
            print("\nLlama Models (first 10):")
            for m in llama_models[:10]:
                print(f" - {m.get('id')} ({m.get('name')})")
        else:
            print("Failed to list models:", res.status_code, res.text)

if __name__ == "__main__":
    asyncio.run(list_models())
