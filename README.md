# InfraGuide AI

InfraGuide AI is a local-first infrastructure log analyzer. It parses logs on the backend, links findings to exact source records, and recommends human-reviewed troubleshooting steps. Optional model chat and analysis use the LM Studio server on this PC; the application does not call hosted AI APIs.

## HPE Smart Array sample diagnosis

The parser recognizes structured hardware state, not only words such as `ERROR`. For the supplied report, it detects `Cache Status: Permanently Disabled`, the `Cache Status Details` failed-charge reason, and the failed battery/capacitor status. The resulting finding points to those exact lines. It recommends confirming current controller/capacitor alerts through the installed management utility and keeping write-cache protection unchanged while a server-specific service plan is prepared. It does not infer disk failure or data loss from this excerpt.

A sanitized test fixture is at [samples/synthetic_hpe_smart_array.log](samples/synthetic_hpe_smart_array.log); it does not contain the serial numbers from the supplied log. The original `backend/data/sample_log.txt` remains local and should not be committed or shared.

## Features

- React, Vite, TypeScript, Tailwind CSS upload and incident dashboard with evidence, timeline, recommendations, source links, contextual chat, and outcome feedback.
- FastAPI API with validated incident, evidence, analysis, source, chat, feedback, and health routes.
- `.log`, `.txt`, `.csv`, `.json`, and ZIP containing supported files. EVTX is rejected with an explanatory message.
- Deterministic event parsing, HPE Smart Array cache/capacitor rules, evidence-linked hypotheses, bounded upload/archive handling, best-effort secret redaction, and SQLite persistence.
- Optional local chat/analysis through LM Studio's OpenAI-compatible API. The backend accepts only localhost/loopback or Docker Desktop's `host.docker.internal`; no hosted model client is included.
- Curated documentation indexing stores submitted text and trusted HTTPS metadata in local SQLite; retrieval uses local keyword matching and never crawls URLs. No source citation is shown unless it was actually indexed and retrieved.
- Transparent heuristic ranking (35% evidence, 25% documentation, 20% product compatibility, 20% diagnostic value) with separate risk/evidence gates. These weights are uncalibrated.
- The application recommends only. It does not execute shell, PowerShell, iLO, or storage commands and does not modify infrastructure.

## Local model through LM Studio

Load `gemma-4-12B-it-qat-q4_0-gguf` in LM Studio, start its local server in the Developer tab, and use the model ID reported by `GET http://localhost:1235/v1/models`. This workspace currently sees `gemma-4-12b-it-qat` at that endpoint. Set `.env` to `LOCAL_MODEL_ENABLED=true`, `LOCAL_MODEL_BASE_URL=http://127.0.0.1:1235/v1`, and `LOCAL_MODEL_NAME=gemma-4-12b-it-qat`. The backend sends bounded, redacted evidence to this local endpoint only; if LM Studio is unavailable, analysis remains deterministic and chat falls back with an explicit provider status. No model runtime is installed in the backend; LM Studio owns loading and running the model. Model weights are not downloaded by the app.
## Run locally

Prerequisites: Python 3.11+, Node.js 20+, npm. LM Studio is optional for deterministic analysis and required for local model chat/analysis.

1. Copy `.env.example` to `.env`. Set a strong `ADMIN_API_KEY` before indexing documents. Keep `.env` private.
2. Backend, from PowerShell:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m uvicorn app.main:app --reload --port 8000 --env-file ..\.env
   ```

3. Frontend, in another terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open `http://localhost:5173`. API docs are at `http://localhost:8000/docs`.

## Docker Compose

For Docker Compose, set `.env` and configure LM Studio to accept a connection from Docker at `host.docker.internal:1235`. This may require enabling local-network serving in LM Studio; restrict access to your trusted machine/network. Then run `docker compose up --build`. For a localhost-only setup, run the backend directly on Windows instead. Open `http://localhost:5173`. SQLite persists in a Docker volume.
## Configuration

`LOCAL_MODEL_ENABLED` enables LM Studio requests. `LOCAL_MODEL_BASE_URL` points to its local OpenAI-compatible API, and `LOCAL_MODEL_NAME` selects the loaded model. `LOCAL_MODEL_TIMEOUT_SECONDS` bounds requests. `MAX_UPLOAD_MB`, `DATABASE_PATH`, `TRUSTED_DOMAINS`, `ADMIN_API_KEY`, and `CORS_ORIGINS` configure the API. `VITE_API_URL` configures the frontend backend URL.

## Curated documentation

See [knowledge/README.md](knowledge/README.md). `POST /api/knowledge/index` stores administrator-submitted document text locally in SQLite and uses keyword matching (no model embeddings or ChromaDB). The backend validates that the submitted HTTPS source URL belongs to `TRUSTED_DOMAINS`; it does not fetch that URL. Respect source licensing and terms. Clicking a displayed source opens its submitted URL in the user's browser.

## Tests

Backend: `cd backend; python -m pytest -q`. Focused sample coverage: `python -m pytest tests/test_hpe_cache.py -q`. Frontend build: `cd frontend; npm install; npm run build`. Synthetic expected behavior is described in [samples/EXPECTED.md](samples/EXPECTED.md).

## Limits and privacy

This is a prototype, not a production incident platform. EVTX parsing, full VMware/HPE adapter coverage, asynchronous job processing, user authentication/tenant isolation, retention jobs, semantic vector retrieval, live web search, and calibrated ranking are not implemented. HPE cache rules recognize only the explicit conditions described above; physical component diagnosis still requires the exact server/controller service guide and operator verification. Uploaded event data persists in SQLite until removed. Redaction is best-effort. Keep production logs local and do not upload them to any deployment without approved access, retention, and data-handling controls.