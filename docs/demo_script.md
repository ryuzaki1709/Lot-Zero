# Lot Zero — 4-Minute Hackathon Video Walkthrough Script

**Total Duration**: 04:00  
**Live Target**: `https://lot-zero-1051797806634.us-central1.run.app`  
**Tone**: Confident, technical, authoritative, calm.

---

### Segment 1: The Problem & Architecture Overview (0:00 – 0:45)
- **Visual**: Show the Architecture diagram ([`docs/architecture.png`](architecture.png)) and open the live Cloud Run URL in browser.
- **Audio / Voiceover**:
  > *"Welcome to Lot Zero. In regulated food manufacturing, a single contaminated ingredient can compromise thousands of consumer units. Current recall workflows rely on error-prone manual spreadsheets, hallucinating AI wrappers, or malleable audit trails.*
  > 
  > *Lot Zero is an industrial-grade incident workspace designed around two core principles: Grounded extraction via Gemini 3.5 on Google Vertex AI, paired with a deterministic, event-sourced authority kernel deployed on Google Cloud Run with persistent GCS FUSE storage and cryptographic SHA-256 audit chaining.*
  > 
  > *Let's walk through an active food contamination incident end-to-end."*

---

### Segment 2: Grounded Extraction & Separation of Duties Refusal (0:45 – 1:45)
- **Visual**: 
  1. Role Selector in Header is set to **Recall Coordinator** (`key-coord-01`).
  2. Click **"Simulate Safety Signal"**.
  3. Show the raw Apex Laboratories Salmonella notice and the parsed Gemini 3.5 Flash citation spans highlighted with character-offset badges bound to the document's SHA-256 digest.
  4. Show the Dynamic Genealogy DAG isolating raw lot `ING-4417`, quarantining 200 units across `FP-100-L240814-A` and `FP-100-L240814-B`, while keeping negative control `FP-100-ADJ` (made from `ING-4418`) clear.
  5. Attempt to click **"Sign Off Firm Quarantine"** as the Recall Coordinator.
  6. Show the red server denial toast: **Server Refusal (HTTP 403): requester and approver must be different people**.
- **Audio / Voiceover**:
  > *"We start as the Recall Coordinator. A third-party laboratory Salmonella notice arrives. Powered by Gemini 3.5 Flash on Vertex AI, Lot Zero extracts the contaminated lot ING-4417 and binds exact character-offset citation spans to the lab report's SHA-256 digest.*
  > 
  > *The genealogy DAG immediately isolates affected finished goods FP-100-L240814-A and B while unblocking clean control batch FP-100-ADJ. Notice what happens if the Recall Coordinator attempts to approve their own quarantine: the server rejects the request with HTTP 403: 'requester and approver must be different people'. In Lot Zero, Separation of Duties is server-enforced at the domain kernel level—no self-approvals allowed."*

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

### Segment 4: Dual-Signature Release, Cryptographic Export & Cloud Run Proof (2:45 – 4:00)
- **Visual**:
  - **[2:45 – 3:15] Dual-Signature Release Rail**:
    1. Switch Role to **QA Lead**; enter certified negative re-test lab document hash; complete **Step 1: Biological Clearance**.
    2. Show Step 2 remaining locked until **Closure Authority** (`key-closure-auth-01`) provides **Step 2: Operational Release Authorization**.
    3. Complete Step 2 (noting optional non-response escalation closure capabilities).
  - **[3:15 – 3:35] Cryptographic Audit Export & CLI Verification**:
    1. Navigate to the **Evidence Ledger**; click **"Download Cryptographic Audit Bundle"**.
    2. Show terminal executing `python scripts/verify_cloud_deploy.py https://lot-zero-1051797806634.us-central1.run.app` with 100% verified SHA-256 hash chain and 11 immutable events.
  - **[3:35 – 3:50] Google Cloud Console & Live Vertex AI Logs Proof**:
    1. Switch screen to the **Google Cloud Run Console** showing service `lot-zero` (region `us-central1`, persistent GCS FUSE volume mount `gs://lot-zero-events-project-b2c3348e-d718-4255-be2`).
    2. Highlight the genuine Cloud Logging execution line:  
       `[Gemini Agent] Successfully executed live on Vertex AI (location=global, model=gemini-3.5-flash)`
  - **[3:50 – 4:00] Closing Wrap-up**:
    1. Show the Lot Zero dashboard with all green gates.
- **Audio / Voiceover**:
  > *"To release a hold, Lot Zero enforces a statutory 2-Step Dual-Signature Rail: Step 1 requires the QA Lead's biological clearance bound to a certified negative re-test hash. Step 2 requires the Closure Authority's operational release.*
  > 
  > *When regulatory auditors arrive, we export a self-verifying JSON audit bundle where every event is cryptographically chained to its predecessor with a top-level SHA-256 root digest.*
  > 
  > *Here in the Google Cloud Console, we see our Cloud Run deployment backed by persistent Cloud Storage FUSE and our live Cloud Logging telemetry confirming genuine, live execution against Gemini 3.5 Flash on Vertex AI.*
  > 
  > *All 119 tests passing. That is Lot Zero: deterministic, evidence-backed recall management."*
