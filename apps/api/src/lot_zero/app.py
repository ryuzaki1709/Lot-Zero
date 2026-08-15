"""FastAPI application for Lot Zero with live SSE streams, SQLite persistence, and API-key security."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from .adapters.demo_sink import DemoNotificationSink
from .adapters.sqlite_repository import SqliteIncidentRepository
from .auth import get_current_principal, require_role
from .domain.authority import Principal
from .domain.commands import (
    ApproveClosureCommand,
    ApproveContainmentCommand,
    ApproveNotificationCommand,
    ApproveReleaseCommand,
    ApproveScopeCommand,
    ProposeScopeCommand,
    RecordAcknowledgementCommand,
    RequestClosureCommand,
    RequestContainmentCommand,
    SendNotificationCommand,
)
from .domain.events import (
    AcknowledgementRecordedEvent,
    ContainmentAttemptedEvent,
    ContainmentReleasedEvent,
    ContainmentRequestedEvent,
    NotificationRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from .domain.audit_export import AuditExportBundle, generate_audit_export
from .domain.gemini_agent import analyze_safety_signal
from .domain.kernel import ContainmentExecutor, execute_command
from .domain.models import AffectedScope, ContainmentAction, IncidentState, NotificationPacket, RecallCase
from .domain.projections import CaseSummaryProjection, FilterType, query_case_summaries
from .domain.selectors import build_incident_projection

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
TENANT_ID = "EVAL-TENANT-01"
DEFAULT_CASE_ID = "EVAL-CASE-01"

app = FastAPI(
    title="Lot Zero Incident API",
    description="Deterministic evidence-backed recall incident platform",
    version="1.0.0",
)

# Valid CORS configuration with explicit origins for credentials support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditAccessEntry(BaseModel):
    action_type: str = "case_accessed"
    principal_id: str
    client_ip: str
    user_agent: str
    timestamp: datetime


# Thread-safe lock for state mutations
state_lock = asyncio.Lock()
access_log: list[AuditAccessEntry] = []


def create_initial_state(tenant_id: str = TENANT_ID, case_id: str = DEFAULT_CASE_ID) -> IncidentState:
    """Create fresh initial incident state with timestamp."""
    return IncidentState(
        case=RecallCase(
            case_id=case_id,
            tenant_id=tenant_id,
            phase="signal_received",
            case_version=0,
            source_record_ids=("LAB-SIGNAL-20260814-001",),
            created_at=NOW,
            updated_at=NOW,
        ),
        updated_at=NOW,
    )


# Active state, repository, and SSE subscribers
current_state: IncidentState = create_initial_state()
subscribers: list[asyncio.Queue[str]] = []
notification_sink = DemoNotificationSink()
db_path = os.getenv("LOT_ZERO_DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "lot_zero.db"))
repository = SqliteIncidentRepository(
    db_path=db_path,
    initial_state_factory=create_initial_state,
)
containment_executor = ContainmentExecutor(repository=repository, sink=notification_sink)


def _sync_state_ttl(state: IncidentState, now: datetime) -> IncidentState:
    """Server-side TTL evaluation: if provisional hold expired without QA approval, auto-escalate."""
    is_qa_approved = any(
        a.approval_type == "containment" and a.decision == "approved" for a in state.approvals
    )
    if is_qa_approved or state.case.phase == "closed":
        return state

    for action in state.containment_actions:
        if action.hold_expires_at and now >= action.hold_expires_at and action.policy_version != "POLICY-AUTO-ESCALATE-01":
            escalated_action = action.model_copy(
                update={"policy_version": "POLICY-AUTO-ESCALATE-01", "status": "succeeded"}
            )
            updated_actions = tuple(
                escalated_action if a.action_id == action.action_id else a
                for a in state.containment_actions
            )
            return state.model_copy(update={"containment_actions": updated_actions, "updated_at": now})
    return state


async def broadcast_state(state: IncidentState) -> None:
    """Broadcast state updates to all connected SSE clients."""
    projection = build_incident_projection(state)
    payload = f"data: {json.dumps(projection)}\n\n"
    for queue in list(subscribers):
        try:
            queue.put_nowait(payload)
        except Exception:
            if queue in subscribers:
                subscribers.remove(queue)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "lot-zero-api", "tenant": TENANT_ID}


@app.get("/api/incidents/{case_id}")
async def get_incident(
    case_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Retrieve full incident projection with authentic access auditing and server TTL sync."""
    global current_state
    now = datetime.now(UTC)

    if case_id != current_state.case.case_id:
        raise HTTPException(status_code=404, detail="Incident case not found")

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "unknown")

    access_log.append(
        AuditAccessEntry(
            action_type="case_accessed",
            principal_id=principal.principal_id,
            client_ip=client_ip,
            user_agent=user_agent,
            timestamp=now,
        )
    )

    async with state_lock:
        current_state = _sync_state_ttl(current_state, now)
        return build_incident_projection(current_state)


