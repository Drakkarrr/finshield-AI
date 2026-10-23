"""S6.4: the Python SDK screens a transaction against the real app and reads back decision + reasons."""
import json
import sys
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk" / "python"))

from finshield import FinShield, FinShieldError, verify_webhook  # noqa: E402

from app.domain import webhooks  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ScreeningStatus  # noqa: E402

SNAPSHOT = Path(__file__).with_name("openapi_snapshot.json")


def _sdk() -> FinShield:
    http = TestClient(app)
    r = http.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@sdk.io", "password": "SecurePass123!",
                                              "first_name": "S", "last_name": "D", "company": "sdk"})
    key = http.post("/api/v1/keys", json={"name": "sdk"},
                    headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()["key"]
    http.cookies.clear()  # an integrator has only the API key
    return FinShield("http://testserver", api_key=key, http_client=http)


def test_sdk_screens_and_reads_back_the_decision_with_reasons():
    with _sdk() as fs:
        d = fs.screen_transaction(amount=48000, currency="USD", transaction_type="wire", sender_name="Sdk Sender",
                                  receiver_name="Sdk Receiver", destination_country="IR", idempotency_key="sdk-1")
        assert d["status"] in {s.value for s in ScreeningStatus} and d["reasons"]
        assert all({"source", "feature"} <= set(r) for r in d["reasons"])
        again = fs.screen_transaction(amount=48000, currency="USD", transaction_type="wire", sender_name="Sdk Sender",
                                      receiver_name="Sdk Receiver", destination_country="IR", idempotency_key="sdk-1")
        assert again["transaction_id"] == d["transaction_id"]  # idempotent retry
        stored = fs.get_transaction(d["transaction_id"])
        assert stored["status"] == d["status"] and stored["risk_score"] == d["risk_score"]
        page, total = fs.list_transactions(limit=10)
        assert total == 1 and page[0]["id"] == d["transaction_id"]


def test_sdk_raises_with_status_detail_and_request_id():
    with _sdk() as fs:
        try:
            fs.get_case("no-such-case")
        except FinShieldError as e:
            assert e.status == 404 and e.request_id
        else:
            raise AssertionError("expected FinShieldError")


def test_sdk_webhook_verifier_matches_the_server_signature():
    body = json.dumps({"event": "case.created"}).encode()
    now = int(time.time())
    header = webhooks.signature("whsec_sdk", now, body)
    assert verify_webhook(body, header, "whsec_sdk")
    assert not verify_webhook(body + b" ", header, "whsec_sdk")
    assert not verify_webhook(body, header, "other-secret")
    assert not verify_webhook(body, header, "whsec_sdk", now=now + 301)  # replay window


def test_every_sdk_path_exists_in_the_api_contract():
    paths = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["paths"]
    called = {("POST", "/api/v1/transactions"), ("GET", "/api/v1/transactions"), ("GET", "/api/v1/transactions/{tx_id}"),
              ("GET", "/api/v1/cases"), ("GET", "/api/v1/cases/{case_id}")}
    assert all(m.lower() in paths.get(p, {}) for m, p in called)
