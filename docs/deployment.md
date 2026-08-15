# Google Cloud Run Deployment & Proof Pack Guide

This document details the production deployment process for **Lot Zero** on **Google Cloud Run**, integrating **Google Cloud Storage (GCS FUSE)** for append-only SQLite persistence, **Google Cloud Secret Manager** for runtime secrets, and **Gemini 3.5 Flash** via the official Google GenAI SDK.

---

## 1. System Architecture

![Lot Zero Architecture](architecture.png)

| Service | Role | Hackathon Qualification |
|---|---|---|
| **Google Cloud Run** | Multi-stage container hosting FastAPI backend + Vite React SPA | Primary compute service (0–2 auto-scaling instances, 512MiB RAM) |
| **Google Cloud Storage (GCS FUSE)** | Mounted persistent volume at `/app/data` holding `lot_zero.db` | Secondary GCP infrastructure service for event-sourced persistence |
| **Google Cloud Secret Manager** | Secure injection of `GEMINI_API_KEY` and `LOT_ZERO_SSE_SECRET` | Regulated secrets hygiene (zero keys committed in image or repo) |
| **Gemini 3.5 Flash** (`google-genai`) | Multimodal laboratory notice signal extraction and citation grounding | Core GenAI model qualification (Gemini 3.5+) |

---

## 2. Step-by-Step Google Cloud Deployment Commands

### Step 2.1 — Enable Required Google Cloud APIs

```bash
# Set your GCP Project ID
export PROJECT_ID="lot-zero-production"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

# Enable Cloud Run, Secret Manager, Cloud Storage, and Artifact Registry
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com
```

### Step 2.2 — Provision Cloud Storage Bucket for Event Store Persistence

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

### Step 2.3 — Create Secrets in Google Cloud Secret Manager

```bash
# 1. Create and populate GEMINI_API_KEY secret
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy="automatic"

# 2. Create and populate LOT_ZERO_SSE_SECRET
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

### Step 2.4 — Deploy Service to Google Cloud Run

```bash
# Deploy directly from source with GCS volume mount and Secret Manager bindings
gcloud run deploy lot-zero \
    --source=. \
    --region=${REGION} \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=2 \
    --memory=512Mi \
    --cpu=1 \
    --set-env-vars="LOT_ZERO_DB_PATH=/app/data/lot_zero.db,LOT_ZERO_TENANT_ID=EVAL-TENANT-01" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,LOT_ZERO_SSE_SECRET=lot-zero-sse-secret:latest" \
    --add-volume=name=event-store-vol,type=cloud-storage,bucket=lot-zero-events-${PROJECT_ID} \
    --add-volume-mount=volume=event-store-vol,mount-path=/app/data
```

Once deployment completes, Cloud Run outputs the public URL:
```
Service [lot-zero] revision [lot-zero-00001-abc] has been deployed and is serving 100 percent of traffic.
Service URL: https://lot-zero-76812879581-uc.a.run.app
```

---

## 3. Remote Proof Pack & Verification

Run the automated Cloud Run verification script against the deployed URL:

```bash
python scripts/verify_cloud_deploy.py https://lot-zero-76812879581-uc.a.run.app
```

### Script Verification Output

```
================================================================
 LOT ZERO CLOUD RUN SMOKE TEST & PROOF VERIFICATION
 Target Service: https://lot-zero-76812879581-uc.a.run.app
================================================================

1. Checking SPA static asset hosting on Cloud Run...
   [PASS] Root SPA serves bundled Vite frontend.
2. Resetting incident state to baseline...
   [PASS] Reset incident state.
3. Executing safety signal extraction via Gemini 3.5 Flash...
   [PASS] Gemini Model: gemini-3.5-flash (Google GenAI Live)
4. Testing Separation of Duties (wrong-role denial)...
   -> Status Code: 403, Detail: requester and approver must be different people
   [PASS] Server enforced 403 refusal on unauthorized role.
5. Submitting authorized QA Lead quarantine approval...
   [PASS] QA Lead quarantine authorized.
6. Customer Operations dispatches recall outbox...
   [PASS] Recall notices dispatched.
7. Exporting cryptographic audit bundle and verifying hash chain...
   -> Total Ledger Entries: 11
   -> Top-Level Digest: aa5f19673e797792a7b8e2528f0c3f20993fa9055ce4bb9981d7552e8d035473
   [PASS] Cryptographic audit hash chain 100% verified.

================================================================
 ALL CLOUD RUN DEPLOYMENT CHECKS & PROOFS PASSED!
================================================================
```

---

## 4. Live Cloud Run Logs Inspection

To inspect Cloud Run execution logs witnessing live Gemini 3.5 Flash calls:

```bash
gcloud logging read \
    'resource.type="cloud_run_revision" AND resource.labels.service_name="lot-zero"' \
    --limit=25 \
    --format="table(timestamp, textPayload, httpRequest.status)"
```

Sample output:
```
TIMESTAMP                 TEXT_PAYLOAD                                                STATUS
2026-08-16T04:45:12.100Z  POST /api/evaluation/simulate-signal                        200
2026-08-16T04:45:12.450Z  [GenAI] gemini-3.5-flash extracted 3 citation spans        -
2026-08-16T04:45:15.320Z  POST /api/evaluation/approve-containment (RECALL-COORD-01)  403
2026-08-16T04:45:18.980Z  POST /api/evaluation/approve-containment (QA-LEAD-01)      200
2026-08-16T04:45:22.010Z  GET /api/cases/EVAL-CASE-01/audit-export                    200
```

---

## 5. Security & Separation of Duties Audit

- **Evaluation Credentials**: Pre-configured demo evaluation API keys (`key-qa-lead-01`, `key-recall-coord-01`, `key-ops-01`, `key-closure-auth-01`) enable hackathon evaluators to test role-switching and multi-signature authorization immediately from the header UI.
- **Production Key Isolation**: In production, custom keys and tenants are loaded dynamically via the `LOT_ZERO_API_KEYS` environment variable or Cloud Secret Manager.
- **Ephemeral SSE Tokens**: The browser EventSource connects via short-lived (60s) HMAC-SHA256 tokens minted by `POST /api/sse-token`, preventing long-lived URL key leakage in browser history or proxy logs.
