"""Key material derived from one secret, DATA_ENCRYPTION_KEY (S3.2, S3.3, S3.5).

HKDF derives independent subkeys, so one rotation-managed secret (platform secret store, ruling D9)
yields:
  - pseudonym(): keyed HMAC refs for personal data in audit entries. The audit log is append-only,
    so it must never hold raw names; a stable ref still links entries about the same subject.
  - encrypt_json()/decrypt_json(): Fernet column encryption (DSAR exports, webhook secrets).
  - sign()/public_key_pem(): Ed25519 signature on audit exports, verifiable with the public key only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_TEST_KEY = "test-only-data-encryption-key-not-a-secret"


@lru_cache(maxsize=1)
def _master() -> bytes:
    key = os.getenv("DATA_ENCRYPTION_KEY")
    if not key:
        if os.getenv("APP_ENV", "production") == "test":
            key = _TEST_KEY
        else:
            raise RuntimeError("DATA_ENCRYPTION_KEY must be set (generate: python -c \"import secrets; "
                               "print(secrets.token_urlsafe(32))\")")
    if len(key) < 32:
        raise RuntimeError("DATA_ENCRYPTION_KEY must be at least 32 characters")
    return key.encode("utf-8")


def _derive(purpose: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=f"finshield/{purpose}".encode()).derive(_master())


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derive("fernet")))


@lru_cache(maxsize=1)
def _signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_derive("audit-signing"))


def pseudonym(value: str | None) -> str | None:
    """Stable, non-reversible reference for a personal identifier (case/space-insensitive)."""
    if not value:
        return None
    norm = " ".join(value.casefold().split())
    return "ps_" + hmac.new(_derive("pseudonym"), norm.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def encrypt_json(value: Any) -> str:
    return _fernet().encrypt(json.dumps(value, default=str).encode("utf-8")).decode("ascii")


def decrypt_json(token: str) -> Any:
    return json.loads(_fernet().decrypt(token.encode("ascii")))


def sign(payload: bytes) -> str:
    return base64.b64encode(_signing_key().sign(payload)).decode("ascii")


def public_key_pem() -> str:
    return _signing_key().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
