"""FastAPI application for Lot Zero with live SSE streams, SQLite persistence, and API-key security."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from .adapters.demo_sink import DemoNotificationSink
from .adapters.sqlite_repository import SqliteIncidentRepository
from .auth import (
    create_sse_token,
    get_current_principal,
    get_evaluation_personas,
    get_principal_for_key,
    verify_sse_token,
)
from .config import load_config, validate_config_for_startup
from .domain.audit_export import AuditExportBundle, generate_audit_export
from .domain.authority import Principal
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
    RequestNotificationCommand,
    SendNotificationCommand,
)
from .domain.gemini_agent import analyze_safety_signal
from .domain.genealogy import GenealogyEdge, InventoryRecord, ShipmentRecord
from .domain.kernel import ContainmentExecutor, execute_command
from .domain.models import (
    IncidentState,
    RecallCase,
)
from .domain.projections import CaseSummaryProjection, FilterType, query_case_summaries
from .domain.recall import FinishedLot, compute_impact
from .domain.scope import RecallScope, ScopePredicate
from .domain.selectors import RAW_TEXT, build_incident_projection
from .fixtures.loader import load_fixture

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("lot_zero.app")

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
DEFAULT_CASE_ID = "EVAL-CASE-01"

config = load_config()

ReqStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Str = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-fA-F0-9]{64}$")]


class AuditAccessEntry(BaseModel):
    action_type: str = "case_accessed"
    principal_id: str
    client_ip: str
    user_agent: str
    timestamp: datetime


# Thread-safe lock for state mutations
state_lock = asyncio.Lock()
access_log: list[AuditAccessEntry] = []


def create_initial_state(
    tenant_id: str = config.tenant_id, case_id: str = DEFAULT_CASE_ID
) -> IncidentState:
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


# Active state, repository, and partitioned SSE subscribers
current_state: IncidentState = create_initial_state()
subscribers: dict[tuple[str, str], list[asyncio.Queue[str]]] = {}
principal_connections: dict[str, int] = {}
notification_sink = DemoNotificationSink()
repository = SqliteIncidentRepository(
    db_path=config.db_path,
    initial_state_factory=create_initial_state,
)
containment_executor = ContainmentExecutor(repository=repository, sink=notification_sink)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration and rehydrate current_state from durable SQLite on startup."""
    global current_state
    # 1. Fail-fast validation in non-evaluation mode
    validate_config_for_startup(config)

    # 2. Rehydrate state
    async with state_lock:
        try:
            loaded_state = await repository.load(DEFAULT_CASE_ID, tenant_id=config.tenant_id)
            if loaded_state is not None:
                current_state = loaded_state
                logger.info(
                    "Rehydrated current_state from SQLite (phase=%s, v=%d, ledger_entries=%d)",
                    current_state.case.phase,
                    current_state.case.case_version,
                    len(current_state.ledger),
                )
            else:
                current_state = create_initial_state()
                logger.info("Initialized fresh current_state baseline (no prior events found)")
        except Exception as exc:
            logger.critical(
                "FATAL: Failed to rehydrate incident state from SQLite: %s", exc, exc_info=True
            )
            raise RuntimeError(
                f"FATAL: Failed to rehydrate incident state from SQLite event store: {exc}"
            ) from exc
    yield


app = FastAPI(
    title="Lot Zero Incident API",
    description="Deterministic evidence-backed recall incident platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Explicit CORS allowlist
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sync_state_ttl(state: IncidentState, now: datetime) -> IncidentState:
    """Server-side TTL evaluation: if provisional hold expired without QA approval, auto-escalate."""
    is_qa_approved = any(
        a.approval_type == "containment" and a.decision == "approved" for a in state.approvals
    )
    if is_qa_approved or state.case.phase == "closed":
        return state

    for action in state.containment_actions:
        if (
            action.hold_expires_at
            and now >= action.hold_expires_at
            and action.policy_version != "POLICY-AUTO-ESCALATE-01"
        ):
            escalated_action = action.model_copy(
                update={"policy_version": "POLICY-AUTO-ESCALATE-01", "status": "succeeded"}
            )
            updated_actions = tuple(
                escalated_action if a.action_id == action.action_id else a
                for a in state.containment_actions
            )
            return state.model_copy(
                update={"containment_actions": updated_actions, "updated_at": now}
            )
    return state


async def broadcast_state(state: IncidentState) -> None:
    """Broadcast state updates to connected SSE clients matching tenant and case."""
    projection = build_incident_projection(state)
    payload = f"data: {json.dumps(projection)}\n\n"
    key = (state.case.tenant_id, state.case.case_id)
    queues = subscribers.get(key, [])
    for queue in list(queues):
        try:
            queue.put_nowait(payload)
        except Exception:
            if queue in queues:
                queues.remove(queue)


@app.get("/healthz")
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "lot-zero-api",
        "tenant": config.tenant_id,
        "evaluation_mode": config.evaluation_mode,
    }


