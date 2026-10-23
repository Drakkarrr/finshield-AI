"""Shared test setup. APP_ENV must be set before any app module is imported."""
import os

os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402

from app.database import IS_SQLITE, create_test_schema  # noqa: E402

create_test_schema()


def pytest_collection_modifyitems(config, items):
    if not IS_SQLITE:
        return
    skip = pytest.mark.skip(reason="needs TEST_DATABASE_URL=postgresql://...")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


FIXTURES = __import__("pathlib").Path(__file__).with_name("fixtures") / "lists"


def _fixture_entries():
    from app.domain.lists.importers import parse_ofac_sdn, parse_pep_csv

    read = lambda name: (FIXTURES / name).read_text(encoding="utf-8")  # noqa: E731
    sdn, sdn_version = parse_ofac_sdn(read("sdn.csv"), read("alt.csv"), read("add.csv"), source="FIXTURE-OFAC")
    pep, pep_version = parse_pep_csv(read("pep.csv"), source="FIXTURE-PEP")
    return sdn, sdn_version, pep, pep_version


def _seed_reference_data():
    """Load the list fixtures and the legacy high-risk countries into the test database once."""
    from app.database import SessionLocal
    from app.db_models import HighRiskCountry, ListImport
    from app.domain.lists.provider import store_import

    db = SessionLocal()
    try:
        if db.query(ListImport).filter(ListImport.source == "FIXTURE-OFAC").first() is None:
            sdn, sdn_version, pep, pep_version = _fixture_entries()
            store_import(db, sdn, "FIXTURE-OFAC", "sanctions", sdn_version, is_fixture=True)
            store_import(db, pep, "FIXTURE-PEP", "pep", pep_version, is_fixture=True)
        for code in ("KP", "IR", "SY", "CU", "RU"):
            if db.get(HighRiskCountry, code) is None:
                db.add(HighRiskCountry(code=code, source="legacy-config"))
        db.commit()
    finally:
        db.close()


_seed_reference_data()


@pytest.fixture(scope="session")
def fixture_watchlist():
    from app.domain.lists import WatchlistSnapshot

    sdn, sdn_version, pep, pep_version = _fixture_entries()
    return WatchlistSnapshot(entries=sdn + pep, versions={"FIXTURE-OFAC": sdn_version, "FIXTURE-PEP": pep_version})


def system_session():
    """A session that may read across tenants (RLS bypass), for assertions on stored rows."""
    from app.database import SessionLocal

    s = SessionLocal()
    s.info["rls_bypass"] = True
    return s


def effective_routes(app) -> list:
    """Every HTTP route as FastAPI will match it, in matching order.

    FastAPI >= 0.13x keeps included routers as `_IncludedRouter` wrappers, so `app.routes` holds no
    APIRoute at all and a naive walk passes vacuously. Each item exposes .path, .methods,
    .path_regex and the combined .dependencies.
    """
    from fastapi.routing import APIRoute

    out = []

    def walk(routes, resolve):
        for r in routes:
            if isinstance(r, APIRoute):
                out.append(r)
            elif type(r).__name__ == "_IncludedRouter":
                walk(r.effective_candidates(), True)
            elif resolve and type(r).__name__ == "_EffectiveRouteContext":
                out.append(r)

    walk(app.routes, False)
    return out
