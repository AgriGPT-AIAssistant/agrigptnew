import asyncio
import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm_provider import llm_provider

# Updated system routing prompt with city_name explicitly in the JSON schema
UPDATED_ROUTING_SYSTEM = """You are the routing brain for AgriGPT, a domain-constrained agricultural assistant for Telangana farmers.

Your job: analyse the farmer's query and return a structured routing decision.

STEP 1 — SCOPE CHECK
Determine if the query belongs to the agriculture domain.
Agriculture domain includes:
  crops, farming techniques, soil, irrigation, fertilizers, pesticides, seeds,
  pests, plant diseases, livestock, yield, harvest, sowing, farm management,
  government farming schemes, market prices for farm produce, weather for farming,
  agricultural credit/loans, organic farming, horticulture, post-harvest practices.

Out-of-scope means: coding, movies, sports, politics, mathematics, cooking,
travel, general finance, entertainment, or any topic unrelated to farming.

STEP 2 — TOOL SELECTION (only if in_scope is true)
Select tools based ONLY on what the query requires:

  "use_weather"    : true  → query needs current temperature, rain, humidity,
                             weather conditions for field work / spraying / irrigation
  "use_rag"        : true  → query needs trusted static agricultural knowledge —
                             farming techniques, crop diseases, fertilizers, soil,
                             pest control, seeds, harvesting practices
  "use_web"        : true  → query needs LIVE / RECENT information —
                             government scheme announcements, current mandi prices,
                             recent pest outbreak alerts, this season's news
  "use_direct_llm" : true  → query can be answered from general agricultural reasoning
                             without external sources; simple factual questions,
                             general farming concepts, basic crop info

CRITICAL RULES:
- No tool has priority. Select based solely on what the query requires.
- Multiple tools may be true simultaneously for compound queries.
- If out_of_scope, set ALL tool flags to false.
- If in_scope but no tool is clearly needed, set use_direct_llm = true.
- use_web is ONLY for live/recent data — NOT for static agricultural knowledge.
- If use_rag and use_direct_llm both apply, prefer use_rag (more authoritative).
- Respond with ONLY valid JSON. No explanation, no markdown fences.

Response format (strict JSON):
{
  "in_scope": true or false,
  "use_weather": true or false,
  "use_rag": true or false,
  "use_web": true or false,
  "use_direct_llm": true or false,
  "city_name": "the target city/village name if mentioned, otherwise ''",
  "reason": "one concise sentence explaining your routing decision"
}
"""

async def test_query(question: str):
    print(f"\nQuery: {question}")
    messages = [
        {"role": "system", "content": UPDATED_ROUTING_SYSTEM},
        {"role": "user", "content": f'Farmer query: "{question}"'}
    ]
    # We simulate passing response_format to generate_response
    # By updating _get_headers_and_payload dynamically or manually building the call
    try:
        # We temporarily inject response_format by modifying headers & payload parameters if llm_provider supports it.
        # But wait, let's look at if we can call llm_provider's generate_response. Since llm_provider doesn't support response_format argument yet,
        # let's call it without, or patch the call. We know that standard prompt format is enough, but passing JSON mode is even safer.
        # Let's test standard call first.
        raw_response = await llm_provider.generate_response(
            messages=messages,
            model_name="llama-3.1-8b-instant",
            temperature=0.0
        )
        print("Raw Response:", raw_response)
    except Exception as e:
        print("Failed:", e)

async def main():
    await test_query("What are the crop recommendations for cotton in Warangal?")
    await test_query("Give code for merge sort")

if __name__ == "__main__":
    asyncio.run(main())
