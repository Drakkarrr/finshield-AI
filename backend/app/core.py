"""Process-wide singletons shared by the routers: logger, rate limiter, start time."""
import logging
import os
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finshield")

limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("APP_ENV") != "test")

start_time = time.monotonic()
