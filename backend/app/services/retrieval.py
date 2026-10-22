import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from ..models import RetrievedSource
from . import store


def trusted_domain(url: str) -> bool:
    parsed = urlparse(url)
    allowed = [item.strip().lower().lstrip(".") for item in os.getenv("TRUSTED_DOMAINS", "learn.microsoft.com,knowledge.broadcom.com,hpe.com").split(",") if item.strip()]
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in allowed)


def index_document(title: str, publisher: str, url: str, content: str, product_family: str = "", product_version: str = "") -> str:
    if not trusted_domain(url):
        raise ValueError("Source URL must use HTTPS and match a configured trusted domain")
    if len(content) > 100_000 or len(content.strip()) < 30:
        raise ValueError("Document content must be between 30 and 100000 characters")
    document_id = str(uuid.uuid4())
    retrieved_at = datetime.now(timezone.utc).isoformat()
    chunks = [content[index:index + 1800] for index in range(0, len(content), 1500)]
    store.save_knowledge_chunks([
        (f"{document_id}:{index}", document_id, title[:300], publisher[:200], url, product_family[:200], product_version[:100], retrieved_at, chunk)
        for index, chunk in enumerate(chunks)
    ])
    return document_id


def search_sources(query: str, count: int = 3) -> list[RetrievedSource]:
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z0-9_-]{3,}", query.lower())))[:20]
    chunks = store.search_knowledge_chunks(terms, count)
    ranked = {}
    for chunk in chunks:
        if not trusted_domain(chunk["url"]):
            continue
        matched_terms = sum(term in (chunk["title"] + " " + chunk["content"]).lower() for term in terms)
        current = ranked.get(chunk["document_id"])
        if current is None or matched_terms > current[0]:
            ranked[chunk["document_id"]] = (matched_terms, chunk)
    ordered = sorted(ranked.values(), key=lambda item: (-item[0], item[1]["title"]))[:count]
    return [RetrievedSource(source_id=chunk["document_id"], title=chunk["title"], publisher=chunk["publisher"], url=chunk["url"], retrieved_at=chunk["retrieved_at"]) for _, chunk in ordered]