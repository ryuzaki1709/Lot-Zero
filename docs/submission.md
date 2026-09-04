# Hackathon Submission Package: Lot Zero

## 1. Project Overview

- **Project Title**: Lot Zero
- **Tagline**: Evidence-Grounded Food Safety Recall Incident Workspace with Disciplined Agency & Separation-of-Duties Authority
- **Primary Category**: AI Agents / Enterprise Automation / Google Cloud & Vertex AI

---

## 2. Executive Summary & Descriptions

### Short Description (50 words)
Lot Zero transforms chaotic food safety recalls into a disciplined, auditable workflow. Powered by Google Gemini on Vertex AI, deterministic supply chain genealogy traversal, and strict separation-of-duties authority gates, Lot Zero isolates contaminated lots while the demonstrated synthetic scenario leaves clean adjacent batches unheld, generating tamper-evident, hash-chained audit ledgers.

### Full Description
In food manufacturing, contamination incidents (such as *Salmonella*) require rapid, high-stakes decisions. Traditional recall workflows suffer from two major flaws: over-containment that causes unnecessary destruction of clean inventory and operational disruption, or delayed/flawed outreach that leaves tainted goods on retail shelves. Furthermore, naive conversational generative AI chatbots create operational risks through hallucinations and uncontrolled execution.

**Lot Zero introduces Disciplined Agency**:
1. **Verifiable Ingestion**: Google Gemini 3.5 Flash extracts biohazard findings from unstructured laboratory text notices, anchoring lot citations to exact character offsets with document SHA-256 verification (computed dynamically from the exact notice text).
2. **Deterministic Containment**: Pure Python graph algorithms trace supply chain genealogy to isolate affected finished goods across two batches (`FP-100-L240814-A`: 120 units and `FP-100-L240814-B`: 80 units, totaling 200 units) while the demonstrated synthetic scenario leaves adjacent clean control runs (`FP-100-ADJ`, 100 units) unheld (zero false holds in the synthetic evaluation fixture).
3. **Multi-Persona Authorization**: Role gates enforce anti-self-approval (`requester != approver`) across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator).
4. **Authentic Workflow Modeling**: Outbound consignee notices (`PKT-001`) are dispatched and tracked. When consignee `ACK-006` is unverified, case closure is blocked until distributor phone attestation or modeled non-response referral is recorded.
5. **Tamper-Evident Ledgers**: Every state transition appends to an event-sourced ledger with a SHA-256 cryptographic hash chain, exportable as a self-verifying audit bundle where the verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.

---

## 3. Key Differentiators & Technical Accomplishments

| Feature | Generic AI Recall Chatbot | Lot Zero Architecture |
| :--- | :--- | :--- |
| **Model Grounding** | Unanchored prompt completions | Verbatim character-offset spans checked against document SHA-256 |
| **Scope Calculation** | Model-estimated quantities | Deterministic supply chain graph traversal (zero false holds in synthetic fixture) |
| **Governance Gates** | Unbounded autonomous execution | Multi-persona separation of duties with server-enforced 403 refusals |
| **Outreach Tracking** | Static outbound email template | Packet versioning, oral attestation recording, modeled non-response referral |
| **Audit Trail** | Unstructured chat history | Cryptographic SHA-256 hash-chained event ledger |

---

## 4. Google Cloud & Gemini Integration

- **Model**: `gemini-3.5-flash` on Google Vertex AI when configured.
- **SDK**: Official `google-genai` Python SDK (`location="global"`).
- **Deployment**: Verified on Google Cloud Run with a dedicated least-privilege runtime service account (`lot-zero-runtime`). Cloud Run resolves `LOT_ZERO_SSE_SECRET` from a Secret Manager reference at runtime. The plaintext value is not stored in Git or passed as a deployment argument. Configured with ephemeral container storage (`/tmp/lot_zero.db`), single-instance concurrency (`--max-instances=1`), and live Vertex AI Gemini 3.5 Flash integration.
- **Evaluation Replay Engine**: Built-in deterministic extraction replay harness (`gemini-3.5-flash (Deterministic Replay)`) ensuring reliable offline evaluation by judges without external billing friction.

---

## 5. Challenges & Lessons Learned

- **Balancing Agency with Strict Governance**: Designing an AI system that acts autonomously where safety requires immediate action (30-minute provisional soft hold) while halting at human authority gates.
- **Out-of-Order Network Races in Read Models**: Solved UI synchronization races by associating projection requests with monotonically increasing request IDs and AbortControllers, ensuring older responses never overwrite newer state.
- **Authentic Provenance over Synthetic Shortcuts**: Ensured all approval commands reference persisted event records, preventing manufactured requester identities.

---

## 6. Future Work & Roadmap

1. **Enterprise Database Integration**: Direct support for Google Cloud SQL (PostgreSQL) or Cloud Spanner for multi-region high availability.
2. **Enterprise IAM / SSO**: Full OIDC and SAML single-sign-on integration with hardware MFA.
3. **WORM Storage & Automated Key Rotation**: Automated periodic key rotation and streaming of audit bundles to immutable Google Cloud Storage Bucket Lock vaults for long-term regulatory archiving.

---

## 7. Submission Links & Resources

- **Live Evaluation Workspace**: [https://lot-zero-m4vizenaoa-uc.a.run.app](https://lot-zero-m4vizenaoa-uc.a.run.app)
- **Deployment Evidence & Provenance**: [docs/deployment_evidence.md](deployment_evidence.md)
- **Late-Submission Rescue & Portfolio Launch**: [docs/late_submission_rescue.md](late_submission_rescue.md)
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **Walkthrough Video**: `[DEMO_VIDEO_URL_PLACEHOLDER]`
- **Devpost / Platform Submission**: `[SUBMISSION_URL_PLACEHOLDER]`

---

## 8. Concise Judge Testing Instructions

To evaluate Lot Zero in under 3 minutes:
1. Open the web interface (locally at `http://localhost:8000` or deployed service).
2. Switch persona to **Evaluation Administrator** -> Click **Reset State** (initializes clean baseline in `signal_received` phase).
3. Switch persona to **Recall Coordinator** -> Click **Simulate Signal** (Gemini extracts `ING-4417` and places 30m soft hold, advancing to `provisional_containment`).
4. Switch persona to **QA Lead** -> Click **Approve Firm Quarantine** (standing policy upgrades to `AUTH-HOLD-01` in `action_review` phase).
5. Switch to **Recall Coordinator** -> Click **Request Notification Packet**.
6. Switch to **Customer Operations** -> Click **Approve Notification Packet** -> Click **Dispatch Recall Outbox** (advances to `ack_monitoring`).
7. Switch to **Recall Coordinator** -> Click **Request Incident Closure**. Observe closure gate is **BLOCKED** by unverified `ACK-006`.
8. Switch to **Customer Operations** -> Under Consignee Outreach, click **Log Phone Attestation** for `ACK-006` -> Submit (advances to `effectiveness_check`).
9. Switch to **Closure Authority** -> Click **Authorize Final Closure** (advances to `closed` phase).
10. Click **Export Audit Bundle** in the top bar to inspect the SHA-256 cryptographic hash chain.

---

> *Disclosure: This project was created for the purposes of entering the All Things Agentic Hackathon, but was not submitted on time unless a late submission is actually accepted.*
