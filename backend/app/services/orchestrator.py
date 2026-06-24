import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

logger = logging.getLogger("agrigpt.services.orchestrator")

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
        city: Optional[str] = None
    ) -> Dict[str, Any]:
        execution_start = time.time()
        # Default to Hyderabad if no city is provided
        target_city = city if city else "Hyderabad"

        if tools_to_use is None:
            tools_to_use = []
        else:
            tools_to_use = [t for t in tools_to_use if t in self.VALID_TOOLS]

        # Execute parallel APIs
        tasks = []
        for tool_name in tools_to_use:
            if tool_name == "direct_llm":
                continue
            tasks.append(self._execute_tool(tool_name, user_query, target_city))
        
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
            "city": target_city,
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
