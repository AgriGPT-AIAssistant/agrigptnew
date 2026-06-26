import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.services.key_manager import KeyRotator, ProviderHealthTracker

logger = logging.getLogger("agrigpt.services.llm_provider")

class LLMProvider:
    """
    Unified async client for Groq and OpenRouter endpoints.
    Handles primary provider selection, failover recovery, robust key rotation, and circuit breakers.
    """
    def __init__(self):
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

        # Initialize API Key Rotators
        self.rotators = {
            "groq": KeyRotator("groq", settings.GROQ_API_KEYS),
            "openrouter": KeyRotator("openrouter", settings.OPENROUTER_API_KEYS)
        }

        # Initialize Circuit Breakers (Health Trackers)
        self.health_trackers = {
            "groq": ProviderHealthTracker("groq", max_failures=3, cooldown_seconds=60),
            "openrouter": ProviderHealthTracker("openrouter", max_failures=3, cooldown_seconds=60)
        }

    def _determine_provider(self, override_provider: Optional[str] = None) -> str:
        prov = override_provider or settings.LLM_PROVIDER
        if prov:
            prov = prov.lower().strip()
            if prov in ("groq", "openrouter"):
                return prov

        # Auto-selection based on active keys
        if self.rotators["groq"].active_keys:
            return "groq"
        elif self.rotators["openrouter"].active_keys:
            return "openrouter"
        
        return "groq"

    def _get_headers_and_payload(
        self,
        provider: str,
        api_key: str,
        messages: List[Dict[str, str]],
        stream: bool,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None
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
        if response_format:
            payload["response_format"] = response_format

        if provider == "groq":
            url = self.groq_url
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            model = model_name or settings.GROQ_MODEL
            payload["model"] = model
            payload["max_completion_tokens"] = 1500

        else: # openrouter
            url = self.openrouter_url
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/agrigpt",
                "X-Title": "AgriGPT"
            }
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
        tool_choice: Optional[Any] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        primary_provider = self._determine_provider(provider_override)
        providers_to_try = [primary_provider]
        
        alt_provider = "openrouter" if primary_provider == "groq" else "groq"
        if self.rotators[alt_provider].active_keys:
            providers_to_try.append(alt_provider)

        last_error = None
        for prov in providers_to_try:
            tracker = self.health_trackers[prov]
            if not tracker.is_healthy():
                logger.warning(f"Skipping {prov} - circuit is open (cooling down).")
                continue

            rotator = self.rotators[prov]
            
            # Key rotation loop
            while True:
                api_key = rotator.get_key()
                if not api_key:
                    logger.error(f"No active API keys left for {prov}.")
                    break

                try:
                    url, headers, payload = self._get_headers_and_payload(
                        prov, api_key, messages, stream=False, model_name=model_name, temperature=temperature,
                        tools=tools, tool_choice=tool_choice, response_format=response_format
                    )
                    logger.info(f"Sending standard chat completion to {prov} using model {payload.get('model')}")
                    
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        response = await client.post(url, headers=headers, json=payload)
                        
                        if response.status_code == 401:
                            rotator.disable_key(api_key)
                            continue # Try next key immediately
                            
                        if response.status_code != 200:
                            if response.status_code == 429:
                                tracker.record_failure()
                                break # Rate limited across the provider/key, break to try alt_provider
                            raise Exception(f"HTTP {response.status_code}: {response.text}")
                        
                        tracker.record_success()
                        data = response.json()
                        choices = data.get("choices", [])
                        if choices:
                            message = choices[0].get("message", {})
                            if message.get("tool_calls"):
                                return message["tool_calls"][0]["function"]["arguments"].strip()
                            return message.get("content", "").strip()
                        raise Exception("Empty choices list received")
                except httpx.TimeoutException as e:
                    logger.warning(f"Timeout on provider '{prov}'")
                    tracker.record_failure()
                    last_error = e
                    break
                except Exception as e:
                    logger.warning(f"Failed standard completion on provider '{prov}': {str(e)}")
                    last_error = e
                    break

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
        if self.rotators[alt_provider].active_keys:
            providers_to_try.append(alt_provider)

        last_error = None
        stream_started = False

        for prov in providers_to_try:
            if stream_started:
                break
                
            tracker = self.health_trackers[prov]
            if not tracker.is_healthy():
                logger.warning(f"Skipping {prov} - circuit is open (cooling down).")
                continue

            rotator = self.rotators[prov]
            
            while True:
                api_key = rotator.get_key()
                if not api_key:
                    break

                try:
                    url, headers, payload = self._get_headers_and_payload(
                        prov, api_key, messages, stream=True, model_name=model_name, temperature=temperature
                    )
                    logger.info(f"Initiating stream chat completion with {prov} using model {payload.get('model')}")

                    async with httpx.AsyncClient(timeout=45.0) as client:
                        async with client.stream("POST", url, headers=headers, json=payload) as response:
                            if response.status_code == 401:
                                rotator.disable_key(api_key)
                                continue
                                
                            if response.status_code != 200:
                                if response.status_code == 429:
                                    tracker.record_failure()
                                    break
                                error_text = await response.aread()
                                raise Exception(f"HTTP {response.status_code}: {error_text.decode('utf-8')}")
                            
                            stream_started = True
                            tracker.record_success()
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
                            break
                except httpx.TimeoutException as e:
                    logger.warning(f"Streaming timeout on provider '{prov}'")
                    tracker.record_failure()
                    last_error = e
                    break
                except Exception as e:
                    logger.warning(f"Failed streaming completion on provider '{prov}': {str(e)}")
                    last_error = e
                    break

        if not stream_started:
            raise last_error or Exception("All configured LLM providers failed to initialize stream.")

llm_provider = LLMProvider()
