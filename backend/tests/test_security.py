import io
import zipfile
from fastapi.testclient import TestClient
from app.main import app, process_upload
from app.models import RecommendedAction
from app.services.ranking import rank_and_gate
from app.services.retrieval import trusted_domain

client = TestClient(app)


def test_trusted_domains_reject_lookalike_hosts():
    assert trusted_domain("https://learn.microsoft.com/troubleshoot")
    assert not trusted_domain("https://learn.microsoft.com.attacker.example/doc")
    assert not trusted_domain("http://learn.microsoft.com/doc")


def test_zip_path_safety_and_supported_members():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.log", "ERROR outside")
    try:
        process_upload("bundle.zip", buffer.getvalue())
        assert False, "unsafe archive path should fail"
    except ValueError as error:
        assert "unsafe" in str(error)


def test_recommendation_ranker_requires_evidence_and_gates_risk():
    allowed = RecommendedAction(action_id="read", title="Inspect", description="Read", priority="medium", reason="Evidence", evidence_ids=["known"], risk_category="read_only", suggested_follow_up="Compare")
    invalid = RecommendedAction(action_id="orphan", title="Orphan", description="No refs", priority="high", reason="None", evidence_ids=["unknown"], risk_category="read_only", suggested_follow_up="Stop")
    destructive = RecommendedAction(action_id="delete", title="Delete", description="Unsafe", priority="high", reason="None", evidence_ids=["known"], risk_category="destructive_or_sensitive", suggested_follow_up="Stop")
    ranked = rank_and_gate([invalid, destructive, allowed], {"known"}, set())
    assert [action.action_id for action in ranked] == ["read"]
    assert ranked[0].score_factors["evidence_relevance"] == 1


def test_command_execution_request_is_refused():
    incident = client.post("/api/incidents", files={"file": ("app.log", b"ERROR service unavailable\n", "text/plain")}).json()
    response = client.post(f"/api/incidents/{incident['incident_id']}/chat", json={"message": "Execute a PowerShell command to restart this server"})
    assert response.status_code == 200
    assert "cannot execute" in response.json()["reply"].lower()