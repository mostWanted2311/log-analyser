from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class EvidenceReference(BaseModel):
    evidence_id: str
    source_file: str
    line_number: int | None = None
    timestamp: str | None = None
    severity: str = "unknown"
    message: str


class KeyFinding(BaseModel):
    finding_id: str
    title: str
    detail: str
    severity: str
    evidence_ids: list[str]


class DiagnosticHypothesis(BaseModel):
    hypothesis_id: str
    title: str
    explanation: str
    confidence: Literal["low", "medium", "high"]
    evidence_ids: list[str]
    alternatives: list[str] = Field(default_factory=list)


class RetrievedSource(BaseModel):
    source_id: str
    title: str
    publisher: str
    url: HttpUrl
    retrieved_at: str
    supports: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    action_id: str
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    reason: str
    evidence_ids: list[str]
    source_ids: list[str] = Field(default_factory=list)
    risk_category: Literal["read_only", "reversible", "service_impacting", "destructive_or_sensitive"]
    prerequisites: list[str] = Field(default_factory=list)
    expected_observations: list[str] = Field(default_factory=list)
    suggested_follow_up: str
    requires_authorization: bool = True
    score: float = Field(default=0, ge=0, le=1)
    score_factors: dict[str, float] = Field(default_factory=dict)


class IncidentAnalysis(BaseModel):
    incident_id: str
    status: Literal["complete", "needs_review"] = "complete"
    summary: str
    detected_log_type: str
    severity: str
    findings: list[KeyFinding]
    hypotheses: list[DiagnosticHypothesis]
    actions: list[RecommendedAction]
    evidence: list[EvidenceReference]
    sources: list[RetrievedSource] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    provider: str = "deterministic"
    history: list[ConversationMessage]


class ActionOutcome(BaseModel):
    performed: bool = False
    outcome: Literal["resolved", "partially_resolved", "unsuccessful", "inconclusive"]
    rating: int | None = Field(default=None, ge=1, le=5)
    explanation: str = Field(default="", max_length=2000)


class FeedbackRecord(BaseModel):
    feedback_id: str
    incident_id: str
    action_id: str
    performed: bool
    outcome: str
    rating: int | None = None
    explanation: str = ""
    created_at: str
class KnowledgeDocumentRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    publisher: str = Field(min_length=2, max_length=200)
    url: HttpUrl
    content: str = Field(min_length=30, max_length=100000)
    product_family: str = Field(default="", max_length=200)
    product_version: str = Field(default="", max_length=100)