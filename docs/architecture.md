# Lot Zero — Technical Architecture

This document describes the architectural design, event flow, state transitions, security boundaries, and runtime topology of **Lot Zero**.

---

## 1. System Context & High-Level Flow

Lot Zero is structured as a decoupled, event-driven web application with a deterministic Python domain kernel at its center.

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (React / Vite)"]
        UI[Operational Dashboard SPA]
        SSE_SUB[SSE Event Subscriber]
    end

    subgraph APILayer ["API & Security Boundary (FastAPI)"]
        AUTH[Auth Interceptor /auth.py]
        ROUTES[Command Handlers /app.py]
        SSE_PUB[SSE Broadcaster /sse]
    end

    subgraph KernelLayer ["Domain Authority Kernel"]
        AUTHORITY[Authority Gate /authority.py]
        KERNEL[Command Processor /kernel.py]
        GROUNDING[Gemini Grounding /gemini_agent.py]
        GENEALOGY[Genealogy Traversal /recall.py]
    end

    subgraph StateLayer ["Event Store & Projections"]
        REDUCER[Pure State Reducer /reducer.py]
        REPO[SQLite Repository /sqlite_repository.py]
        LEDGER[Hash-Chained Ledger /ledger.py]
        PROJ[Materialized Projections /projections.py]
    end

    UI -->|Authenticated HTTP Requests| AUTH
    AUTH -->|Principal & Roles| ROUTES
    ROUTES -->|Verify Separation of Duties| AUTHORITY
    AUTHORITY -->|Execute Command| KERNEL
    KERNEL -->|Grounded Extractions| GROUNDING
    KERNEL -->|Compute Bounded Scope| GENEALOGY
    KERNEL -->|Emit Domain Events| REDUCER
    REDUCER -->|Append Event Records| REPO
    REPO -->|Record Entry Hash| LEDGER
    REDUCER -->|Update Projections| PROJ
    PROJ -->|Broadcast Updates| SSE_PUB
    SSE_PUB -->|Real-Time State Stream| SSE_SUB
```

---

## 2. Command & Event Processing Lifecycle

All domain mutations are driven by command packets processed through the deterministic authority kernel:

1. **Client Dispatches Command**: The frontend constructs a request (e.g. `POST /api/evaluation/approve-containment`) authenticated with the active operator's `X-API-Key`.
2. **Authentication & Identity Resolution**: [`auth.py`](../apps/api/src/lot_zero/auth.py) extracts the principal ID, tenant ID, and role permissions from configured API-key mappings across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator).
3. **Separation of Duties Verification**: [`authority.py`](../apps/api/src/lot_zero/domain/authority.py) verifies:
   - The operator possesses the required role (e.g. `qa`).
   - The approver is distinct from the requester (`requester_id != approver_id`).
   - The referenced proposal/packet/scope actually exists in the persisted event history.
4. **Command Execution**: [`kernel.py`](../apps/api/src/lot_zero/domain/kernel.py) evaluates current state, verifies optimistic concurrency version (`case_version`), and produces domain events.
5. **Pure State Reduction**: [`reducer.py`](../apps/api/src/lot_zero/domain/reducer.py) applies the events to produce an updated `IncidentState`.
6. **Persistence & Cryptographic Chaining**: [`sqlite_repository.py`](../apps/api/src/lot_zero/adapters/sqlite_repository.py) writes the events to `incident_events` and calculates the next SHA-256 hash in the chain.
7. **Projection & Broadcast**: Updated read models and wire projections are compiled by [`selectors.py`](../apps/api/src/lot_zero/domain/selectors.py) and broadcast to connected SSE clients.

---

## 3. Workflow Sequences

### A. Notification Request, Approval & Dispatch Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Coord as Recall Coordinator
    actor Ops as Customer Operations
    participant API as FastAPI /app.py
    participant Auth as Authority Kernel
    participant Reducer as Reducer / SQLite

    Coord->>API: POST /api/evaluation/request-notification (PKT-001)
    API->>Auth: Authorize (role: recall_coordinator)
    Auth->>Reducer: Emit NotificationRequestedEvent
    Reducer-->>API: State updated (notice requested)

    Note over Ops,API: Notification Approval Gate
    Ops->>API: POST /api/evaluation/approve-notification (PKT-001)
    API->>Auth: Verify Requester!=Approver & Exact Packet Match
    Auth->>Reducer: Emit NotificationApprovedEvent
    Reducer-->>API: State updated (notice approved)

    Note over Ops,API: Outbox Dispatch
    Ops->>API: POST /api/evaluation/dispatch-outbox
    API->>Auth: Authorize (role: customer_operations)
    Auth->>Reducer: Emit NoticeDispatchedEvents & Pending ACKs
    Reducer-->>API: State updated (ack_monitoring, ACK-006 outstanding)
```

