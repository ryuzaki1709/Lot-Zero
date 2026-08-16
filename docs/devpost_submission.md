# Lot Zero — Devpost Hackathon Submission

## Project Information
- **Project Title**: Lot Zero: Deterministic, Evidence-Backed Food Recall Incident Workspace
- **Tagline**: An industrial-grade, event-sourced recall workspace powered by Gemini 3.5 on Vertex AI, strict Separation of Duties, and tamper-evident cryptographic audit chains.
- **Hackathon Category**: The Taskmaster
- **Live Cloud Run URL**: [https://lot-zero-1051797806634.us-central1.run.app](https://lot-zero-1051797806634.us-central1.run.app)
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **Local Spin-Up Instructions**: See [README.md](../README.md) for full local and container instructions.

---

## 1. Inspiration & Problem Statement
In regulated industries like food manufacturing and pharmaceuticals, product recalls are high-stakes, time-critical events governed by federal regulations (such as **FDA 21 CFR § 7.49**). 

Today, recall management suffers from three systemic vulnerabilities:
1. **Unverifiable AI Hallucinations**: Standard LLM wrappers generate unverifiable summaries and hallucinate inventory quantities or disposition statuses.
2. **Authorization & Collision Failures**: In the chaos of an active incident, organizational hierarchy is often bypassed, leading to conflicts of interest where the requester of a quarantine signs off on their own scope.
3. **Malleable Audit Records**: Post-incident regulatory audits rely on mutable database rows and disparate PDF exports that offer no cryptographic proof against tampering, reordering, or omission.

**Lot Zero** was engineered from first principles to solve these challenges: a disciplined workspace where **Gemini 3.5 Flash** performs grounded extraction with character-offset citations bound to the document SHA-256, while an immutable **event-sourced authority kernel** guarantees deterministic arithmetic, strict role boundaries, and hash-chained cryptographic auditability.

---

## 2. What Lot Zero Does

Lot Zero converts raw laboratory contamination notices into a provably correct, compliant recall workflow:

- **Grounded Extraction with Character-Offset Citations Bound to Document SHA-256**: Ingests raw lab reports (e.g., Salmonella detection) using **Gemini 3.5 Flash** on **Vertex AI**, extracting contaminated lot IDs and exact character-offset citation spans bound to the source document's SHA-256 digest.
- **Strict Separation of Duties Authority Kernel**: Server-enforced role gates reject unauthorized actions with HTTP 403. A Recall Coordinator cannot approve their own quarantine; firm quarantine sign-off requires an independent QA Lead.
- **Dynamic Lot Genealogy DAG**: Visualizes the upstream and downstream flow of contaminated raw materials (`ING-4417`), automatically quarantining affected finished goods (`FP-100-L240814-A` and `FP-100-L240814-B`, 200 units total) while unblocking negative control batches (`FP-100-ADJ` derived from clean raw lot `ING-4418`).
- **21 CFR § 7.49 Dual-Signature Release Rail**:
  - *Step 1*: QA Lead Biological Clearance (mandating negative laboratory re-test hash verification).
  - *Step 2*: Closure Authority Operational Release (with mandatory verification of disposition and regulatory notifications).
- **Tamper-Evident SHA-256 Audit Export**: Generates self-verifying JSON audit bundles where every event is cryptographically chained to its predecessor with a top-level root digest, immediately exposing any record tampering, omission, or reordering.
- **Real-Time Reactive Cockpit**: Role-based cockpit powered by Server-Sent Events (SSE) with 60-second HMAC-signed ephemeral token authentication.

---

## 3. Data Sources & Fixtures
- **Evaluation Tenant Fixtures (`EVAL-TENANT-01`)**: Synthetic regulated manufacturing supply chain data modeling USDA/FDA regulated dairy, beverage, and dry goods packaging.
- **Genealogy Models**: Traceability graph mapping raw ingredient lots (`ING-4417` contaminated with Salmonella, `ING-4418` clean control) into finished good batches (`FP-100-L240814-A`, `FP-100-L240814-B`, and `FP-100-ADJ`) with exact consignee delivery allocations.
- **Lab Notification Fixtures**: Canonical third-party analytical laboratory notices from Apex Analytical Laboratories with known cryptographic SHA-256 document anchors.

---

## 4. How We Built It (Google Cloud & Technology Stack)

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

1. **Google Cloud Run**: Hosts the unified container running the FastAPI backend and static SPA frontend with 0–1 auto-scaling and single-writer concurrency safety (`--max-instances=1`).
2. **Google Vertex AI (`google-genai` SDK)**: Powers grounded safety signal extraction using `gemini-3.5-flash` at the Vertex AI `global` endpoint with enterprise Application Default Credentials (ADC).
3. **Google Cloud Storage (GCS FUSE)**: Mounts a persistent Cloud Storage bucket (`gs://lot-zero-events-...`) to `/app/data/lot_zero.db`, providing persistent append-only event sourcing across container restarts.
4. **Google Cloud Secret Manager**: Securely stores and injects runtime secrets (`LOT_ZERO_SSE_SECRET`) at container initialization with zero credentials committed to source code.

---

## 5. Challenges We Overcame

1. **Global Model Discovery on Vertex AI**: During deployment, `gemini-3.5-flash` returned HTTP 404 on regional endpoints (`us-central1`). We analyzed the Vertex AI publisher API topology and discovered that Gemini 3.5 endpoints are provisioned globally. Setting `location="global"` with Application Default Credentials resolved the live endpoint cleanly.
2. **Single-Writer Safety on GCS FUSE**: SQLite requires single-writer access because Cloud Storage FUSE does not implement POSIX file locking. We designed the Cloud Run deployment with `--max-instances=1` and encapsulated persistence behind the `SqliteIncidentRepository` interface, establishing a clean migration path to Cloud SQL (PostgreSQL) for multi-region scale.
3. **Cryptographic Tamper-Evidence**: Ensuring offline verifiability without external dependencies by implementing canonical SHA-256 event hashing that validates sequence continuity, event payloads, and top-level digests.

---

## 6. Accomplishments & Verification

- **119 Automated Tests Passing**: Complete test suite covering contract schemas, SQLite optimistic concurrency, replay equivalence, tenant isolation, dual-signature gates, and 4 distinct cryptographic tamper vectors (omission, insertion, payload edits, fake digest).
- **100% Live Cloud Deployment**: Verified against the production Google Cloud Run endpoint ([`https://lot-zero-1051797806634.us-central1.run.app`](https://lot-zero-1051797806634.us-central1.run.app)).
- **Live Gemini 3.5 Execution**: Live extraction verified with model tag `gemini-3.5-flash (Vertex AI Live)` and confirmed via Cloud Run execution logs.

---

## 7. Findings & Learnings

- **AI Should Propose; Event Stores Must Decide**: In regulated domains, generative AI excels at unstructured signal parsing and entity extraction. However, business invariants, quantity calculations, and legal authorization gates must be strictly enforced by a deterministic state machine.
- **Cryptographic Audit Trails Outperform Static Logs**: By embedding SHA-256 predecessor hash chaining into the event stream, post-incident regulatory audits become mathematically self-proving and tamper-evident.
- **What's Next**:
  - Direct integration with FDA Electronic Submissions Gateway (ESG) for automated 21 CFR § 7.49 status filings.
  - Multi-tenant Cloud SQL (Postgres) persistence for enterprise multi-plant operations.