@app.get("/api/config")
@app.get("/api/evaluation/personas")
async def get_app_config():
    """Return runtime configuration and synthetic evaluation personas if evaluation mode is active."""
    return {
        "evaluation_mode": config.evaluation_mode,
        "tenant_id": config.tenant_id,
        "personas": get_evaluation_personas(),
    }


@app.get("/api/incidents/{case_id}")
async def get_incident(
    case_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Retrieve full incident projection with authentic access auditing and server TTL sync."""
    global current_state
    now = datetime.now(UTC)

    if case_id != current_state.case.case_id or principal.tenant_id != current_state.case.tenant_id:
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
    """Subscribe to real-time incident state changes via partitioned Server-Sent Events."""
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

    if case_id != current_state.case.case_id or principal.tenant_id != current_state.case.tenant_id:
        raise HTTPException(status_code=404, detail="Incident case not found")

    # Enforce bounded connections per principal (max 10 concurrent streams)
    p_id = principal.principal_id
    current_conns = principal_connections.get(p_id, 0)
    if current_conns >= 10:
        raise HTTPException(
            status_code=429, detail="Too many active SSE connections for this principal."
        )

    principal_connections[p_id] = current_conns + 1
    key = (principal.tenant_id, case_id)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    if key not in subscribers:
        subscribers[key] = []
    subscribers[key].append(queue)

    async def event_generator():
        initial_proj = build_incident_projection(current_state)
        yield f"data: {json.dumps(initial_proj)}\n\n"
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            if key in subscribers and queue in subscribers[key]:
                subscribers[key].remove(queue)
            principal_connections[p_id] = max(0, principal_connections.get(p_id, 1) - 1)

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
        summaries = query_case_summaries(repository._conn, principal.tenant_id, filter_type=filter)
        active_ids = {s.case_id for s in summaries}
        if (
            current_state
            and current_state.case.tenant_id == principal.tenant_id
            and current_state.case.case_id not in active_ids
            and filter == "all"
        ):
            active_summary = CaseSummaryProjection(
                case_id=current_state.case.case_id,
                tenant_id=current_state.case.tenant_id,
                phase=current_state.case.phase,
                case_version=current_state.case.case_version,
                has_open_holds=False,
                open_hold_quantity=0.0,
                has_pending_qa=False,
                pending_qa_type=None,
                has_rejected_acks=False,
                rejected_ack_count=0,
                last_event_type="INITIALIZED",
                updated_at=current_state.case.updated_at,
            )
            summaries.insert(0, active_summary)
        return summaries


@app.get("/api/projections/cases/open-holds")
async def get_open_holds_projections(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type="open_holds")


@app.get("/api/projections/cases/pending-qa")
async def get_pending_qa_projections(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    async with state_lock:
        return query_case_summaries(repository._conn, principal.tenant_id, filter_type="pending_qa")


@app.get("/api/projections/cases/blocked-by-rejections")
async def get_blocked_by_rejections_projections(
    principal: Principal = Depends(get_current_principal),
) -> list[CaseSummaryProjection]:
    async with state_lock:
        return query_case_summaries(
            repository._conn, principal.tenant_id, filter_type="blocked_by_rejections"
        )


@app.get("/api/cases/{case_id}/audit-export")
@app.get("/api/incidents/{case_id}/audit-export")
async def export_case_audit(
    case_id: str,
    principal: Principal = Depends(get_current_principal),
) -> AuditExportBundle:
    """Export the complete, ordered, hash-chained audit bundle for an incident case."""
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
    """Reset evaluation tenant to initial clean baseline. Requires evaluation mode and admin capability."""
    global current_state
    if not config.evaluation_mode:
        raise HTTPException(
            status_code=404, detail="Evaluation reset is not available in non-evaluation mode."
        )

    if not principal.can_reset_evaluation:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Principal '{principal.principal_id}' does not possess evaluation reset authority.",
        )

    async with state_lock:
        await repository.archive_and_reset(
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            reset_by_principal_id=principal.principal_id,
        )
        current_state = create_initial_state(principal.tenant_id, current_state.case.case_id)
        await broadcast_state(current_state)
        return {"status": "reset", "projection": build_incident_projection(current_state)}


@app.post("/api/evaluation/simulate-signal")
async def simulate_signal(principal: Principal = Depends(get_current_principal)):
    """Trigger autonomous Gemini signal analysis, propose scope, and set server-side provisional hold."""
    global current_state
    now = datetime.now(UTC)

    if principal.tenant_id != current_state.case.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

    async with state_lock:
        # 1. Analyze signal via Gemini Agent
        signal_res = analyze_safety_signal(
            RAW_TEXT,
            case_id=current_state.case.case_id,
            tenant_id=principal.tenant_id,
        )

        if not signal_res.is_grounded or signal_res.status != "grounded":
            logger.warning(
                "Signal extraction failed grounding check: lot=%s", signal_res.ingredient_lot
            )
            return {
                "status": "needs_review",
                "reason": "Signal extraction failed mechanical grounding checks",
                "signal": signal_res,
                "projection": build_incident_projection(current_state),
            }

        # 2. Reconcile with authoritative genealogy
        fixture = load_fixture("evaluation-tenant-v1")
        products = tuple(
            FinishedLot(
                record_id=lot.lot_id,
                tenant_id=principal.tenant_id,
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
                tenant_id=principal.tenant_id,
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
                tenant_id=principal.tenant_id,
                case_id=current_state.case.case_id,
                source_id=lot.ingredient_lot,
                target_id=lot.lot_id,
            )
            for lot in fixture.operations.affected_finished_lots
        ) + tuple(
            GenealogyEdge(
                edge_id=edge.edge_id,
                tenant_id=principal.tenant_id,
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
                tenant_id=principal.tenant_id,
                case_id=current_state.case.case_id,
                lot_id=lot.lot_id,
                quantity=Decimal(str(lot.quantity)),
            )
            for lot in fixture.operations.affected_finished_lots
        ) + (
            InventoryRecord(
                record_id=f"INV-{adj_batch.lot_id}",
                tenant_id=principal.tenant_id,
                case_id=current_state.case.case_id,
                lot_id=adj_batch.lot_id,
                quantity=Decimal(str(adj_batch.quantity)),
            ),
        )
        shipments = (
            ShipmentRecord(
                record_id=f"SHIP-{first_lot.lot_id}",
                tenant_id=principal.tenant_id,
                case_id=current_state.case.case_id,
                lot_id=first_lot.lot_id,
                quantity=Decimal(str(fixture.operations.shipped_quantity)),
            ),
        )
        scope = RecallScope(
            scope_id="SCOPE-EVAL-01",
            tenant_id=principal.tenant_id,
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

        evidence_ids = tuple(s.evidence_id for s in signal_res.spans) or (signal_res.source_id,)
        if not evidence_ids:
            return {
                "status": "needs_review",
                "reason": "No evidence spans generated",
                "signal": signal_res,
                "projection": build_incident_projection(current_state),
            }

        # 3. Propose scope through domain authority
        scope_cmd = ProposeScopeCommand(
            kind="propose_scope",
            command_id=f"CMD-SCOPE-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            affected_record_ids=affected_record_ids,
            affected_quantity=affected_quantity,
            evidence_record_ids=evidence_ids,
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
            tenant_id=principal.tenant_id,
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
            # 4. Request provisional hold
            hold_cmd = RequestContainmentCommand(
                kind="request_containment",
                command_id=f"CMD-HOLD-{current_state.case.case_version + 1}",
                tenant_id=principal.tenant_id,
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
                tenant_id=principal.tenant_id,
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
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        # Locate the actual persisted scope proposal
        matching_scope = next(
            (s for s in current_state.scopes if s.scope_id == "SCOPE-EVAL-01"), None
        )
        if matching_scope is None or not matching_scope.requester_id:
            raise HTTPException(
                status_code=409,
                detail="Containment approval requires a prior persisted scope proposal.",
            )

        # Locate the actual persisted containment action request
        matching_hold = next(
            (
                a
                for a in current_state.containment_actions
                if a.scope_id == "SCOPE-EVAL-01" and a.action_type == "provisional_hold"
            ),
            None,
        )
        if matching_hold is None or not matching_hold.requester_id:
            raise HTTPException(
                status_code=409,
                detail="Containment approval requires a prior persisted containment request.",
            )

        # Approve scope if in scope review
        if current_state.case.phase == "scope_review":
            scope_app_cmd = ApproveScopeCommand(
                kind="approve_scope",
                command_id=f"CMD-APP-SCOPE-{current_state.case.case_version + 1}",
                tenant_id=principal.tenant_id,
                case_id=current_state.case.case_id,
                actor_id=matching_scope.requester_id,
                case_version=current_state.case.case_version,
                approval_id=f"APP-SCOPE-{current_state.case.case_version + 1}",
                rationale=req.rationale,
                scope_id=matching_scope.scope_id,
                scope_version=matching_scope.scope_version,
                policy_version="EVAL-HOLD-01",
            )
            res1 = execute_command(current_state, scope_app_cmd, principal, occurred_at=now)
            if not res1.decision.allowed:
                if res1.decision.code in ("ROLE_NOT_AUTHORIZED", "REQUESTER_APPROVER_CONFLICT"):
                    raise HTTPException(status_code=403, detail=res1.decision.explanation)
                raise HTTPException(status_code=400, detail=res1.decision.explanation)
            current_state = res1.state

        # Approve containment -> converts hold to firm quarantine
        hold_app_cmd = ApproveContainmentCommand(
            kind="approve_containment",
            command_id=f"CMD-APP-HOLD-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=matching_hold.requester_id,
            case_version=current_state.case.case_version,
            approval_id=f"APP-HOLD-{current_state.case.case_version + 1}",
            rationale=req.rationale,
            scope_id=matching_hold.scope_id,
            scope_version=matching_hold.scope_version,
            policy_version=matching_hold.policy_version,
        )
        res2 = execute_command(current_state, hold_app_cmd, principal, occurred_at=now)

        if not res2.decision.allowed:
            if res2.decision.code in ("ROLE_NOT_AUTHORIZED", "REQUESTER_APPROVER_CONFLICT"):
                raise HTTPException(status_code=403, detail=res2.decision.explanation)
            raise HTTPException(status_code=400, detail=res2.decision.explanation)
        current_state = res2.state

        # Advance: provisional_containment -> action_review
        adv_action_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-ACTION-{int(now.timestamp())}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="action_review",
        )
        res_adv_action = execute_command(current_state, adv_action_cmd, principal, occurred_at=now)
        if res_adv_action.decision.allowed:
            current_state = res_adv_action.state

        all_events = (
            [*res1.events, *res2.events, *res_adv_action.events]
            if "res1" in locals()
            else [*res2.events, *res_adv_action.events]
        )
        if all_events:
            await repository.append(
                current_state.case.case_id,
                expected_version=current_state.case.case_version - len(all_events),
                events=all_events,
                tenant_id=principal.tenant_id,
            )

        await broadcast_state(current_state)
        return {
            "status": "approved",
            "phase": current_state.case.phase,
            "projection": build_incident_projection(current_state),
        }


class RequestNotificationRequest(BaseModel):
    packet_id: ReqStr = "PKT-001"
    scope_id: ReqStr = "SCOPE-EVAL-01"
    scope_version: int = 1
    payload_version: ReqStr = "PAYLOAD-001"
    payload_hash: ReqStr = "payload-sha256-verified-digest"
    policy_version: ReqStr = "EVAL-HOLD-01"


@app.post("/api/evaluation/request-notification")
async def request_notification(
    req: RequestNotificationRequest | None = None,
    principal: Principal = Depends(get_current_principal),
):
    """Recall Coordinator requests drafting of notification packet for Customer Operations approval."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        body = req or RequestNotificationRequest()
        matching_scope = next(
            (s for s in current_state.scopes if s.scope_id == body.scope_id),
            None,
        )
        if not matching_scope:
            raise HTTPException(
                status_code=409,
                detail=f"Notification request refused: scope '{body.scope_id}' does not exist in case.",
            )

        fixture = load_fixture("evaluation-tenant-v1")
        recipients = tuple(r.recipient_id for r in fixture.operations.recipients)

        notif_req_cmd = RequestNotificationCommand(
            kind="request_notification",
            command_id=f"CMD-REQ-NOTIF-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id=body.scope_id,
            scope_version=body.scope_version,
            packet_id=body.packet_id,
            payload_version=body.payload_version,
            payload_hash=body.payload_hash,
            policy_version=body.policy_version,
            recipient_ids=recipients,
        )
        res = execute_command(current_state, notif_req_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            status_code = 403 if "role" in res.decision.explanation.lower() else 400
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
            "status": "notification_requested",
            "packet_id": body.packet_id,
            "projection": build_incident_projection(current_state),
        }


class ApproveNotificationRequest(BaseModel):
    packet_id: ReqStr
    payload_version: ReqStr
    payload_hash: ReqStr
    scope_id: ReqStr
    scope_version: int
    policy_version: ReqStr
    rationale: ReqStr


@app.post("/api/evaluation/approve-notification")
async def approve_notification(
    req: ApproveNotificationRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Customer Operations approves notification packet payload for dispatch."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        # Locate matching proposed scope or notification packet
        matching_packet = next(
            (
                p
                for p in current_state.notification_packets
                if p.packet_id == req.packet_id and p.scope_id == req.scope_id
            ),
            None,
        )
        matching_scope = next(
            (s for s in current_state.scopes if s.scope_id == req.scope_id),
            None,
        )
        if matching_packet and matching_packet.requester_id:
            notif_requester = matching_packet.requester_id
        elif matching_scope and matching_scope.requester_id:
            notif_requester = matching_scope.requester_id
        else:
            raise HTTPException(
                status_code=409,
                detail="Notification approval requires a prior persisted scope proposal or packet request.",
            )

        notif_app_cmd = ApproveNotificationCommand(
            kind="approve_notification",
            command_id=f"CMD-APP-NOTIF-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=notif_requester,
            case_version=current_state.case.case_version,
            approval_id=f"APP-NOTIF-{current_state.case.case_version + 1}",
            rationale=req.rationale,
            scope_id=req.scope_id,
            scope_version=req.scope_version,
            packet_id=req.packet_id,
            payload_version=req.payload_version,
            payload_hash=req.payload_hash,
            policy_version=req.policy_version,
        )
        res = execute_command(current_state, notif_app_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            status_code = (
                403
                if res.decision.code in ("ROLE_NOT_AUTHORIZED", "REQUESTER_APPROVER_CONFLICT")
                else 400
            )
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
            "status": "notification_approved",
            "projection": build_incident_projection(current_state),
        }


@app.post("/api/evaluation/dispatch-outbox")
async def dispatch_outbox(principal: Principal = Depends(get_current_principal)):
    """Dispatch recipient notification packets and record acknowledgements via kernel commands."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        # 1. Send notification command (strictly requires prior matching approval)
        fixture = load_fixture("evaluation-tenant-v1")
        recipients = tuple(r.recipient_id for r in fixture.operations.recipients)
        notif_cmd = SendNotificationCommand(
            kind="send_notification",
            command_id=f"CMD-NOTIF-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            scope_id="SCOPE-EVAL-01",
            scope_version=1,
            packet_id="PKT-001",
            payload_version="PAYLOAD-001",
            payload_hash="payload-sha256-verified-digest",
            policy_version="EVAL-HOLD-01",
            recipient_ids=recipients,
        )
        res1 = execute_command(current_state, notif_cmd, principal, occurred_at=now)
        if not res1.decision.allowed:
            status_code = (
                403
                if "lacks" in res1.decision.explanation.lower()
                or "role" in res1.decision.explanation.lower()
                else 409
            )
            raise HTTPException(status_code=status_code, detail=res1.decision.explanation)
        current_state = res1.state

        # 2. Record 5 verified acks and 1 outstanding ACK-006
        acks_data: list[tuple[str, str, Literal["verified", "outstanding", "rejected"]]] = [
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
                tenant_id=principal.tenant_id,
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
                status_code = (
                    403
                    if "lacks" in res_ack.decision.explanation.lower()
                    or "role" in res_ack.decision.explanation.lower()
                    else 400
                )
                raise HTTPException(status_code=status_code, detail=res_ack.decision.explanation)
            current_state = res_ack.state
            all_ack_events.extend(res_ack.events)

        # 3. Advance phase to ack_monitoring via domain command
        adv_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-ACK-{int(now.timestamp())}",
            tenant_id=principal.tenant_id,
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
        return {
            "status": "outbox_dispatched",
            "projection": build_incident_projection(current_state),
        }


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
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        ack_cmd = RecordAcknowledgementCommand(
            kind="record_acknowledgement",
            command_id=f"CMD-ACK-PHONE-ACK-006-{int(now.timestamp())}",
            tenant_id=principal.tenant_id,
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
            status_code = (
                403
                if "lacks" in res_ack.decision.explanation.lower()
                or "role" in res_ack.decision.explanation.lower()
                else 400
            )
            raise HTTPException(status_code=status_code, detail=res_ack.decision.explanation)
        current_state = res_ack.state

        events_to_append = list(res_ack.events)
        all_verified = len(current_state.acknowledgements) >= 6 and all(
            a.status == "verified" for a in current_state.acknowledgements
        )
        if all_verified and current_state.case.phase == "ack_monitoring":
            adv_eff_cmd = AdvancePhaseCommand(
                command_id=f"CMD-ADV-EFF-{int(now.timestamp())}",
                tenant_id=principal.tenant_id,
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
    """Execute sequential dual-signature release step (Step 1: QA biological clearance, Step 2: Closure Authority release)."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        # Locate matching containment action or scope
        matching_hold = next(
            (
                a
                for a in current_state.containment_actions
                if a.scope_id == "SCOPE-EVAL-01" and a.action_type == "provisional_hold"
            ),
            None,
        )
        matching_scope = next(
            (s for s in current_state.scopes if s.scope_id == "SCOPE-EVAL-01"),
            None,
        )
        if matching_hold and matching_hold.requester_id:
            rel_requester = matching_hold.requester_id
        elif matching_scope and matching_scope.requester_id:
            rel_requester = matching_scope.requester_id
        else:
            raise HTTPException(
                status_code=409,
                detail="Release approval requires a prior persisted containment hold or scope proposal.",
            )

        acting_role = (
            "qa"
            if "qa" in principal.roles
            else (
                "closure_authority"
                if "closure_authority" in principal.roles
                else principal.roles[0]
            )
        )
        rel_cmd = ApproveReleaseCommand(
            kind="approve_release",
            command_id=f"CMD-REL-{acting_role.upper()}-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=rel_requester,
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
            status_code = (
                403
                if res.decision.code in ("ROLE_NOT_AUTHORIZED", "REQUESTER_APPROVER_CONFLICT")
                else 400
            )
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


class RequestClosureBody(BaseModel):
    closure_id: ReqStr = "EVAL-CLOSE-01"
    policy_version: ReqStr = "EVAL-CLOSE-01"
    evidence_record_ids: tuple[ReqStr, ...] | None = None


@app.post("/api/evaluation/request-closure")
async def request_closure(
    body: RequestClosureBody | None = None,
    principal: Principal = Depends(get_current_principal),
):
    """Recall Coordinator requests formal closure review, creating an immutable ClosureRequest record."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        known_evidence: set[str] = set()
        for s in current_state.scopes:
            known_evidence.update(s.evidence_record_ids)
        if current_state.case.source_record_ids:
            known_evidence.update(current_state.case.source_record_ids)

        if body and body.evidence_record_ids:
            for ev_id in body.evidence_record_ids:
                if ev_id not in known_evidence:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Evidence record '{ev_id}' is unknown in this incident case.",
                    )
            evidence_ids = tuple(body.evidence_record_ids)
        else:
            evidence_ids = tuple(sorted(known_evidence))
            if not evidence_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot request closure without valid evidence records in scope.",
                )

        outstanding = [
            ack.acknowledgement_id
            for ack in current_state.acknowledgements
            if ack.status == "outstanding"
        ]
        request_id = f"REQ-CLOSE-{current_state.case.case_version + 1}"
        scope_v = current_state.scopes[0].scope_version if current_state.scopes else 1
        closure_req_cmd = RequestClosureCommand(
            kind="request_closure",
            command_id=f"CMD-CLOSE-REQ-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            request_id=request_id,
            closure_id=body.closure_id if body else "EVAL-CLOSE-01",
            policy_version=body.policy_version if body else "EVAL-CLOSE-01",
            scope_version=scope_v,
            outstanding_acknowledgement_ids=tuple(outstanding),
            evidence_record_ids=evidence_ids,
        )

        res = execute_command(current_state, closure_req_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            if res.decision.code in (
                "ROLE_NOT_AUTHORIZED",
                "SEPARATION_OF_DUTIES",
                "REQUESTER_APPROVER_CONFLICT",
            ):
                raise HTTPException(status_code=403, detail=res.decision.explanation)
            elif res.decision.code == "TENANT_MISMATCH":
                raise HTTPException(status_code=403, detail=res.decision.explanation)
            else:
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
            "status": "closure_requested",
            "request_id": request_id,
            "projection": build_incident_projection(current_state),
        }


class AuthorizeClosureBody(BaseModel):
    request_id: ReqStr | None = None
    rationale: ReqStr = "Verified consignee containment complete."
    effectiveness_evidence_ids: tuple[ReqStr, ...] | None = None


@app.post("/api/evaluation/authorize-closure")
async def authorize_closure(
    body: AuthorizeClosureBody | None = None,
    principal: Principal = Depends(get_current_principal),
):
    """Closure Authority authorizes incident closure matching an active unconsumed ClosureRequest."""
    global current_state
    now = datetime.now(UTC)

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        req_body = body or AuthorizeClosureBody()
        if req_body.request_id:
            matching_req = next(
                (
                    r
                    for r in current_state.closure_requests
                    if r.request_id == req_body.request_id and not r.is_consumed
                ),
                None,
            )
        else:
            matching_req = next(
                (r for r in reversed(current_state.closure_requests) if not r.is_consumed),
                None,
            )

        if matching_req is None:
            raise HTTPException(
                status_code=400,
                detail="No pending closure request found to authorize. Recall Coordinator must request closure first.",
            )

        known_evidence: set[str] = set()
        for s in current_state.scopes:
            known_evidence.update(s.evidence_record_ids)
        if current_state.case.source_record_ids:
            known_evidence.update(current_state.case.source_record_ids)

        if req_body.effectiveness_evidence_ids:
            for ev_id in req_body.effectiveness_evidence_ids:
                if ev_id not in known_evidence:
                    return {
                        "status": "closure_blocked",
                        "reason": f"Effectiveness evidence ID '{ev_id}' does not exist in this incident case.",
                        "code": "UNKNOWN_EVIDENCE_ID",
                        "blocked": True,
                        "outstanding_acknowledgements": [],
                        "projection": build_incident_projection(current_state),
                    }
            eff_evidence = tuple(req_body.effectiveness_evidence_ids)
        else:
            eff_evidence = (
                matching_req.evidence_record_ids
                if matching_req.evidence_record_ids
                else tuple(sorted(known_evidence))
            )

        close_app_cmd = ApproveClosureCommand(
            kind="approve_closure",
            command_id=f"CMD-CLOSE-APP-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=matching_req.requester_principal_id,
            case_version=current_state.case.case_version,
            approval_id=f"APP-CLOSE-{current_state.case.case_version + 1}",
            rationale=req_body.rationale,
            request_id=matching_req.request_id,
            expected_request_stream_version=matching_req.request_stream_version,
            expected_scope_version=matching_req.requested_scope_version,
            expected_policy_version=matching_req.requested_policy_version,
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            effectiveness_evidence_ids=eff_evidence,
        )

        res = execute_command(current_state, close_app_cmd, principal, occurred_at=now)

        if not res.decision.allowed:
            if res.decision.code in (
                "ROLE_NOT_AUTHORIZED",
                "SEPARATION_OF_DUTIES",
                "REQUESTER_APPROVER_CONFLICT",
            ):
                raise HTTPException(status_code=403, detail=res.decision.explanation)
            elif res.decision.code == "TENANT_MISMATCH":
                raise HTTPException(status_code=403, detail=res.decision.explanation)
            elif res.decision.code in (
                "STALE_REQUEST_STREAM_VERSION",
                "STALE_SCOPE_VERSION",
                "STALE_POLICY_VERSION",
                "CLOSURE_REQUEST_ALREADY_CONSUMED",
                "MISSING_CLOSURE_REQUEST",
            ):
                raise HTTPException(status_code=409, detail=res.decision.explanation)
            elif res.decision.code in (
                "OUTSTANDING_ACKNOWLEDGEMENT",
                "UNRESOLVED_BLOCKER",
                "MISSING_EFFECTIVENESS_EVIDENCE",
                "REJECTED_ACKNOWLEDGEMENT_REQUIRES_SEIZURE_REFERRAL",
                "UNKNOWN_EVIDENCE_ID",
            ):
                outstanding = [
                    ack.acknowledgement_id
                    for ack in current_state.acknowledgements
                    if ack.status == "outstanding"
                ]
                return {
                    "status": "closure_blocked",
                    "reason": res.decision.explanation,
                    "code": res.decision.code,
                    "blocked": True,
                    "outstanding_acknowledgements": outstanding,
                    "projection": build_incident_projection(current_state),
                }
            else:
                raise HTTPException(status_code=400, detail=res.decision.explanation)

        current_state = res.state

        # Advance phase to closed
        adv_close_cmd = AdvancePhaseCommand(
            command_id=f"CMD-ADV-CLOSE-{int(now.timestamp())}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=principal.principal_id,
            case_version=current_state.case.case_version,
            target_phase="closed",
        )
        res_close = execute_command(current_state, adv_close_cmd, principal, occurred_at=now)
        if not res_close.decision.allowed:
            raise HTTPException(status_code=400, detail=res_close.decision.explanation)
        current_state = res_close.state

        all_close_events = [*res.events, *res_close.events]
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


class NonResponseClosureRequest(BaseModel):
    request_id: ReqStr | None = None
    attempt_count: int = Field(ge=3)
    regulatory_filing_id: ReqStr
    good_faith_notes: ReqStr
    effectiveness_evidence_ids: tuple[ReqStr, ...] | None = None


@app.post("/api/evaluation/close-with-non-response")
async def close_with_non_response(
    req: NonResponseClosureRequest,
    principal: Principal = Depends(get_current_principal),
):
    """Close incident with synthetic non-response documentation and modeled referral note (not a legal or regulatory certification)."""
    global current_state
    now = datetime.now(UTC)

    if not req.regulatory_filing_id.strip() or not req.good_faith_notes.strip():
        raise HTTPException(
            status_code=422, detail="Regulatory filing ID and good faith notes are required."
        )

    async with state_lock:
        if principal.tenant_id != current_state.case.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant boundary mismatch")

        # Locate matching active unconsumed closure request
        if req.request_id:
            matching_req = next(
                (r for r in current_state.closure_requests if r.request_id == req.request_id), None
            )
        else:
            matching_req = next(
                (r for r in reversed(current_state.closure_requests) if not r.is_consumed), None
            )

        if matching_req is None:
            raise HTTPException(
                status_code=400,
                detail="Non-response closure requires a prior unconsumed closure request from a Recall Coordinator.",
            )

        known_evidence: set[str] = set()
        for s in current_state.scopes:
            known_evidence.update(s.evidence_record_ids)
        if current_state.case.source_record_ids:
            known_evidence.update(current_state.case.source_record_ids)

        if req.effectiveness_evidence_ids:
            for ev_id in req.effectiveness_evidence_ids:
                if ev_id not in known_evidence:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Evidence ID '{ev_id}' is unknown in this incident.",
                    )
            eff_evidence = tuple(req.effectiveness_evidence_ids)
        else:
            eff_evidence = (
                matching_req.evidence_record_ids
                if matching_req.evidence_record_ids
                else tuple(sorted(known_evidence))
            )

        close_cmd = ApproveClosureCommand(
            kind="approve_closure",
            command_id=f"CMD-CLOSE-NON-RESP-{current_state.case.case_version + 1}",
            tenant_id=principal.tenant_id,
            case_id=current_state.case.case_id,
            actor_id=matching_req.requester_principal_id,
            case_version=current_state.case.case_version,
            approval_id=f"APP-CLOSE-NON-RESP-{current_state.case.case_version + 1}",
            rationale=f"SYNTHETIC NON-RESPONSE DOCUMENTATION (modeled workflow): {req.good_faith_notes}",
            request_id=matching_req.request_id,
            expected_request_stream_version=matching_req.request_stream_version,
            expected_scope_version=matching_req.requested_scope_version,
            expected_policy_version=matching_req.requested_policy_version,
            closure_id="EVAL-CLOSE-01",
            policy_version="EVAL-CLOSE-01",
            effectiveness_evidence_ids=eff_evidence,
            non_response_filing_id=req.regulatory_filing_id,
            attempt_count=req.attempt_count,
        )
        res = execute_command(current_state, close_cmd, principal, occurred_at=now)
        if not res.decision.allowed:
            if res.decision.code in (
                "ROLE_NOT_AUTHORIZED",
                "SEPARATION_OF_DUTIES",
                "REQUESTER_APPROVER_CONFLICT",
            ):
                raise HTTPException(status_code=403, detail=res.decision.explanation)
            elif res.decision.code in (
                "STALE_REQUEST_STREAM_VERSION",
                "CLOSURE_REQUEST_ALREADY_CONSUMED",
                "MISSING_CLOSURE_REQUEST",
            ):
                raise HTTPException(status_code=409, detail=res.decision.explanation)
            else:
                raise HTTPException(status_code=400, detail=res.decision.explanation)
        current_state = res.state

        adv_events: list[object] = []
        if current_state.case.phase == "ack_monitoring":
            adv_eff_cmd = AdvancePhaseCommand(
                kind="advance_phase",
                command_id=f"CMD-ADV-EFF-NONRESP-{int(now.timestamp())}",
                tenant_id=principal.tenant_id,
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
            kind="advance_phase",
            command_id=f"CMD-ADV-CLOSE-NONRESP-{int(now.timestamp())}",
            tenant_id=principal.tenant_id,
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
            "status": "closed",
            "regulatory_filing_id": req.regulatory_filing_id,
            "attempt_count": req.attempt_count,
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
static_dir = next(
    (p for p in web_dist_candidates if p.exists() and (p / "index.html").exists()), None
)

if static_dir is not None:
    current_static_dir: Path = static_dir
    assets_dir = current_static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"API endpoint '/{full_path}' not found")
        file_path = current_static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(current_static_dir / "index.html")
