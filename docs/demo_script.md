# Lot Zero — Demonstration Script for Evaluators & Video Recording

This script provides step-by-step instructions for demonstrating **Lot Zero** in a live evaluation or video presentation.

---

## Part 1: Primary Demo Script (2–3 Minutes)

### Step 0: Baseline Preparation
- **Persona**: `Evaluation Administrator` (select in top right dropdown).
- **Action**: Click **Reset State** -> Click **Reset Evaluation State** in modal.
- **Verification**: Header displays `signal_received` phase, Units on hold: `0`, False holds: `0`, Ledger events: `0`.
- **Narration**: *"We start with a clean evaluation baseline. Lot Zero is connected to an append-oriented event store."*

---

### Step 1: Lab Signal Ingestion & Grounding
- **Persona**: Switch to `Recall Coordinator`.
- **Action**: Click **Simulate Signal**.
- **Verification**:
  - Phase advances to `provisional_containment`.
  - Signal Viewer highlights *Salmonella enterica serovar Typhimurium* and Lot `ING-4417` with green verbatim citation offset boxes anchored to SHA-256 digest `e3b0c442...`.
  - Units on hold displays `200` units (`FP-100-AFF`).
  - False holds displays `0` units (proves adjacent batch `FP-100-ADJ` is unquarantined).
  - Standing policy: `EVAL-HOLD-01 · provisional soft hold (30m)`.
- **Narration**: *"An incoming Apex Labs report is parsed by Gemini 3.5 Flash. The agent extracts contaminated lot ING-4417 with exact character-offset citations. It immediately traverses the supply chain graph and places a 30-minute soft hold on 200 affected units, while leaving adjacent clean batches untouched with zero false holds."*

---

### Step 2: QA Quarantine Approval Gate
- **Persona**: Switch to `QA Lead`.
- **Action**:
  - Notice the **QA Approval Rationale** text box is enabled.
  - Click **Approve Firm Quarantine (QA)**.
- **Verification**:
  - Phase advances to `action_review`.
  - Standing policy upgrades to `AUTH-HOLD-01 · firm quarantine`.
  - Signed approval badge `AUTH-HOLD-01` appears under Governance.
- **Narration**: *"The agent cannot permanently quarantine product alone. The QA Lead reviews the evidence and signs off, upgrading the soft hold into authorized firm quarantine under policy AUTH-HOLD-01."*

---

### Step 3: Outbound Consignee Notice Drafting & Approval
- **Persona**: Switch to `Recall Coordinator`.
- **Action**: Click **Request Notification Packet (Coord)**.
- **Verification**: Button updates to `Packet PKT-001 Requested`.
- **Persona**: Switch to `Customer Operations`.
- **Action**: Click **Approve Notification Packet (Ops)**.
- **Verification**: Button updates to `Notification Approved (Ops)`.
- **Narration**: *"Separation of duties in action: the Recall Coordinator requests the formal recall notice packet, and Customer Operations reviews and authorizes the outbound consignment payload."*

---

### Step 4: Outbox Dispatch & Blocked Closure Demonstration
- **Persona**: Stay on `Customer Operations`.
- **Action**: Click **Dispatch Recall Outbox (Ops)**.
- **Verification**:
  - Phase advances to `ack_monitoring`.
  - Outreach table displays consignees: `ACK-001`, `ACK-002`, `ACK-003`, `ACK-004`, `ACK-005` verified, but `ACK-006` is **Unverified**.
- **Persona**: Switch to `Recall Coordinator`.
- **Action**: Click **Request Incident Closure (Coord)**.
- **Verification**:
  - Closure Gate alert banner displays: *Awaiting verified consignment acknowledgement from: ACK-006*.
  - Closure Authority button is disabled / blocked.
- **Narration**: *"Recall notices are dispatched. But distributor ACK-006 has not acknowledged receipt. If we attempt to close the incident, the system strictly refuses. This is authentic workflow modeling inspired by FDA recall-effectiveness practices."*

---

### Step 5: Consignee Phone Attestation & Final Closure
- **Persona**: Switch to `Customer Operations`.
- **Action**:
  - In the Outreach table next to `ACK-006`, click **Log Phone Attestation**.
  - Review pre-filled oral attestation details (Contact: David Miller, Note: 'All units dock quarantined').
  - Click **Submit Attestation**.
- **Verification**:
  - Phase advances to `effectiveness_check`.
  - All 6/6 consignees are marked **Verified**.
  - Closure gate changes to green: *All 6/6 Consignees Verified*.
- **Persona**: Switch to `Closure Authority`.
- **Action**: Click **Authorize Final Closure (Auth)**.
- **Verification**:
  - Phase advances to `closed`.
  - Units on hold returns to `0`.
  - Evidence Ledger displays: *Incident disposition complete — tamper-evident audit record archived under 21 CFR*.
- **Narration**: *"Customer Operations logs a phone attestation from the distributor. With all consignees verified, the Closure Authority signs the final closure command, moving the incident to closed status."*

---

### Step 6: Self-Verifying Audit Export
- **Action**: Click **Export Audit Bundle** in the top navigation bar.
- **Verification**: A JSON file `lot_zero_audit_EVAL-CASE-01.json` is downloaded containing all hash-chained events with `prior_entry_hash` and top-level `root_digest`.
- **Narration**: *"Every single decision, approval, and state transition was recorded to an append-oriented event store with a SHA-256 cryptographic hash chain, providing a self-verifying audit bundle for regulators."*

---

## Part 2: Fast 60-Second Fallback Script

1. **Start at Reset** (`Eval Admin`): Click **Reset State** (0s–5s).
2. **Ingest Signal** (`Recall Coord`): Click **Simulate Signal** -> Highlight Gemini character-exact citation and 0 false holds (5s–20s).
3. **QA Approval** (`QA Lead`): Click **Approve Firm Quarantine** (20s–30s).
4. **Notice & Dispatch** (`Recall Coord` -> `Customer Ops`): Click **Request Packet** -> Click **Approve Packet** -> Click **Dispatch Outbox** (30s–45s).
5. **Resolve & Close** (`Customer Ops` -> `Closure Auth`): Click **Log Phone Attestation** on `ACK-006` -> Click **Authorize Final Closure** -> Highlight case closed state (45s–60s).

---

## Part 3: Troubleshooting & Recovery

- **If a button is disabled**: Check the top-right persona selector. Ensure the active persona matches the required role indicated in the button label / tooltip.
- **If the network disconnects**: Check the SSE indicator in the top bar. If it shows "Offline", click **Refresh** on the Incident card or reload the page.
- **To restart the demo from scratch**: Switch to `Evaluation Administrator` and click **Reset State**.
