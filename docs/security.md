# Lot Zero — Security, Governance & Trust Model

This document outlines the security architecture, threat model, trust assumptions, governance controls, and known technical limitations of **Lot Zero**.

> [!IMPORTANT]
> **Prototype Disclosure**: Lot Zero is an evaluation prototype designed to demonstrate grounded AI ingestion, deterministic authority kernels, and separation-of-duties governance under simulated FDA recall scenarios. It is not an enterprise-certified food safety system.

---

## 1. Threat Boundaries & System Trust Model

```
+-------------------------------------------------------------------------+
| UNTRUSTED EXTERNAL ZONE                                                 |
| - Unauthenticated HTTP requests                                         |
| - Arbitrary client request bodies                                       |
| - Raw third-party laboratory unstructured text reports                  |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ [auth.py: API Key / Token Auth]
+-------------------------------------------------------------------------+
| AUTHENTICATED OPERATOR ZONE                                             |
| - 5 Evaluation Personas (4 Operational Personas + Evaluation Admin)     |
| - Separation of duties verification                                     |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ [authority.py: Authority Kernel]
+-------------------------------------------------------------------------+
| DETERMINISTIC DOMAIN KERNEL (TRUSTED)                                   |
| - Gemini character-offset mechanical grounding validation               |
| - Exact supply chain genealogy calculation                              |
| - State machine transition validation                                   |
| - Pure state reducer                                                    |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ [sqlite_repository.py / ledger.py]
+-------------------------------------------------------------------------+
| APPEND-ORIENTED AUDIT EVENT STORE & HASH CHAIN                          |
| - SHA-256 linked event ledger                                           |
| - Archived evaluation run store                                         |
+-------------------------------------------------------------------------+
```

---

## 2. Authentication & Fail-Closed Production Configuration

### Evaluation Mode (`LOT_ZERO_EVALUATION_MODE=true`)
- Pre-configured evaluation API keys are accepted (`key-recall-coord-01`, `key-qa-lead-01`, etc.).
- The client UI exposes the persona switcher to facilitate judge walkthroughs across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator).
- `POST /api/evaluation/reset` is accessible to `EVAL-ADMIN-01` to archive prior runs and establish a clean baseline.

### Non-Evaluation Mode (`LOT_ZERO_EVALUATION_MODE=false`)
- **Fails Closed on Startup**: Startup fails fast with `RuntimeError` if `LOT_ZERO_API_KEYS`, a strong `LOT_ZERO_SSE_SECRET` ($\ge 32$ characters, non-default), or explicit `LOT_ZERO_ALLOWED_ORIGINS` are missing.
- **Frontend Fails Closed**: The frontend bootstraps by requesting `/api/config`. When `evaluation_mode` is false, `personas` is empty `[]`, no evaluation keys are loaded from localStorage, and the persona switcher is disabled.
- **Demo Key Rejection**: Fixed evaluation keys are rejected with `401 Unauthorized` unless explicitly registered in the configured `LOT_ZERO_API_KEYS` mapping.
- **Reset Endpoint Disabled**: `POST /api/evaluation/reset` returns `404 Not Found`.
- **Identity Provider Scope**: Current production-like authentication resolves principals via configured `LOT_ZERO_API_KEYS` JSON mappings with Bearer/header lookup. Enterprise OIDC / SAML SSO integration with signed JWT/JWKS validation is planned as future work.

---

## 3. Separation of Duties (Anti-Self-Approval)

To prevent rogue actors or mistakes from bypassing safety gates:
1. **Requester-Approver Disjointness**: The authority kernel strictly verifies `requester_id != approver_id`. If the operator who requested a hold, notification, or closure attempts to approve it, the backend returns **HTTP 403 Forbidden**.
2. **Role-Scoped Capabilities**:
   - `recall_coordinator`: Can simulate signals, request holds, draft notifications, and request closures. Cannot approve firm quarantines or sign closures.
   - `qa`: Can approve firm quarantine and sign Step 1 biological clearances. Cannot draft consignee notices or authorize operational releases.
   - `customer_operations`: Can approve notice packets, dispatch outboxes, and log consignee oral attestations. Cannot approve biological clearances or execute final closures.
   - `closure_authority`: Can execute Step 2 operational releases and authorize final closures. Cannot initiate signals or approve notification packets.
