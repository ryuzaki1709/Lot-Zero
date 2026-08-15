"""Closed command boundary for consequential incident operations."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .identifiers import ActionIntent
from .models import DomainRecord, Identifier, NonNegativeVersion


class CommandRecord(DomainRecord):
    command_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    actor_id: Identifier
    case_version: NonNegativeVersion


class ProposeScopeCommand(CommandRecord):
    kind: Literal["propose_scope"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    policy_version: Identifier


class RequestContainmentCommand(CommandRecord):
    kind: Literal["request_containment"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    policy_version: Identifier
    action_type: Literal["provisional_hold", "release_hold"]
    target_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class SendNotificationCommand(CommandRecord):
    kind: Literal["send_notification"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    packet_id: Identifier
    payload_version: Identifier
    policy_version: Identifier
    recipient_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class RecordAcknowledgementCommand(CommandRecord):
    kind: Literal["record_acknowledgement"]
    packet_id: Identifier
    acknowledgement_id: Identifier
    recipient_id: Identifier
    acknowledgement_status: Literal["verified", "outstanding", "rejected"]


class RequestClosureCommand(CommandRecord):
    kind: Literal["request_closure"]
    closure_id: Identifier
    policy_version: Identifier
    outstanding_acknowledgement_ids: tuple[Identifier, ...] = ()


class ApprovalCommand(CommandRecord):
    """A human decision request; the principal supplies the approver identity."""

    approval_id: Identifier
    rationale: str


class ApproveScopeCommand(ApprovalCommand):
    kind: Literal["approve_scope"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    policy_version: Identifier


class ApproveContainmentCommand(ApprovalCommand):
    kind: Literal["approve_containment"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    policy_version: Identifier


class ApproveNotificationCommand(ApprovalCommand):
    kind: Literal["approve_notification"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    packet_id: Identifier
    payload_version: Identifier
    policy_version: Identifier


class ApproveClosureCommand(ApprovalCommand):
    kind: Literal["approve_closure"]
    closure_id: Identifier
    policy_version: Identifier
    effectiveness_evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class ExecuteStandingPolicyCommand(CommandRecord):
    kind: Literal["execute_standing_policy"]
    intent: ActionIntent


type CommandValue = Annotated[
    ProposeScopeCommand
    | RequestContainmentCommand
    | SendNotificationCommand
    | RecordAcknowledgementCommand
    | RequestClosureCommand
    | ApproveScopeCommand
    | ApproveContainmentCommand
    | ApproveNotificationCommand
    | ApproveClosureCommand
    | ExecuteStandingPolicyCommand,
    Field(discriminator="kind"),
]
Command = TypeAdapter(CommandValue)
