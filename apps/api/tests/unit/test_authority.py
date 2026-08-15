"""Authority decisions bind each approval to its exact incident boundary."""

from datetime import UTC, datetime

import pytest

from lot_zero.domain.authority import Principal, authorize
from lot_zero.domain.commands import (
    ApproveClosureCommand,
    ApproveNotificationCommand,
    ApproveScopeCommand,
    ExecuteStandingPolicyCommand,
    ProposeScopeCommand,
    SendNotificationCommand,
)
from lot_zero.domain.identifiers import ActionIntent
from lot_zero.domain.models import (
    Acknowledgement,
    AffectedScope,
    ApprovalDecision,
    IncidentState,
    NotificationPacket,
    RecallCase,
)

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"


def principal(
    role: str, *, tenant_id: str = TENANT, principal_id: str = "APPROVER-001"
) -> Principal:
    return Principal(tenant_id=tenant_id, principal_id=principal_id, roles=(role,))


def state(*, approvals: tuple[ApprovalDecision, ...] = ()) -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=CASE,
            tenant_id=TENANT,
            phase="ack_monitoring",
            case_version=7,
            source_record_ids=("LAB-SIGNAL-20260814-001",),
            created_at=NOW,
            updated_at=NOW,
        ),
        scopes=(
            AffectedScope(
                scope_id="SCOPE-EVAL-01",
                tenant_id=TENANT,
                case_id=CASE,
                case_version=7,
                scope_version=4,
                status="approved",
                affected_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
                evidence_record_ids=("LAB-SIGNAL-20260814-001",),
                affected_quantity=200,
                created_at=NOW,
            ),
        ),
        notification_packets=(
            NotificationPacket(
                packet_id="PACKET-001",
                tenant_id=TENANT,
                case_id=CASE,
                scope_id="SCOPE-EVAL-01",
                scope_version=4,
                payload_version="PAYLOAD-002",
                payload_hash="payload-sha256",
                status="planned",
                recipient_ids=("RECIPIENT-001",),
                created_at=NOW,
            ),
        ),
        acknowledgements=(
            Acknowledgement(
                acknowledgement_id="ACK-006",
                tenant_id=TENANT,
                case_id=CASE,
                packet_id="PACKET-001",
                recipient_id="RECIPIENT-006",
                status="outstanding",
            ),
        ),
        approvals=approvals,
        updated_at=NOW,
    )


def propose_scope(**overrides: object) -> ProposeScopeCommand:
    return ProposeScopeCommand.model_validate(
        {
            "kind": "propose_scope",
            "command_id": "CMD-SCOPE-001",
            "tenant_id": TENANT,
            "case_id": CASE,
            "actor_id": "REQUESTER-001",
            "case_version": 7,
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 4,
            "evidence_record_ids": ("LAB-SIGNAL-20260814-001",),
            "policy_version": "SCOPE-POLICY-01",
            **overrides,
        }
    )


def send_notification(**overrides: object) -> SendNotificationCommand:
    return SendNotificationCommand.model_validate(
        {
            "kind": "send_notification",
            "command_id": "CMD-NOTIFY-001",
            "tenant_id": TENANT,
            "case_id": CASE,
            "actor_id": "REQUESTER-001",
            "case_version": 7,
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 4,
            "packet_id": "PACKET-001",
            "payload_version": "PAYLOAD-002",
            "policy_version": "NOTIFY-POLICY-01",
            "recipient_ids": ("RECIPIENT-001",),
            **overrides,
        }
    )


def notification_approval() -> ApprovalDecision:
    return ApprovalDecision(
        approval_id="APPROVAL-NOTIFY-001",
        tenant_id=TENANT,
        case_id=CASE,
        approval_type="notification",
        decision="approved",
        rationale="Recipient and payload reviewed",
        requester_id="REQUESTER-001",
        approver_id="APPROVER-002",
        case_version=7,
        boundary_version="PAYLOAD-002",
        scope_version=4,
        payload_version="PAYLOAD-002",
        policy_version="NOTIFY-POLICY-01",
        decided_at=NOW,
    )


def hold_intent() -> ActionIntent:
    return ActionIntent(
        tenant_id=TENANT,
        case_id=CASE,
        effect_kind="provisional_hold",
        scope_id="SCOPE-EVAL-01",
        scope_version=4,
        payload_version="HOLD-PAYLOAD-001",
        policy_version="EVAL-HOLD-01",
        target_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
        payload_hash="hold-payload-sha256",
    )


def containment_approval() -> ApprovalDecision:
    return ApprovalDecision(
        approval_id="APPROVAL-HOLD-001",
        tenant_id=TENANT,
        case_id=CASE,
        approval_type="containment",
        decision="approved",
        rationale="Hold reviewed",
        requester_id="REQUESTER-001",
        approver_id="APPROVER-002",
        case_version=7,
        boundary_version="4",
        scope_version=4,
        payload_version="HOLD-PAYLOAD-001",
        policy_version="EVAL-HOLD-01",
        decided_at=NOW,
    )


def assert_inert_denial(decision, code: str) -> None:
    assert decision.allowed is False
    assert decision.code == code
    assert decision.events == ()
    assert decision.requested_effects == ()