3. **Dual-Signature Release Rail**: Releasing a quarantined batch requires two distinct signatures in sequence:
   - **Step 1 (QA Lead)**: Biological clearance confirming negative re-test laboratory documentation.
   - **Step 2 (Closure Authority)**: Operational release authorization.

---

## 4. Evidence Grounding & Hallucination Prevention

To eliminate generative AI hallucinations in food safety operations:
1. **Verbatim Citation Matching**: When Gemini extracts the pathogen name and contaminated lot, it must return exact `start_offset` and `end_offset` indexes corresponding to the lab document.
2. **Digest Anchoring**: The extraction is dynamically checked against the SHA-256 hash of the ingested report. If offsets fail to match verbatim text in the source report, the extraction is rejected.
3. **Deterministic Quantity Calculation**: Gemini is **never** permitted to calculate or estimate inventory quantities. All quantities on hold are calculated deterministically by traversing supply chain records in Python.

---

## 5. Exact Notification Approval Identity & Status Handling

When Customer Operations approves a recall notice packet:
- The command specifies the exact `packet_id`, `scope_id`, `scope_version`, `payload_version`, `payload_hash`, and `policy_version`.
- The authority kernel verifies these parameters against the active `IncidentState`.
- Any mismatch or invalid authority state is rejected (e.g. 400 Bad Request or 409 Conflict), producing zero approved dispatches and appending zero authorization events to the ledger.

---

## 6. Closure Gate & Version Concurrency

- **Closure Blockers**: Case closure is blocked while any consignee acknowledgement remains unverified (`is_blocked: true`).
- **Synthetic Non-Response Path**: If a consignee fails to respond after 3 documented contact attempts, synthetic non-response documentation with a modeled referral note is recorded before closure can proceed (not a legal or regulatory certification).
- **Optimistic Concurrency**: Mutation commands verify `case_version`. If another operator mutated the case concurrently, the command fails with `409 Conflict`, preventing race conditions.

---

## 7. Audit Hash Chains: Guarantees & Non-Guarantees

### What the Audit Hash Chain Guarantees:
- **Tamper Evidence**: Every event entry includes `prior_entry_hash` and `entry_hash = SHA256(...)`. If any historic event payload, timestamp, or order is modified, the hash chain breaks.
- **Export Verification**: The verifier detects post-export payload changes, reordering, or record removal when checked against the originally retained root digest. Stronger completeness guarantees require an independently retained checkpoint.

### What It Does Not Guarantee:
- **Immutable Hardware Storage**: The local SQLite database file (`lot_zero.db`) resides on mutable filesystem storage. The hash chain detects tampering within the exported chain, but mutable storage does not prevent a privileged root administrator from modifying or deleting the database file. Stronger completeness guarantees against whole-database modification require an independently retained checkpoint or external WORM storage.

---

## 8. SSE Token Disclosure Considerations

- Ephemeral SSE tokens are passed as query parameters (`/api/events?token=<hmac_token>`).
- Tokens expire in 60 seconds and are bound to the specific tenant and principal.
- In production, server access logs should be configured to redact URL query parameters or use cookie-based SSE authentication to prevent token leakage in proxy logs.

---

## 9. Requirements for Production Deployment

Before Lot Zero could be deployed in a regulated commercial production environment:
1. Connect authentication to enterprise OIDC / SAML SSO with MFA.
2. Replace local SQLite with distributed event sourcing (e.g. Google Cloud SQL for PostgreSQL or Cloud Spanner).
3. Bind secrets via Google Cloud Secret Manager instead of raw environment variables.
4. Connect notification dispatch to authenticated SMTP / SMS / EDI gateways with delivery receipts.
5. Stream audit event logs to immutable cloud storage (e.g. Google Cloud Storage with Bucket Lock).
6. Conduct formal 21 CFR Part 11 software validation.