---

### B. Consignee Resolution, Closure Request & Authorization Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Coord as Recall Coordinator
    actor Ops as Customer Operations
    actor AuthOff as Closure Authority
    participant API as FastAPI /app.py
    participant Auth as Authority Kernel
    participant Reducer as Reducer / SQLite

    Coord->>API: POST /api/evaluation/request-closure
    API->>Auth: Authorize (role: recall_coordinator)
    Auth->>Reducer: Emit ClosureRequestedEvent (REQ-001)
    Reducer-->>API: State updated (closure requested)

    Note over AuthOff,API: Attempt premature closure
    AuthOff->>API: POST /api/evaluation/authorize-closure
    API->>Auth: Check Closure Gate (ACK-006 unverified)
    Auth-->>API: Reject: Closure Gate Blocked

    Note over Ops,API: Phone Attestation
    Ops->>API: POST /api/evaluation/resolve-ack (ACK-006 oral attestation)
    API->>Reducer: Emit AcknowledgementVerifiedEvent
    Reducer-->>API: State updated (effectiveness_check, Closure Gate Ready)

    Note over AuthOff,API: Authorized Final Closure
    AuthOff->>API: POST /api/evaluation/authorize-closure (REQ-001)
    API->>Auth: Verify Requester!=Approver & Gate Unblocked
    Auth->>Reducer: Emit CaseClosedEvent
    Reducer-->>API: State updated (closed)
```

---

## 4. Multi-Tenant Isolation & Boundaries

- **Tenant Scoping**: Every database record and event entry is keyed by `tenant_id` (`EVAL-TENANT-01`).
- **Database Schema**: The SQLite event store enforces tenant boundaries:
  ```sql
  CREATE TABLE IF NOT EXISTS incident_events (
      tenant_id TEXT NOT NULL,
      case_id TEXT NOT NULL,
      stream_version INTEGER NOT NULL,
      event_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      payload TEXT NOT NULL,
      entry_hash TEXT NOT NULL,
      prior_entry_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (tenant_id, case_id, stream_version)
  );
  ```
- **Cross-Tenant Refusal**: Any request containing a principal whose tenant does not match the requested case returns `403 Forbidden` or `404 Not Found`.

---

## 5. Evaluation State Archiving & Reset Mechanism

To prevent test-run pollution during judging, `POST /api/evaluation/reset` executes an **archived baseline reset**:
1. It queries all events for `EVAL-TENANT-01`.
2. It transfers the existing events into `archived_evaluation_runs` with a timestamped `run_id`.
3. It initializes a clean baseline case in the `signal_received` phase for `EVAL-CASE-01`.
4. It broadcasts the clean baseline state to all SSE subscribers.

---

## 6. Server-Sent Events (SSE) Lifecycle & Token Authentication

1. **Client Token Request**: The SPA fetches an ephemeral token from `GET /api/evaluation/auth/token` authenticated via `X-API-Key`.
2. **HMAC Signature**: The backend generates an HMAC-SHA256 token encoding the principal ID, tenant ID, and an expiration timestamp (60s TTL).
3. **SSE Connection**: The frontend establishes `EventSource('/api/events?token=<hmac_token>')`.
4. **Broadcast Loop**: When any domain mutation updates `current_state`, `broadcast_state()` serializes the incident projection and delivers it across open SSE connections.

---

## 7. Deployment Topology (Google Cloud Run)

```mermaid
flowchart LR
    Browser[Web Browser] -->|HTTPS| CloudRun[Google Cloud Run Container]
    CloudRun -->|FastAPI Static Mount| SPA[Vite React SPA]
    CloudRun -->|FastAPI REST / SSE| Backend[Lot Zero Python App]
    Backend -->|Async Vertex AI Calls| VertexAI[Gemini 3.5 Flash]
    Backend -->|Local Ephemeral Storage| DB[lot_zero.db /tmp]
```

---

## 8. Architectural Limitations & Future Work

1. **In-Memory Concurrency & Single-Instance Lock**: The application uses `asyncio.Lock()` (`state_lock`) around in-memory `current_state`. Scaling horizontally requires migrating to a managed distributed transactional database (such as Google Cloud SQL for PostgreSQL or Cloud Spanner) with distributed optimistic concurrency leases.
2. **Local Ephemeral SQLite on Cloud Run**: In evaluation deployment, SQLite runs on container-local ephemeral storage. State resets when a new revision deploys or after cold start recycling. Persistent enterprise deployment requires a managed database backend.
3. **Identity Provider Integration & Secret Management**: Current authentication resolves principals via configured API-key dictionaries. Integration with enterprise OIDC/SAML providers and runtime Secret Manager binding is planned as future work.
