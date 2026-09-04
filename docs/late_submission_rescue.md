# Lot Zero — Late-Submission Rescue Package & Portfolio Launch Plan

This document serves as the single source of truth for submitting **Lot Zero** if a late-submission link is approved, or executing an immediate public portfolio launch if late submission is denied.

---

## 1. Submission-Ready Copy Block (Devpost / Hackathon Forms)

### Project Title
**Lot Zero: Evidence-Grounded Food Safety Recall Incident Workspace**

### Tagline
An evidence-grounded recall incident workspace powered by Gemini 3.5 on Vertex AI, deterministic supply chain genealogy traversal, strict Separation of Duties, and tamper-evident audit ledgers.

### One-Sentence Pitch
Lot Zero pairs Google Gemini 3.5 Flash on Vertex AI with deterministic supply chain genealogy traversal, strict separation-of-duties authority kernels, and tamper-evident SHA-256 event streams to contain contamination incidents rapidly, leaving clean adjacent batches unheld in the synthetic evaluation fixture.

### Short Description (Under 200 words)
In food manufacturing and life sciences, contamination incidents like *Salmonella* demand instant, high-stakes decisions. Traditional recalls rely on frantic spreadsheets that cause unnecessary destruction of clean inventory and operational disruption, or naive AI chatbots that hallucinate batch numbers and breach authority boundaries.

**Lot Zero** solves this through **Disciplined Agency: AI proposes; deterministic authority decides.** 

When a raw microbiological lab report arrives, Google Gemini 3.5 Flash on Vertex AI ingests the unstructured notice, extracts contaminated ingredient lots, and binds its findings to exact character-offset citation spans anchored to the document's SHA-256 digest. A deterministic graph engine traverses supplier genealogy to place an autonomous 30-minute soft hold on affected inventory, while the demonstrated synthetic scenario leaves clean adjacent batches unheld. 

State mutations are governed by a strict server-enforced Separation of Duties kernel where no single actor can self-approve firm quarantines or bypass unverified consignees. The export verifier detects post-export payload changes, reordering, or removal when checked against the originally retained root digest. Packaged for Google Cloud Run with Google Secret Manager and verified live on Vertex AI.

---

### Full Inspiration
Every year, contaminated food products cause severe illnesses, costly product recalls, and catastrophic brand damage. Yet when a presumptive pathogen signal arrives from a testing laboratory, food safety teams face a painful dilemma:

1. **Over-Containment**: Out of caution, companies quarantine entire production weeks across multiple facilities, causing unnecessary destruction of clean inventory and severe operational disruption.
2. **Under-Containment**: In the chaos of manual ERP spreadsheets and bill-of-materials exports, contaminated sub-lots slip through into retail distribution.
3. **Probabilistic Chatbot Failure**: Generative AI tools offer immense potential for parsing complex lab documents, but naive chatbots hallucinate batch numbers, fabricate inventory quantities, and lack governance boundaries.

We built **Lot Zero** to bridge this divide with Disciplined Agency. By constraining Google Gemini 3.5 Flash on Vertex AI to evidence extraction with character-level citations and delegating containment calculations and role governance to deterministic state machines, Lot Zero provides food safety teams with speed without ungrounded outputs, and automation without abdication of human authority.

---

### What It Does
Lot Zero orchestrates the synthetic evaluation workflow across seven disciplined stages:

1. **Evidence-Grounded Ingestion**: Parses unstructured pathogen laboratory text notices using Google Gemini 3.5 Flash on Vertex AI (`global` endpoint), extracting contaminated lots (`ING-4417`, Organic Wheat Flour), pathogens, and verbatim character-offset citation spans verified against the report's SHA-256 digest.
2. **Deterministic Genealogy Traversal**: Traverses raw-ingredient-to-finished-good production trees to isolate affected finished goods across two batches (`FP-100-L240814-A`: 120 units, `FP-100-L240814-B`: 80 units, totaling 200 units) while the demonstrated synthetic scenario leaves clean adjacent control batches (`FP-100-ADJ`, 100 units) unheld—achieving **zero false holds in the synthetic evaluation fixture**.
3. **Autonomous Provisional Containment**: Enacts an immediate 30-minute soft hold on affected inventory while biological verification takes place, preventing premature shipment.
4. **Strict Separation of Duties (Anti-Collision)**: Server-side authority rules strictly prevent the Recall Coordinator from approving their own quarantine; a distinct QA Lead must review evidence and sign firm quarantine policy (`AUTH-HOLD-01`).
5. **Consignee Outreach & Outbox Orchestration**: Stages targeted consignee notification packets (`PKT-001`), requiring Customer Operations human approval before outbox dispatch.
6. **Closure Guardrails & Non-Response Workflows**: Authority kernel strictly blocks premature case closure if any consignee (`ACK-006`) has not verified product receipt. Customer Operations can conduct manual outreach and record verified phone attestations directly into the ledger to clear the gate.
7. **Tamper-Evident SHA-256 Audit Bundle**: Exports the recorded incident event stream as a self-verifying JSON bundle where every event is cryptographically hash-chained to its predecessor. The verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.

