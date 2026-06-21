import os
import re
import json
import uuid
import time
import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import httpx
import numpy as np

from app.core.config import settings
from app.services.llm_provider import llm_provider
from app.schemas.chat import ChatResponse, ChatMessageResponse
from app.retrieval import (
    ArtifactLoader,
    ChildChunk,
    ParentChunk,
    RetrievedChunk
)

logger = logging.getLogger("agrigpt.services.ai_service")

# ─── Prompts & Responses ─────────────────────────────────────────────────────

_RESPONSE_SYSTEM = """You are AgriGPT, a helpful agricultural advisor for Telangana farmers.

STRICT FORMATTING RULES:
You MUST format your response into structured sections using Markdown headings. 
Depending on the query type, use headings like:
# Overview
# Symptoms (for pest/disease/crop health issues)
# Recommendations
# Prevention (for pest/disease/crop health issues)
# Actionable Tip (always end with one warm, actionable farming tip)

Use emojis, bullet points, bold text, and callout blocks (e.g. `> [!NOTE]` or `> [!TIP]`) to make the response look like a premium, highly structured article. Never output a plain block of paragraphs without these section headings.

CONTENT RULES:
1. Use data from the CONTEXT block as the primary source of your answer.
2. If weather data is provided, use it. If not, do NOT mention weather conditions.
3. If no RAG or web context was retrieved (low retrieval), use your own agricultural
   knowledge to answer — but do NOT fabricate specific Telangana policy numbers,
   exact current market prices, or recent government announcements.
4. Answer only what the farmer actually asked. Do not pad with unrequested info.
5. Be specific with data you have: temperatures, humidity, crop advice.
6. End with one actionable farming tip relevant to the question. (Include this under the # Actionable Tip section).
7. Write in a warm, conversational tone. Minimum 2 sentences.
8. If context is sparse, answer with your agricultural knowledge and stop.
   Never say 'I do not have context' — always give a useful agricultural answer.
"""

_ROUTING_SYSTEM = """You are the routing brain for AgriGPT, a domain-constrained agricultural assistant for Telangana farmers.

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
  "reason": "one concise sentence explaining your routing decision"
}
"""

_OUT_OF_SCOPE_REPLY = (
    "I am designed to assist Telangana farmers with agriculture-related queries. "
    "This question appears to be outside my domain — I may not be able to answer "
    "non-agricultural questions. Please ask me about crops, soil, irrigation, "
    "fertilizers, pests, weather for farming, government schemes, or livestock."
)

# ─── Location Extraction ─────────────────────────────────────────────────────

KNOWN_CITIES = [
    "hyderabad", "warangal", "karimnagar", "nizamabad", "khammam",
    "nalgonda", "mahbubnagar", "adilabad", "rangareddy", "medak",
    "siddipet", "mancherial", "jagtial", "rajanna sircilla", "kamareddy",
    "vikarabad", "sangareddy", "yadadri", "suryapet", "bhadradri",
    "nagarkurnool", "wanaparthy", "jogulamba", "narayanpet", "medchal",
    "mulugu", "mahabubabad", "jayashankar", "kumuram bheem", "nirmal",
    "peddapalli", "rajanna", "sircilla", "gadwal", "kollapur",
    "secunderabad", "uppal", "kukatpally", "gachibowli",
    "mumbai", "delhi", "bangalore", "chennai", "kolkata", "pune",
    "ahmedabad", "surat", "jaipur", "lucknow", "kanpur", "nagpur",
    "indore", "bhopal", "patna", "vadodara", "visakhapatnam",
]

def extract_city(query: str) -> Optional[str]:
    """Extract city name from query using keyword matching."""
    if not query:
        return None
    q = query.lower()
    for city in KNOWN_CITIES:
        if city in q:
            return city.title()
    match = re.search(r"\b(?:in|at|for|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", query)
    if match:
        return match.group(1)
    return None

def _parse_routing_response(raw: str) -> dict:
    """Parse the unified routing LLM JSON response."""
    _DEFAULT = {
        "in_scope": True,
        "use_weather": False, "use_rag": False,
        "use_web": False, "use_direct_llm": True,
    }
    if not raw or not raw.strip():
        return _DEFAULT

    text = raw.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        return _DEFAULT
    try:
        parsed = json.loads(text[start:end])
    except Exception:
        return _DEFAULT

    in_scope = bool(parsed.get("in_scope", True))
    result = {
        "in_scope":       in_scope,
        "use_weather":    bool(parsed.get("use_weather",    False)) if in_scope else False,
        "use_rag":        bool(parsed.get("use_rag",        False)) if in_scope else False,
        "use_web":        bool(parsed.get("use_web",        False)) if in_scope else False,
        "use_direct_llm": bool(parsed.get("use_direct_llm", False)) if in_scope else False,
    }
    if in_scope and not any([result["use_weather"], result["use_rag"],
                              result["use_web"], result["use_direct_llm"]]):
        result["use_direct_llm"] = True
    return result

