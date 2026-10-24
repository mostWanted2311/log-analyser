# API Reference

Base URL: `http://localhost:8000`. Interactive FastAPI docs are available at `http://localhost:8000/docs` while the service is running. JSON request and response models are defined in `backend/app/models.py`.

## Health

`GET /api/health` returns service and optional model readiness:

```json
{
  "status": "ok",
  "ai_provider": "local_api_ready",
  "web_search": "not_configured",
  "max_upload_mb": 10
}
```

`ai_provider` is one of `deterministic`, `local_api_ready`, `local_model_not_loaded`, `local_api_offline`, or `local_config_invalid`. Model readiness checks the configured `LOCAL_MODEL_NAME` against LM Studio's local `/v1/models` response. It does not perform a generation request.

## Incidents and evidence

### `POST /api/incidents`

Upload one file as multipart form field `file`. The response is a completed `IncidentAnalysis`; processing is synchronous.

Supported extensions: `.log`, `.txt`, `.csv`, `.json`, and `.zip` containing supported files. EVTX is not supported and returns 415. The default upload limit is 10 MB and is configurable with `MAX_UPLOAD_MB`. ZIP processing rejects unsafe paths and encrypted entries, limits archives to 30 files and 3 times the configured upload limit when expanded, and caps processing at 30,000 aggregate events. Text parsers process at most 10,000 records per file. Supported text encodings are UTF-8 and UTF-16.

Typical errors: 400 for empty, malformed, or unsafe content; 413 when the upload exceeds the configured limit; 415 for unsupported extensions. The `Content-Type` header is not used as proof of file type.

### `GET /api/incidents/{incident_id}`

Returns `incident_id`, original basename, status, detected log type, and creation timestamp.

### `GET /api/incidents/{incident_id}/analysis`

Returns the persisted `IncidentAnalysis`: summary, detected log type, severity, findings, hypotheses, ranked actions, evidence references, retrieved sources, safety notes, missing information, and limitations.

### `GET /api/incidents/{incident_id}/evidence/{evidence_id}`

Returns one evidence record only if its ID belongs to the requested incident. Evidence includes source filename, line number when available, timestamp when parsed, severity, and message.

### `GET /api/incidents/{incident_id}/sources`

Returns only sources retrieved from locally indexed documentation and whose URL still matches the configured trusted HTTPS domains. An empty list means no source matched; the app does not crawl URLs or invent citations.

Unknown incidents, evidence IDs, or actions return 404.

## Chat and feedback

### `POST /api/incidents/{incident_id}/chat`

Request body:

```json
{ "message": "Why is the first recommendation ranked first?" }
```

`message` must be 1 to 4,000 characters. The response contains `reply`, `provider`, and recent conversation `history`. Up to 20 messages are returned from storage; the LM Studio prompt uses a bounded subset. If enabled, the backend sends bounded incident context to the configured local LM Studio endpoint only. If it is disabled or unavailable, deterministic fallback responses are used. Requests to execute commands are refused; no infrastructure action is performed.

### `POST /api/incidents/{incident_id}/actions/{action_id}/outcome`

Request body:

```json
{
  "performed": false,
  "outcome": "inconclusive",
  "rating": 3,
  "explanation": "The status could not be confirmed."
}
```

`outcome` must be `resolved`, `partially_resolved`, `unsuccessful`, or `inconclusive`; `rating` is optional from 1 to 5; `explanation` is optional and capped at 2,000 characters. The action must belong to that incident. Feedback is stored separately and is not verified ground truth.

## Curated knowledge

### `POST /api/knowledge/index`

Administrator/developer indexing endpoint. Requires header `X-Admin-Key` matching `ADMIN_API_KEY`. Request fields: `title` (2-300 characters), `publisher` (2-200), canonical HTTPS `url`, `content` (30-100,000 characters), optional `product_family` (up to 200), and optional `product_version` (up to 100). The URL host must match `TRUSTED_DOMAINS`. The endpoint stores submitted text and metadata in local SQLite; retrieval uses keyword matching. It does not download the URL, fetch web pages, or create embeddings.

Returns `document_id` and `status`. Invalid fields return 422; missing or incorrect admin configuration returns 403; a disallowed URL or unavailable indexing operation returns 400.

## Configuration and limitations

- `LOCAL_MODEL_ENABLED`, `LOCAL_MODEL_BASE_URL`, `LOCAL_MODEL_NAME`, and `LOCAL_MODEL_TIMEOUT_SECONDS` control the LM Studio integration. The URL validator permits only localhost/loopback or `host.docker.internal`, and HTTP requests bypass environment proxies.
- `MAX_UPLOAD_MB`, `CORS_ORIGINS`, `DATABASE_PATH`, `TRUSTED_DOMAINS`, and `ADMIN_API_KEY` configure the backend. Relative `DATABASE_PATH` values resolve from the backend process working directory.
- The prototype has no user authentication or tenant isolation. An incident ID is not an authorization system. Protect the service and database accordingly; do not expose it as a multi-user deployment without access control.
- Analysis is synchronous in the upload request; there is no job queue or status polling workflow. Provider timeouts may make uploads take longer when the local model is enabled.
- Standard FastAPI error responses use a `detail` field. `GET /api/health` reports the optional model provider but does not guarantee that analysis generation will succeed.