---

### How We Built It
- **Generative AI & Grounding**: Integrated Google Gemini 3.5 Flash via the official `google-genai` Python SDK (`location="global"`, Application Default Credentials). Built prompt constraints enforcing structured JSON output with verbatim citation spans, character offsets, and document hash bindings.
- **Backend Architecture**: Built with Python 3.12 and FastAPI using an event-sourced domain model. SQLite acts as the transactional event store with optimistic concurrency controls (`version` checks) to prevent race conditions.
- **Frontend Experience**: Developed with React 18, Vite, and Tailwind CSS. Features real-time state synchronization via Server-Sent Events (SSE) with 60-second HMAC-signed tokens, interactive supply chain genealogy visualization, persona switching, and separation-of-duties role enforcement.
- **Google Cloud Infrastructure**:
  - **Google Cloud Run**: Deployed as a fully managed container service (`--max-instances=1`, `--concurrency=10`, ephemeral `/tmp/lot_zero.db`, scale-to-zero enabled).
  - **Dedicated Runtime Identity**: Runs under dedicated Lot Zero runtime service account with scoped roles (`roles/aiplatform.user`, `roles/logging.logWriter`).
  - **Google Secret Manager**: Cloud Run resolves `LOT_ZERO_SSE_SECRET` from a Secret Manager reference at runtime. The plaintext value is not stored in Git or passed as a deployment argument.

---

### Challenges We Ran Into
1. **Preventing Probabilistic Hallucination in High-Stakes Extraction**: Early prompts allowed the model to summarize or infer lot numbers. We solved this by implementing strict deterministic validation: every extracted lot must map to an exact verbatim character-offset span that exists within the source document's SHA-256 text. The pipeline halts with `needs_review` when live extraction fails validation, and inventory quantities are derived by the deterministic fixture-backed genealogy engine, not generated by the model.
2. **Server-Enforced Separation of Duties**: Creating a governance kernel that prevents role collision required strict server-side state enforcement. If a user attempts to approve their own request or perform an action outside their granted role, the API returns HTTP 403 Forbidden with a transparent explanation.
3. **Single-Instance Event Consistency on Cloud Run**: To prevent multi-instance split-brain states in an evaluation deployment while maintaining atomic SQLite transactions, we configured Cloud Run with `--max-instances=1` and `--concurrency=10`, backed by real-time SSE push updates.
4. **Cloud Run Public Health Routing**: During public deployment verification, `/healthz` returned 404 while `/api/health` returned 200. `/api/health` is therefore the documented canonical public health endpoint.

---

### Accomplishments That We're Proud Of
- **169 Backend Tests Passing**: 100% test pass rate across contract schemas, optimistic concurrency, replay equivalence, tenant isolation, dual-signature gates, and cryptographic tamper detection.
- **25 Frontend Tests Passing**: Node test runner suites (21 primary frontend/workflow tests and 4 sites-worker tests) verifying authentication fail-closed rules, persona gating, and race-free projection synchronization.
- **Live Google Cloud Run & Vertex AI Verification**: Successfully deployed and validated live against Google Cloud Run with dedicated service account IAM and Secret Manager injection.
- **Clean Batch Isolation in Synthetic Fixture**: Demonstrated precise genealogy traversal that isolates contaminated lots while the demonstrated synthetic scenario leaves clean adjacent batches unheld (zero false holds in the synthetic evaluation fixture).
- **Self-Verifying Cryptographic Audit Ledger**: Verified that the verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.

