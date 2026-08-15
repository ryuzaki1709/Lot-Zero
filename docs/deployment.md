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
# 1. Create and populate GEMINI_API_KEY secret (prompted from your Google AI Studio key)
echo -n "<YOUR_GEMINI_API_KEY>" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy="automatic"

# 2. Create and populate LOT_ZERO_SSE_SECRET (random 32-byte hex secret)
echo -n "$(openssl rand -hex 32)" | gcloud secrets create lot-zero-sse-secret \
    --data-file=- \
    --replication-policy="automatic"

# Grant Secret Accessor role to Cloud Run service account
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding lot-zero-sse-secret \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 3.4 — Deploy Service to Google Cloud Run

```bash
# Deploy directly from source via Cloud Build with GCS volume mount and Secret Manager bindings
gcloud run deploy lot-zero \
    --source=. \
    --region=${REGION} \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --set-env-vars="LOT_ZERO_DB_PATH=/app/data/lot_zero.db,LOT_ZERO_TENANT_ID=EVAL-TENANT-01" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,LOT_ZERO_SSE_SECRET=lot-zero-sse-secret:latest" \
    --add-volume=name=event-store-vol,type=cloud-storage,bucket=lot-zero-events-${PROJECT_ID} \
    --add-volume-mount=volume=event-store-vol,mount-path=/app/data
```

---

## 4. Post-Deployment Verification & Proof Capture

### Step 4.1 — Remote Smoke Test & Cryptographic Audit Verification

Run the automated verification script against the deployed service URL:

```bash
python scripts/verify_cloud_deploy.py <DEPLOYED_SERVICE_URL>
```

#### Captured Verification Output (To be populated upon live deployment)

```text
[Expected output after executing verify_cloud_deploy.py against live Cloud Run URL]
- SPA static asset hosting on Cloud Run: HTTP 200 (serves index.html)
- Incident state baseline reset: HTTP 200
- Gemini 3.5 Flash signal extraction: HTTP 200 (live citation spans & model descriptor)
- Separation of Duties enforcement: HTTP 403 Forbidden on wrong-role approval
- Authorized QA Lead quarantine approval: HTTP 200
- Recall notification outbox dispatch: HTTP 200
- Cryptographic audit export bundle: 100% verified SHA-256 hash chain and top-level root digest
```

---

## 5. Live Cloud Run Revision & Logs Inspection

### Step 5.1 — Inspect Deployed Revision

```bash
gcloud run services describe lot-zero \
    --region=${REGION} \
    --format="yaml(status.url, status.latestCreatedRevisionName, status.conditions)"
```

### Step 5.2 — Inspect Gemini 3.5 Live Execution Logs

```bash
gcloud logging read \
    'resource.type="cloud_run_revision" AND resource.labels.service_name="lot-zero"' \
    --limit=20 \
    --format="table(timestamp, textPayload, httpRequest.status)"
```

---

## 6. Security & Separation of Duties Audit

- **Evaluation Credentials**: Pre-configured demo evaluation API keys (`key-qa-lead-01`, `key-recall-coord-01`, `key-ops-01`, `key-closure-auth-01`) enable hackathon evaluators to test role-switching and multi-signature authorization immediately from the header UI.
- **Production Key Isolation**: In production, custom keys and tenants are loaded dynamically via the `LOT_ZERO_API_KEYS` environment variable or Cloud Secret Manager.
- **Ephemeral SSE Tokens**: The browser EventSource connects via short-lived (60s) HMAC-SHA256 tokens minted by `POST /api/sse-token`, preventing long-lived URL key leakage in browser history or proxy logs.
