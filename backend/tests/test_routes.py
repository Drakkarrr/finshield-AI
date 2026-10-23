"""API-surface guards for refactors (S1.6): nothing lost, renamed or shadowed."""
import json
import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app

SNAPSHOT = Path(__file__).with_name("openapi_snapshot.json")


def test_openapi_matches_snapshot():
    """Paths, methods, request/response schemas and status codes are unchanged.

    If an API change is intentional, regenerate the snapshot in the same commit:
    APP_ENV=test python -c "import json;from app.main import app;json.dump(app.openapi(),
    open('tests/openapi_snapshot.json','w'),indent=1,sort_keys=True)"
    """
    current = json.loads(json.dumps(app.openapi(), sort_keys=True))
    assert current == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_no_route_is_shadowed_by_an_earlier_route():
    """FastAPI matches in registration order: a literal path registered after a
    parameterised one with the same method is unreachable (the S0.5 /export bug)."""
    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    shadowed = []
    for i, route in enumerate(routes):
        concrete = re.sub(r"\{[^}]+\}", "sample-value", route.path)
        for earlier in routes[:i]:
            if earlier.methods & route.methods and earlier.path != route.path and earlier.path_regex.match(concrete):
                shadowed.append(f"{sorted(route.methods)} {route.path} <- {earlier.path}")
    assert shadowed == []
