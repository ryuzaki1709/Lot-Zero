# Lot Zero — Cloud Run Deployment & Live Verification Evidence

**Verification Date**: 2026-08-30  
**Target Environment**: Google Cloud Run (`us-central1`)  
**Deployment Status**: **Verified & Active**

---

## 1. Deployment Provenance & Container Identifiers

| Parameter | Provenance Identifier |
| :--- | :--- |
| **Git Commit** | `3a84b481e0fc2088f503d09526a6b944c38618e4` (`fix: prepare secure cloud run deployment`) |
| **Cloud Build ID** | `40503dc4-5874-4aae-87e7-8b352e474aa3` |
| **Active Serving Revision** | `lot-zero-00024-yaj` |
| **Immutable Container Image Digest** | `us-central1-docker.pkg.dev/project-b2c3348e-d718-4255-be2/cloud-run-source-deploy/lot-zero@sha256:3b5a9d4511da0b85be4310ea69e8687907f279ed6b1ddb37822b875e39d66e59` |
| **Public Live URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app) |
| **Canonical Public Health URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app/api/health](https://lot-zero-m4vizenaoa-uc.a.run.app/api/health) |
| **Retained Rollback Revision** | `lot-zero-00023-md4` (0% traffic) |

---

## 2. Runtime Identity & Least-Privilege IAM Configuration

The deployment executes under a dedicated runtime service account rather than the default compute identity.

- **Dedicated Service Account**: `lot-zero-runtime@project-b2c3348e-d718-4255-be2.iam.gserviceaccount.com`
- **Project-Level Role Grants**:
  - `roles/aiplatform.user` (Enables Vertex AI Gemini API model execution via `google-genai` SDK)
  - `roles/logging.logWriter` (Enables Cloud Logging runtime stdout/stderr log emission)
- **Secret-Level Role Grant**:
  - `roles/secretmanager.secretAccessor` granted specifically and exclusively on secret `lot-zero-sse-secret`
- **Excluded Broad Privileges**: Zero administrative or broad privileges granted (`Owner`, `Editor`, `Storage Admin`, `Secret Manager Admin`, and `Artifact Registry Writer` were explicitly withheld).

---

## 3. Container Runtime & Infrastructure Parameters

- **Platform**: Google Cloud Run (Fully Managed)
- **Scaling Limits**: `min-instances: 0` (scale-to-zero enabled), `max-instances: 1` (strict single-instance evaluation concurrency)
- **Concurrency**: `10` simultaneous evaluation requests
- **Compute Resources**: `1 vCPU`, `512 MiB RAM`, `300s` request timeout
- **Storage**: Ephemeral local container storage (`LOT_ZERO_DB_PATH=/tmp/lot_zero.db`). Legacy GCS FUSE volume mounts were cleared.
- **Secret Binding**: Cloud Run resolves `LOT_ZERO_SSE_SECRET` from a Secret Manager reference at runtime. The plaintext value is not stored in Git or passed as a deployment argument.
- **Vertex AI Environment**: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=project-b2c3348e-d718-4255-be2`, `GOOGLE_CLOUD_LOCATION=global`.

---

## 4. Live Post-Promotion Verification Results

All endpoints and domain workflows were validated live against `https://lot-zero-m4vizenaoa-uc.a.run.app`:

### A. Health & System Configuration
- `GET /api/health` -> HTTP 200 OK:
  ```json
  {"status": "ok", "service": "lot-zero-api", "tenant": "EVAL-TENANT-01", "evaluation_mode": true}
  ```
- `GET /api/config` -> HTTP 200 OK:
  - `evaluation_mode: true`
  - Exactly 5 human evaluation personas returned (`RECALL-COORD-01`, `QA-LEAD-01`, `OPS-001`, `CLOSURE-AUTH-01`, `EVAL-ADMIN-01`).
  - Internal automated service principal `AGENT-SVC-01` and its credential `key-agent-svc-01` are absent from the browser configuration.

### B. Frontend SPA & Static Assets
- `GET /` -> HTTP 200 OK: Production React SPA Asset bundle served.
- `GET /assets/index-KTIdlj9Z.css` -> HTTP 200 OK (`text/css; charset=utf-8`).
- `GET /assets/index-DwLJ3ghR.js` -> HTTP 200 OK (`text/javascript; charset=utf-8`).

### C. Evaluation State Reset
- `POST /api/evaluation/reset` (with `X-API-Key: key-eval-admin-01`) -> HTTP 200 OK:
  - Database re-seeded to clean baseline in `signal_received` state.

### D. Live Vertex AI Gemini Execution & Grounded Extraction
- `POST /api/evaluation/simulate-signal` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - **Live Model Flag**: `is_live_model: true`
  - **Model Version Tag**: `gemini-3.5-flash (Vertex AI Live)`
  - **Grounding Status**: `is_grounded: true`
  - **Extracted Contaminated Lot**: `ING-4417`
  - **Identified Pathogen**: `Salmonella enterica serovar Typhimurium`
  - **Evidence Spans**: 3 verbatim character-offset citation spans verified against source document SHA-256.

### E. Real-Time Token Issuance
- `POST /api/sse-token` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - Generates 60-second HMAC-signed token using the Secret Manager-injected key for `RECALL-COORD-01`.

### F. Observability & Log Audit
- Cloud Run logs for `lot-zero-00024-yaj` confirm:
  - Clean startup without initialization failures.
  - Automatic Function Calling (AFC) initialized: `AFC is enabled with max remote calls: 10`.
  - Zero Python tracebacks, zero secret leakage, zero database errors, and zero unhandled HTTP 500 errors.

---

## 5. Process Disclosure

During the deployment sequence, the candidate tag URL (`https://candidate---lot-zero-m4vizenaoa-uc.a.run.app`) was initially unreachable due to edge routing behavior. Traffic was promoted to revision `lot-zero-00024-yaj` before candidate HTTP verification could be completed. Full health, configuration, SPA, static asset, reset, live Vertex AI, SSE-token, IAM, and log verification was executed and validated post-promotion against the service URL.

---

## 6. Known Limitations & Scope Boundaries

1. **Ephemeral Container Storage**: SQLite runs at `/tmp/lot_zero.db`. Instance recycling, scale-to-zero cold starts, or new revisions reset database state to baseline.
2. **Evaluation Personas**: Browser personas use synthetic API keys for demonstration and hackathon evaluation, not enterprise OIDC/SAML SSO.
3. **Audit Ledger Scope**: Hash chains provide cryptographic tamper evidence within the export bundle but do not commit root hashes to an external distributed ledger or WORM hardware vault.
4. **Regulatory Boundaries**: The system models FDA-inspired recall effectiveness and non-response workflows; it does not submit data to FDA systems or certify statutory compliance.
5. **Multi-User Evaluation**: Public evaluators share a single evaluation tenant (`EVAL-TENANT-01`) and active incident state.
6. **Cloud Consumption**: Live Vertex AI Gemini calls utilize Google Cloud resources and may incur billing charges.