---

### What We Learned
- **Disciplined Agency is Essential for Regulated AI**: In safety-critical systems, AI should never have autonomous write authority over business state. Generative models excel at unstructured parsing and synthesis; deterministic kernels must enforce governance, mathematical calculations, and authority boundaries.
- **Cryptographic Chaining Delivers Lightweight Trust**: You do not need complex, energy-intensive distributed ledgers to achieve tamper evidence. Embedding SHA-256 predecessor hash chaining into the event stream provides immediate, inspectable proof of integrity.

---

### What's Next for Lot Zero
1. **Google Cloud SQL & Cloud Spanner Migration**: Transition from ephemeral SQLite to Cloud SQL (PostgreSQL) or Cloud Spanner for multi-region active-active enterprise clustering.
2. **Enterprise OIDC & SAML SSO**: Integrate corporate identity providers (Okta, Google Workspace, Azure AD) with hardware FIDO2/WebAuthn MFA.
3. **WORM Storage Vault Archiving**: Stream finalized incident audit bundles into Google Cloud Storage Bucket Lock (WORM) vaults for long-term regulatory retention.
4. **Autonomous Consignee Inbound Channels**: Ingest distributor acknowledgements directly via secure webhooks and EDI 856 transaction sets.

---

### Technology List
- **AI & ML**: Google Vertex AI, Google Gemini 3.5 Flash (`gemini-3.5-flash`), `google-genai` Python SDK
- **Cloud Infrastructure**: Google Cloud Run, Google Secret Manager, Cloud Logging, Cloud Build
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLite, Uvicorn, SSE-Starlette
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons, Mermaid.js
- **Testing & Tooling**: Pytest, Hypothesis, Node.js Test Runner, Ruff, Mypy, Docker

---

