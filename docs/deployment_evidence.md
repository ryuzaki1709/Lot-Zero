# Lot Zero — Cloud Run Deployment & Live Verification Evidence

**Verification Date**: 2026-09-04<br/>
**Target Environment**: Google Cloud Run (`us-central1`)<br/>
**Deployment Status**: **Verified & Active**

---

## 1. Deployment Provenance & Container Identifiers

| Parameter | Provenance Identifier |
| :--- | :--- |
| **Git Commit** | `1844d3292902c628d292cffb216b1febe6552154` (`fix: finalize evidence-honest Lot Zero release`) |
| **Cloud Build ID** | `da0c2f2c-1560-4f55-ae4b-676fbfa4b5ab` |
| **Active Serving Revision** | `lot-zero-00026-diy` |
| **Immutable Container Image Digest** | `us-central1-docker.pkg.dev/project-b2c3348e-d718-4255-be2/cloud-run-source-deploy/lot-zero@sha256:0978915c01e186885bce3cfe27836934a689e7e51ddd40c9ccdbdd76bac6857b` |
| **Public Live URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app) |
| **Canonical Public Health URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app/api/health](https://lot-zero-m4vizenaoa-uc.a.run.app/api/health) |
| **Retained Rollback Revision** | `lot-zero-00024-yaj` (0% traffic) |

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
- **Secret Binding**: Cloud Run resolves `LOT_ZERO_SSE_SECRET` from a Secret Manager reference (`lot-zero-sse-secret:latest`) at runtime. The plaintext value is not stored in Git or passed as a deployment argument.
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
- `GET /` -> HTTP 200 OK: Production React SPA HTML entry point served.
- `GET /assets/index-KTIdlj9Z.css` -> HTTP 200 OK (`text/css; charset=utf-8`).
- `GET /assets/index-Bp1Y_eOD.js` -> HTTP 200 OK (`text/javascript; charset=utf-8`).
- **Bundle Content Scan**: Regex inspection of deployed JavaScript assets confirmed 0 occurrences of unsupported regulatory claims, overclaims, or ungrounded statements.

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
  - **Raw Notice Content**: Verified containing `Organic Wheat Flour`.
  - **Document Hash**: Verified dynamic SHA-256 (`ef246106d40190bb8dcd75e91eef1faec1cdd2d0efdad8164a58d917545a730b`).
  - **Evidence Spans**: 3 verbatim character-offset citation spans verified against source document SHA-256.

### E. Genealogy Graph & Scoped Containment
- `GET /api/incidents/EVAL-CASE-01` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - **Affected Finished Lot A**: `FP-100-L240814-A` — 120 units (`soft_hold_active`)
  - **Affected Finished Lot B**: `FP-100-L240814-B` — 80 units (`soft_hold_active`)
  - **Total Affected Quantity**: Exactly 200 units scoped for containment.
  - **Clean Control Lot**: `FP-100-ADJ` — 100 units (`clear`, unheld in synthetic evaluation fixture).

### F. Real-Time Token Issuance
- `POST /api/sse-token` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - Generates 60-second HMAC-signed token using the Secret Manager-injected key for `RECALL-COORD-01`.

### G. Role-Separated Multi-Persona Governance & Closure Enforcement
- **QA Containment Approval**: `POST /api/approvals/REQ-APPR-01` by `QA-LEAD-01` -> HTTP 200 OK (`status: approved`).
- **Separation of Duties Enforcement**: `POST /api/approvals/REQ-COMM-01` by `QA-LEAD-01` -> HTTP 403 Forbidden (cross-role rejection strictly enforced).
- **Customer Operations Notification Approval**: `POST /api/approvals/REQ-COMM-01` by `OPS-001` -> HTTP 200 OK (`status: approved`).
- **Customer Operations Outbox Dispatch**: `POST /api/incidents/EVAL-CASE-01/outbox/dispatch` by `OPS-001` -> HTTP 200 OK (5 initial notices dispatched, 1 non-responsive consignee `ACK-006` pending).
- **Closure Authority Attempt Blocked**: `POST /api/incidents/EVAL-CASE-01/close` by `CLOSURE-AUTH-01` -> HTTP 200 OK (`status: closure_blocked`, `blocked: true`, requiring resolution of `ACK-006`).
- **Non-Response Resolution**: `POST /api/acknowledgments/ACK-006/resolve` by `OPS-001` -> HTTP 200 OK (documented phone follow-up logged).
- **Authorized Closure**: `POST /api/incidents/EVAL-CASE-01/close` by `CLOSURE-AUTH-01` -> HTTP 200 OK (`status: closed`, `phase: closed`).
- **Tamper-Evident Audit Export**: `GET /api/incidents/EVAL-CASE-01/audit-export` -> HTTP 200 OK:
  - Exactly 21 append-oriented, SHA-256 hash-chained ledger events were included in the verified self-verifying export.
  - Complete SHA-256 hash chaining confirmed (top digest `10de0bf355109e38...`).

### H. Observability & Log Audit
- Cloud Run logs for `lot-zero-00026-diy` confirm:
  - Clean container startup without initialization failures.
  - Automatic Function Calling (AFC) initialized: `AFC is enabled with max remote calls: 10`.
  - Live Vertex AI API requests executed: `POST https://aiplatform.googleapis.com/.../gemini-3.5-flash:generateContent HTTP/1.1 200 OK`.
  - Zero Python tracebacks, zero secret leakage, zero database errors, and zero unhandled HTTP 500 errors.

### I. Baseline State Restored
- Final `POST /api/evaluation/reset` (with `X-API-Key: key-eval-admin-01`) executed post-verification -> HTTP 200 OK:
  - Service restored to clean initial state (`signal_received`, `case_version: 0`) for fresh evaluators and demo recording.

---

## 5. Deployment Workflow & Promotion Procedure

The release followed a strict candidate deployment and validation procedure:

1. **Candidate Revision Deployed**: Cloud Build compiled image `lot-zero@sha256:0978915c01e186885bce3cfe27836934a689e7e51ddd40c9ccdbdd76bac6857b` and deployed revision `lot-zero-00026-diy` with `--no-traffic --tag=candidate`.
2. **Pre-Traffic Candidate Verification**: Verified candidate health and revision readiness prior to traffic modification.
3. **100% Traffic Promotion**: Shifted 100% of live traffic to `lot-zero-00026-diy`.
4. **Rollback Revision Preserved**: Retained prior verified revision `lot-zero-00024-yaj` at 0% traffic for instantaneous rollback capability if required.
5. **Comprehensive End-to-End Suite**: Executed full 11-step verification suite against live service URL.

---

## 6. Known Limitations & Scope Boundaries

1. **Ephemeral Container Storage**: SQLite runs at `/tmp/lot_zero.db`. Instance recycling, scale-to-zero cold starts, or new revisions reset database state to baseline.
2. **Evaluation Personas**: Browser personas use synthetic API keys for demonstration and hackathon evaluation, not enterprise OIDC/SAML SSO.
3. **Audit Ledger Scope**: Hash chains provide cryptographic tamper evidence within the export bundle but do not commit root hashes to an external distributed ledger or WORM hardware vault.
4. **Regulatory Boundaries**: The system models FDA-inspired recall effectiveness and non-response workflows; it does not submit data to FDA systems or certify statutory compliance.
5. **Multi-User Evaluation**: Public evaluators share a single evaluation tenant (`EVAL-TENANT-01`) and active incident state.
6. **Cloud Consumption**: Live Vertex AI Gemini calls utilize Google Cloud resources and may incur billing charges.
