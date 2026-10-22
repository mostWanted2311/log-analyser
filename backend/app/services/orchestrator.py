from .ai import enrich_analysis
from .retrieval import search_sources
from ..models import IncidentAnalysis
from .ranking import rank_and_gate


def complete_analysis(analysis: IncidentAnalysis, events: list[dict]) -> IncidentAnalysis:
    enrich_analysis(analysis, events)
    codes = [event["event_code"] for event in events if event.get("event_code")]
    query = " ".join([analysis.detected_log_type, *codes, *[finding.title for finding in analysis.findings]])[:1500]
    sources = search_sources(query)
    analysis.sources = sources
    if sources:
        supported_evidence = [event["evidence_id"] for event in events if event.get("event_code")]
        for source in sources:
            source.supports = supported_evidence
        coded_action = next((action for action in analysis.actions if action.action_id == "action-verify-code"), None)
        if coded_action:
            coded_action.source_ids = [source.source_id for source in sources]
            coded_action.reason = "An observed event code can be compared with the retrieved curated documentation; confirm product/version applicability."
    if not sources:
        analysis.limitations.append("No matching trusted documentation was retrieved; no source citations are displayed.")
    analysis.actions = rank_and_gate(analysis.actions, {item.evidence_id for item in analysis.evidence}, {source.source_id for source in sources})
    return analysis