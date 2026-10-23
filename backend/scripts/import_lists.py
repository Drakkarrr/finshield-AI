"""Import sanctions / PEP list data (S2.3).

From backend/ (DATABASE_URL set):
  python -m scripts.import_lists ofac --download [--dry-run]          # official OFAC SDN export
  python -m scripts.import_lists ofac --sdn sdn.csv [--alt alt.csv] [--add add.csv] [--dry-run]
  python -m scripts.import_lists pep --csv peps.csv --source MY-PEP-VENDOR [--dry-run] [--fixture]
  python -m scripts.import_lists fixtures [--if-empty]                # bundled FICTIONAL test data

Each import replaces that source's entries atomically and records a list_imports row (source,
version, count, time), which /api/v1/lists/status and /api/health report on.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from app.database import SessionLocal
from app.db_models import ListImport
from app.domain.lists.importers import OFAC_SOURCE, parse_ofac_sdn, parse_pep_csv
from app.domain.lists.provider import store_import

OFAC_BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "lists"


def _download(name: str) -> str:
    req = urllib.request.Request(OFAC_BASE + name, headers={"User-Agent": "FinShield-list-import/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (fixed https URL)
        return r.read().decode("latin-1")


def _read(path: str | None) -> str:
    return Path(path).read_text(encoding="latin-1") if path else ""


def _store(entries, source: str, list_type: str, version: str, dry_run: bool, is_fixture: bool = False) -> None:
    aliases = sum(len(e.aliases) for e in entries)
    print(f"{source}: {len(entries)} entries, {aliases} aliases, version {version}")
    if dry_run:
        print("dry run: nothing written")
        return
    db = SessionLocal()
    try:
        store_import(db, entries, source, list_type, version, is_fixture=is_fixture)
    finally:
        db.close()
    print("imported")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("ofac")
    o.add_argument("--download", action="store_true")
    o.add_argument("--sdn")
    o.add_argument("--alt")
    o.add_argument("--add")
    o.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("pep")
    p.add_argument("--csv", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fixture", action="store_true", help="label as fixture (non-production) data")
    f = sub.add_parser("fixtures")
    f.add_argument("--if-empty", action="store_true", help="only when no list has ever been imported")
    args = ap.parse_args(argv)

    if args.cmd == "ofac":
        if args.download:
            sdn, alt, add = _download("SDN.CSV"), _download("ALT.CSV"), _download("ADD.CSV")
        elif args.sdn:
            sdn, alt, add = _read(args.sdn), _read(args.alt), _read(args.add)
        else:
            ap.error("ofac needs --download or --sdn")
        entries, version = parse_ofac_sdn(sdn, alt, add)
        if not entries:
            print("refusing to import an empty sanctions list", file=sys.stderr)
            return 1
        _store(entries, OFAC_SOURCE, "sanctions", version, args.dry_run)
    elif args.cmd == "pep":
        entries, version = parse_pep_csv(_read(args.csv), source=args.source)
        _store(entries, args.source, "pep", version, args.dry_run, is_fixture=args.fixture)
    else:
        if args.if_empty:
            db = SessionLocal()
            try:
                if db.query(ListImport).first() is not None:
                    print("lists already imported; skipping fixtures")
                    return 0
            finally:
                db.close()
        read = lambda n: (FIXTURES / n).read_text(encoding="utf-8")  # noqa: E731
        sdn, sdn_version = parse_ofac_sdn(read("sdn.csv"), read("alt.csv"), read("add.csv"), source="FIXTURE-OFAC")
        pep, pep_version = parse_pep_csv(read("pep.csv"), source="FIXTURE-PEP")
        _store(sdn, "FIXTURE-OFAC", "sanctions", sdn_version, False, is_fixture=True)
        _store(pep, "FIXTURE-PEP", "pep", pep_version, False, is_fixture=True)
        print("WARNING: fixture entries are fictional test data, not real list data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
