import time
import logging
from typing import List, Optional

logger = logging.getLogger("agrigpt.services.key_manager")

class KeyRotator:
    """Manages API key rotation, round-robin cycling, and auto-disabling on 401."""
    def __init__(self, provider_name: str, keys: List[str]):
        self.provider_name = provider_name
        self.active_keys = [k.strip() for k in keys if k.strip()]
        self.disabled_keys = []
        self._current_index = 0
        if not self.active_keys:
            logger.warning(f"KeyRotator initialized for {provider_name} with NO active keys!")

    def get_key(self) -> Optional[str]:
        if not self.active_keys:
            return None
        key = self.active_keys[self._current_index % len(self.active_keys)]
        self._current_index += 1
        return key

    def disable_key(self, key: str):
        if key in self.active_keys:
            self.active_keys.remove(key)
            self.disabled_keys.append(key)
            logger.error(f"KeyRotator ({self.provider_name}): Disabled an API key due to 401 Unauthorized. Active keys left: {len(self.active_keys)}")

class ProviderHealthTracker:
    """Circuit breaker for API providers to handle rate limits (429) or timeouts."""
    def __init__(self, provider_name: str, max_failures: int = 3, cooldown_seconds: int = 60):
        self.provider_name = provider_name
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._cooldown_until = 0.0

    def is_healthy(self) -> bool:
        if time.time() < self._cooldown_until:
            return False
        return True

    def record_success(self):
        if self._failures > 0:
            logger.info(f"ProviderHealthTracker ({self.provider_name}): Recovered successfully. Circuit CLOSED.")
        self._failures = 0
        self._cooldown_until = 0.0

    def record_failure(self):
        self._failures += 1
        logger.warning(f"ProviderHealthTracker ({self.provider_name}): Recorded failure {self._failures}/{self.max_failures}")
        if self._failures >= self.max_failures:
            self._cooldown_until = time.time() + self.cooldown_seconds
            logger.critical(f"ProviderHealthTracker ({self.provider_name}): Circuit OPEN! Provider disabled for {self.cooldown_seconds}s cooldown.")
