import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("agrigpt.services.llm_provider")

class LLMProvider:
    """
    Unified async client for Groq and OpenRouter endpoints.
    Handles primary provider selection, failover recovery, standard responses, and async streaming.
    """
    def __init__(self):
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

    def _determine_provider(self, override_provider: Optional[str] = None) -> str:
        prov = override_provider or settings.LLM_PROVIDER
        if prov:
            prov = prov.lower().strip()
            if prov in ("groq", "openrouter"):
                return prov

        # Auto-selection based on API key presence
        if settings.GROQ_API_KEY:
            return "groq"
        elif settings.OPENROUTER_API_KEY:
            return "openrouter"
        
        return "groq"

    def _get_headers_and_payload(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        stream: bool,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None
    ) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "messages": messages,
            "stream": stream,
            "temperature": temperature
        }
        
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        if provider == "groq":
            url = self.groq_url
            api_key = settings.GROQ_API_KEY or ""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # Use requested model_name or fallback to default
            model = model_name or settings.GROQ_MODEL
            payload["model"] = model
            # Groq chat API parameter: max_completion_tokens
            payload["max_completion_tokens"] = 1500

        else: # openrouter
            url = self.openrouter_url
            api_key = settings.OPENROUTER_API_KEY or ""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/agrigpt",
                "X-Title": "AgriGPT"
            }
            # Use requested model_name or mapping
            model = model_name
            if model == "llama-3.1-8b-instant":
                model = "meta-llama/llama-3.2-3b-instruct:free"
            elif model == "llama-3.1-70b-versatile":
                model = "meta-llama/llama-3.3-70b-instruct:free"
            elif not model:
                model = settings.OPENROUTER_RESP
            payload["model"] = model
            payload["max_tokens"] = 1500


        return url, headers, payload

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        provider_override: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None
    ) -> str:
        primary_provider = self._determine_provider(provider_override)
        providers_to_try = [primary_provider]
        
        alt_provider = "openrouter" if primary_provider == "groq" else "groq"
        if alt_provider == "groq" and settings.GROQ_API_KEY:
            providers_to_try.append(alt_provider)
        elif alt_provider == "openrouter" and settings.OPENROUTER_API_KEY:
            providers_to_try.append(alt_provider)

        last_error = None
        for prov in providers_to_try:
            try:
                url, headers, payload = self._get_headers_and_payload(
                    prov, messages, stream=False, model_name=model_name, temperature=temperature,
                    tools=tools, tool_choice=tool_choice
                )
                logger.info(f"Sending standard chat completion to {prov} using model {payload.get('model')}")
                
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        if message.get("tool_calls"):
                            return message["tool_calls"][0]["function"]["arguments"].strip()
                        return message.get("content", "").strip()
                    raise Exception("Empty choices list received")
            except Exception as e:
                logger.warning(f"Failed standard completion on provider '{prov}': {str(e)}")
                last_error = e

        raise last_error or Exception("All configured LLM providers failed to generate a response.")

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        provider_override: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        primary_provider = self._determine_provider(provider_override)
        providers_to_try = [primary_provider]
        
        alt_provider = "openrouter" if primary_provider == "groq" else "groq"
        if alt_provider == "groq" and settings.GROQ_API_KEY:
            providers_to_try.append(alt_provider)
        elif alt_provider == "openrouter" and settings.OPENROUTER_API_KEY:
            providers_to_try.append(alt_provider)

        last_error = None
        stream_started = False

        for prov in providers_to_try:
            if stream_started:
                break
            try:
                url, headers, payload = self._get_headers_and_payload(
                    prov, messages, stream=True, model_name=model_name, temperature=temperature
                )
                logger.info(f"Initiating stream chat completion with {prov} using model {payload.get('model')}")

                async with httpx.AsyncClient(timeout=45.0) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            raise Exception(f"HTTP {response.status_code}: {error_text.decode('utf-8')}")
                        
                        stream_started = True
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    choices = data_json.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except Exception:
                                    continue
            except Exception as e:
                logger.warning(f"Failed streaming completion on provider '{prov}': {str(e)}")
                last_error = e

        if not stream_started:
            raise last_error or Exception("All configured LLM providers failed to initialize stream.")

llm_provider = LLMProvider()
