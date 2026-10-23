"""S3.5: required secrets, no plaintext card data."""
import os
import subprocess
import sys
import uuid
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect

from app.database import engine
from app.main import app

BACKEND = Path(__file__).resolve().parent.parent


def _run(code: str, **env) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET_KEY", "DATA_ENCRYPTION_KEY", "APP_ENV")}
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env={**base, **env},
                          capture_output=True, text=True, timeout=120)


def test_api_refuses_to_start_without_jwt_secret():
    r = _run("import app.auth", APP_ENV="production", DATABASE_URL="postgresql://u:p@localhost:1/x")
    assert r.returncode != 0 and "JWT_SECRET_KEY must be set" in r.stderr


def test_api_refuses_to_start_without_data_encryption_key():
    r = _run("import app.crypto as c; c.public_key_pem()", APP_ENV="production", JWT_SECRET_KEY="x" * 40)
    assert r.returncode != 0 and "DATA_ENCRYPTION_KEY must be set" in r.stderr


def test_no_card_columns_in_the_schema():
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert not {c for c in columns if "card" in c}


async def test_saved_card_endpoints_are_gone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@sec.io",
                                                      "password": "SecurePass123!", "first_name": "S",
                                                      "last_name": "Ec"})
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        assert (await ac.patch("/api/v1/billing/saved-card", json={})).status_code == 501
        assert (await ac.delete("/api/v1/billing/saved-card")).status_code == 501
        me = (await ac.get("/api/auth/me")).json()
    assert not [k for k in me if "card" in k]
