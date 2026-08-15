# Lot Zero — Evidence-Backed Food Safety Recall Incident Workspace

> **Disciplined, Deterministic Event-Sourced Recall Incident Workspace**  
> *Built with Google GenAI SDK (Gemini), Append-Only SQLite Event Store, Strict Role-Based Authority Kernel, FastAPI, and React Dashboard.*

---

## 1. Product & Architecture Overview

**Lot Zero** converts incoming safety signals (e.g., laboratory Salmonella contamination reports) into an auditable, tamper-evident incident management process:

![Lot Zero System Architecture](docs/architecture.png)

### Core Architectural Pillars

1. **Deterministic Domain Kernel & Authenticity Reducer** ([`kernel.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/domain/kernel.py), [`reducer.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/domain/reducer.py)):
   - The reducer never invents quantities, recipients, hashes, or statuses.
   - Graph traversal from contaminated ingredient `ING-4417` through manufactured finished batches `FP-100-L240814-A` and `B` (200 total units) is 100% deterministic with 0% AI hallucination on operational math.

2. **Append-Only SQLite Event Store** ([`sqlite_repository.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/adapters/sqlite_repository.py)):
   - Append-only `incident_events` table with schema `UNIQUE(tenant_id, case_id, stream_version)`.
   - Optimistic concurrency control via `expected_version` checks.
   - Deterministic state rehydration upon restart.

3. **Fast Read-Model Projections** ([`projections.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/domain/projections.py)):
   - Projects open holds, pending QA approvals, and refusal-blocked cases directly from `incident_events` without loading full domain aggregates.

4. **Dual-Signature Release Rail & § 7.49 Non-Response Closure**:
   - **Step 1:** QA Lead Biological Clearance (verifies negative re-test documentation hash).
   - **Step 2:** Distinct Closure Authority Operational Release.
   - **Non-Response Closure:** Strict FDA 21 CFR § 7.49 regulatory referral path requiring $\ge 3$ documented contact attempts and district office escalation notes.

5. **Cryptographic Tamper-Evident Audit Export** ([`audit_export.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/domain/audit_export.py)):
   - Exports the entire ordered event log for a case with a SHA-256 hash chain (`prior_entry_hash == previous.entry_hash`) and a top-level root digest.
   - Detects any payload edits, omitted events, reordered entries, or forged digests.

---

## 2. Authentication, Authorization & Security

All API endpoints strictly require authentication via the `X-API-Key` header. Principal identities, roles, and tenant scopes are derived server-side from [`auth.py`](file:///C:/Users/sujan%20reddy/Documents/john/lot-zero/apps/api/src/lot_zero/auth.py).

### Evaluation API Keys & Roles

| Principal ID | Role | Evaluation API Key | Permissions |
| :--- | :--- | :--- | :--- |
| `RECALL-COORD-01` | `recall_coordinator` | `key-recall-coord-01` | Signal simulation, propose scope, request holds |
| `QA-LEAD-01` | `qa` | `key-qa-lead-01` | Approve scope/containment, Step 1 biological clearance |
| `OPS-01` | `operations` | `key-ops-01` | Consignee notification dispatch, acknowledgement recording |
| `CLOSURE-AUTH-01` | `closure_authority` | `key-closure-auth-01` | Step 2 operational release, § 7.49 non-response closure |
| `AGENT-SVC-01` | `agent_service` | `key-agent-svc-01` | Background event ingestion & safety signals |

> [!WARNING]
> **Production Security Note**:
> The UI includes a client-side **Caller Key / Role Switcher** designed strictly for local evaluation and interactive demonstration. In production deployments, API keys must **never** be shipped in frontend JavaScript bundles; they must be replaced with server-issued sessions, OAuth2, or OIDC tokens.

---

## 3. API Endpoint Reference

### Read Models & Projections
- `GET /api/projections/cases` — List projected case summaries (filters: `all`, `open_holds`, `pending_qa`, `blocked_by_rejections`).
- `GET /api/projections/cases/open-holds` — Filter cases with active unreleased holds.
- `GET /api/projections/cases/pending-qa` — Filter cases awaiting QA sign-off.
- `GET /api/projections/cases/blocked-by-rejections` — Filter cases blocked by consignee refusals.

### Aggregate & Live State
- `GET /api/incidents/{case_id}` — Rehydrated aggregate projection with access auditing.
- `GET /api/incidents/{case_id}/events` — Server-Sent Events (SSE) live stream.

### Cryptographic Audit Export
- `GET /api/cases/{case_id}/audit-export` — Tamper-evident hash-chained event stream with root digest.

### Lifecycle Actions
- `POST /api/evaluation/simulate-signal` — Ingest lab signal and trigger Gemini agent.
- `POST /api/evaluation/approve-containment` — QA sign-off for firm quarantine.
- `POST /api/evaluation/dispatch-outbox` — Dispatch consignee recall notifications.
- `POST /api/evaluation/resolve-ack` — Record distributor acknowledgement.
- `POST /api/evaluation/release-hold/step` — Dual-signature release step (QA step 1, Closure Authority step 2).
- `POST /api/evaluation/close-with-non-response` — FDA § 7.49 non-response regulatory escalation.
- `POST /api/evaluation/reset` — Clean evaluation baseline reset.

---

## 4. Quick Start Guide

### 1. Launch Backend API Server
```powershell
cd apps/api
& .venv/Scripts/python.exe -m uvicorn lot_zero.app:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Launch Web Dashboard
```powershell
cd apps/web
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 5. Google Cloud Deployment (Cloud Run + GCS FUSE + Secret Manager)

Lot Zero runs in a single unified multi-stage container on **Google Cloud Run**, mounting **Google Cloud Storage (GCS FUSE)** for persistent event sourcing and utilizing **Secret Manager** for credential hygiene.

For full GCP deployment commands and the video proof pack, see [docs/deployment.md](docs/deployment.md).

```bash
# Deploy to Google Cloud Run (us-central1) with GCS Volume Mount and Secret Manager
gcloud run deploy lot-zero \
    --source=. \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --set-env-vars="LOT_ZERO_DB_PATH=/app/data/lot_zero.db,LOT_ZERO_TENANT_ID=EVAL-TENANT-01" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,LOT_ZERO_SSE_SECRET=lot-zero-sse-secret:latest" \
    --add-volume=name=event-store-vol,type=cloud-storage,bucket=lot-zero-events-production \
    --add-volume-mount=volume=event-store-vol,mount-path=/app/data
```

Verify the live deployment with the smoke-test script:
```bash
python scripts/verify_cloud_deploy.py <DEPLOYED_SERVICE_URL>
```

---

## 6. Automated Test Suite

Run the full pytest suite (119 tests covering contracts, SQLite optimistic concurrency, replay equivalence, tenant isolation, dual-signature release, HMAC SSE stream tokens, and audit tamper detection):

```powershell
cd apps/api
& .venv/Scripts/python.exe -m pytest tests/
```
```
======================= 119 passed, 1 warning in 1.00s =======================
```

Build the web application:
```powershell
cd apps/web
npm run build
```
```
✓ built in 1.09s (0 errors)
```
