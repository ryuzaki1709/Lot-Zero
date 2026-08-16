# Lot Zero — Devpost Hackathon Submission

## Project Title
**Lot Zero: Deterministic, Evidence-Backed Food Recall Incident Workspace**

## Tagline
An industrial-grade, event-sourced recall workspace powered by Gemini 3.5 on Vertex AI, strict Separation of Duties, and tamper-evident cryptographic audit chains.

---

## 1. Inspiration & Problem Statement
In regulated industries like food manufacturing and pharmaceuticals, product recalls are high-stakes, time-critical events governed by federal regulations (such as **FDA 21 CFR § 7.49**). 

Today, recall management suffers from three systemic vulnerabilities:
1. **Unverifiable AI Hallucinations**: Standard LLM wrappers generate unverifiable summaries and hallucinate inventory quantities or disposition statuses.
2. **Authorization & Collision Failures**: In the chaos of an active incident, organizational hierarchy is often bypassed, leading to conflicts of interest where the requester of a quarantine signs off on their own scope.
3. **Malleable Audit Records**: Post-incident regulatory audits rely on mutable database rows and disparate PDF exports that offer no cryptographic proof against tampering, reordering, or omission.

**Lot Zero** was engineered from first principles to solve these challenges: a disciplined workspace where **Gemini 3.5 Flash** performs multimodal signal extraction grounded in source citations, while an immutable **event-sourced authority kernel** guarantees deterministic arithmetic, strict role boundaries, and hash-chained cryptographic auditability.

---

## 2. What Lot Zero Does

Lot Zero converts raw laboratory contamination notices into a provably correct, compliant recall workflow:

- **Multimodal Signal Extraction with Bounding Citations**: Ingests raw lab reports (e.g., Salmonella detection) using **Gemini 3.5 Flash** on **Vertex AI**, extracting contaminated lot IDs and exact character-offset citation spans bound to the source document's SHA-256 digest.
- **Strict Separation of Duties Authority Kernel**: Server-enforced role gates reject unauthorized actions with HTTP 403. A Recall Coordinator cannot approve their own quarantine; firm quarantine sign-off requires an independent QA Lead.
- **Dynamic Lot Genealogy DAG**: Visualizes the upstream and downstream flow of contaminated raw materials (`ING-4417`), automatically quarantining affected finished goods (`FP-A` and `FP-B`) while unblocking negative control batches (`FP-C`).
- **21 CFR § 7.49 Dual-Signature Release Rail**:
  - *Step 1*: QA Lead Biological Clearance (mandating negative laboratory re-test hash verification).
  - *Step 2*: Closure Authority Operational Release (with mandatory tracking of consignee contact attempts and district office escalations).
- **Tamper-Evident SHA-256 Audit Export**: Generates self-verifying JSON audit bundles where every event is cryptographically chained to its predecessor with a top-level root digest, immediately exposing any record tampering, omission, or reordering.
- **Real-Time Reactive Cockpit**: Features an ultra-premium dark slate interface (Linear/Vercel benchmark) powered by Server-Sent Events (SSE) with 60-second HMAC-signed ephemeral token authentication.

---

## 3. How We Built It (Google Cloud & Technology Stack)

Lot Zero is built on a full-stack, enterprise-grade architecture utilizing **4 Google Cloud services**:

```
+---------------------------------------------------------------------------------------+
|                                    GOOGLE CLOUD RUN                                   |
|  +-----------------------------------+     +---------------------------------------+  |
|  |       React SPA (Vite Bundle)     | <-> |          FastAPI Domain Router        |  |
|  | - Role Cockpit (4 Actor Personas) |     | - Separation of Duties Kernel         |  |
|  | - Dual-Signature Release Rail     |     | - Deterministic Reducer Engine        |  |
|  | - Live SSE Stream Subscriber      |     | - Real-Time SSE Hub (HMAC Tokens)     |  |
|  +-----------------------------------+     +---------------------------------------+  |
+---------------------------------------------------------------------------------------+
           |                                             |                      |
           v                                             v                      v
+-----------------------+                    +--------------------+   +-------------------+
|  GOOGLE VERTEX AI     |                    | GOOGLE CLOUD GCS   |   | SECRET MANAGER    |
| - Gemini 3.5 Flash    |                    | - GCS FUSE Mount   |   | - LOT_ZERO_SSE_   |
| - Application Default |                    | - SQLite Event     |   |   SECRET          |
|   Credentials (ADC)   |                    |   Store Persistent |   +-------------------+
+-----------------------+                    +--------------------+
```

1. **Google Cloud Run**: Hosts the unified container running the FastAPI backend and static SPA frontend with 0–1 auto-scaling and single-writer concurrency safety.
2. **Google Vertex AI (`google-genai` SDK)**: Powers multimodal safety signal extraction using `gemini-3.5-flash` with enterprise Application Default Credentials (ADC).
3. **Google Cloud Storage (GCS FUSE)**: Mounts a persistent Cloud Storage bucket (`gs://lot-zero-events-...`) to `/app/data/lot_zero.db`, providing persistent append-only event sourcing across container restarts.
4. **Google Cloud Secret Manager**: Securely stores and injects runtime secrets (`LOT_ZERO_SSE_SECRET`) at container initialization with zero credentials committed to source code.

---

## 4. Challenges We Overcame

1. **Single-Writer Safety on GCS FUSE**: SQLite requires single-writer access because Cloud Storage FUSE does not implement POSIX file locking. We designed the Cloud Run deployment with `--max-instances=1` and encapsulated persistence behind the `SqliteIncidentRepository` interface, establishing a clean migration path to Cloud SQL (PostgreSQL) for multi-region scale.
2. **Enterprise Key Restrictions & ADC Migration**: When Google Cloud organizational policies disabled raw API keys, we refactored `gemini_agent.py` to seamlessly negotiate between Vertex AI Application Default Credentials (`genai.Client(vertexai=True)`) and local developer environments.
3. **Cryptographic Tamper-Evidence**: Ensuring offline verifiability without external dependencies by implementing canonical SHA-256 event hashing that validates sequence continuity, event payloads, and top-level digests.

---

## 5. Accomplishments & Verification

- **119 Automated Tests Passing**: Complete test suite covering contract schemas, SQLite optimistic concurrency, replay equivalence, tenant isolation, dual-signature gates, and 4 distinct cryptographic tamper vectors (omission, insertion, payload edits, fake digest).
- **100% Live Cloud Deployment**: Verified against the production Google Cloud Run endpoint ([`https://lot-zero-1051797806634.us-central1.run.app`](https://lot-zero-1051797806634.us-central1.run.app)).

---

## 6. What We Learned & What's Next

- **What We Learned**: Event-sourced domain design is the optimal pairing for generative AI in regulated spaces—AI proposes, but immutable deterministic kernels decide.
- **What's Next**:
  - Direct integration with FDA Electronic Submissions Gateway (ESG).
  - Multi-tenant Cloud SQL (Postgres) persistence for global manufacturing supply chains.
