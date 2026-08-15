"""Pure authority decisions for tenant- and version-bound incident commands."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .commands import (
    ApprovalCommand,
    ApproveClosureCommand,
    ApproveContainmentCommand,
    ApproveNotificationCommand,
    ApproveScopeCommand,
    CommandRecord,
    ExecuteStandingPolicyCommand,
    ProposeScopeCommand,
    RecordAcknowledgementCommand,
    RequestClosureCommand,
    RequestContainmentCommand,
    SendNotificationCommand,
)
from .identifiers import ActionIntent
from .models import DomainRecord, IncidentState

type Role = Literal[
    "recall_coordinator",
    "qa",
    "customer_operations",
    "closure_authority",
    "agent_service",
]


class Principal(DomainRecord):
    tenant_id: str
    principal_id: str
    roles: Annotated[tuple[Role, ...], Field(min_length=1)]


class AuthorizationDecision(DomainRecord):
    allowed: bool
    code: str
    explanation: str
    events: tuple[object, ...] = ()
    requested_effects: tuple[ActionIntent, ...] = ()


def _deny(code: str, explanation: str) -> AuthorizationDecision:
    return AuthorizationDecision(allowed=False, code=code, explanation=explanation)


def _allow(explanation: str, *, effects: tuple[ActionIntent, ...] = ()) -> AuthorizationDecision:
    return AuthorizationDecision(
        allowed=True,
        code="ALLOWED",
        explanation=explanation,
        requested_effects=effects,
    )


def _base_boundary(
    command: CommandRecord, principal: Principal, state: IncidentState
) -> AuthorizationDecision | None:
    if command.tenant_id != state.case.tenant_id or principal.tenant_id != state.case.tenant_id:
        return _deny("TENANT_MISMATCH", "principal and command must match the incident tenant")
    if command.case_id != state.case.case_id:
        return _deny("CASE_MISMATCH", "command case must match the incident")
    if command.case_version != state.case.case_version:
        return _deny("STALE_CASE_VERSION", "command is bound to an old case version")
    return None


def _has_role(principal: Principal, role: Role) -> bool:
    return role in principal.roles


def _scope_for(command: object, state: IncidentState):
    scope_id = getattr(command, "scope_id")
    return next((scope for scope in state.scopes if scope.scope_id == scope_id), None)


def _check_scope(command: object, state: IncidentState) -> AuthorizationDecision | None:
    scope = _scope_for(command, state)
    if scope is None:
        return _deny("MISSING_SCOPE", "command scope is not present in the incident")
    if scope.scope_version != getattr(command, "scope_version"):
        return _deny("STALE_SCOPE_VERSION", "command is bound to an old scope version")
    return None


def _check_human_approval(
    command: ApprovalCommand, principal: Principal, role: Role
) -> AuthorizationDecision | None:
    if not command.rationale.strip():
        return _deny("MISSING_RATIONALE", "human approval requires a nonblank rationale")
    if command.actor_id == principal.principal_id:
        return _deny(
            "REQUESTER_APPROVER_CONFLICT", "requester and approver must be different people"
        )
    if not _has_role(principal, role):
        return _deny("ROLE_NOT_AUTHORIZED", "principal lacks the required human approval role")
    return None


def _notification_approval(
    command: SendNotificationCommand, state: IncidentState
) -> AuthorizationDecision | None:
    related = tuple(
        approval
        for approval in state.approvals
        if approval.approval_type == "notification"
        and approval.decision == "approved"
        and approval.case_version == state.case.case_version
        and approval.scope_version == command.scope_version
        and approval.payload_version == command.payload_version
    )
    if not related:
        return _deny("MISSING_NOTIFICATION_APPROVAL", "notification needs its own approved payload")
    if not any(approval.policy_version == command.policy_version for approval in related):
        return _deny(
            "STALE_POLICY_VERSION", "notification approval is bound to another policy version"
        )
    return None


def _authorize_notification(
    command: SendNotificationCommand, principal: Principal, state: IncidentState
) -> AuthorizationDecision:
    scope_denial = _check_scope(command, state)
    if scope_denial is not None:
        return scope_denial
    packet = next(
        (packet for packet in state.notification_packets if packet.packet_id == command.packet_id),
        None,
    )
    if packet is None:
        return _deny(
            "MISSING_NOTIFICATION_PACKET", "notification packet is not present in the incident"
        )
    if packet.scope_version != command.scope_version:
        return _deny("STALE_SCOPE_VERSION", "packet is bound to another scope version")
    if packet.payload_version != command.payload_version:
        return _deny("STALE_PAYLOAD_VERSION", "command is bound to an old payload version")
    approval_denial = _notification_approval(command, state)
    if approval_denial is not None:
        return approval_denial
    if not _has_role(principal, "customer_operations"):
        return _deny("ROLE_NOT_AUTHORIZED", "customer operations owns notification approval")
    return _allow("notification is bound to a current customer operations approval")


def _authorize_closure(
    command: ApproveClosureCommand, principal: Principal, state: IncidentState
) -> AuthorizationDecision:
    human_denial = _check_human_approval(command, principal, "closure_authority")
    if human_denial is not None:
        return human_denial
    if command.closure_id != "EVAL-CLOSE-01" or command.policy_version != "EVAL-CLOSE-01":
        return _deny("CLOSURE_POLICY_NOT_ALLOWED", "closure requires EVAL-CLOSE-01")
    if any(ack.status == "outstanding" for ack in state.acknowledgements):
        return _deny("OUTSTANDING_ACKNOWLEDGEMENT", "all acknowledgements must be resolved first")
    if state.recovery is not None:
        return _deny("UNRESOLVED_BLOCKER", "closure requires all blockers to be resolved")
    if not command.effectiveness_evidence_ids:
        return _deny("MISSING_EFFECTIVENESS_EVIDENCE", "closure requires effectiveness evidence")
    return _allow("closure evidence and acknowledgement state are complete")


def _standing_policy_approval(
    intent: ActionIntent, state: IncidentState
) -> AuthorizationDecision | None:
    matching_approval = next(
        (
            approval
            for approval in state.approvals
            if approval.approval_type == "containment"
            and approval.decision == "approved"
            and approval.case_version == state.case.case_version
            and approval.scope_version == intent.scope_version
            and approval.payload_version == intent.payload_version
            and approval.policy_version == intent.policy_version
        ),
        None,
    )
    if matching_approval is None:
        return _deny(
            "MISSING_CONTAINMENT_APPROVAL",
            "agent service needs a matching human containment approval",
        )
    return None


def authorize(
    command: CommandRecord, principal: Principal, state: IncidentState
) -> AuthorizationDecision:
    """Return a complete, inert denial or a side-effect-free authority approval."""

    base_denial = _base_boundary(command, principal, state)
    if base_denial is not None:
        return base_denial
    if isinstance(command, ProposeScopeCommand):
        if not _has_role(principal, "recall_coordinator"):
            return _deny("ROLE_NOT_AUTHORIZED", "only a recall coordinator may propose scope")
        return _allow("recall coordinator may propose scope")
    if isinstance(command, RequestContainmentCommand):
        scope_denial = _check_scope(command, state)
        if scope_denial is not None:
            return scope_denial
        if not _has_role(principal, "recall_coordinator"):
            return _deny("ROLE_NOT_AUTHORIZED", "only a recall coordinator may request review")
        return _allow("containment review request is within coordinator authority")
    if isinstance(command, ApproveScopeCommand):
        human_denial = _check_human_approval(command, principal, "qa")
        if human_denial is not None:
            return human_denial
        return _check_scope(command, state) or _allow("QA may approve the current scope")
    if isinstance(command, ApproveContainmentCommand):
        human_denial = _check_human_approval(command, principal, "qa")
        if human_denial is not None:
            return human_denial
        return _check_scope(command, state) or _allow("QA may approve containment")
    if isinstance(command, ApproveNotificationCommand):
        human_denial = _check_human_approval(command, principal, "customer_operations")
        if human_denial is not None:
            return human_denial
        return _check_scope(command, state) or _allow(
            "customer operations may approve notification"
        )
    if isinstance(command, SendNotificationCommand):
        return _authorize_notification(command, principal, state)
    if isinstance(command, ApproveClosureCommand):
        return _authorize_closure(command, principal, state)
    if isinstance(command, ExecuteStandingPolicyCommand):
        if not _has_role(principal, "agent_service"):
            return _deny("ROLE_NOT_AUTHORIZED", "only agent service may execute standing policy")
        if (
            command.intent.tenant_id != state.case.tenant_id
            or command.intent.case_id != state.case.case_id
        ):
            return _deny("TENANT_MISMATCH", "standing policy intent must match the incident")
        scope_denial = _check_scope(command.intent, state)
        if scope_denial is not None:
            return scope_denial
        approval_denial = _standing_policy_approval(command.intent, state)
        if approval_denial is not None:
            return approval_denial
        return _allow(
            "agent service may execute a matching human-approved standing-policy intent",
            effects=(command.intent,),
        )
    if isinstance(command, RecordAcknowledgementCommand):
        if not _has_role(principal, "customer_operations"):
            return _deny("ROLE_NOT_AUTHORIZED", "customer operations records acknowledgements")
        return _allow("customer operations may record an acknowledgement")
    if isinstance(command, RequestClosureCommand):
        if not _has_role(principal, "recall_coordinator"):
            return _deny("ROLE_NOT_AUTHORIZED", "only a coordinator may request closure review")
        return _allow("closure review request is within coordinator authority")
    return _deny("COMMAND_NOT_SUPPORTED", "command is outside the closed authority boundary")
