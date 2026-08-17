"""Domain kernel for coordinating command authorization, event generation, and state reduction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from ..ports.actions import ActionAdapter, ActionReceipt
from ..ports.repositories import IncidentRepository
from .authority import AuthorizationDecision, Principal, _deny, authorize
from .commands import (
    AdvancePhaseCommand,
    ApproveClosureCommand,
    ApproveContainmentCommand,
    ApproveNotificationCommand,
    ApproveReleaseCommand,
    ApproveScopeCommand,
    CommandRecord,
    ProposeScopeCommand,
    RecordAcknowledgementCommand,
    RequestClosureCommand,
    RequestContainmentCommand,
    SendNotificationCommand,
)

from .errors import InvariantViolation
from .events import (
    AcknowledgementRecordedEvent,
    ClosureRequestedEvent,
    ContainmentAttemptedEvent,
    ContainmentReleasedEvent,
    ContainmentRequestedEvent,
    NotificationRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from .transitions import _ALLOWED_PRIMARY_TARGETS
from .identifiers import ActionIntent, action_key
from .models import ApprovalDecision, ContainmentAction, IncidentState
from .reducer import apply_event


class CommandExecutionResult:
    def __init__(
        self,
        state: IncidentState,
        events: Sequence[object],
        decision: AuthorizationDecision,
    ):
        self.state = state
        self.events = tuple(events)
        self.decision = decision


def execute_command(
    state: IncidentState,
    command: CommandRecord,
    principal: Principal,
    *,
    occurred_at: datetime | None = None,
) -> CommandExecutionResult:
    """Authorize a command and fold its resulting events into a new incident state."""
    decision = authorize(command, principal, state)
    if not decision.allowed:
        return CommandExecutionResult(state, (), decision)

    now = occurred_at or datetime.now(UTC)
    events: list[object] = []

    if isinstance(command, ProposeScopeCommand):
        event = ScopeProposedEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            case_version=command.case_version,
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            affected_record_ids=command.affected_record_ids,
            affected_quantity=command.affected_quantity,
            evidence_record_ids=command.evidence_record_ids,
            ingredient_lot=command.ingredient_lot,
            pathogen=command.pathogen,
            kind="scope_proposed",
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, RequestContainmentCommand):
        event = ContainmentRequestedEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            case_version=command.case_version,
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            action_id=f"ACT-{command.command_id}",
            policy_version=command.policy_version,
            target_record_ids=command.target_record_ids,
            quantity=command.quantity,
            kind="containment_requested",
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, SendNotificationCommand):
        event = NotificationRequestedEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            case_version=command.case_version,
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            packet_id=command.packet_id,
            payload_version=command.payload_version,
            policy_version=command.policy_version,
            kind="notification_requested",
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, RecordAcknowledgementCommand):
        event = AcknowledgementRecordedEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            case_version=command.case_version,
            packet_id=command.packet_id,
            acknowledgement_id=command.acknowledgement_id,
            recipient_id=command.recipient_id,
            acknowledgement_status=command.acknowledgement_status,
            caller_id=command.caller_id,
            recipient_contact=command.recipient_contact,
            recipient_phone=command.recipient_phone,
            attestation_notes=command.attestation_notes,
            attestation_hash=command.attestation_hash,
            call_timestamp=command.call_timestamp,
            kind="acknowledgement_recorded",
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, RequestClosureCommand):
        event = ClosureRequestedEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            case_version=command.case_version,
            closure_id=command.closure_id,
            policy_version=command.policy_version,
            outstanding_acknowledgement_ids=command.outstanding_acknowledgement_ids,
            kind="closure_requested",
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, AdvancePhaseCommand):
        expected_target = _ALLOWED_PRIMARY_TARGETS.get(state.case.phase)
        if command.target_phase != expected_target:
            return CommandExecutionResult(
                state,
                (),
                _deny(
                    "ILLEGAL_PHASE_TRANSITION",
                    f"Cannot advance phase from '{state.case.phase}' to '{command.target_phase}'. Allowed target is '{expected_target}'.",
                ),
            )
        event = TransitionEvent(
            event_id=f"EVT-{command.command_id}",
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            case_version=command.case_version,
            kind="advance",
            target_phase=command.target_phase,
            occurred_at=now,
        )
        events.append(event)

    elif isinstance(command, ApproveScopeCommand):
        approval = ApprovalDecision(
            approval_id=command.approval_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            approval_type="scope",
            decision="approved",
            rationale=command.rationale,
            requester_id=command.actor_id,
            approver_id=principal.principal_id,
            approver_role=principal.roles[0] if principal.roles else None,
            case_version=command.case_version,
            boundary_version="BOUND-01",
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            policy_version=command.policy_version,
            decided_at=now,
        )
        events.append(approval)

    elif isinstance(command, ApproveContainmentCommand):
        approval = ApprovalDecision(
            approval_id=command.approval_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            approval_type="containment",
            decision="approved",
            rationale=command.rationale,
            requester_id=command.actor_id,
            approver_id=principal.principal_id,
            approver_role=principal.roles[0] if principal.roles else None,
            case_version=command.case_version,
            boundary_version="BOUND-01",
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            policy_version=command.policy_version,
            payload_version="PL-01",
            decided_at=now,
        )
        events.append(approval)

    elif isinstance(command, ApproveNotificationCommand):
        approval = ApprovalDecision(
            approval_id=command.approval_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            approval_type="notification",
            decision="approved",
            rationale=command.rationale,
            requester_id=command.actor_id,
            approver_id=principal.principal_id,
            approver_role=principal.roles[0] if principal.roles else None,
            case_version=command.case_version,
            boundary_version="BOUND-01",
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            payload_version=command.payload_version,
            policy_version=command.policy_version,
            decided_at=now,
        )
        events.append(approval)

    elif isinstance(command, ApproveClosureCommand):
        approval = ApprovalDecision(
            approval_id=command.approval_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            approval_type="closure",
            decision="approved",
            rationale=command.rationale,
            requester_id=command.actor_id,
            approver_id=principal.principal_id,
            approver_role=principal.roles[0] if principal.roles else None,
            case_version=command.case_version,
            boundary_version="BOUND-01",
            policy_version=command.policy_version,
            decided_at=now,
        )
        events.append(approval)

    elif isinstance(command, ApproveReleaseCommand):
        approval = ApprovalDecision(
            approval_id=command.approval_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            approval_type="release",
            decision="approved",
            rationale=command.rationale,
            requester_id=command.actor_id,
            approver_id=principal.principal_id,
            approver_role=principal.roles[0] if principal.roles else None,
            case_version=command.case_version,
            boundary_version="BOUND-RELEASE-01",
            scope_id=command.scope_id,
            scope_version=command.scope_version,
            policy_version=command.policy_version,
            retest_doc_id=command.retest_doc_id,
            retest_doc_hash=command.retest_doc_hash,
            decided_at=now,
        )
        events.append(approval)

        # Emit release events ONLY when authority explicitly confirms Step 2 final clearance
        if decision.code == "ALLOWED_RELEASE_FINAL_STEP":
            for action in state.containment_actions:
                if action.scope_id == command.scope_id and action.action_type == "provisional_hold":
                    events.append(
                        ContainmentReleasedEvent(
                            event_id=f"EVT-REL-{action.action_id}",
                            tenant_id=command.tenant_id,
                            case_id=command.case_id,
                            actor_id=command.actor_id,
                            case_version=command.case_version,
                            action_id=action.action_id,
                            scope_id=command.scope_id,
                            retest_doc_id=command.retest_doc_id,
                            retest_doc_hash=command.retest_doc_hash,
                            kind="containment_released",
                            occurred_at=now,
                        )
                    )


    # Fold all new events over current state
    new_state = state
    for ev in events:
        new_state = apply_event(new_state, ev)

    return CommandExecutionResult(new_state, events, decision)


@dataclass(frozen=True)
class ActionExecution:
    """The result of one orchestration step for a reserved containment action."""

    status: Literal["succeeded", "failed", "unknown"]
    idempotency_token: str
    payload_hash: str
    receipt: ActionReceipt | None
    action: ContainmentAction
    state: IncidentState


class ContainmentExecutor:
    """Drives one reserved containment action through an idempotent adapter.

    Guarantees three properties the design spec requires of the safe-retry protocol:

    * **persist before effect** — the in-flight reservation is appended to the event
      stream *before* the adapter is ever called, so a crash cannot lose the fact that
      an attempt was made;
    * **reconcile before retry** — ``resume`` asks the adapter whether the effect already
      happened before delivering again, so an ambiguous first attempt cannot double-fire;
    * **one externally visible effect** — the idempotency token is the stable
      ``action_key`` of the approved intent, so the adapter collapses retries of the
      identical payload into a single receipt.
    """

    def __init__(self, repository: IncidentRepository, sink: ActionAdapter) -> None:
        self._repository = repository
        self._sink = sink

    @staticmethod
    def _action_id(token: str) -> str:
        return f"ACTION-{token[:16]}"

    def _reserve(
        self, intent: ActionIntent, token: str, *, attempt: int, now: datetime
    ) -> ContainmentAction:
        if intent.quantity is None:
            raise InvariantViolation("a reserved containment action requires an explicit quantity")
        if intent.effect_kind not in ("provisional_hold", "release_hold"):
            raise InvariantViolation(f"unsupported containment effect kind: {intent.effect_kind}")
        return ContainmentAction(
            action_id=self._action_id(token),
            tenant_id=intent.tenant_id,
            case_id=intent.case_id,
            scope_id=intent.scope_id,
            scope_version=intent.scope_version,
            action_type=intent.effect_kind,
            status="in_flight",
            target_record_ids=intent.target_record_ids,
            quantity=intent.quantity,
            policy_version=intent.policy_version,
            requested_at=now,
            idempotency_token=token,
            payload_hash=intent.payload_hash,
            provider_reference=None,
            attempt=attempt,
        )

    async def _append_action(
        self, case_id: str, action: ContainmentAction, *, actor_id: str, now: datetime
    ) -> IncidentState:
        state = await self._repository.load(case_id)
        if state is None:
            raise InvariantViolation(f"unknown incident case: {case_id}")
        event = ContainmentAttemptedEvent(
            kind="containment_attempted",
            event_id=f"EVT-{action.action_id}-{action.status}-A{action.attempt}",
            tenant_id=action.tenant_id,
            case_id=action.case_id,
            actor_id=actor_id,
            case_version=state.case.case_version,
            occurred_at=now,
            action=action,
        )
        return await self._repository.append(case_id, state.case.case_version, (event,))

    def _find_action(self, state: IncidentState, token: str) -> ContainmentAction | None:
        action_id = self._action_id(token)
        return next(
            (action for action in state.containment_actions if action.action_id == action_id),
            None,
        )

    async def _settle(
        self,
        case_id: str,
        action: ContainmentAction,
        receipt: ActionReceipt,
        *,
        actor_id: str,
        now: datetime,
        state: IncidentState,
    ) -> ActionExecution:
        token = action.idempotency_token or ""
        payload_hash = action.payload_hash or ""
        if receipt.status == "succeeded":
            settled = action.model_copy(
                update={"status": "succeeded", "provider_reference": receipt.provider_reference}
            )
            state = await self._append_action(case_id, settled, actor_id=actor_id, now=now)
            return ActionExecution("succeeded", token, payload_hash, receipt, settled, state)
        # Transient failure or ambiguous outcome: the persisted in-flight reservation is
        # the durable checkpoint. resume() decides whether to reconcile or retry.
        return ActionExecution(receipt.status, token, payload_hash, receipt, action, state)

    async def dispatch(
        self, *, case_id: str, intent: ActionIntent, actor_id: str, now: datetime
    ) -> ActionExecution:
        """Reserve, persist, and attempt a containment action for the first time."""
        token = action_key(intent)
        state = await self._repository.load(case_id)
        if state is None:
            raise InvariantViolation(f"unknown incident case: {case_id}")
        existing = self._find_action(state, token)
        if existing is not None and existing.status == "succeeded":
            # Duplicate delivery of an already-completed action: never re-execute.
            receipt = await self._sink.reconcile(token)
            return ActionExecution(
                "succeeded", token, existing.payload_hash or "", receipt, existing, state
            )
        reserved = self._reserve(intent, token, attempt=1, now=now)
        state = await self._append_action(case_id, reserved, actor_id=actor_id, now=now)
        receipt = await self._sink.execute(intent, idempotency_token=token)
        return await self._settle(
            case_id, reserved, receipt, actor_id=actor_id, now=now, state=state
        )

    async def resume(
        self, *, case_id: str, intent: ActionIntent, actor_id: str, now: datetime
    ) -> ActionExecution:
        """Resume a reserved action, reconciling before any retry of the payload."""
        token = action_key(intent)
        state = await self._repository.load(case_id)
        if state is None:
            raise InvariantViolation(f"unknown incident case: {case_id}")
        action = self._find_action(state, token)
        if action is None:
            raise InvariantViolation("cannot resume an action that was never reserved")
        if action.status == "succeeded":
            receipt = await self._sink.reconcile(token)
            return ActionExecution(
                "succeeded", token, action.payload_hash or "", receipt, action, state
            )
        prior = await self._sink.reconcile(token)
        if prior is not None and prior.status == "succeeded":
            # The effect already happened; adopt it instead of delivering a second time.
            settled = action.model_copy(
                update={
                    "status": "succeeded",
                    "provider_reference": prior.provider_reference,
                    "attempt": action.attempt + 1,
                }
            )
            state = await self._append_action(case_id, settled, actor_id=actor_id, now=now)
            return ActionExecution(
                "succeeded", token, action.payload_hash or "", prior, settled, state
            )
        retried = action.model_copy(update={"attempt": action.attempt + 1})
        receipt = await self._sink.execute(intent, idempotency_token=token)
        return await self._settle(
            case_id, retried, receipt, actor_id=actor_id, now=now, state=state
        )
