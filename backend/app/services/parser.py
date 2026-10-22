import csv
import io
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from .security import redact_secrets

SUPPORTED = {".log", ".txt", ".csv", ".json"}
TIMESTAMP = re.compile(r"\b(\d{4}-\d{2}-\d{2}[T ][0-9:.+-]+Z?)\b")
SEVERITY = re.compile(r"\b(critical|fatal|error|err|warning|warn|info|debug)\b", re.I)
CODE = re.compile(r"\b(?:event(?:\s+id)?|error\s+code|code)\s*[:=#-]?\s*([A-Z0-9_-]{2,})", re.I)


def _event(file_name: str, line: int, text: str, attrs: dict[str, Any] | None = None) -> dict[str, Any]:
    timestamp_match = TIMESTAMP.search(text)
    severity_match = SEVERITY.search(text)
    code_match = CODE.search(text)
    semantic_failure = bool(re.search(r"(?i)(?:cache status.*permanently disabled|cache status details.*(?:disabled|failed)|cache disable reason.*failed|battery/capacitor status.*failed|controller status.*(?:failed|degraded)|\bstatus\s*:\s*(?:failed|degraded)\b)", text))
    event_id = str(uuid.uuid4())
    timestamp = timestamp_match.group(1) if timestamp_match else None
    timezone_match = re.search(r"(Z|[+-]\d{2}:?\d{2})$", timestamp or "")
    host_match = re.search(r"\b(?:host|hostname|computer)\s*[=:]\s*([^\s,;]+)", text, re.I)
    component_match = re.search(r"\b(?:service|component|source)\s*[=:]\s*([^\s,;]+)", text, re.I)
    return {
        "event_id": event_id, "evidence_id": event_id, "source_file": PurePosixPath(file_name).name,
        "line_number": line, "timestamp": timestamp, "original_timestamp": timestamp,
        "timezone": timezone_match.group(1) if timezone_match else None,
        "source_type": None, "component": component_match.group(1) if component_match else None,
        "host": host_match.group(1) if host_match else None,
        "severity": severity_match.group(1).lower() if severity_match else "error" if semantic_failure else "unknown",
        "event_code": code_match.group(1) if code_match else None,
        "message": redact_secrets(text.strip())[:2000], "parsed_attributes": attrs or {},
    }


def parse_text(file_name: str, raw: bytes) -> tuple[list[dict[str, Any]], str]:
    suffix = PurePosixPath(file_name).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file format: {suffix or 'no extension'}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise ValueError("Could not decode file as UTF-8 or UTF-16 text") from exc
    if not text.strip():
        raise ValueError("The uploaded log is empty")
    if suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON log: {exc.msg}") from exc
        rows = value if isinstance(value, list) else [value]
        events = []
        for index, row in enumerate(rows[:10000], 1):
            serialized = json.dumps(row, ensure_ascii=True, sort_keys=True) if isinstance(row, dict) else str(row)
            events.append(_event(file_name, index, serialized, row if isinstance(row, dict) else {}))
        for event in events:
            event["source_type"] = "application"
        return events, "application"
    if suffix == ".csv":
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except csv.Error as exc:
            raise ValueError("Malformed CSV log") from exc
        if not rows:
            raise ValueError("CSV log has no data rows")
        events = []
        for index, row in enumerate(rows[:10000], 2):
            events.append(_event(file_name, index, json.dumps(row, ensure_ascii=True), row))
        for event in events:
            event["source_type"] = "application"
        return events, "application"
    lines = text.splitlines()[:10000]
    events = [_event(file_name, index, line) for index, line in enumerate(lines, 1) if line.strip()]
    lowered = text.lower()
    if "smart array" in lowered or "cache status details" in lowered or "battery/capacitor status" in lowered:
        category = "hpe_smart_array"
    elif "vmkernel" in lowered or "esxi" in lowered:
        category = "vmware_esxi"
    elif "vmware" in lowered or "vmx:" in lowered:
        category = "vmware_vm"
    elif "ilo" in lowered or "integrated management log" in lowered:
        category = "hpe_ilo_iml"
    elif "windows" in lowered or "event id" in lowered or "eventid" in lowered:
        category = "windows_server_or_event"
    else:
        category = "application"
    if not events:
        raise ValueError("The uploaded log contains no usable records")
    for event in events:
        event["source_type"] = category
    return events, category


def group_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event["message"]].append(event)
    result = []
    for message, records in grouped.items():
        result.append({"message": message, "count": len(records), "representative": records[0], "evidence_ids": [r["evidence_id"] for r in records]})
    return sorted(result, key=lambda group: (group["representative"].get("timestamp") or "", group["representative"]["line_number"]))