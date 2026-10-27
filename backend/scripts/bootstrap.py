"""Idempotent first-run setup, run by the container entrypoint after `alembic upgrade head`.

  python -m scripts.bootstrap            # seed RAG if empty, re-embed on model change, lists if none
  python -m scripts.bootstrap --reembed  # force re-embedding of every RAG row

Lists (only when no list has ever been imported):
  LISTS_AUTO_DOWNLOAD=true   import the official OFAC SDN export
  LISTS_DEMO_FIXTURES=true   load the bundled FICTIONAL PEP fixture (and the fictional OFAC fixture
                             if the download is disabled or fails). For demos only: production
                             needs a licensed PEP source (python -m scripts.import_lists pep ...).
Never fails the container start: each step logs and continues, and /api/health reports what is
missing (a missing sanctions list keeps decisions in review, never approved).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from app.database import SessionLocal
from app.db_models import ListImport
from scripts import import_lists

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] bootstrap: %(message)s")
log = logging.getLogger("bootstrap")


def _flag(name: str) -> bool:
    # LISTS_DEMO_FIXTURES defaults to false unless APP_ENV=development (S7.5)
    if name == "LISTS_DEMO_FIXTURES":
        app_env = os.getenv("APP_ENV", "production").lower()  # unset = production: fail safe
        default = "true" if app_env == "development" else "false"
        return os.getenv(name, default).lower() == "true"
    return os.getenv(name, "false").lower() == "true"


def rag(force_reembed: bool) -> None:
    url = os.getenv("RAG_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        log.info("RAG disabled (no RAG_DATABASE_URL); skipping corpus setup")
        return
    from app.domain.rag.embedders import load_embedder
    from app.domain.rag.seed import seed_rag_data
    from app.domain.rag.service import RAGRetrievalService

    service = RAGRetrievalService(url, load_embedder())
    stored = {m for models in service.model_status().values() for m in models}
    if force_reembed or (stored and stored != {service.embedder.name}):
        log.warning("re-embedding RAG corpora with %s (stored: %s)", service.embedder.name, sorted(stored))
        log.info("re-embedded: %s", service.reembed())
    added = seed_rag_data(service)
    log.info("RAG corpus ready (embedder %s, added %s)", service.embedder.name, added)


def lists() -> None:
    db = SessionLocal()
    try:
        if db.query(ListImport).first() is not None:
            log.info("list data present; skipping import (refresh: python -m scripts.import_lists)")
            return
    finally:
        db.close()
    downloaded = False
    if _flag("LISTS_AUTO_DOWNLOAD"):
        try:
            downloaded = import_lists.main(["ofac", "--download"]) == 0
        except Exception as e:
            log.error("OFAC download failed (%s); sanctions screening stays degraded until a list is imported", e)
    if _flag("LISTS_DEMO_FIXTURES"):
        import_lists.main(["fixtures", "--pep-only"] if downloaded else ["fixtures"])
        log.warning("loaded FICTIONAL fixture list data (%s): production needs a licensed PEP source",
                    "PEP only" if downloaded else "OFAC + PEP")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reembed", action="store_true")
    args = ap.parse_args(argv)
    for step in (lambda: rag(args.reembed), lists):
        try:
            step()
        except Exception:
            log.exception("bootstrap step failed; continuing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