@pytest.mark.parametrize(
    ("role", "allowed"),
    (("recall_coordinator", True), ("qa", False), ("customer_operations", False)),
)
def test_only_coordinator_can_propose_scope(role: str, allowed: bool) -> None:
    decision = authorize(propose_scope(), principal(role), state())

    assert decision.allowed is allowed
    if not allowed:
        assert_inert_denial(decision, "ROLE_NOT_AUTHORIZED")


def test_scope_approval_does_not_authorize_notification() -> None:
    scope_approval = ApprovalDecision(
        approval_id="APPROVAL-SCOPE-001",
        tenant_id=TENANT,
        case_id=CASE,
        approval_type="scope",
        decision="approved",
        rationale="Scope reviewed",
        requester_id="REQUESTER-001",
        approver_id="APPROVER-002",
        case_version=7,
        boundary_version="4",
        scope_version=4,
        decided_at=NOW,
    )

    decision = authorize(send_notification(), principal("qa"), state(approvals=(scope_approval,)))

    assert_inert_denial(decision, "MISSING_NOTIFICATION_APPROVAL")


def test_notification_authorization_requires_matching_current_versions() -> None:
    decision = authorize(
        send_notification(),
        principal("customer_operations"),
        state(approvals=(notification_approval(),)),
    )

    assert decision.allowed is True


@pytest.mark.parametrize(
    ("command_overrides", "code"),
    (
        ({"tenant_id": "OTHER-TENANT"}, "TENANT_MISMATCH"),
        ({"case_id": "OTHER-CASE"}, "CASE_MISMATCH"),
        ({"case_version": 6}, "STALE_CASE_VERSION"),
        ({"scope_version": 3}, "STALE_SCOPE_VERSION"),
        ({"payload_version": "PAYLOAD-001"}, "STALE_PAYLOAD_VERSION"),
        ({"policy_version": "NOTIFY-POLICY-OLD"}, "STALE_POLICY_VERSION"),
    ),
)
def test_stale_or_cross_boundary_notification_is_inert(
    command_overrides: dict[str, object], code: str
) -> None:
    decision = authorize(
        send_notification(**command_overrides),
        principal("customer_operations"),
        state(approvals=(notification_approval(),)),
    )

    assert_inert_denial(decision, code)


@pytest.mark.parametrize(
    ("command", "role", "code"),
    (
        (
            lambda: ApproveScopeCommand(
                kind="approve_scope",
                command_id="CMD-APPROVE-SCOPE",
                approval_id="APPROVAL-SCOPE-001",
                tenant_id=TENANT,
                case_id=CASE,
                actor_id="REQUESTER-001",
                case_version=7,
                scope_id="SCOPE-EVAL-01",
                scope_version=4,
                policy_version="SCOPE-POLICY-01",
                rationale=" ",
            ),
            "qa",
            "MISSING_RATIONALE",
        ),
        (
            lambda: ApproveScopeCommand(
                kind="approve_scope",
                command_id="CMD-APPROVE-SCOPE-SAME",
                approval_id="APPROVAL-SCOPE-002",
                tenant_id=TENANT,
                case_id=CASE,
                actor_id="APPROVER-001",
                case_version=7,
                scope_id="SCOPE-EVAL-01",
                scope_version=4,
                policy_version="SCOPE-POLICY-01",
                rationale="Scope reviewed",
            ),
            "qa",
            "REQUESTER_APPROVER_CONFLICT",
        ),
        (
            lambda: ApproveNotificationCommand(
                kind="approve_notification",
                command_id="CMD-APPROVE-NOTIFY",
                approval_id="APPROVAL-NOTIFY-001",
                tenant_id=TENANT,
                case_id=CASE,
                actor_id="REQUESTER-001",
                case_version=7,
                scope_id="SCOPE-EVAL-01",
                scope_version=4,
                packet_id="PACKET-001",
                payload_version="PAYLOAD-002",
                policy_version="NOTIFY-POLICY-01",
                rationale="Payload reviewed",
            ),
            "qa",
            "ROLE_NOT_AUTHORIZED",
        ),
    ),
)
def test_human_approval_rules_are_total_and_inert(command, role: str, code: str) -> None:
    decision = authorize(command(), principal(role), state())

    assert_inert_denial(decision, code)


def test_closure_is_blocked_by_the_authored_outstanding_acknowledgement() -> None:
    command = ApproveClosureCommand(
        kind="approve_closure",
        command_id="CMD-CLOSE-001",
        approval_id="APPROVAL-CLOSE-001",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="REQUESTER-001",
        case_version=7,
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        rationale="Evidence reviewed",
        effectiveness_evidence_ids=("EVIDENCE-EFFECTIVE-001",),
    )

    decision = authorize(command, principal("closure_authority"), state())

    assert_inert_denial(decision, "OUTSTANDING_ACKNOWLEDGEMENT")


def test_agent_service_needs_a_matching_human_containment_approval() -> None:
    command = ExecuteStandingPolicyCommand(
        kind="execute_standing_policy",
        command_id="CMD-HOLD-001",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="AGENT-001",
        case_version=7,
        intent=hold_intent(),
    )

    missing = authorize(command, principal("agent_service", principal_id="AGENT-001"), state())
    approved = authorize(
        command,
        principal("agent_service", principal_id="AGENT-001"),
        state(approvals=(containment_approval(),)),
    )

    assert_inert_denial(missing, "MISSING_CONTAINMENT_APPROVAL")
    assert approved.allowed is True
    assert approved.requested_effects == (hold_intent(),)