### Important URLs & File References
- **Live Evaluation URL**: [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app)
- **Canonical Health Check**: [https://lot-zero-m4vizenaoa-uc.a.run.app/api/health](https://lot-zero-m4vizenaoa-uc.a.run.app/api/health)
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **Deployment Evidence & Provenance**: [docs/deployment_evidence.md](deployment_evidence.md)
- **Architecture Specification**: [docs/architecture.md](architecture.md)
- **Architecture Diagram (SVG)**: [docs/architecture.svg](architecture.svg)
- **Architecture Diagram (Mermaid)**: [docs/architecture.mmd](architecture.mmd)
- **Local Spin-Up Instructions**: See [README.md](../README.md)

---

### Hackathon Category Justification: The Taskmaster
Lot Zero is custom-built for **The Taskmaster** category:
- **Complex Multi-Step Workflow**: Recalls require coordinating ingestion, genealogy graph traversal, provisional holds, dual-signature firm holds, staged consignee packets, outreach tracking, non-response resolution, and audit sign-off.
- **Disciplined Agency**: An autonomous agent manages the initial containment window, but strict authority boundaries require human-in-the-loop approvals for high-impact operational transitions.
- **Outbox Dispatch & Attestation Tracking**: Coordinates communication outboxes to downstream distributors and tracks acknowledgement states to prevent premature closure.

---

### Synthetic Data & Non-Compliance Disclosure
All facility names (e.g., *Apex Milling*, *Apex Micro Quality Labs*), ingredient lot numbers (`ING-4417`), finished good batch IDs (`FP-100-L240814-A` and `FP-100-L240814-B`, totaling 200 units), supplier entities, and lab contamination reports used in Lot Zero are entirely **synthetic test fixtures** designed for evaluation. Lot Zero models FDA-inspired recall effectiveness and separation-of-duties governance; it does not connect directly to FDA electronic systems, submit statutory recall filings, or certify legal compliance.

---

## 2. Four-Minute Video Recording Checklist

The official hackathon rules state that **judges only evaluate the first four minutes of video**. Target recording duration is approximately **3 minutes 45 seconds** to maintain a comfortable safety buffer within the 4-minute window (pacing should be verified during rehearsal).

### Pre-Recording Setup (T-Minus 5 Minutes)
- [ ] Open clean browser window (1920x1080 or 1440x900 resolution).
- [ ] Ensure bookmarks bar and browser extensions are hidden.
- [ ] Check live health: `https://lot-zero-m4vizenaoa-uc.a.run.app/api/health` -> HTTP 200 OK.
- [ ] Check persona configuration: `https://lot-zero-m4vizenaoa-uc.a.run.app/api/config` -> 5 human personas visible.
- [ ] Select **Evaluation Administrator** -> Click **Reset State** to establish baseline.
- [ ] Open second tab with Cloud Run Deployment Evidence (`docs/deployment_evidence.md`).
- [ ] Silence OS notifications and messaging applications.

---

### Timed Workflow & Narration Sequence (Approximate Target: Under 3 min 45 sec)

```text
+---------------------------------------------------------------------------------------------------+
| 0:00 - 0:25 (25s) | Scene 1: Problem Thesis & Product Overview                                    |
| Action:           | Show Lot Zero clean UI. Highlight "AI proposes; deterministic authority decides" |
| Narration:        | Recall dilemma: over-containment vs. chatbot hallucination. Lot Zero solution.    |
+---------------------------------------------------------------------------------------------------+
| 0:25 - 0:55 (30s) | Scene 2: Live Signal Ingestion & Gemini 3.5 Flash on Vertex AI                |
| Action:           | Persona: Recall Coordinator -> Click "Simulate Signal".                       |
| Visuals:          | "gemini-3.5-flash (Vertex AI Live)" badge, ING-4417, Salmonella, 3 citations. |
| Narration:        | Live Vertex AI extraction, exact character-offset spans, deterministic check. |
+---------------------------------------------------------------------------------------------------+
| 0:55 - 1:20 (25s) | Scene 3: Genealogy Traversal & Clean Batch Isolation                          |
| Action:           | Scroll to Supply Chain Genealogy Graph and Containment Scope Card.            |
| Visuals:          | ING-4417 milled into FP-100-L240814-A (120u) & FP-100-L240814-B (80u). Clean FP-100-ADJ (100u) unheld. |
| Narration:        | 30-min provisional soft hold. Synthetic fixture leaves clean batch unheld.    |
+---------------------------------------------------------------------------------------------------+
| 1:20 - 1:50 (30s) | Scene 4: QA Lead Firm Quarantine Gate                                         |
| Action:           | Persona: QA Lead -> Approve Firm Hold.                                        |
| Visuals:          | AUTH-HOLD-01 firm hold signed. Anti-collision prevents self-approval.         |
| Narration:        | Separation of duties enforces dual signature for firm quarantine.             |
+---------------------------------------------------------------------------------------------------+
| 1:50 - 2:20 (30s) | Scene 5: Staged Notice Request & Operations Dispatch                          |
| Action:           | Persona: Recall Coord -> Request Notice -> Persona: Ops -> Approve & Dispatch.|
| Visuals:          | Staged consignee packets (PKT-001) dispatched after human operational signoff.|
| Narration:        | Operations approves outbound notices before distribution.                     |
+---------------------------------------------------------------------------------------------------+
| 2:20 - 2:55 (35s) | Scene 6: Guardrails Against Premature Closure & ACK-006 Resolution            |
| Action:           | Persona: Recall Coord -> Request Closure -> Point to BLOCKED closure banner.  |
|                   | Persona: Ops -> Log Phone Attestation for ACK-006 -> Submit attestation.      |
| Visuals:          | Closure blocked by ACK-006. Phone attestation clears gate to effectiveness.   |
| Narration:        | Authority kernel prevents premature closure until all consignees are verified.|
+---------------------------------------------------------------------------------------------------+
| 2:55 - 3:20 (25s) | Scene 7: Dual-Signature Final Closure & Operational Release                   |
| Action:           | Persona: Closure Authority -> Authorize Final Closure.                        |
| Visuals:          | Incident moves to 'closed' phase with full biological/operational signoff.    |
| Narration:        | Dual-signature final release closes case.                                     |
+---------------------------------------------------------------------------------------------------+
| 3:20 - 3:45 (25s) | Scene 8: Audit Bundle Export & Live Cloud Run Provenance                      |
| Action:           | Click Export Audit Bundle. Show JSON stream and visible .run.app URL.         |
| Visuals:          | Chained SHA-256 digests. Live .run.app domain and canonical /api/health probe.|
| Narration:        | Export verifier detects post-export changes. Running live on Cloud Run.       |
+---------------------------------------------------------------------------------------------------+
```

---

### Recovery & Troubleshooting Runbook
- **Instance Cold Start Reset**: If Cloud Run instance recycled, switch to **Evaluation Administrator**, click **Reset State**, and restart take.
- **Vertex AI Latency / Rate Limit (`needs_review`)**: Explain that Lot Zero safely halts on low-confidence extraction rather than creating ungrounded holds; reset and re-trigger.
- **Button Disabled (403 Forbidden)**: Check role indicator on button (e.g. `(QA)`, `(Ops)`, `(Auth)`) and select matching persona.
- **Closure Remains Blocked**: Submit phone attestation for `ACK-006` as **Customer Operations**.
- **SSE Stream Lag**: Click manual **Refresh** button in header.

---

## 3. Fallback Portfolio Launch Plan (If Late Submission is Denied)

If the late-submission request is not accepted, Lot Zero immediately transitions into a premier public portfolio project and open-source demonstration of **Disciplined Agency in High-Stakes Systems**.

Execute the following sequential launch plan:

### 1. Repository Publication & Clean Hand-Off
- Ensure `README.md` reflects all verified badges (169 Pytest passed, 25 Frontend passed).
- Update repository description on GitHub: `Evidence-grounded recall incident workspace powered by Gemini 3.5 on Vertex AI, deterministic supply chain genealogy traversal, strict Separation of Duties, and tamper-evident audit ledgers.`
- Add repository topics: `google-cloud`, `vertex-ai`, `gemini-3-5-flash`, `food-safety`, `fastapi`, `react`, `event-sourcing`, `tamper-evident`, `hackathon`.
- Ensure repository visibility is **Public**.

### 2. Retain Live Cloud Run Showcase (14-Day Window)
- Maintain the live Google Cloud Run service (`https://lot-zero-m4vizenaoa-uc.a.run.app`) for 14 days following launch so prospective employers, engineering peers, and judges can test the interactive application.
- Because Cloud Run scales to zero (`--min-instances=0`, `--max-instances=1`), idle hosting costs are minimal.

### 3. Video Walkthrough Publication
- Upload the recorded 3:45 walkthrough to YouTube as a **Public** video with timestamps matching the 8 scenes.
- Title: `Lot Zero: Disciplined AI Agents for Food Safety Recalls (Google Cloud & Vertex AI)`
- Link the video directly in `README.md`, replacing `[DEMO_VIDEO_URL_PLACEHOLDER]`.

### 4. In-Depth Technical Article Publication
- Publish a long-form engineering breakdown on **Dev.to** / **Medium** / **Substack**:
  - *Title*: "Why Food Safety Recalls Can't Trust AI Chatbots: Building Lot Zero with Google Cloud Run & Vertex AI"
  - *Content*: Cover the core architectural principle: Generative AI for probabilistic unstructured parsing; deterministic event-sourced state machines for mathematical calculations and authority enforcement.
  - Include the architecture diagram from `docs/architecture.svg` and link the live demo.

### 5. Social Launch (LinkedIn & X)
- Deploy the ready-to-post copy from [`docs/social_and_blog_pack.md`](social_and_blog_pack.md).
- Include an honest disclosure: *"Engineered for the Google Cloud All Things Agentic Hackathon (not submitted on time unless late submission is accepted), showcasing how Vertex AI and deterministic authority controls combine for evidence-grounded recall incident response."*

### 6. Portfolio Case Study
- Add **Lot Zero** as a featured project on your personal portfolio / engineering website.
- Emphasize enterprise system design: Separation of Duties, cryptographic SHA-256 audit chaining, optimistic concurrency, and least-privilege cloud IAM.

### 7. Reusable Component Open-Sourcing
- Highlight the two reusable patterns pioneered in Lot Zero:
  1. **The Authority Kernel**: Generic anti-collision role-gating engine in FastAPI.
  2. **Audit Chainer**: Lightweight Python decorator for self-verifying SHA-256 event chains.

### 8. Cloud Resource Teardown Schedule
- Set a calendar reminder for **14 days post-launch**:
  - Review Cloud Run invocations in Google Cloud Console.
  - Restrict access or execute teardown if public traffic has concluded:
    ```bash
    gcloud run services delete lot-zero --region=us-central1 --quiet
    ```
