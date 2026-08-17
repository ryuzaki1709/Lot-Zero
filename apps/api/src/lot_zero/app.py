"""FastAPI application for Lot Zero with live SSE streams, SQLite persistence, and API-key security."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from .adapters.demo_sink import DemoNotificationSink
from .adapters.sqlite_repository import SqliteIncidentRepository
from .auth import create_sse_token, get_current_principal, get_principal_for_key, require_role, verify_sse_token
from .domain.authority import Principal
from .domain.genealogy import GenealogyEdge, InventoryRecord, ShipmentRecord
from .domain.recall import FinishedLot, compute_impact
from .domain.scope import RecallScope, ScopePredicate
from .fixtures.loader import load_fixture
from .domain.commands import (
    AdvancePhaseCommand,
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
from .domain.selectors import RAW_TEXT, build_incident_projection

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
TENANT_ID = "EVAL-TENANT-01"
DEFAULT_CASE_ID = "EVAL-CASE-01"

app = FastAPI(
    title="Lot Zero Incident API",
    description="Deterministic evidence-backed recall incident platform",
    version="1.0.0",
)

# Valid CORS configuration with explicit origins and regex for credentials support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.run\.app",
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


@app.post("/api/sse-token")
async def issue_sse_token(principal: Principal = Depends(get_current_principal)):
    """Issue short-lived (60s) HMAC-signed token for EventSource authentication."""
    token = create_sse_token(principal, ttl_seconds=60)
    return {
        "token": token,
        "principal": principal.principal_id,
        "tenant": principal.tenant_id,
        "expires_in": 60,
    }


@app.get("/api/incidents/{case_id}/events")
async def sse_events(
    case_id: str,
    token: str | None = None,
    x_api_key: str | None = Header(default=None),
):
    """Subscribe to real-time incident state changes via Server-Sent Events.
    
    SECURITY AUDIT NOTE:
    Standard browser EventSource API does not support custom HTTP request headers (such as X-API-Key).
    To prevent unauthenticated stream reads, clients acquire a short-lived (60s) HMAC-signed token via
    POST /api/sse-token and provide it via the '?token=' query parameter.
    """
    principal = None
    if token:
        principal = verify_sse_token(token)
    elif x_api_key:
        principal = get_principal_for_key(x_api_key)

    if not principal:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed for SSE stream: Invalid, forged, or expired token.",
        )

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
            RAW_TEXT,
            case_id=current_state.case.case_id,
            tenant_id=TENANT_ID,
        )

        # 2. Derive domain inputs from authored fixture and execute deterministic graph traversal
        fixture = load_fixture("evaluation-tenant-v1")
        products = tuple(
            FinishedLot(
                record_id=lot.lot_id,
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                product_id=lot.product_id,
                lot_id=lot.lot_id,
                quantity=Decimal(str(lot.quantity)),
                produced_on=date(2026, 8, 14),
            )
            for lot in fixture.operations.affected_finished_lots
        ) + (
            FinishedLot(
                record_id=fixture.operations.adjacent_unaffected_batch.lot_id,
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                product_id=fixture.operations.adjacent_unaffected_batch.product_id,
                lot_id=fixture.operations.adjacent_unaffected_batch.lot_id,
                quantity=Decimal(str(fixture.operations.adjacent_unaffected_batch.quantity)),
                produced_on=date(2026, 8, 14),
            ),
        )
        edges = tuple(
            GenealogyEdge(
                edge_id=f"EDGE-{lot.lot_id}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                source_id=lot.ingredient_lot,
                target_id=lot.lot_id,
            )
            for lot in fixture.operations.affected_finished_lots
        ) + tuple(
            GenealogyEdge(
                edge_id=edge.edge_id,
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
            )
            for edge in fixture.operations.broken_genealogy_edges
        )
        adj_batch = fixture.operations.adjacent_unaffected_batch
        first_lot = fixture.operations.affected_finished_lots[0]
        inventory = tuple(
            InventoryRecord(
                record_id=f"INV-{lot.lot_id}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                lot_id=lot.lot_id,
                quantity=Decimal(str(lot.quantity)),
            )
            for lot in fixture.operations.affected_finished_lots
        ) + (
            InventoryRecord(
                record_id=f"INV-{adj_batch.lot_id}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                lot_id=adj_batch.lot_id,
                quantity=Decimal(str(adj_batch.quantity)),
            ),
        )
        shipments = (
            ShipmentRecord(
                record_id=f"SHIP-{first_lot.lot_id}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                lot_id=first_lot.lot_id,
                quantity=Decimal(str(fixture.operations.shipped_quantity)),
            ),
        )
        scope = RecallScope(
            scope_id="SCOPE-EVAL-01",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            evidence_ids=(signal_res.source_id,),
            predicates=(
                ScopePredicate(
                    predicate_id="PRED-INGREDIENT-01",
                    kind="ingredient_lot",
                    expected_value=signal_res.ingredient_lot,
                ),
                ScopePredicate(
                    predicate_id="PRED-PRODUCT-01",
                    kind="product_id",
                    expected_value="FP-100",
                ),
                ScopePredicate(
                    predicate_id="PRED-DATE-01",
                    kind="produced_on",
                    start_date=date(2026, 8, 14),
                    end_date=date(2026, 8, 14),
                ),
            ),
        )

        impact = compute_impact(scope, products, edges, inventory, shipments)
        affected_record_ids = impact.affected_finished_lot_ids
        affected_quantity = impact.affected_inventory_quantity

        # 3. Propose scope through domain authority
        scope_cmd = ProposeScopeCommand(
            kind="propose_scope",
            command_id=f"CMD-SCOPE-{current_state.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            affected_record_ids=affected_record_ids,
            affected_quantity=affected_quantity,
            evidence_record_ids=tuple(s.evidence_id for s in signal_res.spans) or ("EVID-01", "EVID-02", "EVID-03"),
            policy_version="EVAL-HOLD-01",
            ingredient_lot=signal_res.ingredient_lot,
            pathogen=signal_res.pathogen,
        )
        res1 = execute_command(current_state, scope_cmd, principal, occurred_at=now)
        if not res1.decision.allowed:
            raise HTTPException(status_code=400, detail=res1.decision.explanation)
        current_state = res1.state

        # Advance phase: signal_received -> scope_review
        adv_scope_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-SCOPE-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="scope_review",
        )
        res_adv_scope = execute_command(current_state, adv_scope_cmd, principal, occurred_at=now)
        if not res_adv_scope.decision.allowed:
            raise HTTPException(status_code=400, detail=res_adv_scope.decision.explanation)
        current_state = res_adv_scope.state

        all_signal_events = [*res1.events, *res_adv_scope.events]
        if affected_record_ids:
            # 4. Request provisional hold with 30-minute server-side TTL
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
                target_record_ids=affected_record_ids,
                quantity=affected_quantity,
            )
            res2 = execute_command(current_state, hold_cmd, principal, occurred_at=now)
            if not res2.decision.allowed:
                raise HTTPException(status_code=400, detail=res2.decision.explanation)
            current_state = res2.state

            # Advance phase: scope_review -> provisional_containment
            adv_hold_cmd = AdvancePhaseCommand(
                command_id=f"CMD-ADV-HOLD-{int(now.timestamp())}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                actor_id=principal.principal_id,
                case_version=current_state.case.case_version,
                target_phase="provisional_containment",
            )
            res_adv_hold = execute_command(current_state, adv_hold_cmd, principal, occurred_at=now)
            if not res_adv_hold.decision.allowed:
                raise HTTPException(status_code=400, detail=res_adv_hold.decision.explanation)
            current_state = res_adv_hold.state
            all_signal_events.extend([*res2.events, *res_adv_hold.events])

        await repository.append(
            current_state.case.case_id,
            expected_version=0,
            events=all_signal_events,
            tenant_id=principal.tenant_id,
        )

        await broadcast_state(current_state)
        return {
            "status": "signal_processed",
            "signal": signal_res,
            "projection": build_incident_projection(
                current_state,
                model_id=signal_res.model_version,
                ingredient_lot=signal_res.ingredient_lot,
                pathogen=signal_res.pathogen,
            ),
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
                raise HTTPException(status_code=403, detail=res1.decision.explanation)
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
            raise HTTPException(status_code=403, detail=res2.decision.explanation)
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

        # Advance: provisional_containment -> action_review
        adv_action_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-ACTION-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="action_review",
        )
        res_adv_action = execute_command(current_state, adv_action_cmd, principal, occurred_at=now)
        if res_adv_action.decision.allowed:
            current_state = res_adv_action.state

        all_events = [*res1.events, *res2.events, *res3.events, *res_adv_action.events] if "res1" in locals() else [*res2.events, *res3.events, *res_adv_action.events]
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
        res1 = execute_command(current_state, notif_cmd, principal, occurred_at=now)
        if not res1.decision.allowed:
            status_code = 403 if "lacks" in res1.decision.explanation.lower() or "role" in res1.decision.explanation.lower() else 400
            raise HTTPException(status_code=status_code, detail=res1.decision.explanation)
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
            res_ack = execute_command(current_state, ack_cmd, principal, occurred_at=now)
            if not res_ack.decision.allowed:
                status_code = 403 if "lacks" in res_ack.decision.explanation.lower() or "role" in res_ack.decision.explanation.lower() else 400
                raise HTTPException(status_code=status_code, detail=res_ack.decision.explanation)
            current_state = res_ack.state
            all_ack_events.extend(res_ack.events)

        # 3. Advance phase to ack_monitoring via domain command
        adv_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-ACK-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="ack_monitoring",
        )
        res_adv = execute_command(current_state, adv_cmd, principal, occurred_at=now)
        if not res_adv.decision.allowed:
            raise HTTPException(status_code=400, detail=res_adv.decision.explanation)
        current_state = res_adv.state
        all_ack_events.extend(res_adv.events)

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
        res_ack = execute_command(current_state, ack_cmd, principal, occurred_at=now)
        if not res_ack.decision.allowed:
            status_code = 403 if "lacks" in res_ack.decision.explanation.lower() or "role" in res_ack.decision.explanation.lower() else 400
            raise HTTPException(status_code=status_code, detail=res_ack.decision.explanation)
        current_state = res_ack.state

        events_to_append = list(res_ack.events)
        all_verified = len(current_state.acknowledgements) >= 6 and all(
            a.status == "verified" for a in current_state.acknowledgements
        )
        if all_verified and current_state.case.phase == "ack_monitoring":
            adv_eff_cmd = AdvancePhaseCommand(
                command_id=f"CMD-ADV-EFF-{int(now.timestamp())}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                actor_id=principal.principal_id,
                case_version=current_state.case.case_version,
                target_phase="effectiveness_check",
            )
            res_eff = execute_command(current_state, adv_eff_cmd, principal, occurred_at=now)
            if res_eff.decision.allowed:
                current_state = res_eff.state
                events_to_append.extend(res_eff.events)

        if events_to_append:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(events_to_append),
                events=events_to_append,
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
            status_code = 403 if "lacks" in res.decision.explanation.lower() or "role" in res.decision.explanation.lower() else 400
            raise HTTPException(status_code=status_code, detail=res.decision.explanation)
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
        res = execute_command(current_state, close_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            status_code = 403 if "lacks" in res.decision.explanation.lower() or "role" in res.decision.explanation.lower() else 400
            raise HTTPException(status_code=status_code, detail=res.decision.explanation)
        current_state = res.state

        adv_events = []
        if current_state.case.phase == "ack_monitoring":
            adv_eff_cmd = AdvancePhaseCommand(
                command_id=f"CMD-ADV-EFF-NONRESP-{int(now.timestamp())}",
                tenant_id=TENANT_ID,
                case_id=current_state.case.case_id,
                actor_id=principal.principal_id,
                case_version=current_state.case.case_version,
                target_phase="effectiveness_check",
            )
            res_eff = execute_command(current_state, adv_eff_cmd, principal, occurred_at=now)
            if res_eff.decision.allowed:
                current_state = res_eff.state
                adv_events.extend(res_eff.events)

        adv_close_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-CLOSE-NONRESP-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="closed",
        )
        res_close = execute_command(current_state, adv_close_cmd, principal, occurred_at=now)
        if not res_close.decision.allowed:
            raise HTTPException(status_code=400, detail=res_close.decision.explanation)
        current_state = res_close.state
        adv_events.extend(res_close.events)

        all_close_events = [*res.events, *adv_events]
        if all_close_events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(all_close_events),
                events=all_close_events,
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
        state_after_req = res1.state if res1.decision.allowed else current_state

        # 2. Attempt final closure approval
        closure_principal = Principal(tenant_id=TENANT_ID, principal_id="CLOSURE-AUTH-01", roles=("closure_authority",))
        close_app_cmd = ApproveClosureCommand(
            kind="approve_closure",
            command_id=f"CMD-CLOSE-APP-{state_after_req.case.case_version + 1}",
            tenant_id=TENANT_ID,
            case_id=state_after_req.case.case_id,
            actor_id="RECALL-COORD-01",
            case_version=state_after_req.case.case_version,
            approval_id=f"APP-CLOSE-{state_after_req.case.case_version + 1}",
            rationale="Requesting final incident closure following verified consignee containment.",
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            effectiveness_evidence_ids=("EVID-01", "EVID-02"),
        )
        res2 = execute_command(state_after_req, close_app_cmd, closure_principal, occurred_at=now)

        if not res2.decision.allowed:
            # If closure is blocked, do not mutate persistent state
            return {
                "status": "closure_blocked",
                "reason": res2.decision.explanation,
                "code": res2.decision.code,
                "blocked": True,
                "outstanding_acknowledgements": outstanding,
                "projection": build_incident_projection(current_state),
            }

        current_state = res2.state

        # 3. Advance phase to closed
        adv_close_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-CLOSE-{int(now.timestamp())}",
            tenant_id=TENANT_ID,
            case_id=current_state.case.case_id,
            actor_id=closure_principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="closed",
        )
        res_close = execute_command(current_state, adv_close_cmd, closure_principal, occurred_at=now)
        if not res_close.decision.allowed:
            raise HTTPException(status_code=400, detail=res_close.decision.explanation)
        current_state = res_close.state

        all_close_events = [*res1.events, *res2.events, *res_close.events] if res1.decision.allowed else [*res2.events, *res_close.events]
        if all_close_events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(all_close_events),
                events=all_close_events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {
            "status": "closed",
            "blocked": False,
            "projection": build_incident_projection(current_state),
        }


# ============================================================================
# Static Frontend Assets & SPA Fallback Route (Cloud Run & Local Multi-Stage)
# ============================================================================
web_dist_candidates = [
    Path("/app/apps/web/dist/client"),
    Path("/app/apps/web/dist"),
    Path("/app/web/dist/client"),
    Path("/app/web/dist"),
    Path(__file__).resolve().parents[3] / "web" / "dist" / "client",
    Path(__file__).resolve().parents[3] / "web" / "dist",
    Path(__file__).resolve().parents[4] / "apps" / "web" / "dist" / "client",
    Path(__file__).resolve().parents[4] / "apps" / "web" / "dist",
]
static_dir = next((p for p in web_dist_candidates if p.exists() and (p / "index.html").exists()), None)

if static_dir:
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Let explicit API routes pass through or 404
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"API endpoint '/{full_path}' not found")
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")
