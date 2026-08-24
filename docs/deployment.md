# Lot Zero — Deployment Guide & Environment Specification

This guide outlines deployment options for **Lot Zero**, covering local development, Google Cloud Run evaluation deployment, and considerations for hypothetical production deployments.

> [!CAUTION]
> **Security Notice**: Never commit API keys, service account credentials, or secrets into source control or configuration files.

---

## 1. Environment Variable Reference

The application runtime reads the following environment variables:

| Variable Name | Required in Prod | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `LOT_ZERO_EVALUATION_MODE` | No | `false` | Set to `"true"` to enable evaluation persona switcher, demo keys, and reset endpoints. |
| `LOT_ZERO_DB_PATH` | No | `lot_zero.db` | Path to SQLite database file (e.g. `/tmp/lot_zero.db` or `./lot_zero.db`). |
| `LOT_ZERO_TENANT_ID` | No | `EVAL-TENANT-01` | Active evaluation tenant identifier. |
| `LOT_ZERO_SSE_SECRET` | Yes (in Prod) | `""` (or default in eval) | Secret string ($\ge 32$ chars) used to HMAC-sign ephemeral SSE subscription tokens. |
| `LOT_ZERO_API_KEYS` | Yes (in Prod) | `None` | JSON string mapping API keys to principal records. |
| `LOT_ZERO_ALLOWED_ORIGINS` | Yes (in Prod) | `[]` (or localhost in eval) | Comma-separated list of allowed CORS origins. |
| `GOOGLE_GENAI_USE_VERTEXAI`| No | `false` | Set to `"true"` to enable live Vertex AI Gemini API calls via `google-genai` when configured. |
| `GOOGLE_CLOUD_PROJECT` | If Vertex AI | `""` | Google Cloud project ID for Vertex AI access. |
| `GOOGLE_CLOUD_LOCATION` | No | `global` | Vertex AI model location. |
| `GEMINI_API_KEY` | No | `""` | API key for Google GenAI Studio fallback. |

---

## 2. Deployment Tiers

### Tier 1: Local Development & Evaluation (PowerShell)
Runs locally with in-memory or file-backed SQLite:
```powershell
# 1. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Build Vite frontend bundle
cd apps\web
npm ci
npm run build
cd ..\..

# 3. Start FastAPI server with evaluation mode enabled
$env:LOT_ZERO_EVALUATION_MODE = "true"
$env:LOT_ZERO_DB_PATH = "lot_zero.db"
.\.venv\Scripts\python.exe -m uvicorn lot_zero.app:app --host 127.0.0.1 --port 8000 --app-dir apps/api/src
```

---

### Tier 2: Public Evaluation Deployment (Google Cloud Run)
In evaluation mode, Lot Zero is packaged for deployment as a single-instance container on Google Cloud Run using local container storage.

#### Key Architectural Requirements on Cloud Run:
- **Maximum Instances (`--max-instances=1`)**: To ensure atomic state management and single-process SQLite locking without multi-instance split-brain concurrency.
- **Ephemeral Storage**: Uses local container storage (e.g. `/tmp/lot_zero.db`). State resets when a new revision deploys or after instance recycling; the Evaluation Admin persona can establish a clean baseline at any time.
- **Health Check Endpoint**: `/healthz` provides an unauthenticated liveness probe returning `{"status": "ok"}`.

#### Deployment Commands:
```bash
# Deploy container to Google Cloud Run with environment configuration
gcloud run deploy lot-zero \
    --source=. \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --set-env-vars="LOT_ZERO_EVALUATION_MODE=true,LOT_ZERO_DB_PATH=/tmp/lot_zero.db,LOT_ZERO_TENANT_ID=EVAL-TENANT-01,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,LOT_ZERO_SSE_SECRET=YOUR_STRONG_RANDOM_SSE_SECRET_MIN_32_CHARS"
```

*(Note: In production environments, secret environment variables like `LOT_ZERO_SSE_SECRET` should optionally be mounted from Google Cloud Secret Manager using `--set-secrets` rather than `--set-env-vars`.)*

#### Health Check Verification:
```bash
curl -f https://lot-zero-YOUR_RUN_URL.run.app/healthz
# Returns: {"status":"ok"}
```

---

### Tier 3: Hypothetical Enterprise Production Deployment
For commercial food manufacturing deployment in a regulated environment:

1. **Identity & Access Management (IAM)**:
   - Disable evaluation mode (`LOT_ZERO_EVALUATION_MODE=false`).
   - Configure `LOT_ZERO_API_KEYS` mapping or integrate with enterprise Okta/Azure AD SAML or OIDC OAuth2 Bearer tokens.
2. **Distributed Event Store**:
   - Replace file-backed SQLite with a managed distributed transactional database (e.g. Google Cloud SQL PostgreSQL or Google Cloud Spanner).
3. **Multi-Worker Concurrency**:
   - Replace single-process `asyncio.Lock` with distributed optimistic concurrency leases and Redis Pub/Sub for SSE event distribution across autoscaling container instances.
4. **Immutable WORM Audit Vault**:
   - Configure continuous export of closed case audit bundles to Google Cloud Storage with Bucket Lock (Object Retention in Compliance mode).
