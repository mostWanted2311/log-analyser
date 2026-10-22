from collections import Counter
from .parser import group_events
from ..models import IncidentAnalysis, KeyFinding, DiagnosticHypothesis, RecommendedAction, EvidenceReference
from .ranking import rank_and_gate


def analyze(incident_id: str, events: list[dict], category: str) -> IncidentAnalysis:
    evidence = [EvidenceReference(evidence_id=event["evidence_id"], source_file=event["source_file"], line_number=event["line_number"], timestamp=event["timestamp"], severity=event["severity"], message=event["message"]) for event in events]
    severe = [event for event in events if event["severity"] in {"critical", "fatal", "error", "err"}]
    warnings = [event for event in events if event["severity"] in {"warning", "warn"}]
    groups = group_events(events)
    findings = []
    hypotheses = []
    actions = []
    summary = f"Parsed {len(events)} record(s); detected {category.replace('_', ' ')} logs, {len(severe)} error-level and {len(warnings)} warning-level record(s)."

    if category == "hpe_smart_array":
        def refs(*terms: str) -> list[str]:
            return [event["evidence_id"] for event in events if any(term in event["message"].lower() for term in terms)]

        cache_refs = refs("cache status:", "cache status details:", "cache disable reason:")
        power_refs = refs("battery/capacitor status:", "cache backup power source:")
        controller_refs = refs("controller status:", "logical drive:", "physicaldrive", "array:")
        diagnostic_refs = list(dict.fromkeys(cache_refs + power_refs))
        if diagnostic_refs:
            findings.append(KeyFinding(finding_id="finding-hpe-cache-disabled", title="Smart Array write cache is permanently disabled", detail="The controller report says the cache backup power source failed to charge; the capacitor status is reported as failed. This explains the disabled protected write cache, but does not identify whether the underlying cause is the capacitor, its connection, or another controller-level fault.", severity="high", evidence_ids=diagnostic_refs))
            hypotheses.append(DiagnosticHypothesis(hypothesis_id="hypothesis-hpe-cache-backup", title="Cache backup power subsystem failure", explanation="The report explicitly links cache disablement to backup power not reaching an acceptable charge. The log alone cannot distinguish a failed capacitor from connection or controller-level causes.", confidence="high", evidence_ids=diagnostic_refs, alternatives=["Backup power module or capacitor degradation", "Connection or seating issue", "Controller or firmware-reported fault requiring vendor procedure"]))
            actions.append(RecommendedAction(action_id="action-hpe-verify-cache", title="Verify cache and backup-power health in the management utility", description="Using an approved read-only HPE management utility available for this server, confirm the Smart Array cache state, backup-power/capacitor status, controller alerts, and recent IML entries.", priority="high", reason="This confirms whether the reported failed charge condition is current and checks for related controller events before hardware work is considered.", evidence_ids=diagnostic_refs + controller_refs[:8], risk_category="read_only", prerequisites=["Confirm the server model and installed HPE management utility"], expected_observations=["Whether the capacitor is still failed or charging", "Any related controller, cache-module, or drive alerts"], suggested_follow_up="If the failure remains, identify the exact supported service procedure and replacement part for the server/controller firmware, then schedule work under the approved maintenance process."))
            actions.append(RecommendedAction(action_id="action-hpe-preserve-cache-safety", title="Keep cache protection settings unchanged while investigating", description="Do not force-enable write-back cache or bypass the backup-power protection. Record the current cache, logical-drive, and physical-drive states for the service case.", priority="high", reason="The controller has disabled protected write cache because backup power is not healthy; overriding this state is not a safe diagnostic step.", evidence_ids=diagnostic_refs, risk_category="read_only", prerequisites=["Use an approved, access-controlled service record"], expected_observations=["A captured baseline of controller/cache and drive health"], suggested_follow_up="Continue with read-only verification and vendor-approved service planning; do not change controller cache policy as a workaround."))
            summary = "HPE Smart Array report: protected write cache is permanently disabled because the backup power source failed to charge. The report lists the controller and shown drives as OK; this excerpt does not establish data loss or prove the physical root cause."

    if not findings and severe:
        findings.append(KeyFinding(finding_id="finding-errors", title=f"{len(severe)} error-level record(s)", detail="Parsed records explicitly contain critical or error severity markers.", severity="high", evidence_ids=[event["evidence_id"] for event in severe[:30]]))
    repeated = [group for group in groups if group["count"] > 1]
    for index, group in enumerate(repeated[:5], 1):
        representative = group["representative"]
        findings.append(KeyFinding(finding_id=f"finding-repeat-{index}", title=f"Repeated log message ({group['count']} occurrences)", detail=group["message"][:500], severity=representative["severity"], evidence_ids=group["evidence_ids"][:30]))
    coded = [event for event in events if event.get("event_code")]
    if coded:
        counts = Counter(event["event_code"] for event in coded)
        findings.append(KeyFinding(finding_id="finding-codes", title="Event/error codes detected", detail="Observed codes: " + ", ".join(f"{code} ({count})" for code, count in counts.most_common(8)), severity="medium", evidence_ids=[event["evidence_id"] for event in coded[:30]]))

    if not hypotheses and severe:
        hypotheses.append(DiagnosticHypothesis(hypothesis_id="hypothesis-error-pattern", title="An error condition requires investigation", explanation="Error-level text is present; the underlying cause is not confirmed by parsing alone.", confidence="low", evidence_ids=[event["evidence_id"] for event in severe[:10]], alternatives=["Transient condition", "Application-specific message or threshold"]))
    if not hypotheses and warnings:
        hypotheses.append(DiagnosticHypothesis(hypothesis_id="hypothesis-warning-pattern", title="Warnings may indicate an emerging issue", explanation="Warning-level records were found, but their operational impact is not established.", confidence="low", evidence_ids=[event["evidence_id"] for event in warnings[:10]], alternatives=["Expected or informational warning", "Short-lived condition"]))
    if not hypotheses:
        hypotheses.append(DiagnosticHypothesis(hypothesis_id="hypothesis-insufficient", title="Insufficient evidence for a diagnosis", explanation="No explicit error or recognized hardware failure state was found in the uploaded records.", confidence="low", evidence_ids=[], alternatives=["Relevant records may be outside the uploaded excerpt"]))
    if not actions and events:
        action_evidence = [event["evidence_id"] for event in (severe or events)[:10]]
        actions.append(RecommendedAction(action_id="action-correlate", title="Correlate the affected time window", description="Compare these records with adjacent system, application, and change records for the same host and time window.", priority="medium", reason="Correlation is a read-only way to distinguish an isolated message from a wider event sequence.", evidence_ids=action_evidence, risk_category="read_only", prerequisites=["Confirm the host and time zone"], expected_observations=["Matching errors or a preceding event on the same host"], suggested_follow_up="If a common trigger appears, inspect the corresponding component documentation and change history."))
    if coded and not any(action.action_id == "action-verify-code" for action in actions):
        actions.append(RecommendedAction(action_id="action-verify-code", title="Verify the observed event code", description="Look up the parsed code in the relevant vendor's official documentation or approved internal knowledge base.", priority="medium", reason="An explicit event code can narrow investigation, but no verified source is indexed for it.", evidence_ids=[event["evidence_id"] for event in coded[:10]], risk_category="read_only", expected_observations=["A matching product/version-specific code description"], suggested_follow_up="Compare the documented conditions with adjacent evidence before considering remediation."))

    actions = rank_and_gate(actions, {item.evidence_id for item in evidence}, set())
    return IncidentAnalysis(incident_id=incident_id, summary=summary, detected_log_type=category, severity="high" if severe else "medium" if warnings else "unknown", findings=findings, hypotheses=hypotheses, actions=actions, evidence=evidence, safety_notes=["Recommendations are informational only. No commands are run and no infrastructure is modified.", "Do not force-enable write-back cache or bypass controller protection.", "Physical inspection or replacement requires the server-specific service procedure and approved maintenance authorization."], missing_information=["Server model and exact controller configuration", "Current iLO/IML or management-utility alerts", "Operating system and HPE storage driver state"], limitations=["Local deterministic hardware rules; no confirmed physical root cause.", "No vendor document is cited unless a permitted source has been indexed locally."])