import re

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|token|api[_-]?key|secret)\s*([=:])\s*([^\s,;]+)"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]


def redact_secrets(text: str) -> str:
    text = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    return _SECRET_PATTERNS[1].sub("[EMAIL_REDACTED]", text)