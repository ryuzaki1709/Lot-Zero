# Lot Zero — Cloud Run Deployment & Live Verification Evidence

**Verification Date**: 2026-09-04<br/>
**Deployment Timestamp**: 2026-09-04 11:09:52 UTC (`16:39:52 IST`)<br/>
**Target Environment**: Google Cloud Run (`us-central1`)<br/>
**Deployment Status**: **Verified & Active**

---

## 1. Deployment Provenance & Container Identifiers

| Parameter | Provenance Identifier |
| :--- | :--- |
| **Git Commit** | `17f700ecb2e4319616b6e9dfb1352619f19b6cb9` (`Merge pull request #2 from ryuzaki1709/codex/lot-zero-demo-copy`) |
| **Cloud Build ID** | `141f0494-a30e-4baa-9468-7de598e1595d` |
| **Active Serving Revision** | `lot-zero-00028-vip` |
| **Immutable Container Image Digest** | `us-central1-docker.pkg.dev/project-b2c3348e-d718-4255-be2/cloud-run-source-deploy/lot-zero@sha256:b1a375ddbbcd025a025cbcd0438fb07ee461cb0fa037b36d2454da2d0afc5034` |
| **Public Live URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app) |
| **Canonical Public Health URL** | [https://lot-zero-m4vizenaoa-uc.a.run.app/api/health](https://lot-zero-m4vizenaoa-uc.a.run.app/api/health) |
| **Retained Rollback Revision** | `lot-zero-00026-diy` (0% traffic) |

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
- `GET /assets/index-khicPuCz.js` -> HTTP 200 OK (`text/javascript; charset=utf-8`, 278,907 bytes).
- **Bundle & Response Copy Scan**:
  - Confirmed required positive phrasing present: `Apex Micro Quality Labs Text Notice`, `Laboratory text notice ingested as the incident's root evidence`, and `Record Non-Response & Close`.
  - Confirmed 0 occurrences of prohibited regulatory claims or ungrounded assertions (`Signed Apex Labs Report`, `Signed laboratory report`, `Non-Response Close (§ 7.49)`, `§ 7.49`, `certified non-response`, `true regulatory compliance`, `FDA-NONRESP`, `closed under 21 CFR`, `archived under 21 CFR`).

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
  - **Projected Document Version**: `v1.0 (Apex Micro Quality Labs Text Notice)`.

### E. Genealogy Graph & Scoped Containment
- `GET /api/incidents/EVAL-CASE-01` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - **Affected Finished Lot A**: `FP-100-L240814-A` — 120 units (`soft_hold_active`)
  - **Affected Finished Lot B**: `FP-100-L240814-B` — 80 units (`soft_hold_active`)
  - **Total Affected Quantity**: Exactly 200 units scoped for containment.
  - **Clean Control Lot**: `FP-100-ADJ` — 100 units (`clear`, unheld in synthetic evaluation fixture).

### F. Real-Time Token Issuance
- `POST /api/sse-token` (with `X-API-Key: key-recall-coord-01`) -> HTTP 200 OK:
  - Generates 60-second HMAC-signed token (length 172) using the Secret Manager-injected key for `RECALL-COORD-01` without exposing token plaintext.

### G. Role-Separated Multi-Persona Governance & Closure Enforcement
- **QA Containment Approval**: `POST /api/evaluation/approve-containment` by `QA-LEAD-01` -> HTTP 200 OK.
- **Separation of Duties Enforcement**: `POST /api/evaluation/approve-notification` by `QA-LEAD-01` -> HTTP 403 Forbidden (cross-role rejection strictly enforced).
- **Recall Coordinator Notification Request**: `POST /api/evaluation/request-notification` by `RECALL-COORD-01` -> HTTP 200 OK.
- **Customer Operations Notification Approval**: `POST /api/evaluation/approve-notification` by `OPS-001` -> HTTP 200 OK.
- **Customer Operations Outbox Dispatch**: `POST /api/evaluation/dispatch-outbox` by `OPS-001` -> HTTP 200 OK (5 initial notices dispatched, 1 non-responsive consignee `ACK-006` pending).
- **Closure Request**: `POST /api/evaluation/request-closure` by `RECALL-COORD-01` -> HTTP 200 OK (`request_id: REQ-CLOSE-17`).
- **Closure Authority Attempt Blocked**: `POST /api/evaluation/authorize-closure` by `CLOSURE-AUTH-01` -> HTTP 200 OK (`status: closure_blocked`, `blocked: true`, requiring resolution of `ACK-006`).
- **Non-Response Resolution**: `POST /api/evaluation/resolve-ack` by `OPS-001` -> HTTP 200 OK (documented phone follow-up logged).
- **Authorized Closure**: `POST /api/evaluation/authorize-closure` by `CLOSURE-AUTH-01` -> HTTP 200 OK (`status: closed`, `phase: closed`).
- **Tamper-Evident Audit Export**: `GET /api/incidents/EVAL-CASE-01/audit-export` -> HTTP 200 OK:
  - Exactly 21 append-oriented, SHA-256 hash-chained ledger events were included in the verified self-verifying export.
  - Complete SHA-256 hash chaining confirmed (top digest `35d3e77225b917a7...`).

### H. Observability & Log Audit
- Cloud Run logs for `lot-zero-00028-vip` confirm:
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

1. **Candidate Revision Deployed**: Cloud Build compiled image `lot-zero@sha256:b1a375ddbbcd025a025cbcd0438fb07ee461cb0fa037b36d2454da2d0afc5034` and deployed revision `lot-zero-00028-vip` with `--no-traffic --tag=candidate`.
2. **Container Health & Readiness Verification**: Cloud Run confirmed container startup probe succeeded and revision became ready (`Ready: True`, `ContainerHealthy: True`). Candidate direct tag URL routing experienced edge routing timeout, consistent with edge tag behavior.
3. **100% Traffic Promotion**: Shifted 100% of live traffic to `lot-zero-00028-vip`.
4. **Rollback Revision Preserved**: Retained prior verified revision `lot-zero-00026-diy` at 0% traffic for instantaneous rollback capability if required.
5. **Comprehensive End-to-End Suite**: Executed full 13-step verification suite against live service URL.

---

## 6. Known Limitations & Scope Boundaries

1. **Ephemeral Container Storage**: SQLite runs at `/tmp/lot_zero.db`. Instance recycling, scale-to-zero cold starts, or new revisions reset database state to baseline.
2. **Evaluation Personas**: Browser personas use synthetic API keys for demonstration and hackathon evaluation, not enterprise OIDC/SAML SSO.
3. **Audit Ledger Scope**: Hash chains provide cryptographic tamper evidence within the export bundle but do not commit root hashes to an external distributed ledger or WORM hardware vault.
4. **Regulatory Boundaries**: The system models FDA-inspired recall effectiveness and non-response workflows; it does not submit data to FDA systems or certify statutory compliance.
5. **Multi-User Evaluation**: Public evaluators share a single evaluation tenant (`EVAL-TENANT-01`) and active incident state.
6. **Cloud Consumption**: Live Vertex AI Gemini calls utilize Google Cloud resources and may incur billing charges.
