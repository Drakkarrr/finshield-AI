"""Process-wide singletons shared by the routers: logger, rate limiter, start time."""
import logging
import os
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

from app import observability

observability.configure()
logger = logging.getLogger("finshield")

limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("APP_ENV") != "test")

start_time = time.monotonic()
