# API

Base URL: `http://localhost:8000`. FastAPI interactive API docs are available at `/docs` while the service is running.

- `GET /api/health`: provider and service status.
- `POST /api/incidents`: multipart field `file`; returns the completed analysis. Supported: `.log`, `.txt`, `.csv`, `.json`, `.zip` of supported files. EVTX returns 415.
- `GET /api/incidents/{incident_id}`: incident metadata/status.
- `GET /api/incidents/{incident_id}/analysis`: validated structured analysis.
- `GET /api/incidents/{incident_id}/evidence/{evidence_id}`: one evidence record scoped to its incident.
- `GET /api/incidents/{incident_id}/sources`: retrieved curated sources. Empty means no trusted source matched.
- `POST /api/incidents/{incident_id}/chat`: JSON `{ "message": "..." }`; bounded history is retained.
- `POST /api/incidents/{incident_id}/actions/{action_id}/outcome`: JSON `{ "performed": false, "outcome": "inconclusive", "rating": 3, "explanation": "..." }`.
- `POST /api/knowledge/index`: administrator-only curated document indexing. Requires `X-Admin-Key`; JSON fields `title`, `publisher`, `url`, `content`, with optional `product_family` and `product_version`. URL must be HTTPS on an allowed trusted domain.

Errors use FastAPI's standard JSON `detail`; typical statuses are 400 malformed content, 403 unauthorized indexing, 404 unknown incident/evidence/action, 413 size limit, and 415 unsupported format. The prototype has no user authentication; do not deploy it as a multi-user service without adding identity, tenant isolation, and authorization.