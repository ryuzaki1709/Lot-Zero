"""Integration tests for complete 6-tuple notification approval identity matching."""

from datetime import UTC, datetime

from lot_zero.domain.authority import Principal, authorize
from lot_zero.domain.commands import SendNotificationCommand
from lot_zero.domain.models import (
    AffectedScope,
    ApprovalDecision,
    IncidentState,
    NotificationPacket,
    RecallCase,
)

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"


def setup_state_with_notification_approval(
    approval_scope_id="SCOPE-01",
    approval_scope_version=1,
    approval_payload_version="PL-01",
    approval_payload_hash="HASH-PL-01",
    approval_policy_version="POL-01",
) -> IncidentState:
    approval = ApprovalDecision(
        approval_id="APP-NOTIF-01",
        tenant_id=TENANT,
        case_id=CASE,
        approval_type="notification",
        decision="approved",
        rationale="Payload approved",
        requester_id="COORD-01",
        approver_id="OPS-01",
        case_version=3,
        boundary_version=approval_payload_hash,
        packet_id="PKT-01",
        scope_id=approval_scope_id,
        scope_version=approval_scope_version,
        payload_version=approval_payload_version,
        payload_hash=approval_payload_hash,
        policy_version=approval_policy_version,
        decided_at=NOW,
    )

    packet = NotificationPacket(
        packet_id="PKT-01",
        tenant_id=TENANT,
        case_id=CASE,
        scope_id=approval_scope_id,
        scope_version=approval_scope_version,
        payload_version=approval_payload_version,
        payload_hash=approval_payload_hash,
        status="planned",
        recipient_ids=("REC-01",),
        created_at=NOW,
    )
    return IncidentState(
        case=RecallCase(
            case_id=CASE,
            tenant_id=TENANT,
            phase="action_review",
            case_version=3,
            source_record_ids=("SIG-01",),
            created_at=NOW,
            updated_at=NOW,
        ),
        scopes=(
            AffectedScope(
                scope_id=approval_scope_id,
                tenant_id=TENANT,
                case_id=CASE,
                case_version=3,
                scope_version=approval_scope_version,
                status="approved",
                affected_record_ids=("LOT-01",),
                evidence_record_ids=("SIG-01",),
                affected_quantity=100,
                created_at=NOW,
            ),
        ),
        notification_packets=(packet,),
        approvals=(approval,),
        acknowledgements=(),
        closure_requests=(),
        updated_at=NOW,
    )


def test_matching_all_6_fields_succeeds():
    state = setup_state_with_notification_approval()
    ops_p = Principal(tenant_id=TENANT, principal_id="OPS-01", roles=("customer_operations",))

    cmd = SendNotificationCommand(
        kind="send_notification",
        command_id="CMD-NOTIF-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="OPS-01",
        case_version=3,
        packet_id="PKT-01",
        scope_id="SCOPE-01",
        scope_version=1,
        payload_version="PL-01",
        payload_hash="HASH-PL-01",
        policy_version="POL-01",
        recipient_ids=("REC-01",),
    )
    decision = authorize(cmd, ops_p, state)
    assert decision.allowed is True


def test_mismatch_in_payload_hash_denied():
    state = setup_state_with_notification_approval(approval_payload_hash="CORRECT-HASH")
    ops_p = Principal(tenant_id=TENANT, principal_id="OPS-01", roles=("customer_operations",))

    cmd = SendNotificationCommand(
        kind="send_notification",
        command_id="CMD-NOTIF-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="OPS-01",
        case_version=3,
        packet_id="PKT-01",
        scope_id="SCOPE-01",
        scope_version=1,
        payload_version="PL-01",
        payload_hash="ALTERED-HASH",
        policy_version="POL-01",
        recipient_ids=("REC-01",),
    )
    decision = authorize(cmd, ops_p, state)
    assert decision.allowed is False
    assert decision.code == "PAYLOAD_HASH_MISMATCH"
    assert decision.events == ()


def test_mismatch_in_packet_id_denied():
    state = setup_state_with_notification_approval()
    ops_p = Principal(tenant_id=TENANT, principal_id="OPS-01", roles=("customer_operations",))

    cmd = SendNotificationCommand(
        kind="send_notification",
        command_id="CMD-NOTIF-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="OPS-01",
        case_version=3,
        packet_id="PKT-DIFFERENT-02",
        scope_id="SCOPE-01",
        scope_version=1,
        payload_version="PL-01",
        payload_hash="HASH-PL-01",
        policy_version="POL-01",
        recipient_ids=("REC-01",),
    )
    decision = authorize(cmd, ops_p, state)
    assert decision.allowed is False
    assert decision.code == "MISSING_PACKET"
    assert decision.events == ()


def test_mismatch_in_policy_version_denied():
    state = setup_state_with_notification_approval(approval_policy_version="POL-01")
    ops_p = Principal(tenant_id=TENANT, principal_id="OPS-01", roles=("customer_operations",))

    cmd = SendNotificationCommand(
        kind="send_notification",
        command_id="CMD-NOTIF-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="OPS-01",
        case_version=3,
        packet_id="PKT-01",
        scope_id="SCOPE-01",
        scope_version=1,
        payload_version="PL-01",
        payload_hash="HASH-PL-01",
        policy_version="POL-DIFFERENT-99",
        recipient_ids=("REC-01",),
    )
    decision = authorize(cmd, ops_p, state)
    assert decision.allowed is False
    assert decision.code == "MISSING_NOTIFICATION_APPROVAL"
    assert decision.events == ()