def _rag_has_confidence(knowledge_context: dict) -> bool:
    n_final = knowledge_context.get("n_final", 0)
    if n_final < 1:
        return False
    ctx = knowledge_context.get("context", "")
    if not ctx or "No relevant context found" in ctx:
        return False
    return True

# ─── Response Validator ──────────────────────────────────────────────────────

class ResponseValidator:
    MIN_LENGTH = 50
    MAX_LENGTH = 3000

    HALLUCINATION_PATTERNS = [
        r"as of \d{4}",
        r"according to (?:the )?(?:latest|recent) (?:data|report|update)",
        r"i (?:just )?checked (?:the )?(?:internet|web|online)",
        r"real-?time data",
    ]

    @classmethod
    def validate_and_clean(cls, response: str) -> str:
        if not response or not response.strip():
            return "I was unable to generate a response. Please try again."
        response = response.strip()
        if len(response) < cls.MIN_LENGTH:
            return response
        if len(response) > cls.MAX_LENGTH:
            response = response[:cls.MAX_LENGTH].rstrip() + "…"
        for pattern in cls.HALLUCINATION_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                logger.warning(f"Possible hallucination pattern: {pattern}")
        return response

# ─── Tools Implementations ───────────────────────────────────────────────────

class WeatherTool:
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    def _farming_advice(self, temp: float, humidity: int, desc: str) -> str:
        if temp > 38:
            return "Extreme heat alert — urgent irrigation needed. Avoid midday field work."
        if temp > 32:
            return "Hot conditions — irrigate regularly. Good period for crop drying."
        if "rain" in desc.lower():
            return "Rainy conditions — natural irrigation active. Avoid pesticide spraying."
        if humidity > 80:
            return "High humidity — elevated fungal disease risk. Check drainage."
        if temp < 10:
            return "Cool weather — excellent for transplanting and post-harvest operations."
        return "Normal farming conditions — proceed with regular activities."

    async def get_weather(self, city: str = "Hyderabad") -> Dict[str, Any]:
        api_key = settings.WEATHER_API_KEY
        if not api_key:
            logger.warning("WeatherTool: No weather API key configured. Using default mock weather.")
            return self._mock_weather(city)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"q": f"{city},IN", "appid": api_key, "units": "metric"}
                )
                if resp.status_code == 200:
                    d = resp.json()
                    temp = d["main"]["temp"]
                    hum = d["main"]["humidity"]
                    desc = d["weather"][0]["description"]
                    return {
                        "success": True,
                        "city": d.get("name", city),
                        "temperature": round(temp, 1),
                        "feels_like": round(d["main"]["feels_like"], 1),
                        "humidity": hum,
                        "description": desc,
                        "wind_speed": round(d["wind"]["speed"], 1),
                        "advice": self._farming_advice(temp, hum, desc),
                        "source": "api",
                    }
                else:
                    logger.warning(f"Weather API status code {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"WeatherTool error: {e}")
            
        return self._mock_weather(city)

    def _mock_weather(self, city: str) -> Dict[str, Any]:
        return {
            "success": True,
            "city": city,
            "temperature": 32,
            "feels_like": 30,
            "humidity": 60,
            "description": "partly cloudy",
            "wind_speed": 5.0,
            "advice": "Normal farming conditions — proceed with regular activities.",
            "source": "default",
        }


class WebSearchTool:
    MAX_RESULTS = 7
    TOP_RESULTS = 5
    MAX_CONTENT_CHARS = 500
    TOTAL_BUDGET = 2000

    def _make_search_query(self, query: str) -> str:
        q = query.strip()
        terms = []
        if "telangana" not in q.lower():
            terms.append("Telangana")
        if not any(w in q.lower() for w in ("farm", "agri", "crop", "kisan")):
            terms.append("agriculture")
        if terms:
            q = q + " " + " ".join(terms)
        return q

    def _rerank_results(self, results: List[Dict]) -> List[Dict]:
        scored = []
        for r in results:
            base_score = float(r.get("score", 0.5))
            has_date = bool(r.get("published_date"))
            recency_bonus = 0.05 if has_date else 0.0
            final_score = base_score + recency_bonus
            scored.append((final_score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:self.TOP_RESULTS]]

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        seen_urls, seen_domains, deduped = set(), set(), []
        for r in results:
            url = r.get("url", "")
            domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0]
            if url in seen_urls or domain in seen_domains:
                continue
            seen_urls.add(url)
            seen_domains.add(domain)
            deduped.append(r)
        return deduped

    def _compress_content(self, content: str, max_chars: int) -> str:
        if not content or len(content) <= max_chars:
            return content.strip()
        sentences = re.split(r"(?<=[.!?])\s+", content.strip())
        compressed, used = [], 0
        for s in sentences:
            if used + len(s) + 1 > max_chars:
                break
            compressed.append(s)
            used += len(s) + 1
        return " ".join(compressed) if compressed else content[:max_chars].rstrip() + "…"

    async def search(self, query: str) -> Dict[str, Any]:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            logger.warning("WebSearchTool: No Tavily API key configured. Web search disabled.")
            return {"success": False, "context": "", "sources": [], "n_results": 0}

        search_query = self._make_search_query(query)
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": api_key,
                "query": search_query,
                "max_results": self.MAX_RESULTS,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": False
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_results = data.get("results", [])
                else:
                    logger.warning(f"Tavily search API failed: HTTP {resp.status_code}: {resp.text}")
                    return {"success": False, "context": "", "sources": [], "n_results": 0}
        except Exception as e:
            logger.warning(f"WebSearchTool error: {e}")
            return {"success": False, "context": "", "sources": [], "n_results": 0}

        if not raw_results:
            return {"success": False, "context": "", "sources": [], "n_results": 0}

        reranked = self._rerank_results(raw_results)
        deduped = self._deduplicate(reranked)

        parts, sources, total_chars = [], [], 0
        for i, r in enumerate(deduped, 1):
            title = (r.get("title", "") or "")[:100]
            content = r.get("content", "") or r.get("snippet", "")
            url = r.get("url", "")
            score = round(float(r.get("score", 0.0)), 3)
            date = r.get("published_date", "")

            compressed = self._compress_content(content, self.MAX_CONTENT_CHARS)
            if not compressed:
                continue

            date_str = f"  Date   : {date}\n" if date else ""
            block = (
                f"WEB SOURCE {i}: {title}\n"
                f"  URL    : {url}\n"
                f"  Score  : {score}\n"
                f"{date_str}"
                f"  Content: {compressed}\n"
            )
            if total_chars + len(block) > self.TOTAL_BUDGET:
                break

            parts.append(block)
            sources.append({"title": title, "url": url, "score": score, "date": date})
            total_chars += len(block)

        context = "\n".join(parts) if parts else ""
        return {
            "success": bool(context),
            "context": context,
            "sources": sources,
            "n_results": len(parts),
        }