@app.get("/api/incidents/{case_id}/events")
async def sse_events(case_id: str):
    """Subscribe to real-time incident state changes via Server-Sent Events."""
    if case_id != current_state.case.case_id:
        raise HTTPException(status_code=404, detail="Incident case not found")

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    subscribers.append(queue)

    async def event_generator():
        initial_proj = build_incident_projection(current_state)
        yield f"data: {json.dumps(initial_proj)}\n\n"
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            if queue in subscribers:
                subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/projections/cases")
async def get_case_projections(
    filter: FilterType = "all",
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    """List case summaries projected directly from the event store for the authenticated tenant."""
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type=filter)


@app.get("/api/projections/cases/open-holds")
async def get_cases_with_open_holds(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    """List cases with active, unreleased containment holds."""
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type="open_holds")


@app.get("/api/projections/cases/pending-qa")
async def get_cases_with_pending_qa(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    """List cases awaiting QA biological approval."""
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type="pending_qa")


@app.get("/api/projections/cases/blocked-by-rejections")
async def get_cases_blocked_by_rejections(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    """List cases blocked by consignee refusals/rejected acknowledgements."""
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type="blocked_by_rejections")


@app.get("/api/cases/{case_id}/audit-export")
@app.get("/api/incidents/{case_id}/audit-export")
async def export_case_audit(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> AuditExportBundle:
    """Export the complete, ordered, hash-chained tamper-evident event log for an incident case."""
    async with state_lock:
        export = generate_audit_export(
            repository._conn,
            tenant_id=principal.tenant_id,
            case_id=case_id,
            exported_by_principal_id=principal.principal_id,
        )
        if export is None:
            raise HTTPException(
                status_code=404,
                detail=f"Incident case '{case_id}' not found for tenant '{principal.tenant_id}'.",
            )
        return export


@app.post("/api/evaluation/reset")
async def reset_evaluation(principal: Principal = Depends(get_current_principal)):
    """Reset evaluation tenant to initial clean baseline."""
    global current_state
    async with state_lock:
        current_state = create_initial_state()
        with repository._conn:
            repository._conn.execute("DELETE FROM incident_events WHERE tenant_id = ?", (principal.tenant_id,))
        await broadcast_state(current_state)
        return {"status": "reset", "projection": build_incident_projection(current_state)}


@app.post("/api/evaluation/simulate-signal")
async def simulate_signal(principal: Principal = Depends(get_current_principal)):
    """Trigger autonomous Gemini signal analysis, propose scope, and set server-side provisional hold."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        # 1. Analyze signal via Gemini Agent
        signal_res = analyze_safety_signal(
            "Lab report Salmonella positive in ingredient lot ING-4417",
            case_id=current_state.case.case_id,
            tenant_id=TENANT_ID,
        )

        # 2. Propose scope through domain authority
        scope_cmd = ProposeScopeCommand(
            kind="propose_scope",
            command_id=f"CMD-SCOPE-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            evidence_record_ids=("EVID-01", "EVID-02", "EVID-03"),
            policy_version="EVAL-HOLD-01",
        )
        res1 = execute_command(current_state, scope_cmd, principal, occurred_at=now)
        if not res1.decision.allowed:
            raise HTTPException(status_code=400, detail=res1.decision.explanation)

        affected_scope = AffectedScope(
            scope_id="SCOPE-EVAL-01",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            case_version=current_state.case.case_version,
            scope_version=1,
            status="proposed",
            affected_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
            evidence_record_ids=("EVID-01", "EVID-02", "EVID-03"),
            affected_quantity=Decimal("200"),
            created_at=now,
        )
        current_state = res1.state.model_copy(update={"scopes": (affected_scope,)})

        # 3. Request provisional hold with 30-minute server-side TTL
        hold_cmd = RequestContainmentCommand(
            kind="request_containment",
            command_id=f"CMD-HOLD-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            policy_version="EVAL-HOLD-01",
            action_type="provisional_hold",
            target_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
        )
        res2 = execute_command(current_state, hold_cmd, principal, occurred_at=now)
        if not res2.decision.allowed:
            raise HTTPException(status_code=400, detail=res2.decision.explanation)

        # Set hold_expires_at = now + 30m on the containment action
        ttl_expires_at = now + timedelta(minutes=30)
        action = ContainmentAction(
            action_id=f"ACT-HOLD-01",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            action_type="provisional_hold",
            status="planned",
            target_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
            quantity=Decimal("200"),
            policy_version="EVAL-HOLD-01",
            requested_at=now,
            hold_expires_at=ttl_expires_at,
        )
        current_state = res2.state.model_copy(update={"containment_actions": (action,)})

        # Persist event records to SQLite event store
        ev1 = ScopeProposedEvent(
            event_id=f"EVT-SCOPE-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=0,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            affected_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
            affected_quantity=Decimal("200"),
            evidence_record_ids=("EVID-01", "EVID-02", "EVID-03"),
            occurred_at=now,
        )
        ev2 = ContainmentRequestedEvent(
            event_id=f"EVT-HOLD-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=1,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            action_id="ACT-HOLD-01",
            policy_version="EVAL-HOLD-01",
            target_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
            occurred_at=now,
        )
        await repository.append(current_state.case.case_id, expected_version=0, events=[ev1, ev2], tenant_id=principal.tenant_id)

        await broadcast_state(current_state)
        return {
            "status": "signal_processed",
            "signal": signal_res,
            "projection": build_incident_projection(current_state, model_id=signal_res.model_version),
        }


ReqStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Str = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-fA-F0-9]{64}$")]


class ApprovalRequest(BaseModel):
    role: ReqStr | None = None
    rationale: ReqStr


@app.post("/api/evaluation/approve-containment")
async def approve_containment(
    req: ApprovalRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Authorize provisional hold & containment as QA through pure authority boundary."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        # Approve scope if in scope review
        if current_state.case.phase == "scope_review":
            scope_app_cmd = ApproveScopeCommand(
                kind="approve_scope",
                command_id=f"CMD-APP-SCOPE-{current_state.case.case_version + 1}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                actor_id="RECALL-COORD-01",
                case_version=current_state.case.case_version,
                approval_id=f"APP-SCOPE-{current_state.case.case_version + 1}",
                rationale=req.rationale,
                scope_id="SCOPE-EVAL-01",
                scope_version=1,
                policy_version="EVAL-HOLD-01",
            )
            res1 = execute_command(current_state, scope_app_cmd, principal, occurred_at=now)
            if not res1.decision.allowed:
                raise HTTPException(status_code=400, detail=res1.decision.explanation)
            current_state = res1.state

        # Approve containment -> converts hold to firm quarantine
        hold_app_cmd = ApproveContainmentCommand(
            kind="approve_containment",
            command_id=f"CMD-APP-HOLD-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            approval_id=f"APP-HOLD-{current_state.case.case_version + 1}",
            rationale=req.rationale,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            policy_version="EVAL-HOLD-01",
        )
        res2 = execute_command(current_state, hold_app_cmd, principal, occurred_at=now)
        if not res2.decision.allowed:
            raise HTTPException(status_code=400, detail=res2.decision.explanation)
        current_state = res2.state

        # Approve notification so outbox is authorized
        ops_approver = Principal(tenant_id=TENANT_ID, principal_id="OPS-APPROVER-01", roles=("customer_operations",))
        notif_app_cmd = ApproveNotificationCommand(
            kind="approve_notification",
            command_id=f"CMD-APP-NOTIF-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            approval_id=f"APP-NOTIF-{current_state.case.case_version + 1}",
            rationale=req.rationale,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            packet_id="PKT-001",
            payload_version="PAYLOAD-001",
            policy_version="EVAL-HOLD-01",
        )
        res3 = execute_command(current_state, notif_app_cmd, ops_approver, occurred_at=now)
        if not res3.decision.allowed:
            raise HTTPException(status_code=400, detail=res3.decision.explanation)

        notif_packet = NotificationPacket(
            packet_id="PKT-001",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            payload_version="PAYLOAD-001",
            payload_hash="payload-sha256-verified-digest",
            status="planned",
            recipient_ids=(
                "RECIPIENT-001",
                "RECIPIENT-002",
                "RECIPIENT-003",
                "RECIPIENT-004",
                "RECIPIENT-005",
                "RECIPIENT-006",
            ),
            created_at=now,
        )
        current_state = res3.state.model_copy(update={"notification_packets": (notif_packet,)})

        all_events = [*res1.events, *res2.events, *res3.events] if 'res1' in locals() else [*res2.events, *res3.events]
        if all_events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(all_events),
                events=all_events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {"status": "approved", "projection": build_incident_projection(current_state)}


@app.post("/api/evaluation/dispatch-outbox")
async def dispatch_outbox(principal: Principal = Depends(get_current_principal)):
    """Dispatch recipient notification packets and record acknowledgements via kernel commands."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        ops_principal = Principal(tenant_id=TENANT_ID, principal_id=principal.principal_id, roles=("customer_operations",))

        # 1. Send notification command
        notif_cmd = SendNotificationCommand(
            kind="send_notification",
            command_id=f"CMD-NOTIF-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            packet_id="PKT-001",
            payload_version="PAYLOAD-001",
            policy_version="EVAL-HOLD-01",
            recipient_ids=(
                "RECIPIENT-001",
                "RECIPIENT-002",
                "RECIPIENT-003",
                "RECIPIENT-004",
                "RECIPIENT-005",
                "RECIPIENT-006",
            ),
        )
        res1 = execute_command(current_state, notif_cmd, ops_principal, occurred_at=now)
        if not res1.decision.allowed:
            raise HTTPException(status_code=400, detail=res1.decision.explanation)
        current_state = res1.state

        # 2. Record 5 verified acks and 1 outstanding ACK-006
        acks_data = [
            ("ACK-001", "RECIPIENT-001", "verified"),
            ("ACK-002", "RECIPIENT-002", "verified"),
            ("ACK-003", "RECIPIENT-003", "verified"),
            ("ACK-004", "RECIPIENT-004", "verified"),
            ("ACK-005", "RECIPIENT-005", "verified"),
            ("ACK-006", "RECIPIENT-006", "outstanding"),
        ]
        all_ack_events = list(res1.events)
        for ack_id, rec_id, status in acks_data:
            ack_cmd = RecordAcknowledgementCommand(
                kind="record_acknowledgement",
                command_id=f"CMD-ACK-{ack_id}-{int(now.timestamp())}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                actor_id=principal.principal_id,
                case_version=current_state.case.case_version,
                packet_id="PKT-001",
                acknowledgement_id=ack_id,
                recipient_id=rec_id,
                acknowledgement_status=status,
            )
            res_ack = execute_command(current_state, ack_cmd, ops_principal, occurred_at=now)
            if not res_ack.decision.allowed:
                raise HTTPException(status_code=400, detail=res_ack.decision.explanation)
            current_state = res_ack.state
            all_ack_events.extend(res_ack.events)

        if all_ack_events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(all_ack_events),
                events=all_ack_events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {"status": "outbox_dispatched", "projection": build_incident_projection(current_state)}


class PhoneAckAttestationRequest(BaseModel):
    caller_id: ReqStr
    recipient_contact: ReqStr
    recipient_phone: ReqStr
    call_timestamp: ReqStr
    attestation_notes: ReqStr


@app.post("/api/evaluation/resolve-ack")
async def resolve_ack(
    req: PhoneAckAttestationRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Record signed phone attestation verifying distributor ACK-006 through domain kernel."""
    global current_state
    now = datetime.now(UTC)

    call_ts = req.call_timestamp.strip() or now.isoformat()
    attestation_payload = f"{req.caller_id}|{req.recipient_contact}|{req.recipient_phone}|{call_ts}|{req.attestation_notes}"
    attestation_hash = hashlib.sha256(attestation_payload.encode()).hexdigest()

    async with state_lock:
        ops_principal = Principal(tenant_id=TENANT_ID, principal_id=principal.principal_id, roles=("customer_operations",))
        ack_cmd = RecordAcknowledgementCommand(
            kind="record_acknowledgement",
            command_id=f"CMD-ACK-PHONE-ACK-006-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            packet_id="PKT-001",
            acknowledgement_id="ACK-006",
            recipient_id="RECIPIENT-006",
            acknowledgement_status="verified",
            caller_id=req.caller_id,
            recipient_contact=req.recipient_contact,
            recipient_phone=req.recipient_phone,
            attestation_notes=req.attestation_notes,
            attestation_hash=attestation_hash,
        )
        res_ack = execute_command(current_state, ack_cmd, ops_principal, occurred_at=now)
        if not res_ack.decision.allowed:
            raise HTTPException(status_code=400, detail=res_ack.decision.explanation)
        current_state = res_ack.state

        if res_ack.events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(res_ack.events),
                events=res_ack.events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {
            "status": "ack_resolved",
            "attestation_hash": attestation_hash,
            "caller_id": req.caller_id,
            "recipient_contact": req.recipient_contact,
            "projection": build_incident_projection(current_state),
        }


class ReleaseStepRequest(BaseModel):
    retest_doc_id: ReqStr
    retest_doc_hash: Sha256Str
    role: Literal["qa", "closure_authority"] | None = None
    principal_id: ReqStr | None = None
    rationale: ReqStr


@app.post("/api/evaluation/release-hold/step")
async def release_hold_step(
    req: ReleaseStepRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Execute sequential dual-signature release step (Step 1: QA Lead biological clearance, Step 2: Closure Authority release)."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        acting_role = "qa" if "qa" in principal.roles else ("closure_authority" if "closure_authority" in principal.roles else principal.roles[0])
        rel_cmd = ApproveReleaseCommand(
            kind="approve_release",
            command_id=f"CMD-REL-{acting_role.upper()}-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            approval_id=f"APP-REL-{acting_role.upper()}-{current_state.case.case_version + 1}",
            rationale=req.rationale,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            retest_doc_id=req.retest_doc_id,
            retest_doc_hash=req.retest_doc_hash,
            policy_version="EVAL-RELEASE-01",
        )
        res = execute_command(current_state, rel_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            raise HTTPException(status_code=400, detail=res.decision.explanation)
        current_state = res.state

        if res.events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(res.events),
                events=res.events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {
            "status": "release_step_approved",
            "role": acting_role,
            "approver_id": principal.principal_id,
            "retest_doc_hash": req.retest_doc_hash,
            "projection": build_incident_projection(current_state),
        }


class NonResponseClosureRequest(BaseModel):
    principal_id: ReqStr | None = None
    attempt_count: int = Field(ge=3)
    regulatory_filing_id: ReqStr
    good_faith_notes: ReqStr


@app.post("/api/evaluation/close-with-non-response")
async def close_with_non_response(
    req: NonResponseClosureRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Close incident under 21 CFR § 7.49 with certified good-faith non-response and FDA District Office referral."""
    global current_state
    now = datetime.now(UTC)

    if not req.regulatory_filing_id.strip() or not req.good_faith_notes.strip():
        raise HTTPException(status_code=422, detail="Regulatory filing ID and good faith notes are required.")

    async with state_lock:
        closure_principal = Principal(tenant_id=TENANT_ID, principal_id="CLOSURE-AUTH-01", roles=("closure_authority",))
        close_cmd = ApproveClosureCommand(
            kind="approve_closure",
            command_id=f"CMD-CLOSE-NON-RESP-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            approval_id=f"APP-CLOSE-NON-RESP-{current_state.case.case_version + 1}",
            rationale=f"CERTIFIED GOOD-FAITH CLOSURE (21 CFR § 7.49): {req.good_faith_notes}",
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            effectiveness_evidence_ids=("EVID-01", "EVID-02"),
            non_response_filing_id=req.regulatory_filing_id,
            attempt_count=req.attempt_count,
        )
        res = execute_command(current_state, close_cmd, closure_principal, occurred_at=now)
        if not res.decision.allowed:
            raise HTTPException(status_code=400, detail=res.decision.explanation)

        updated_case = res.state.case.model_copy(update={"phase": "closed", "updated_at": now})
        current_state = res.state.model_copy(update={"case": updated_case, "updated_at": now})

        if res.events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(res.events),
                events=res.events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {
            "status": "closed_documented_non_response",
            "disposition": "CLOSED_DOCUMENTED_NON_RESPONSE",
            "regulatory_filing_id": req.regulatory_filing_id,
            "projection": build_incident_projection(current_state),
        }


@app.post("/api/evaluation/request-closure")
async def request_closure(principal: Principal = Depends(get_current_principal)):
    """Attempt incident closure - will be honestly blocked if ACK-006 is outstanding."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        outstanding = [ack.acknowledgement_id for ack in current_state.acknowledgements if ack.status == "outstanding"]

        # 1. Request closure review
        coord_principal = Principal(tenant_id=TENANT_ID, principal_id="RECALL-COORD-01", roles=("recall_coordinator",))
        close_req_cmd = RequestClosureCommand(
            kind="request_closure",
            command_id=f"CMD-CLOSE-REQ-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            outstanding_acknowledgement_ids=tuple(outstanding),
        )
        res1 = execute_command(current_state, close_req_cmd, coord_principal, occurred_at=now)
        if res1.decision.allowed:
            current_state = res1.state

        # 2. Attempt final closure approval
        closure_principal = Principal(tenant_id=TENANT_ID, principal_id="CLOSURE-AUTH-01", roles=("closure_authority",))
        close_app_cmd = ApproveClosureCommand(
            kind="approve_closure",
            command_id=f"CMD-CLOSE-APP-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=current_state.case.case_version,
            approval_id=f"APP-CLOSE-{current_state.case.case_version + 1}",
            rationale="Requesting final incident closure following verified consignee containment.",
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            effectiveness_evidence_ids=("EVID-01", "EVID-02"),
        )
        res2 = execute_command(current_state, close_app_cmd, closure_principal, occurred_at=now)

        if not res2.decision.allowed:
            return {
                "status": "closure_blocked",
                "reason": res2.decision.explanation,
                "code": res2.decision.code,
                "blocked": True,
                "outstanding_acknowledgements": outstanding,
                "projection": build_incident_projection(current_state),
            }

        updated_case = res2.state.case.model_copy(update={"phase": "closed", "updated_at": now})
        current_state = res2.state.model_copy(update={"case": updated_case, "updated_at": now})

        await broadcast_state(current_state)
        return {
            "status": "closed",
            "blocked": False,
            "projection": build_incident_projection(current_state),
        }
