# Google Cloud Run Deployment & Proof Pack Guide

This document details the deployment process for **Lot Zero** on **Google Cloud Run**, integrating **Google Cloud Storage (GCS FUSE)** for append-only SQLite persistence, **Google Cloud Secret Manager** for runtime secrets, and **Gemini 3.5 Flash** via the official Google GenAI SDK.

---

## 1. System Architecture

![Lot Zero Architecture](architecture.png)

| Service | Role | Hackathon Qualification |
|---|---|---|
| **Google Cloud Run** | Multi-stage container hosting FastAPI backend + Vite React SPA | Primary compute service (0–1 auto-scaling instance, 512MiB RAM) |
| **Google Cloud Storage (GCS FUSE)** | Mounted persistent volume at `/app/data` holding `lot_zero.db` | Secondary GCP infrastructure service for event-sourced persistence |
| **Google Cloud Secret Manager** | Secure injection of `GEMINI_API_KEY` and `LOT_ZERO_SSE_SECRET` | Regulated secrets hygiene (zero keys committed in image or repo) |
| **Gemini 3.5 Flash** (`google-genai`) | Multimodal laboratory notice signal extraction and citation grounding | Core GenAI model qualification (Gemini 3.5+) |

---

## 2. Concurrency Safety & Scaling Architecture

> [!IMPORTANT]
> **Single-Writer Design & Cloud Run Concurrency Note**:
> Google Cloud Storage FUSE provides object-backed storage without POSIX file-level write locking. Concurrently running multiple Cloud Run instances writing to the same SQLite database file over GCS FUSE can cause database lock contention or corruption.
>
> Therefore, Cloud Run is deployed with `--max-instances=1` by design for this demo architecture.
>
> **Production Upgrade Path**: The backend repository architecture is abstracted behind the `SqliteIncidentRepository` interface (`apps/api/src/lot_zero/adapters/sqlite_repository.py`). In high-concurrency production environments requiring horizontal scaling across multiple container instances, the persistence layer seamlessly switches to **Cloud SQL (PostgreSQL)** with row-level locking or Spanner, while preserving the exact same domain events, reducers, and optimistic concurrency semantics.

---

## 3. Step-by-Step Google Cloud Deployment Commands

### Step 3.1 — Enable Required Google Cloud APIs

```bash
# Set your GCP Project ID
export PROJECT_ID="project-b2c3348e-d718-4255-be2"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

# Enable Cloud Run, Secret Manager, Cloud Storage, and Cloud Build
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com
```

### Step 3.2 — Provision Cloud Storage Bucket for Event Store Persistence

```bash
# Create a dedicated Cloud Storage bucket in us-central1
gcloud storage buckets create gs://lot-zero-events-${PROJECT_ID} \
    --location=${REGION} \
    --uniform-bucket-level-access

# Grant Cloud Run default compute service account permission to read/write the bucket
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud storage buckets add-iam-policy-binding gs://lot-zero-events-${PROJECT_ID} \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### Step 3.3 — Create Secrets in Google Cloud Secret Manager

```bash
# 1. Create and populate LOT_ZERO_SSE_SECRET (random 32-byte hex secret)
echo -n "$(openssl rand -hex 32)" | gcloud secrets create lot-zero-sse-secret \
    --data-file=- \
    --replication-policy="automatic"

# 2. Grant Secret Accessor role on lot-zero-sse-secret to Cloud Run compute service account
gcloud secrets add-iam-policy-binding lot-zero-sse-secret \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# 3. Grant Vertex AI user role for enterprise Gemini 3.5 ADC authentication
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### Step 3.4 — Deploy Service to Google Cloud Run

```bash
# Deploy directly from source via Cloud Build with GCS volume mount, Vertex AI ADC, and Secret Manager bindings
gcloud run deploy lot-zero \
    --source=. \
    --region=${REGION} \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --set-env-vars="LOT_ZERO_DB_PATH=/app/data/lot_zero.db,LOT_ZERO_TENANT_ID=EVAL-TENANT-01,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=project-b2c3348e-d718-4255-be2,GOOGLE_CLOUD_LOCATION=global" \
    --set-secrets="LOT_ZERO_SSE_SECRET=lot-zero-sse-secret:latest" \
    --add-volume=name=event-store-vol,type=cloud-storage,bucket=lot-zero-events-${PROJECT_ID} \
    --add-volume-mount=volume=event-store-vol,mount-path=/app/data
```

---

## 4. Post-Deployment Verification & Proof Capture

### Step 4.1 — Remote Smoke Test & Cryptographic Audit Verification

