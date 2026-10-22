WEIGHTS = {"evidence_relevance": 0.35, "documentation_relevance": 0.25, "product_compatibility": 0.20, "diagnostic_value": 0.20}
ALLOWED_RISKS = {"read_only", "reversible"}


def rank_and_gate(actions, evidence_ids: set[str], source_ids: set[str]):
    ranked = []
    for action in actions:
        if action.risk_category not in ALLOWED_RISKS:
            continue
        if not action.evidence_ids or any(reference not in evidence_ids for reference in action.evidence_ids):
            continue
        if any(source_id not in source_ids for source_id in action.source_ids):
            continue
        factors = {
            "evidence_relevance": 1.0,
            "documentation_relevance": 1.0 if action.source_ids else 0.0,
            "product_compatibility": 0.5,
            "diagnostic_value": 0.9 if action.risk_category == "read_only" else 0.6,
        }
        action.score_factors = factors
        action.score = round(sum(factors[key] * WEIGHTS[key] for key in WEIGHTS), 3)
        action.priority = "high" if action.score >= 0.7 else "medium" if action.score >= 0.5 else "low"
        ranked.append(action)
    return sorted(ranked, key=lambda action: (-action.score, action.action_id))