"""Process-wide singletons shared by the routers: logger, rate limiter, screening engine."""
import logging
import os
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.compliance_engine import ComplianceEngine

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finshield")

limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("APP_ENV") != "test")

engine = ComplianceEngine()
start_time = time.monotonic()
