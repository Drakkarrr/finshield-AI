"""Process-wide singletons shared by the routers: logger, rate limiter, screening engine."""
import os
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.compliance_engine import ComplianceEngine
from app.observability import logger

limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("APP_ENV") != "test")

engine = ComplianceEngine()
start_time = time.monotonic()
