import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Configure rate limits using env vars with sensible defaults
RATE_LIMIT_PER_MINUTE = os.getenv("RATE_LIMIT_PER_MINUTE", "30/minute")

# Auto-append /minute if the environment variable is just a raw digit/number
if RATE_LIMIT_PER_MINUTE.isdigit():
    RATE_LIMIT_PER_MINUTE = f"{RATE_LIMIT_PER_MINUTE}/minute"

limiter = Limiter(key_func=get_remote_address)
