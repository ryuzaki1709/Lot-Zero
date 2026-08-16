# Lot Zero — 4-Minute Hackathon Video Walkthrough Script

**Total Duration**: 04:00  
**Live Target**: `https://lot-zero-1051797806634.us-central1.run.app`  
**Tone**: Confident, technical, authoritative, high-craft, calm.

---

### Segment 1: The Problem & Architecture Overview (0:00 – 0:45)
- **Visual**: Show the Architecture diagram ([`docs/architecture.png`](architecture.png)) and open the live Cloud Run URL in browser.
- **Audio / Voiceover**:
  > *"Welcome to Lot Zero. In regulated food manufacturing, a single contaminated ingredient can compromise thousands of consumer units. Current recall workflows rely on error-prone manual spreadsheets, hallucinating AI wrappers, or malleable audit trails.*
  > 
  > *Lot Zero is an industrial-grade incident workspace designed around two core principles: Generative AI for grounded multimodal extraction via Gemini 3.5 on Google Vertex AI, paired with a deterministic, event-sourced authority kernel deployed on Google Cloud Run with GCS FUSE persistence and cryptographic SHA-256 audit chaining.*
  > 
  > *Let's walk through an active food contamination incident end-to-end."*

---

### Segment 2: Multimodal Signal Extraction & Role Separation Denial (0:45 – 1:45)
- **Visual**: 
  1. Role Selector is set to **Recall Coordinator**.
  2. Click **"Simulate Safety Signal"**.
  3. Show the raw Apex Laboratories Salmonella notice and the parsed Gemini 3.5 Flash citation spans highlighted with character-offset badges.
  4. Show the Dynamic Genealogy DAG isolating `ING-4417`, quarantining 200 units across `FP-A` & `FP-B`, while keeping negative control `FP-C` clean.
  5. Attempt to click **"Sign Off Firm Quarantine"** as the Recall Coordinator.
  6. Show the red banner: **Server Denied (HTTP 403): Requester and Approver must be different principals.**
- **Audio / Voiceover**:
  > *"We start as the Recall Coordinator. A third-party lab Salmonella notice arrives. Powered by Gemini 3.5 Flash on Vertex AI, Lot Zero extracts the contaminated lot ING-4417 and binds exact character-offset citation spans to the lab document's SHA-256 digest.*
  > 
  > *The genealogy DAG immediately isolates affected products FP-A and FP-B while unblocking negative controls. Notice what happens if the Recall Coordinator attempts to approve their own quarantine: the server immediately rejects the request with HTTP 403. In Lot Zero, Separation of Duties is server-enforced at the domain kernel level—no self-approvals allowed."*

---

### Segment 3: QA Sign-off & Customer Operations Outbox (1:45 – 2:45)
- **Visual**:
  1. Switch Role dropdown in Header to **QA Lead** (`key-qa-lead-01`).
  2. Click **"Sign Off Firm Quarantine"** (shows green success and appends event to live ledger).
  3. Switch Role to **Customer Operations** (`key-ops-01`).
  4. Navigate to the Outbox panel; click **"Dispatch Consignee Notifications"**.
  5. Show the real-time SSE stream updating consignee delivery statuses.
- **Audio / Voiceover**:
  > *"Now we switch to the QA Lead role. With authorized credentials, the QA Lead signs the quarantine, transitioning the incident into active containment.*
  > 
  > *Next, Customer Operations takes over to dispatch 21 CFR § 7.49 compliant recall notices to consignees. All updates stream reactively to connected browser cockpits using Server-Sent Events secured by 60-second ephemeral HMAC tokens minted by the backend."*

---

### Segment 4: Dual-Signature Release Rail & Cryptographic Audit Export (2:45 – 4:00)
- **Visual**:
  1. Switch Role to **QA Lead**; enter re-test lab document hash; complete **Step 1: Biological Clearance**.
  2. Show Step 2 remaining locked until **Closure Authority** (`key-closure-auth-01`) provides operational release.
  3. Complete **Step 2** with non-response escalation documentation.
  4. Navigate to the **Evidence Ledger**; click **"Download Cryptographic Audit Bundle"**.
  5. Open terminal/console; run `python scripts/verify_cloud_deploy.py https://lot-zero-1051797806634.us-central1.run.app` showing 100% verified SHA-256 hash chain and 0 tamper vulnerabilities.
- **Audio / Voiceover**:
  > *"To release a hold, Lot Zero enforces a 2-Step Dual-Signature Rail: Step 1 requires the QA Lead's biological clearance bound to a certified negative re-test hash. Step 2 requires the Closure Authority's operational release.*
  > 
  > *Finally, when regulatory auditors arrive, we don't hand over spreadsheets—we export a cryptographically chained JSON audit bundle. Every event is hashed with SHA-256 to its predecessor and signed with a top-level root digest. Any attempt to modify timestamps, reorder events, or omit actions immediately invalidates the cryptographic chain.*
  > 
  > *All 119 tests pass, running live on Google Cloud Run and Vertex AI. That is Lot Zero: deterministic, tamper-evident safety incident management."*
