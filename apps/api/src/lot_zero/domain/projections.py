"""Fast read-model projections querying the append-only event store directly."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

FilterType = Literal["all", "open_holds", "pending_qa", "blocked_by_rejections"]


class CaseSummaryProjection(BaseModel):
    """Lightweight projection of an incident case derived directly from event stream."""

    case_id: str
    tenant_id: str
    phase: str = "signal_received"
    case_version: int = 0
    has_open_holds: bool = False
    open_hold_quantity: float = 0.0
    has_pending_qa: bool = False
    pending_qa_type: str | None = None
    has_rejected_acks: bool = False
    rejected_ack_count: int = 0
    last_event_type: str = "INITIALIZED"
    updated_at: datetime


def query_case_summaries(
    conn: sqlite3.Connection,
    tenant_id: str,
    filter_type: FilterType = "all",
) -> list[CaseSummaryProjection]:
    """Project case summaries directly from incident_events table without full aggregate rehydration.
    
    NOTE ON SCALE: For high-event-volume enterprise deployments, maintaining an incrementally 
    updated materialized projection table (via asynchronous subscriber or database triggers) 
    is the recommended upgrade path over querying the append-only events log per request.
    """
    # 1. Fetch all distinct cases for the tenant
    cursor = conn.execute(
        """
        SELECT DISTINCT case_id 
        FROM incident_events 
        WHERE tenant_id = ?
        ORDER BY case_id ASC
        """,
        (tenant_id,),
    )
    case_ids = [row[0] for row in cursor.fetchall()]
    if not case_ids:
        return []

    summaries: list[CaseSummaryProjection] = []

    for case_id in case_ids:
        events_cursor = conn.execute(
            """
            SELECT stream_version, event_type, payload, occurred_at
            FROM incident_events
            WHERE tenant_id = ? AND case_id = ?
            ORDER BY stream_version ASC
            """,
            (tenant_id, case_id),
        )
        rows = events_cursor.fetchall()
        if not rows:
            continue

        phase = "signal_received"
        case_version = 0
        last_event_type = "INITIALIZED"
        last_updated_str = rows[-1][3] if rows else datetime.now(UTC).isoformat()

        # Tracking state
        holds: dict[str, float] = {}  # scope_id -> quantity
        released_scopes: set[str] = set()
        pending_qa_types: set[str] = set()
        qa_containment_approved = False
        qa_release_approved_scopes: set[str] = set()
        acks: dict[str, str] = {}  # ack_id -> status

        for row in rows:
            stream_version = row[0]
            event_type = row[1]
            payload_raw = row[2]
            case_version = max(case_version, stream_version)
            last_event_type = event_type

            try:
                data = json.loads(payload_raw)
            except Exception:
                continue

            # Phase tracking from TransitionEvents
            if event_type == "advance" or data.get("kind") == "advance":
                target_phase = data.get("target_phase")
                if target_phase:
                    phase = target_phase
            elif event_type == "TRANSITION_ADVANCE":
                target_phase = data.get("target_phase")
                if target_phase:
                    phase = target_phase

            # Scope proposals
            if event_type in ("scope_proposed", "SCOPE_PROPOSED") or data.get("kind") == "scope_proposed":
                scope_id = data.get("scope_id", "SCOPE-001")
                qty = float(data.get("affected_quantity", 0.0))
                holds[scope_id] = qty
                if phase == "scope_review":
                    pending_qa_types.add("scope")

            # Containment requests
            if event_type in ("containment_requested", "CONTAINMENT_REQUESTED") or data.get("kind") == "containment_requested":
                scope_id = data.get("scope_id", "SCOPE-001")
                if not qa_containment_approved:
                    pending_qa_types.add("containment")

            # Containment attempts
            if event_type in ("containment_attempted", "CONTAINMENT_ATTEMPTED") or data.get("kind") == "containment_attempted":
                action = data.get("action", {})
                scope_id = action.get("scope_id", "SCOPE-001")
                qty = float(action.get("quantity", 0.0))
                holds[scope_id] = qty
                if not qa_containment_approved:
                    pending_qa_types.add("containment")

            # Approvals
            if event_type in ("approval_decision", "APPROVAL_DECISION") or data.get("kind") == "approval_decision":
                app_type = data.get("approval_type")
                decision = data.get("decision")
                role = data.get("approver_role")
                if decision == "approved":
                    if app_type == "containment" and role == "qa":
                        qa_containment_approved = True
                        pending_qa_types.discard("containment")
                    if app_type == "scope" and role == "qa":
                        pending_qa_types.discard("scope")
                    if app_type == "release" and role == "qa":
                        qa_release_approved_scopes.add(data.get("scope_id", "SCOPE-001"))

            # Releases
            if event_type in ("containment_released", "CONTAINMENT_RELEASED") or data.get("kind") == "containment_released":
                scope_id = data.get("scope_id", "SCOPE-001")
                released_scopes.add(scope_id)

            # Acknowledgements
            if event_type in ("acknowledgement_recorded", "ACKNOWLEDGEMENT_RECORDED") or data.get("kind") == "acknowledgement_recorded":
                ack_id = data.get("acknowledgement_id")
                status = data.get("acknowledgement_status")
                if ack_id and status:
                    acks[ack_id] = status

        # Compute projected indicators
        active_hold_scopes = {s: q for s, q in holds.items() if s not in released_scopes and phase != "closed"}
        has_open_holds = len(active_hold_scopes) > 0
        open_hold_quantity = sum(active_hold_scopes.values())

        if phase == "scope_review":
            pending_qa_types.add("scope")

        has_pending_qa = len(pending_qa_types) > 0 and phase != "closed"
        pending_qa_type = next(iter(pending_qa_types)) if pending_qa_types else None

        rejected_acks = [ack_id for ack_id, status in acks.items() if status == "rejected"]
        has_rejected_acks = len(rejected_acks) > 0
        rejected_ack_count = len(rejected_acks)

        try:
            updated_dt = datetime.fromisoformat(last_updated_str)
            if updated_dt.tzinfo is None:
                updated_dt = updated_dt.replace(tzinfo=UTC)
        except Exception:
            updated_dt = datetime.now(UTC)

        summary = CaseSummaryProjection(
            case_id=case_id,
            tenant_id=tenant_id,
            phase=phase,
            case_version=case_version,
            has_open_holds=has_open_holds,
            open_hold_quantity=open_hold_quantity,
            has_pending_qa=has_pending_qa,
            pending_qa_type=pending_qa_type,
            has_rejected_acks=has_rejected_acks,
            rejected_ack_count=rejected_ack_count,
            last_event_type=last_event_type,
            updated_at=updated_dt,
        )

        # Apply filter criteria
        if filter_type == "open_holds" and not summary.has_open_holds:
            continue
        if filter_type == "pending_qa" and not summary.has_pending_qa:
            continue
        if filter_type == "blocked_by_rejections" and not summary.has_rejected_acks:
            continue

        summaries.append(summary)

    return summaries
