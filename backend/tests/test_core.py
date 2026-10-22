from fastapi.testclient import TestClient
from app.main import app, process_upload
from app.services.parser import parse_text, group_events
from app.services.security import redact_secrets

client = TestClient(app)


def test_health_reports_honest_providers():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ai_provider"] in {"local_api_ready", "local_model_not_loaded", "local_api_offline", "local_config_invalid", "deterministic"}


def test_parse_and_analysis_links_evidence():
    response = client.post("/api/incidents", files={"file": ("server.log", b"2026-01-01T10:00:00Z ERROR Event ID: 42 disk alert\n", "text/plain")})
    assert response.status_code == 200
    result = response.json()
    assert result["detected_log_type"] == "windows_server_or_event"
    assert result["findings"][0]["evidence_ids"][0] == result["evidence"][0]["evidence_id"]
    assert result["actions"][0]["risk_category"] == "read_only"


def test_rejects_unsupported_and_malformed_files():
    unsupported = client.post("/api/incidents", files={"file": ("events.evtx", b"binary", "application/octet-stream")})
    malformed = client.post("/api/incidents", files={"file": ("events.json", b"{broken", "application/json")})
    assert unsupported.status_code == 415
    assert malformed.status_code == 400


def test_csv_and_empty_validation():
    assert parse_text("events.csv", b"time,message\nnow,ERROR broken\n")[0][0]["severity"] == "error"
    try:
        parse_text("empty.txt", b"  \n")
        assert False
    except ValueError as exc:
        assert "empty" in str(exc)


def test_duplicate_grouping_and_redaction():
    events, _ = parse_text("app.log", b"ERROR password=secret123 failed\nERROR password=secret123 failed\n")
    groups = group_events(events)
    assert groups[0]["count"] == 2
    assert "secret123" not in events[0]["message"]
    assert "[REDACTED]" in redact_secrets("token=abc123")


def test_chat_continuity_and_action_outcome():
    created = client.post("/api/incidents", files={"file": ("app.log", b"ERROR service unavailable\n", "text/plain")}).json()
    incident_id = created["incident_id"]
    chat = client.post(f"/api/incidents/{incident_id}/chat", json={"message": "What does this mean?"})
    assert chat.status_code == 200 and len(chat.json()["history"]) == 2
    action_id = created["actions"][0]["action_id"]
    outcome = client.post(f"/api/incidents/{incident_id}/actions/{action_id}/outcome", json={"performed": False, "outcome": "inconclusive"})
    assert outcome.status_code == 200
    assert outcome.json()["outcome"] == "inconclusive"