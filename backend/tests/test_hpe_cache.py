import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.parser import parse_text

client = TestClient(app)
SAMPLE = b"""Smart Array P420i in Slot 0\nController Status: OK\nCache Status: Permanently Disabled\nCache Status Details: Cache disabled; backup power source failed to charge to an acceptable level\nCache Disable Reason: Backup power source attached to flash-backed write cache has failed to charge\nBattery/Capacitor Status: Failed (Replace Batteries)\nLogical Drive: 1\nStatus: OK\nphysicaldrive 1I:1:1\nStatus: OK\n"""


def test_smart_array_cache_failure_produces_specific_evidence_linked_steps():
    response = client.post("/api/incidents", files={"file": ("controller.txt", SAMPLE, "text/plain")})
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["detected_log_type"] == "hpe_smart_array"
    finding = next(item for item in analysis["findings"] if item["finding_id"] == "finding-hpe-cache-disabled")
    messages = {item["evidence_id"]: item["message"] for item in analysis["evidence"]}
    assert any("Cache Status Details" in messages[reference] for reference in finding["evidence_ids"])
    assert any("Battery/Capacitor Status" in messages[reference] for reference in finding["evidence_ids"])
    assert any("management utility" in action["title"].lower() for action in analysis["actions"])
    assert all(action["risk_category"] == "read_only" for action in analysis["actions"])
    assert "does not establish data loss" in analysis["summary"]


def test_hardware_failure_state_is_detected_without_error_keyword():
    events, category = parse_text("controller.txt", b"Cache Status Details: backup power source failed to charge\n")
    assert category == "hpe_smart_array"
    assert events[0]["severity"] == "error"


def test_local_model_url_rejects_remote_host(monkeypatch):
    from app.services.ai import _local_base_url
    monkeypatch.setenv("LOCAL_MODEL_BASE_URL", "https://remote.example.com/v1")
    with pytest.raises(ValueError, match="localhost"):
        _local_base_url()


def test_lm_studio_chat_uses_local_endpoint_and_schema(monkeypatch):
    from app.services import ai

    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"hypotheses\": []}"}}]}

    def fake_post(url, json, timeout, trust_env):
        captured.update(url=url, payload=json, timeout=timeout, trust_env=trust_env)
        return Response()

    monkeypatch.setenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:1235/v1")
    monkeypatch.setenv("LOCAL_MODEL_NAME", "ministral-3-8b-instruct-2512")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    result = ai._chat([{"role": "user", "content": "test"}], json_mode=True)

    assert result == "{\"hypotheses\": []}"
    assert captured["url"] == "http://127.0.0.1:1235/v1/chat/completions"
    assert captured["payload"]["model"] == "ministral-3-8b-instruct-2512"
    assert captured["payload"]["response_format"]["type"] == "json_schema"
    assert captured["trust_env"] is False