Run the automated verification script against the deployed service URL:

```bash
python scripts/verify_cloud_deploy.py https://lot-zero-1051797806634.us-central1.run.app
```

#### Genuine Live Verification Output

```text
================================================================
 LOT ZERO CLOUD RUN SMOKE TEST & PROOF VERIFICATION
 Target Service: https://lot-zero-1051797806634.us-central1.run.app
================================================================

1. Checking SPA static asset hosting on Cloud Run...
   [PASS] Root SPA serves bundled Vite frontend.
2. Resetting incident state to baseline...
   [PASS] Reset incident state.
3. Executing safety signal extraction via Gemini on Vertex AI...
   [PASS] Gemini Model: gemini-3.5-flash (Vertex AI Live)
4. Testing Separation of Duties (wrong-role denial)...
   -> Status Code: 403, Detail: requester and approver must be different people
   [PASS] Server enforced 403 refusal on unauthorized role.
5. Submitting authorized QA Lead quarantine approval...
   [PASS] QA Lead quarantine authorized.
6. Customer Operations dispatches recall outbox...
   [PASS] Recall notices dispatched.
7. Exporting cryptographic audit bundle and verifying hash chain...
   -> Total Ledger Entries: 11
   -> Top-Level Digest: c318bea41096cf485e1fde7fbc26f2f34d85b029325d3610373cfcae25ae6ff9
   [PASS] Cryptographic audit hash chain 100% verified.

================================================================
 ALL CLOUD RUN DEPLOYMENT CHECKS & PROOFS PASSED!
================================================================
```

---

## 5. Live Cloud Run Revision & Logs Inspection

### Step 5.1 — Deployed Service Description

```text
+ Service lot-zero in region us-central1
 
URL:     https://lot-zero-1051797806634.us-central1.run.app
Ingress: all
Traffic: 100% LATEST (currently lot-zero-00007-2fk)
Scaling: Auto (Min: 0, Max: 1)

Image: us-central1-docker.pkg.dev/project-b2c3348e-d718-4255-be2/cloud-run-source-deploy/lot-zero@sha256:6ef8e74e47cf7a1a0c8b3ebf2bf05ef343274291f03f7e6f85fa3240e94bb10b
Port: 8080 | Memory: 512Mi | CPU: 1
Volume Mounts:
  /app/data -> event-store-vol (GCS Bucket: lot-zero-events-project-b2c3348e-d718-4255-be2)
Secrets:
  LOT_ZERO_SSE_SECRET -> lot-zero-sse-secret:latest
Env Vars:
  GOOGLE_GENAI_USE_VERTEXAI: true
  GOOGLE_CLOUD_PROJECT: project-b2c3348e-d718-4255-be2
  GOOGLE_CLOUD_LOCATION: global
```

### Step 5.2 — Live Execution Logs Snippet

```text
2026-08-16T09:10:04Z  INFO: GET / HTTP/1.1 200 OK
2026-08-16T09:10:05Z  INFO: POST /api/evaluation/reset HTTP/1.1 200 OK
2026-08-16T09:10:13Z  [Gemini Agent] Successfully executed live on Vertex AI (location=global, model=gemini-3.5-flash)
2026-08-16T09:10:14Z  INFO: POST /api/evaluation/simulate-signal HTTP/1.1 200 OK
2026-08-16T09:10:14Z  INFO: POST /api/evaluation/approve-containment HTTP/1.1 403 Forbidden
2026-08-16T09:10:15Z  INFO: POST /api/evaluation/approve-containment HTTP/1.1 200 OK
2026-08-16T09:10:15Z  INFO: POST /api/evaluation/dispatch-outbox HTTP/1.1 200 OK
2026-08-16T09:10:16Z  INFO: GET  /api/cases/EVAL-CASE-01/audit-export HTTP/1.1 200 OK
```

---

## 6. Security & Separation of Duties Audit

- **Evaluation Credentials**: Pre-configured demo evaluation API keys (`key-qa-lead-01`, `key-recall-coord-01`, `key-ops-01`, `key-closure-auth-01`) enable hackathon evaluators to test role-switching and multi-signature authorization immediately from the header UI.
- **Production Key Isolation**: In production, custom keys and tenants are loaded dynamically via the `LOT_ZERO_API_KEYS` environment variable or Cloud Secret Manager.
- **Ephemeral SSE Tokens**: The browser EventSource connects via short-lived (60s) HMAC-SHA256 tokens minted by `POST /api/sse-token`, preventing long-lived URL key leakage in browser history or proxy logs.
