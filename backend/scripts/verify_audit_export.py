"""Independently verify a FinShield audit export (S3.2). Standalone: imports no FinShield code.

  python scripts/verify_audit_export.py export.json [--public-key trusted.pem]

Checks (1) the hash chain from genesis, entry by entry, and (2) the Ed25519 signature over the
bundle. Pass --public-key with a copy obtained out of band (GET /api/v1/audit/public-key): the key
embedded in the bundle only proves the bundle is self-consistent, not who produced it.
Exit 0 only when both checks pass.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key

GENESIS = "0" * 64
CONTENT = ("id", "tenant_id", "seq", "user_id", "action", "resource_type", "resource_id", "details",
           "ip_address", "created_at")


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False).encode("utf-8")


def check_chain(entries: list[dict]) -> tuple[bool, str]:
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        digest = hashlib.sha256(prev.encode("ascii") + canonical({k: e.get(k) for k in CONTENT})).hexdigest()
        if e.get("seq") != i or e.get("prev_hash") != prev or e.get("entry_hash") != digest:
            return False, f"chain broken at seq {e.get('seq')} (entry {e.get('id')})"
        prev = digest
    return True, f"{len(entries)} entries chain from genesis to {prev}"


def check_signature(bundle: dict, pem: str) -> tuple[bool, str]:
    body = {k: v for k, v in bundle.items() if k != "signature"}
    try:
        load_pem_public_key(pem.encode("ascii")).verify(base64.b64decode(bundle["signature"]), canonical(body))
    except (InvalidSignature, KeyError, ValueError) as e:
        return False, f"signature invalid ({type(e).__name__})"
    return True, "signature valid"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export")
    ap.add_argument("--public-key", help="trusted PEM file (recommended)")
    args = ap.parse_args(argv)
    with open(args.export, encoding="utf-8") as f:
        bundle = json.load(f)
    pem = open(args.public_key, encoding="ascii").read() if args.public_key else bundle["public_key"]
    chain_ok, chain_msg = check_chain(bundle["entries"])
    sig_ok, sig_msg = check_signature(bundle, pem)
    print(f"chain:     {'OK  ' if chain_ok else 'FAIL'} {chain_msg}")
    print(f"signature: {'OK  ' if sig_ok else 'FAIL'} {sig_msg}{'' if args.public_key else ' (embedded key)'}")
    return 0 if chain_ok and sig_ok else 1


if __name__ == "__main__":
    sys.exit(main())
