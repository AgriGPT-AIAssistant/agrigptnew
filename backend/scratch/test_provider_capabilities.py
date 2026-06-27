import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_provider import llm_provider
from app.core.config import settings

async def test_capabilities():
    print("Testing OpenRouter with meta-llama/llama-3.3-70b-instruct:free...")
    messages = [
        {"role": "system", "content": "You are a helper. Output JSON: {\"success\": true}"},
        {"role": "user", "content": "Hello"}
    ]
    
    # Test JSON mode on OpenRouter
    try:
        res = await llm_provider.generate_response(
            messages=messages,
            model_name="meta-llama/llama-3.3-70b-instruct:free",
            temperature=0.0,
            provider_override="openrouter",
            response_format={"type": "json_object"}
        )
        print("OpenRouter JSON mode result:", res)
    except Exception as e:
        print("OpenRouter JSON mode failed:", e)

    # Test Tool calling on OpenRouter
    tools = [{
        "type": "function",
        "function": {
            "name": "test_func",
            "description": "A test function",
            "parameters": {
                "type": "object",
                "properties": {
                    "val": {"type": "string"}
                },
                "required": ["val"]
            }
        }
    }]
    try:
        res = await llm_provider.generate_response(
            messages=messages,
            model_name="meta-llama/llama-3.3-70b-instruct:free",
            temperature=0.0,
            provider_override="openrouter",
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "test_func"}}
        )
        print("OpenRouter Tool call result:", res)
    except Exception as e:
        print("OpenRouter Tool call failed:", e)

if __name__ == "__main__":
    asyncio.run(test_capabilities())
