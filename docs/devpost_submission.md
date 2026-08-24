# Lot Zero — Devpost Hackathon Submission

## Project Information
- **Project Title**: Lot Zero: Evidence-Grounded Food Safety Recall Incident Workspace
- **Tagline**: An evidence-grounded recall incident workspace powered by Gemini 3.5 on Vertex AI, deterministic supply chain genealogy traversal, strict Separation of Duties, and tamper-evident audit ledgers.
- **Hackathon Category**: The Taskmaster
- **Live Evaluation URL**: `[LIVE_DEMO_URL_PLACEHOLDER]` *(Deploy and verify service before inserting public URL)*
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **Video Demo (YouTube)**: `[DEMO_VIDEO_URL_PLACEHOLDER]`
- **Local Spin-Up Instructions**: See [README.md](../README.md) for full local and container instructions.

---

## 1. Inspiration & Problem Statement
In regulated industries like food manufacturing and life sciences, product recalls are high-stakes, time-critical events.

Today, recall management suffers from three systemic vulnerabilities:
1. **Unverifiable AI Hallucinations**: Standard LLM wrappers generate unverifiable summaries and hallucinate inventory quantities or disposition statuses.
2. **Authorization & Collision Failures**: In the chaos of an active incident, organizational hierarchy is often bypassed, leading to conflicts of interest where the requester of a quarantine signs off on their own scope.
3. **Malleable Audit Records**: Post-incident regulatory audits rely on mutable database rows and disparate PDF exports that offer no cryptographic proof against tampering, reordering, or omission.

**Lot Zero** was engineered to solve these challenges: a disciplined workspace where **Gemini 3.5 Flash** performs grounded extraction with character-offset citations bound to document SHA-256 digests, while a **deterministic domain authority kernel** enforces exact arithmetic, strict role boundaries, and hash-chained cryptographic auditability.

---

## 2. What Lot Zero Does

Lot Zero converts raw laboratory contamination notices into a disciplined recall workflow:

- **Grounded Extraction with Character-Offset Citations**: Ingests raw lab reports (e.g. Salmonella detection) using **Gemini 3.5 Flash** on **Vertex AI**, extracting contaminated lot IDs and exact character-offset citation spans checked against the source document's SHA-256 digest.
- **Strict Separation of Duties Authority Kernel**: Server-enforced role gates reject unauthorized actions with HTTP 403. A Recall Coordinator cannot approve their own quarantine; firm quarantine sign-off requires an independent QA Lead.
- **Dynamic Lot Genealogy Traversal**: Traverses raw material lot trees (`ING-4417`), automatically quarantining affected finished goods (`FP-100-AFF`, 200 units) while leaving clean control batches (`FP-100-ADJ`) unblocked (0 false holds).
- **Dual-Signature Release Rail**:
  - *Step 1*: QA Lead Biological Clearance (mandating negative laboratory re-test hash verification).
  - *Step 2*: Closure Authority Operational Release (with mandatory verification of disposition and notifications).
- **Tamper-Evident SHA-256 Audit Export**: Generates self-verifying JSON audit bundles where every event is cryptographically chained to its predecessor with a top-level root digest, detecting post-export modifications, omissions, or reordering.
- **Real-Time Reactive Cockpit**: Role-based cockpit powered by Server-Sent Events (SSE) with 60-second HMAC-signed ephemeral token authentication across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator).

---

## 3. Data Sources & Fixtures
- **Evaluation Tenant Fixtures (`EVAL-TENANT-01`)**: Synthetic regulated manufacturing supply chain data modeling dairy, beverage, and dry goods packaging.
- **Genealogy Models**: Traceability graph mapping raw ingredient lots (`ING-4417` contaminated with Salmonella, `ING-4416` clean control) into finished good batches (`FP-100-AFF` and `FP-100-ADJ`) with exact consignee delivery allocations.
- **Lab Notification Fixtures**: Canonical third-party analytical laboratory notices from Apex Analytical Laboratories with known cryptographic SHA-256 document anchors.

---

## 4. How We Built It (Planned Architecture & Technology Stack)

```
+---------------------------------------------------------------------------------------+
|                                    GOOGLE CLOUD RUN                                   |
|  +-----------------------------------+     +---------------------------------------+  |
|  |       React SPA (Vite Bundle)     | <-> |          FastAPI Domain Router        |  |
|  | - 5 Evaluation Personas           |     | - Separation of Duties Kernel         |  |
|  | - Dual-Signature Release Rail     |     | - Deterministic Reducer Engine        |  |
|  | - Live SSE Stream Subscriber      |     | - Real-Time SSE Hub (HMAC Tokens)     |  |
|  +-----------------------------------+     +---------------------------------------+  |
+---------------------------------------------------------------------------------------+
           |                                             |                      |
           v                                             v                      v
+-----------------------+                    +--------------------+   +-------------------+
|  GOOGLE VERTEX AI     |                    | CONTAINER STORAGE  |   | RUNTIME CONFIG    |
| - Gemini 3.5 Flash    |                    | - Local SQLite     |   | - Environment     |
| - Application Default |                    |   Event Store      |   |   Variables       |
|   Credentials (ADC)   |                    |   (Evaluation)     |   +-------------------+
+-----------------------+                    +--------------------+
```

1. **Google Cloud Run**: Hosts the unified container running the FastAPI backend and static SPA frontend with single-instance concurrency (`--max-instances=1`).
2. **Google Vertex AI (`google-genai` SDK)**: Supports grounded safety signal extraction using `gemini-3.5-flash` at the Vertex AI `global` endpoint with Application Default Credentials (ADC).
3. **Container Runtime Configuration**: Injects runtime secrets (`LOT_ZERO_SSE_SECRET`) at container initialization (Secret Manager recommended for production hardening).

---

## 5. Challenges We Overcame

1. **Disciplined Agentic Architecture**: Designing an AI system that acts quickly where public safety requires immediate containment (placing a 30-minute provisional soft hold) while halting strictly at human governance gates.
2. **Out-of-Order Projection Network Races**: In the React dashboard, rapid persona switching created races where older projection queries completed after newer mutations. We resolved this by introducing an AbortController with monotonically increasing request IDs in `CaseDashboard`.
3. **Authentic Provenance**: Ensured all approval handlers reference persisted proposal records, preventing manufactured requester identities.

---

## 6. Accomplishments & Verification

- **164 Backend Tests Passing**: Complete test suite covering contract schemas, SQLite optimistic concurrency, replay equivalence, tenant isolation, dual-signature gates, and cryptographic tamper detection.
- **25 Frontend Tests Passing**: Node test runner suite verifying authentication fail-closed rules, workflow step isolation, and race-free projection synchronization.
- **Self-Verifying Audit Exports**: SHA-256 hash chains exportable directly from the dashboard.

---

## 7. Findings & Learnings

- **AI Should Propose; Event Stores Must Decide**: In regulated domains, generative AI excels at unstructured signal parsing and entity extraction. However, business invariants, quantity calculations, and legal authorization gates must be strictly enforced by a deterministic state machine.
- **Cryptographic Audit Trails Outperform Static Logs**: By embedding SHA-256 predecessor hash chaining into the event stream, post-incident audits gain internal hash-chain consistency and detect post-export modification or omission when verified against the original root digest.
- **What's Next**:
  - Migration to Google Cloud SQL (PostgreSQL) or Cloud Spanner for multi-region enterprise scale.
  - Enterprise OIDC/SAML single-sign-on integration and Secret Manager runtime binding.

---

> *Disclosure: This project was created for the purposes of entering the All Things Agentic Hackathon.*
