import re
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.services.key_manager import KeyRotator, ProviderHealthTracker

logger = logging.getLogger("agrigpt.services.tools")

class WeatherTool:
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

    def __init__(self):
        self.rotator = KeyRotator("openweathermap", settings.WEATHER_API_KEYS)
        self.health_tracker = ProviderHealthTracker("openweathermap", max_failures=3, cooldown_seconds=60)

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
        if not self.health_tracker.is_healthy():
            logger.warning("WeatherTool: Circuit is open (cooldown). Using mock weather.")
            return self._mock_weather(city)

        while True:
            api_key = self.rotator.get_key()
            if not api_key:
                logger.warning("WeatherTool: No active API keys left. Using mock weather.")
                return self._mock_weather(city)

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        self.BASE_URL,
                        params={"q": f"{city},IN", "appid": api_key, "units": "metric"}
                    )
                    
                    if resp.status_code == 401:
                        self.rotator.disable_key(api_key)
                        continue # Try next key immediately

                    if resp.status_code == 200:
                        self.health_tracker.record_success()
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
                        if resp.status_code == 429:
                            self.health_tracker.record_failure()
                        break
            except httpx.TimeoutException:
                logger.warning("WeatherTool: Connection timeout.")
                self.health_tracker.record_failure()
                break
            except Exception as e:
                logger.warning(f"WeatherTool error: {e}")
                break
                
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

    def __init__(self):
        self.rotator = KeyRotator("tavily", settings.TAVILY_API_KEYS)
        self.health_tracker = ProviderHealthTracker("tavily", max_failures=3, cooldown_seconds=60)

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
        if not self.health_tracker.is_healthy():
            logger.warning("WebSearchTool: Circuit is open (cooldown). Web search temporarily disabled.")
            return {"success": False, "context": "", "sources": [], "n_results": 0}

        search_query = self._make_search_query(query)
        raw_results = []
        
        while True:
            api_key = self.rotator.get_key()
            if not api_key:
                logger.warning("WebSearchTool: No active Tavily API keys left.")
                return {"success": False, "context": "", "sources": [], "n_results": 0}

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
                    
                    if resp.status_code == 401:
                        self.rotator.disable_key(api_key)
                        continue
                        
                    if resp.status_code == 200:
                        self.health_tracker.record_success()
                        data = resp.json()
                        raw_results = data.get("results", [])
                        break
                    else:
                        logger.warning(f"Tavily search API failed: HTTP {resp.status_code}: {resp.text}")
                        if resp.status_code == 429:
                            self.health_tracker.record_failure()
                        break
            except httpx.TimeoutException:
                logger.warning("WebSearchTool: Connection timeout.")
                self.health_tracker.record_failure()
                break
            except Exception as e:
                logger.warning(f"WebSearchTool error: {e}")
                break

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
