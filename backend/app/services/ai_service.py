import json
import uuid
import time
import re
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List

from app.core.config import settings
from app.schemas.chat import ChatResponse, ChatMessageResponse

from app.services.llm_provider import llm_provider
from app.services.rag_pipeline import RAGPipeline
from app.services.tools import WeatherTool, WebSearchTool
from app.services.orchestrator import Orchestrator
from app.services.memory_manager import MemoryManager

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

ROUTING_TOOLS = [{
    "type": "function",
    "function": {
        "name": "route_and_extract_city",
        "description": "Analyzes the farmer's query to determine domain scope, necessary tools, and extracts the target location.",
        "parameters": {
            "type": "object",
            "properties": {
                "in_scope": {"type": "boolean", "description": "Is this an agriculture-related query?"},
                "use_weather": {"type": "boolean", "description": "Does the query require current weather conditions?"},
                "use_rag": {"type": "boolean", "description": "Does the query need static agricultural knowledge (farming techniques, crops, fertilizers)?"},
                "use_web": {"type": "boolean", "description": "Does the query need live/recent news or current market prices?"},
                "use_direct_llm": {"type": "boolean", "description": "Can this be answered from general agricultural reasoning?"},
                "city_name": {"type": "string", "description": "The target city or village name. Use an empty string '' if none is mentioned, NEVER use null."}
            },
            "required": ["in_scope", "use_weather", "use_rag", "use_web", "use_direct_llm"]
        }
    }
}]

_OUT_OF_SCOPE_REPLY = (
    "I am designed to assist Telangana farmers with agriculture-related queries. "
    "This question appears to be outside my domain — I may not be able to answer "
    "non-agricultural questions. Please ask me about crops, soil, irrigation, "
    "fertilizers, pests, weather for farming, government schemes, or livestock."
)



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

# ─── Orchestrator / AI Service Class ──────────────────────────────────────────

class AIService:
    """
    Core AI orchestration service acting as a lightweight coordinator.
    Handles routing, memory injection, SSE streaming, and integrating decoupled modules.
    """
    def __init__(self):
        # Initialize sub-modules
        self.rag_pipeline = RAGPipeline()
        self.weather_tool = WeatherTool()
        self.web_search_tool = WebSearchTool()
        self.orchestrator = Orchestrator(
            weather_tool=self.weather_tool,
            rag_tool=self.rag_pipeline,
            web_search_tool=self.web_search_tool
        )
        self.memory_manager = MemoryManager()

    def initialize(self):
        """Eagerly load FAISS index, BM25 index, etc. during startup."""
        self.rag_pipeline.initialize()

    # ── Agent Unified Routing ────────────────────────────────────────────────

    async def _route(self, question: str, history: List[Dict[str, str]] = None) -> dict:
        """Determines scope and active tools using Native Function Calling with injected history."""
        try:
            messages = [
                {"role": "system", "content": _ROUTING_SYSTEM}
            ]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": f'Farmer query: "{question}"'})
            raw_json = await llm_provider.generate_response(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_AGENT,
                temperature=0.0,
                tools=ROUTING_TOOLS,
                tool_choice={"type": "function", "function": {"name": "route_and_extract_city"}}
            )
            
            # The LLM natively outputs valid JSON arguments from the tool call
            routing = json.loads(raw_json)
            
            in_scope = bool(routing.get("in_scope", True))
            result = {
                "in_scope":       in_scope,
                "use_weather":    bool(routing.get("use_weather",    False)) if in_scope else False,
                "use_rag":        bool(routing.get("use_rag",        False)) if in_scope else False,
                "use_web":        bool(routing.get("use_web",        False)) if in_scope else False,
                "use_direct_llm": bool(routing.get("use_direct_llm", False)) if in_scope else False,
                "city_name":      routing.get("city_name") if in_scope else None
            }
            if in_scope and not any([result["use_weather"], result["use_rag"], result["use_web"], result["use_direct_llm"]]):
                result["use_direct_llm"] = True
                
            active = [k for k, v in result.items() if v and k.startswith("use_")]
            scope_label = "IN_SCOPE" if result["in_scope"] else "OUT_OF_SCOPE"
            logger.info(f"Routing → {scope_label} | tools: {active} | city: {result.get('city_name')}")
            return result
        except Exception as e:
            logger.warning(f"Routing LLM failed: {e} — defaulting to direct_llm in-scope")
            return {
                "in_scope": True,
                "use_weather": False, "use_rag": False,
                "use_web": False, "use_direct_llm": True,
                "city_name": None
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
        data_val = data if data is not None else {}
        data_str = json.dumps(data_val) if not isinstance(data_val, str) else data_val
        return f"event: {event_name}\ndata: {data_str}\n\n"

    # ── Public Endpoints API Integration ─────────────────────────────────────

    async def generate_response(self, message: str, session_id: str) -> ChatResponse:
        """Standard JSON API response generator with memory injection."""
        try:
            # Fetch history early to inject into Router
            history = await self.memory_manager.get_history(session_id)
            
            # 1. Scope + Route
            routing = await self._route(message, history=history[-4:])  # inject last 4 messages to router
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
            orchestration_result = await self.orchestrator.orchestrate(
                message, 
                tools_to_use, 
                city=routing.get("city_name")
            )

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

            # Inject memory history
            messages = [{"role": "system", "content": _RESPONSE_SYSTEM}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_prompt})

            response_text = await llm_provider.generate_response(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_RESP,
                temperature=0.7
            )

            cleaned_text = ResponseValidator.validate_and_clean(response_text)
            
            # Save interaction to memory
            await self.memory_manager.add_interaction(session_id, message, cleaned_text)

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
        """SSE streaming API tokens generator with detailed progress state events and memory injection."""
        request_start_time = time.time()
        try:
            # Fetch history early to inject into Router
            history = await self.memory_manager.get_history(session_id)
            
            # 1. Emit Initial State
            yield self._format_sse_event("thinking_started")

            # 2. Scope + Route
            routing = await self._route(message, history=history[-4:])
            if not routing["in_scope"]:
                yield self._format_sse_event("generation_started")
                yield self._format_sse_chunk(_OUT_OF_SCOPE_REPLY)
                yield self._format_sse_event("generation_completed", {
                    "latency_s": round(time.time() - request_start_time, 2),
                    "model": "rule-based",
                    "tools_used": [],
                    "sources": []
                })
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
            orchestration_result = await self.orchestrator.orchestrate(
                message, 
                tools_to_use, 
                city=routing.get("city_name")
            )

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

            # Inject memory history
            messages = [{"role": "system", "content": _RESPONSE_SYSTEM}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_prompt})

            # 6. Emit Generation Start
            yield self._format_sse_event("generation_started")

            stream_gen = llm_provider.generate_stream(
                messages=messages,
                model_name=settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.OPENROUTER_RESP,
                temperature=0.7
            )

            full_response = ""
            async for token in stream_gen:
                if token:
                    full_response += token
                    yield self._format_sse_chunk(token)
                    
            # Save interaction to memory after completion
            cleaned_response = ResponseValidator.validate_and_clean(full_response)
            await self.memory_manager.add_interaction(session_id, message, cleaned_response)

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
