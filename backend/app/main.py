import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from fastapi import FastAPI, File, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from .models import IncidentAnalysis, ChatRequest, ChatResponse, ConversationMessage, ActionOutcome, FeedbackRecord, KnowledgeDocumentRequest
from .services.retrieval import index_document
from .services import store
from .services.parser import parse_text, SUPPORTED
from .services.analyzer import analyze
from .services.orchestrator import complete_analysis
from .services.ai import generate_chat_reply, local_model_status

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_ARCHIVE_FILES = 30
MAX_ARCHIVE_UNPACKED = MAX_UPLOAD_BYTES * 3
app = FastAPI(title="InfraGuide AI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])
store.initialize()


def now():
    return datetime.now(timezone.utc).isoformat()


def process_upload(file_name: str, raw: bytes):
    suffix = PurePosixPath(file_name).suffix.lower()
    if suffix != ".zip":
        return parse_text(file_name, raw)
    events, categories = [], []
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(raw)) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            if len(entries) > MAX_ARCHIVE_FILES:
                raise ValueError("Archive contains too many files")
            total = 0
            for item in entries:
                path = PurePosixPath(item.filename)
                if path.is_absolute() or ".." in path.parts or item.flag_bits & 1:
                    raise ValueError("Archive contains an unsafe or encrypted entry")
                if path.suffix.lower() not in SUPPORTED:
                    continue
                total += item.file_size
                if item.file_size > MAX_UPLOAD_BYTES or total > MAX_ARCHIVE_UNPACKED:
                    raise ValueError("Archive expands beyond the configured size limit")
                data = archive.read(item)
                parsed, category = parse_text(path.name, data)
                events.extend(parsed[:max(0, 30000 - len(events))])
                categories.append(category)
    except zipfile.BadZipFile as exc:
        raise ValueError("Malformed ZIP archive") from exc
    if not events:
        raise ValueError("Archive contains no supported, non-empty log files")
    return events[:30000], max(set(categories), key=categories.count)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_provider": local_model_status(), "web_search": "not_configured", "max_upload_mb": int(os.getenv("MAX_UPLOAD_MB", "10"))}


@app.post("/api/incidents", response_model=IncidentAnalysis)
async def create_incident(file: UploadFile = File(...)):
    name = PurePosixPath(file.filename or "upload").name
    if PurePosixPath(name).suffix.lower() not in SUPPORTED | {".zip"}:
        raise HTTPException(415, "Unsupported file type. Upload LOG, TXT, CSV, JSON, or ZIP containing supported logs. EVTX parsing is not installed.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    if not raw:
        raise HTTPException(400, "The uploaded file is empty")
    try:
        events, category = process_upload(name, raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    incident_id = str(uuid.uuid4())
    result = complete_analysis(analyze(incident_id, events, category), events)
    store.save_incident(incident_id, name, category, result, events, now())
    return result


def load_analysis(incident_id: str):
    item = store.get_incident(incident_id)
    if not item:
        raise HTTPException(404, "Incident not found")
    return item, IncidentAnalysis.model_validate_json(item["analysis"])


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    item, _ = load_analysis(incident_id)
    return {"incident_id": incident_id, "filename": item["filename"], "status": item["status"], "detected_log_type": item["category"], "created_at": item["created_at"]}


@app.get("/api/incidents/{incident_id}/analysis", response_model=IncidentAnalysis)
def get_analysis(incident_id: str):
    return load_analysis(incident_id)[1]


@app.get("/api/incidents/{incident_id}/evidence/{evidence_id}")
def get_evidence(incident_id: str, evidence_id: str):
    item, analysis = load_analysis(incident_id)
    evidence = next((e for e in analysis.evidence if e.evidence_id == evidence_id), None)
    if evidence is None:
        raise HTTPException(404, "Evidence record not found")
    return evidence


@app.get("/api/incidents/{incident_id}/sources")
def get_sources(incident_id: str):
    _, analysis = load_analysis(incident_id)
    return analysis.sources


@app.post("/api/incidents/{incident_id}/chat", response_model=ChatResponse)
def chat(incident_id: str, request: ChatRequest):
    _, analysis = load_analysis(incident_id)
    message = request.message.strip()
    stamp = now()
    store.add_message(incident_id, "user", message, stamp)
    if any(word in message.lower() for word in ("run command", "execute", "powershell", "shell command", "modify infrastructure")):
        reply, provider = "I cannot execute commands or modify infrastructure. I can explain a read-only diagnostic procedure; validate it against your environment and change controls first.", "deterministic_safety"
    else:
        history = store.get_messages(incident_id)[:-1]
        reply, provider = generate_chat_reply(message, analysis, history, store.get_feedback(incident_id))
        if reply is None:
            if "rank" in message.lower() or "first" in message.lower():
                top = analysis.actions[0] if analysis.actions else None
                reply = f"{top.title} is ranked first because: {top.reason}" if top else "There are no evidence-backed actions to rank yet. Please share the relevant time window and product/version."
            else:
                reply = f"Based on this incident, {analysis.summary} I cannot confirm a root cause from these records alone. Which host, product/version, and time zone are involved?"
    rows = store.add_message(incident_id, "assistant", reply, now())
    return ChatResponse(reply=reply, provider=provider, history=[ConversationMessage(**row) for row in rows])


@app.post("/api/incidents/{incident_id}/actions/{action_id}/outcome", response_model=FeedbackRecord)
def record_outcome(incident_id: str, action_id: str, outcome: ActionOutcome, x_admin_key: str | None = Header(default=None)):
    _, analysis = load_analysis(incident_id)
    if not any(action.action_id == action_id for action in analysis.actions):
        raise HTTPException(404, "Action not found for this incident")
    feedback_id = str(uuid.uuid4())
    stamp = now()
    feedback = FeedbackRecord(feedback_id=feedback_id, incident_id=incident_id, action_id=action_id, **outcome.model_dump(), created_at=stamp)
    store.save_feedback(feedback_id, incident_id, action_id, outcome.model_dump(), stamp)
    return feedback


@app.post("/api/knowledge/index")
def index_knowledge(payload: KnowledgeDocumentRequest, x_admin_key: str | None = Header(default=None)):
    configured = os.getenv("ADMIN_API_KEY")
    if not configured or x_admin_key != configured:
        raise HTTPException(403, "Authorized indexing is not configured")
    try:
        document_id = index_document(payload.title, payload.publisher, str(payload.url), payload.content, payload.product_family, payload.product_version)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"document_id": document_id, "status": "indexed"}