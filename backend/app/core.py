"""Process-wide singletons shared by the routers: logger, rate limiter, start time."""
import hashlib
import logging
import os
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

from app import crypto, observability

observability.configure()
logger = logging.getLogger("finshield")

limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("APP_ENV") != "test")

# Screening is limited per credential, not per IP: integrators send from a few gateway IPs, and one
# tenant must not exhaust another's budget. Unauthenticated routes (login/register) stay per IP, so
# inventing an Authorization header cannot dodge their brute-force limits.
SCREENING_RATE_LIMIT = os.getenv("SCREENING_RATE_LIMIT", "60/minute")


def credential_key(request) -> str:
    cred = request.headers.get("authorization") or request.cookies.get("finshield_session")
    if cred:
        return "cred:" + hashlib.sha256(cred.encode("utf-8")).hexdigest()[:32]
    return get_remote_address(request)


def client_ip_pseudonymised(request) -> str | None:
    """Extract client IP from request and pseudonymise it.

    Uses request.client.host which is set by uvicorn after validating trusted proxies
    (when running with --proxy-headers and FORWARDED_ALLOW_IPS). This prevents IP spoofing
    via X-Forwarded-For headers from untrusted sources.
    """
    ip = request.client.host if request.client else None
    return crypto.pseudonym(ip) if ip else None


start_time = time.monotonic()