# ─── Orchestrator Classes ────────────────────────────────────────────────────

@dataclass
class ToolExecutionResult:
    success: bool
    tool: str
    summary: str = ""
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "summary": self.summary,
            "error": self.error
        }


class Orchestrator:
    VALID_TOOLS = ("weather", "rag", "web_search", "direct_llm")

    def __init__(self, weather_tool, rag_tool, web_search_tool):
        self.weather = weather_tool
        self.rag = rag_tool
        self.web_search = web_search_tool

    async def orchestrate(
        self,
        user_query: str,
        tools_to_use: Optional[List[str]] = None,
        default_location: str = "Hyderabad"
    ) -> Dict[str, Any]:
        execution_start = time.time()
        city = extract_city(user_query) or default_location

        if tools_to_use is None:
            tools_to_use = []
        else:
            tools_to_use = [t for t in tools_to_use if t in self.VALID_TOOLS]

        # Execute parallel APIs
        tasks = []
        for tool_name in tools_to_use:
            if tool_name == "direct_llm":
                continue
            tasks.append(self._execute_tool(tool_name, user_query, city))
        
        tool_results = await asyncio.gather(*tasks) if tasks else []

        if "direct_llm" in tools_to_use:
            tool_results.append(ToolExecutionResult(
                success=True,
                tool="direct_llm",
                summary="Using LLM agricultural knowledge directly",
                data={"mode": "direct_llm"}
            ))

        structured_context = self._build_structured_context(tool_results)
        execution_summary = {
            "success_count": sum(1 for r in tool_results if r.success),
            "failure_count": sum(1 for r in tool_results if not r.success),
            "tools_used": [r.tool for r in tool_results if r.success],
            "execution_time_ms": round((time.time() - execution_start) * 1000, 2),
        }
        
        return {
            "is_valid": True,
            "city": city,
            "tools_executed": [r.to_dict() for r in tool_results],
            "context": structured_context,
            "execution_summary": execution_summary,
        }

    async def _execute_tool(self, tool_name: str, user_query: str, city: str) -> ToolExecutionResult:
        try:
            if tool_name == "weather" and self.weather:
                data = await self.weather.get_weather(city)
                return ToolExecutionResult(
                    success=True,
                    tool="weather",
                    summary=f"{data.get('temperature', '?')}°C, {data.get('description', 'Unknown')}",
                    data=data
                )
            elif tool_name == "rag" and self.rag:
                data = self.rag.query(user_query)
                n = data.get("n_final", 0)
                return ToolExecutionResult(
                    success=True,
                    tool="rag",
                    summary=f"Retrieved {n} knowledge chunk(s)" if n else "RAG: no matching chunks",
                    data=data
                )
            elif tool_name == "web_search" and self.web_search:
                data = await self.web_search.search(user_query)
                if data.get("success"):
                    n = data.get("n_results", 0)
                    return ToolExecutionResult(
                        success=True,
                        tool="web_search",
                        summary=f"Tavily web search: {n} result(s)" if n else "No web results found",
                        data=data
                    )
                else:
                    return ToolExecutionResult(success=False, tool="web_search", error="No results or API error")
        except Exception as e:
            logger.warning(f"Tool execution failed: {tool_name}: {e}")
            return ToolExecutionResult(success=False, tool=tool_name, error=str(e))
        return ToolExecutionResult(success=False, tool=tool_name, error="Service not available")

    def _build_structured_context(self, execution_results: List[ToolExecutionResult]) -> Dict[str, Any]:
        structured_context = {}
        for result in execution_results:
            if not result.success or not result.data:
                continue
            if result.tool == "weather":
                structured_context["weather"] = {
                    "city": result.data.get("city", "Unknown"),
                    "temperature": result.data.get("temperature"),
                    "humidity": result.data.get("humidity"),
                    "description": result.data.get("description"),
                    "advice": result.data.get("advice", "")[:200],
                }
            elif result.tool == "rag":
                structured_context["knowledge"] = {
                    "query": result.data.get("query"),
                    "context": result.data.get("context", ""),
                    "sources": result.data.get("sources", []),
                    "n_final": result.data.get("n_final", 0),
                }
            elif result.tool == "web_search":
                structured_context["web"] = {
                    "context": result.data.get("context", ""),
                    "sources": result.data.get("sources", []),
                    "n_results": result.data.get("n_results", 0),
                }
            elif result.tool == "direct_llm":
                structured_context["direct_llm"] = True
        return structured_context

