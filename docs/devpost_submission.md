# Lot Zero — Devpost Hackathon Submission

## Project Information
- **Project Title**: Lot Zero: Evidence-Grounded Food Safety Recall Incident Workspace
- **Tagline**: An evidence-grounded recall incident workspace powered by Gemini 3.5 on Vertex AI, deterministic supply chain genealogy traversal, strict Separation of Duties, and tamper-evident audit ledgers.
- **Hackathon Category**: The Taskmaster
- **Live Evaluation URL**: [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app)
- **Deployment Evidence & Verification**: [docs/deployment_evidence.md](deployment_evidence.md)
- **Late-Submission Rescue & Portfolio Launch**: [docs/late_submission_rescue.md](late_submission_rescue.md)
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
- **Dynamic Lot Genealogy Traversal**: Traverses raw material lot trees (`ING-4417`, Organic Wheat Flour), automatically quarantining affected finished goods across two batches (`FP-100-L240814-A`: 120 units, `FP-100-L240814-B`: 80 units, totaling 200 units) while the demonstrated synthetic scenario leaves clean control batches (`FP-100-ADJ`, 100 units) unheld (zero false holds in the synthetic evaluation fixture).
- **Dual-Signature Release Rail**:
  - *Step 1*: QA Lead Biological Clearance (mandating negative laboratory re-test hash verification).
  - *Step 2*: Closure Authority Operational Release (with mandatory verification of disposition and notifications).
- **Tamper-Evident SHA-256 Audit Export**: Generates self-verifying JSON audit bundles where every event is cryptographically chained to its predecessor. The verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.
- **Real-Time Reactive Cockpit**: Role-based cockpit powered by Server-Sent Events (SSE) with 60-second HMAC-signed ephemeral token authentication across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator).

---

## 3. Data Sources & Fixtures
- **Evaluation Tenant Fixtures (`EVAL-TENANT-01`)**: Synthetic regulated manufacturing supply chain data modeling grain and dry goods packaging.
- **Genealogy Models**: Traceability graph mapping raw ingredient lots (`ING-4417` contaminated with Salmonella, `ING-4418` clean control) into finished good batches (`FP-100-L240814-A` [120 units], `FP-100-L240814-B` [80 units], and clean control `FP-100-ADJ` [100 units]) with exact consignee delivery allocations.
- **Lab Notification Fixtures**: Canonical third-party analytical laboratory notices from Apex Micro Quality Labs with dynamic cryptographic SHA-256 document anchors.

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
3. **Google Secret Manager**: Cloud Run resolves `LOT_ZERO_SSE_SECRET` from a Secret Manager reference at runtime. The plaintext value is not stored in Git or passed as a deployment argument.

---

## 5. Challenges We Overcame

1. **Disciplined Agentic Architecture**: Designing an AI system that acts quickly where public safety requires immediate containment (placing a 30-minute provisional soft hold) while halting strictly at human governance gates.
2. **Out-of-Order Projection Network Races**: In the React dashboard, rapid persona switching created races where older projection queries completed after newer mutations. We resolved this by introducing an AbortController with monotonically increasing request IDs in `CaseDashboard`.
3. **Authentic Provenance**: Ensured all approval handlers reference persisted proposal records, preventing manufactured requester identities.

---

## 6. Accomplishments & Verification

- **169 Backend Tests Passing**: Complete test suite covering contract schemas, SQLite optimistic concurrency, replay equivalence, tenant isolation, dual-signature gates, and cryptographic tamper detection.
- **25 Frontend Tests Passing**: Node test runner suite (21 primary frontend/workflow tests and 4 sites-worker tests) verifying authentication fail-closed rules, workflow step isolation, and race-free projection synchronization.
- **Self-Verifying Audit Exports**: SHA-256 hash chains exportable directly from the dashboard.

---

## 7. Findings & Learnings

- **AI Should Propose; Event Stores Must Decide**: In regulated domains, generative AI excels at unstructured signal parsing and entity extraction. However, business invariants, quantity calculations, and legal authorization gates must be strictly enforced by a deterministic state machine.
- **Cryptographic Audit Trails Outperform Static Logs**: By embedding SHA-256 predecessor hash chaining into the event stream, post-incident audits gain internal hash-chain consistency. The verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.
- **What's Next**:
  - Migration to Google Cloud SQL (PostgreSQL) or Cloud Spanner for multi-region enterprise scale.
  - Enterprise OIDC/SAML single-sign-on integration and automated KMS secret rotation.

---

> *Disclosure: This project was created for the purposes of entering the All Things Agentic Hackathon, but was not submitted on time unless a late submission is actually accepted.*