# ─── Orchestrator / AI Service Class ──────────────────────────────────────────

class AIService:
    """
    Core AI orchestration service. Integrates RAG retrieval pipeline with LLM routing
    and tools execution (weather, search), conforming directly to the AgriGPT notebook.
    """
    def __init__(self):
        # Initialize placeholders for eager-loaded components
        self.children = []
        self.parents = {}
        self.bm25_data = None
        self.faiss_index = None
        self.bm25 = None
        self.bm25_children = []
        self._embed_model_instance = None
        self._reranker_model_instance = None

        # Initialize sub-modules
        self.weather_tool = WeatherTool()
        self.web_search_tool = WebSearchTool()
        self.orchestrator = Orchestrator(
            weather_tool=self.weather_tool,
            rag_tool=self,
            web_search_tool=self.web_search_tool
        )

    def initialize(self):
        """Eagerly load FAISS index, BM25 index, embedding model, and reranker model during startup."""
        logger.info("Starting AI Service eager initialization...")
        
        # Resolve artifacts directory path and load DBs
        artifacts_dir = os.path.abspath(settings.RAG_ARTIFACTS_DIR)
        if not os.path.exists(artifacts_dir) or not os.path.exists(os.path.join(artifacts_dir, "children.pkl")):
            # Go up 3 levels from backend/app/services/ai_service.py to reach backend/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            fallback_dir = os.path.join(base_dir, settings.RAG_ARTIFACTS_DIR)
            if os.path.exists(fallback_dir) and os.path.exists(os.path.join(fallback_dir, "children.pkl")):
                artifacts_dir = fallback_dir
        
        logger.info(f"Initializing RAG retrieval pipeline with assets from: {artifacts_dir}")
        
        loader = ArtifactLoader(artifacts_dir)
        
        # Load FAISS index
        self.faiss_index = loader.load_faiss_index()
        logger.info("[STARTUP] FAISS loaded")
        print("[STARTUP] FAISS loaded", flush=True)
        
        # Load index models with fallback protection
        self.children = loader.load_pickle("children.pkl") or []
        self.parents = loader.load_pickle("parents.pkl") or {}
        self.bm25_data = loader.load_pickle("bm25.pkl")
        logger.info("[STARTUP] BM25 loaded")
        print("[STARTUP] BM25 loaded", flush=True)
        
        if isinstance(self.bm25_data, dict):
            self.bm25 = self.bm25_data.get("bm25")
            self.bm25_children = self.bm25_data.get("children", self.children)
        else:
            self.bm25 = self.bm25_data
            self.bm25_children = self.children

        if isinstance(self.parents, list):
            self.parents = {p.id: p for p in self.parents}

        # Initialize embedding model (triggers load if not already loaded)
        _ = self.embed_model
        logger.info("[STARTUP] Embedding model loaded")
        print("[STARTUP] Embedding model loaded", flush=True)

        # Initialize reranker model (triggers load if not already loaded)
        _ = self.reranker_model
        logger.info("[STARTUP] Reranker loaded")
        print("[STARTUP] Reranker loaded", flush=True)

        logger.info("[STARTUP] AI Service initialized")
        print("[STARTUP] AI Service initialized", flush=True)

    # ── Lazy-Load Retrieval Models ───────────────────────────────────────────

    @property
    def embed_model(self):
        if not hasattr(self, "_embed_model_instance") or self._embed_model_instance is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBED_MODEL}")
            self._embed_model_instance = SentenceTransformer(settings.EMBED_MODEL, device="cpu")
        return self._embed_model_instance

    @property
    def reranker_model(self):
        if not hasattr(self, "_reranker_model_instance") or self._reranker_model_instance is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {settings.RERANKER_MODEL}")
            self._reranker_model_instance = CrossEncoder(settings.RERANKER_MODEL, device="cpu")
        return self._reranker_model_instance

    # ── RAG Search Pipeline Implementation ───────────────────────────────────

    def _tokenise(self, text: str) -> List[str]:
        return re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()

    def _normalise_scores(self, results: List[Tuple[Any, float]]) -> List[Tuple[Any, float]]:
        if not results:
            return []
        scores = [s for _, s in results]
        mn, mx = min(scores), max(scores)
        if mx == mn:
            return [(item, 1.0) for item, _ in results]
        return [(item, (s - mn) / (mx - mn)) for item, s in results]

    def _embed_query(self, query: str) -> np.ndarray:
        prefix = "Represent this sentence for searching relevant passages: "
        return self.embed_model.encode(
            [prefix + query],
            normalize_embeddings=True
        ).astype("float32")

    def _dense_search(self, query: str, top_k: int = 10) -> List[Tuple[ChildChunk, float]]:
        if self.faiss_index is None or not self.children:
            return []
        q_emb = self._embed_query(query)
        scores, indices = self.faiss_index.search(q_emb, top_k)
        results = [
            (self.children[idx], float(s))
            for s, idx in zip(scores[0], indices[0])
            if idx != -1 and idx < len(self.children)
        ]
        return sorted(results, key=lambda x: x[1], reverse=True)

    def _sparse_search(self, query: str, top_k: int = 10) -> List[Tuple[ChildChunk, float]]:
        if self.bm25 is None or not self.bm25_children:
            return []
        tokens = self._tokenise(query)
        scores = self.bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [(self.bm25_children[i], float(scores[i])) for i in top_idx if scores[i] > 0]

    def _hybrid_search(
        self,
        query: str,
        faiss_top_k: int = 10,
        bm25_top_k: int = 10,
        alpha: float = 0.5
    ) -> List[Tuple[ChildChunk, float, str]]:
        dense_raw = self._dense_search(query, faiss_top_k)
        sparse_raw = self._sparse_search(query, bm25_top_k)
        dense_norm = self._normalise_scores(dense_raw)
        sparse_norm = self._normalise_scores(sparse_raw)
        
        merged: Dict[str, Tuple[ChildChunk, float, str]] = {}
        for chunk, score in dense_norm:
            merged[chunk.id] = (chunk, alpha * score, "faiss")
        for chunk, score in sparse_norm:
            if chunk.id in merged:
                prev_chunk, prev_score, _ = merged[chunk.id]
                merged[chunk.id] = (prev_chunk, prev_score + (1 - alpha) * score, "hybrid")
            else:
                merged[chunk.id] = (chunk, (1 - alpha) * score, "bm25")
        return sorted(merged.values(), key=lambda x: x[1], reverse=True)

    def _rerank_results(
        self,
        query: str,
        candidates: List[Tuple[ChildChunk, float, str]],
        pool_size: int = 20,
        top_n: int = 5
    ) -> List[RetrievedChunk]:
        pool = candidates[:pool_size]
        if not pool:
            return []
        pairs = [(query, chunk.text) for chunk, _, _ in pool]
        scores = self.reranker_model.predict(pairs).tolist()
        ranked = sorted(zip(pool, scores), key=lambda x: x[1], reverse=True)[:top_n]
        
        results = []
        for (chunk, hybrid_score, method), rr_score in ranked:
            parent = self.parents.get(chunk.parent_id)
            if parent is None:
                continue
            results.append(RetrievedChunk(
                child=chunk, parent=parent,
                score=float(rr_score),
                retrieval_method=method,
                reranker_score=float(rr_score),
                hybrid_score=float(hybrid_score),
            ))
        return results

    def _deduplicate_results(self, results: List[RetrievedChunk], sim_threshold: float = 0.88) -> List[RetrievedChunk]:
        if len(results) <= 1:
            return results
        texts = [rc.child.text for rc in results]
        embs = self.embed_model.encode(texts, normalize_embeddings=True).astype("float32")
        sim_matrix = embs @ embs.T
        kept, kept_indices = [], []
        for i, rc in enumerate(results):
            if not kept_indices:
                kept.append(rc)
                kept_indices.append(i)
                continue
            max_sim = max(float(sim_matrix[i, j]) for j in kept_indices)
            if max_sim < sim_threshold:
                kept.append(rc)
                kept_indices.append(i)
        return kept

    def _build_context(self, results: List[RetrievedChunk], char_budget: int = 6000, use_parent_text: bool = True) -> str:
        if not results:
            return "No relevant context found."
        parts, used_chars, seen_parent_ids = [], 0, set()
        for i, rc in enumerate(results, 1):
            content_text = rc.parent.text if use_parent_text else rc.child.text
            parent_id = rc.parent.id
            if parent_id in seen_parent_ids:
                content_text = rc.child.text
            seen_parent_ids.add(parent_id)
            header = (
                f"SOURCE {i}:\n"
                f"Document : {rc.parent.source}\n"
                f"Section  : {rc.parent.heading}\n"
                f"Pages    : {rc.parent.page_start}–{rc.parent.page_end}\n"
                f"Method   : {rc.retrieval_method}  "
                f"(reranker={rc.reranker_score:.4f}, hybrid={rc.hybrid_score:.4f})\n"
                f"{'-' * 60}\n"
            )
            block = header + content_text
            if used_chars + len(block) > char_budget:
                remaining = char_budget - used_chars - len(header) - 30
                if remaining > 100:
                    parts.append(header + content_text[:remaining] + " [truncated]")
                break
            parts.append(block)
            used_chars += len(block)
        return "\n\n".join(parts)

    def query(self, question: str) -> Dict[str, Any]:
        """Runs the complete RAG query pipeline synchronously (FAISS -> BM25 -> Rerank -> Dedup)."""
        hybrid_candidates = self._hybrid_search(
            question,
            faiss_top_k=settings.RETRIEVAL_TOP_K,
            bm25_top_k=settings.RETRIEVAL_TOP_K
        )
        reranked = self._rerank_results(
            question,
            hybrid_candidates,
            pool_size=settings.RETRIEVAL_TOP_K * 2,
            top_n=settings.RERANK_TOP_K
        )
        deduped = self._deduplicate_results(reranked, sim_threshold=0.88)
        context = self._build_context(deduped, char_budget=6000)

        sources = [
            {
                "document": rc.parent.source,
                "section": rc.parent.heading,
                "pages": f"{rc.parent.page_start}–{rc.parent.page_end}",
                "method": rc.retrieval_method,
                "reranker_score": round(rc.reranker_score, 4),
                "hybrid_score": round(rc.hybrid_score, 4)
            }
            for rc in deduped
        ]
        return {
            "query": question,
            "context": context,
            "sources": sources,
            "n_final": len(deduped)
        }

    # ── Agent Unified Routing ────────────────────────────────────────────────

    async def _route(self, question: str) -> dict:
        """Determines scope and active tools in a single unified LLM call."""
        try:
            messages = [
                {"role": "system", "content": _ROUTING_SYSTEM},
                {"role": "user", "content": f'Farmer query: "{question}"'}
            ]
            raw = await llm_provider.generate_response(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_AGENT,
                temperature=0.0
            )
            routing = _parse_routing_response(raw)
            active = [k for k, v in routing.items() if v and k not in ("in_scope", "reason")]
            scope_label = "IN_SCOPE" if routing["in_scope"] else "OUT_OF_SCOPE"
            logger.info(f"Routing → {scope_label} | tools: {active}")
            return routing
        except Exception as e:
            logger.warning(f"Routing LLM failed: {e} — defaulting to direct_llm in-scope")
            return {
                "in_scope": True,
                "use_weather": False, "use_rag": False,
                "use_web": False, "use_direct_llm": True,
            }

    # ── Context String Aggregator ────────────────────────────────────────────

    def _build_context_string(self, orchestration_result: Dict, rag_fallback: bool = False) -> str:
        lines = []
        context = orchestration_result.get("context", {})
        city = orchestration_result.get("city", "")
        if city:
            lines.append(f"Location: {city}\n")

        if "weather" in context:
            w = context["weather"]
            lines.append("WEATHER:")
            lines.append(f"  Location   : {w.get('city')}")
            lines.append(f"  Temperature: {w.get('temperature')}°C")
            lines.append(f"  Humidity   : {w.get('humidity')}%")
            lines.append(f"  Conditions : {w.get('description')}")
            if w.get("advice"):
                lines.append(f"  Advice     : {w.get('advice')}")
            lines.append("")

        if "knowledge" in context:
            kn = context["knowledge"]
            if _rag_has_confidence(kn):
                lines.append("KNOWLEDGE BASE (RAG):")
                lines.append(kn["context"])
                sources = kn.get("sources", [])
                if sources:
                    lines.append(f"\n[Retrieved {kn.get('n_final', len(sources))} source(s)]")
                lines.append("")
            else:
                lines.append(
                    "NOTE: RAG retrieval found no closely matching documents. "
                    "Answer using your agricultural knowledge, but avoid fabricating "
                    "specific Telangana government policy numbers or current market prices.\n"
                )

        if "web" in context:
            wb = context["web"]
            if wb.get("context"):
                lines.append("WEB SEARCH RESULTS — Tavily (live/recent data):")
                lines.append(wb["context"])
                web_sources = wb.get("sources", [])
                if web_sources:
                    lines.append(f"\n[{wb.get('n_results', len(web_sources))} web source(s) — reranked & deduplicated]")
                lines.append("")

        if context.get("direct_llm"):
            lines.append(
                "NOTE: Answer this using your agricultural knowledge directly. "
                "Be accurate and helpful.\n"
            )

        summary = orchestration_result.get("execution_summary", {})
        lines.append("EXECUTION SUMMARY:")
        lines.append(f"  Tools used : {', '.join(summary.get('tools_used', []))}")
        lines.append(f"  Latency    : {summary.get('execution_time_ms', '?')} ms")

        return "\n".join(lines)

    # ── Formatting for SSE Streams ──────────────────────────────────────────

    def _format_sse_chunk(self, text: str) -> str:
        """Trim-safe SSE formatting logic to protect layout from aggressively being stripped."""
        if not text:
            return ""
            
        body = text.replace("\n", "\r")
        if all(c == " " for c in body) and body:
            body = "&nbsp;" * len(body)
        else:
            l_spaces = len(body) - len(body.lstrip(' '))
            r_spaces = len(body) - len(body.rstrip(' '))
            
            if l_spaces > 0:
                body = "&nbsp;" * l_spaces + body[l_spaces:]
            if r_spaces > 0:
                body = body[:-r_spaces] + "&nbsp;" * r_spaces
                
            if body.startswith('\r'):
                body = "&nbsp;" + body
            if body.endswith('\r'):
                body = body + "&nbsp;"
                
        return f"data: {body}\n\n"

    def _format_sse_event(self, event_name: str, data: Any = None) -> str:
        """Helper to format SSE event lines with event: and data: prefixes."""
        import json
        data_val = data if data is not None else {}
        data_str = json.dumps(data_val) if not isinstance(data_val, str) else data_val
        return f"event: {event_name}\ndata: {data_str}\n\n"

    # ── Public Endpoints API Integration ─────────────────────────────────────

    async def generate_response(self, message: str, session_id: str) -> ChatResponse:
        """Standard JSON API response generator."""
        try:
            # 1. Scope + Route
            routing = await self._route(message)
            if not routing["in_scope"]:
                cleaned_text = ResponseValidator.validate_and_clean(_OUT_OF_SCOPE_REPLY)
                return ChatResponse(
                    session_id=session_id,
                    message=ChatMessageResponse(
                        id=f"msg_{uuid.uuid4().hex[:12]}",
                        role="assistant",
                        content=cleaned_text,
                        created_at=datetime.utcnow()
                    )
                )

            # 2. Extract tools
            tools_to_use = []
            if routing["use_weather"]:    tools_to_use.append("weather")
            if routing["use_rag"]:        tools_to_use.append("rag")
            if routing["use_web"]:        tools_to_use.append("web_search")
            if routing["use_direct_llm"]: tools_to_use.append("direct_llm")

            # 3. Parallel Execution
            orchestration_result = await self.orchestrator.orchestrate(message, tools_to_use)

            # 4. Fallbacks & Context assembly
            context_obj = orchestration_result.get("context", {})
            rag_fallback = (
                "rag" in tools_to_use 
                and not _rag_has_confidence(context_obj.get("knowledge", {}))
            )

            context_string = self._build_context_string(orchestration_result, rag_fallback=rag_fallback)

            active_tools = orchestration_result.get("execution_summary", {}).get("tools_used", [])
            inactive_note = ""
            if "weather" not in active_tools:
                inactive_note += "NOTE: No weather data was fetched — do not mention weather.\n"
            if "web_search" not in active_tools:
                inactive_note += "NOTE: No web search was done — do not cite recent news or prices.\n"

            user_prompt = (
                f"TOOLS ACTIVATED: {active_tools}\n"
                f"{inactive_note}\n"
                f"CONTEXT:\n{context_string}\n\n"
                f"FARMER'S QUESTION: {message}\n\n"
                f"INSTRUCTIONS:\n"
                f"Format your response into structured sections with Markdown headings (# Overview, # Symptoms, # Recommendations, # Prevention, # Actionable Tip). Always start with '# Overview'. Use emojis and bullet points. Never output plain paragraphs without these section headings.\n\n"
                f"ANSWER (use context above; fall back to agricultural knowledge if RAG is sparse):"
            )

            messages = [
                {"role": "system", "content": _RESPONSE_SYSTEM},
                {"role": "user", "content": user_prompt}
            ]

            response_text = await llm_provider.generate_response(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_RESP,
                temperature=0.7
            )

            cleaned_text = ResponseValidator.validate_and_clean(response_text)

            return ChatResponse(
                session_id=session_id,
                message=ChatMessageResponse(
                    id=f"msg_{uuid.uuid4().hex[:12]}",
                    role="assistant",
                    content=cleaned_text,
                    created_at=datetime.utcnow()
                )
            )

        except Exception as e:
            logger.error(f"Failure in response generation: {str(e)}", exc_info=True)
            raise e

    async def generate_stream(self, message: str, session_id: str) -> AsyncGenerator[str, None]:
        """SSE streaming API tokens generator with detailed progress state events."""
        request_start_time = time.time()
        try:
            # 1. Emit Initial State
            yield self._format_sse_event("thinking_started")

            # 2. Scope + Route
            routing = await self._route(message)
            if not routing["in_scope"]:
                yield self._format_sse_chunk(_OUT_OF_SCOPE_REPLY)
                yield "data: [DONE]\n\n"
                return

            # Emit specific tool starts based on routing decision
            if routing["use_weather"]:
                yield self._format_sse_event("weather_started")
            if routing["use_rag"]:
                yield self._format_sse_event("retrieval_started")
                yield self._format_sse_event("reranking_started")
            if routing["use_web"]:
                yield self._format_sse_event("web_search_started")

            # 3. Extract tools
            tools_to_use = []
            if routing["use_weather"]:    tools_to_use.append("weather")
            if routing["use_rag"]:        tools_to_use.append("rag")
            if routing["use_web"]:        tools_to_use.append("web_search")
            if routing["use_direct_llm"]: tools_to_use.append("direct_llm")

            # 4. Parallel Execution
            orchestration_result = await self.orchestrator.orchestrate(message, tools_to_use)

            # 5. Fallbacks & Context assembly
            context_obj = orchestration_result.get("context", {})
            rag_fallback = (
                "rag" in tools_to_use 
                and not _rag_has_confidence(context_obj.get("knowledge", {}))
            )

            context_string = self._build_context_string(orchestration_result, rag_fallback=rag_fallback)

            active_tools = orchestration_result.get("execution_summary", {}).get("tools_used", [])
            inactive_note = ""
            if "weather" not in active_tools:
                inactive_note += "NOTE: No weather data was fetched — do not mention weather.\n"
            if "web_search" not in active_tools:
                inactive_note += "NOTE: No web search was done — do not cite recent news or prices.\n"

            user_prompt = (
                f"TOOLS ACTIVATED: {active_tools}\n"
                f"{inactive_note}\n"
                f"CONTEXT:\n{context_string}\n\n"
                f"FARMER'S QUESTION: {message}\n\n"
                f"INSTRUCTIONS:\n"
                f"Format your response into structured sections with Markdown headings (# Overview, # Symptoms, # Recommendations, # Prevention, # Actionable Tip). Always start with '# Overview'. Use emojis and bullet points. Never output plain paragraphs without these section headings.\n\n"
                f"ANSWER (use context above; fall back to agricultural knowledge if RAG is sparse):"
            )

            messages = [
                {"role": "system", "content": _RESPONSE_SYSTEM},
                {"role": "user", "content": user_prompt}
            ]

            # 6. Emit Generation Start
            yield self._format_sse_event("generation_started")

            stream_gen = llm_provider.generate_stream(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_RESP,
                temperature=0.7
            )

            async for token in stream_gen:
                if token:
                    yield self._format_sse_chunk(token)

            # 7. Collect metadata & sources, and emit completion details
            latency_s = round(time.time() - request_start_time, 2)
            sources = []
            if "knowledge" in context_obj:
                for src in context_obj["knowledge"].get("sources", []):
                    sources.append({
                        "document": src.get("document"),
                        "section": src.get("section"),
                        "pages": src.get("pages"),
                        "method": src.get("method"),
                        "score": src.get("reranker_score")
                    })
            if "web" in context_obj:
                for src in context_obj["web"].get("sources", []):
                    sources.append({
                        "title": src.get("title"),
                        "url": src.get("url"),
                        "score": src.get("score"),
                        "date": src.get("date")
                    })

            completed_data = {
                "model": settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_RESP,
                "latency_s": latency_s,
                "tools_used": active_tools,
                "sources": sources
            }
            yield self._format_sse_event("generation_completed", completed_data)

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Failure in streaming response generation: {str(e)}", exc_info=True)
            error_msg = f"**System Error**: An internal issue occurred while streaming agricultural advice ({str(e)})."
            yield self._format_sse_chunk(error_msg)
            yield "data: [DONE]\n\n"



ai_service = AIService()
