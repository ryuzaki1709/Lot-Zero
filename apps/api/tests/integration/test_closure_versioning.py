"""Integration tests for closure request versioning, optimistic concurrency, and separation of duties."""

from datetime import UTC, datetime

from lot_zero.domain.authority import Principal, authorize
from lot_zero.domain.commands import ApproveClosureCommand, RequestClosureCommand
from lot_zero.domain.kernel import execute_command
from lot_zero.domain.models import (
    AffectedScope,
    ClosureRequest,
    IncidentState,
    RecallCase,
)

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"


def base_incident_state() -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=CASE,
            tenant_id=TENANT,
            phase="effectiveness_check",
            case_version=5,
            source_record_ids=("LAB-SIGNAL-01",),
            created_at=NOW,
            updated_at=NOW,
        ),
        scopes=(
            AffectedScope(
                scope_id="SCOPE-EVAL-01",
                tenant_id=TENANT,
                case_id=CASE,
                case_version=5,
                scope_version=2,
                status="approved",
                affected_record_ids=("LOT-01",),
                evidence_record_ids=("EVID-01",),
                affected_quantity=100,
                created_at=NOW,
            ),
        ),
        acknowledgements=(),
        approvals=(),
        closure_requests=(),
        updated_at=NOW,
    )


def test_closure_request_and_approval_flow():
    state = base_incident_state()
    coord_p = Principal(tenant_id=TENANT, principal_id="COORD-01", roles=("recall_coordinator",))
    closure_p = Principal(
        tenant_id=TENANT, principal_id="CLOSURE-AUTH-01", roles=("closure_authority",)
    )

    # 1. Recall coordinator requests closure
    req_cmd = RequestClosureCommand(
        kind="request_closure",
        command_id="CMD-REQ-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="COORD-01",
        case_version=5,
        request_id="REQ-001",
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        scope_version=2,
        evidence_record_ids=("EVID-01",),
    )
    res1 = execute_command(state, req_cmd, coord_p, occurred_at=NOW)

    assert res1.decision.allowed is True
    state_after_req = res1.state
    assert len(state_after_req.closure_requests) == 1
    req = state_after_req.closure_requests[0]
    assert req.request_id == "REQ-001"
    assert req.requester_principal_id == "COORD-01"
    assert req.request_stream_version == 6
    assert req.is_consumed is False

    # 2. Closure authority approves closure
    close_cmd = ApproveClosureCommand(
        kind="approve_closure",
        command_id="CMD-CLOSE-01",
        approval_id="APP-CLOSE-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="CLOSURE-AUTH-01",
        case_version=state_after_req.case.case_version,
        request_id="REQ-001",
        expected_request_stream_version=6,
        expected_scope_version=2,
        expected_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        rationale="All criteria met",
        effectiveness_evidence_ids=("EVID-01",),
    )
    res2 = execute_command(state_after_req, close_cmd, closure_p, occurred_at=NOW)
    assert res2.decision.allowed is True
    state_after_close = res2.state
    assert state_after_close.closure_requests[0].is_consumed is True

    # 3. Attempt replay/reuse of consumed closure request -> denied
    replay_cmd = ApproveClosureCommand(
        kind="approve_closure",
        command_id="CMD-CLOSE-02",
        approval_id="APP-CLOSE-02",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="CLOSURE-AUTH-01",
        case_version=state_after_close.case.case_version,
        request_id="REQ-001",
        expected_request_stream_version=6,
        expected_scope_version=2,
        expected_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        rationale="Replay attempt",
        effectiveness_evidence_ids=("EVID-01",),
    )
    res_replay = execute_command(state_after_close, replay_cmd, closure_p, occurred_at=NOW)
    assert res_replay.decision.allowed is False
    assert res_replay.decision.code == "CLOSURE_REQUEST_ALREADY_CONSUMED"


def test_stale_request_stream_version_rejected():
    state = base_incident_state()
    req = ClosureRequest(
        request_id="REQ-001",
        tenant_id=TENANT,
        case_id=CASE,
        requester_principal_id="COORD-01",
        case_version=5,
        requested_scope_version=2,
        requested_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        request_stream_version=6,
        is_consumed=False,
        requested_at=NOW,
    )
    state = state.model_copy(update={"closure_requests": (req,)})
    closure_p = Principal(
        tenant_id=TENANT, principal_id="CLOSURE-AUTH-01", roles=("closure_authority",)
    )

    close_cmd = ApproveClosureCommand(
        kind="approve_closure",
        command_id="CMD-CLOSE-01",
        approval_id="APP-CLOSE-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="CLOSURE-AUTH-01",
        case_version=5,
        request_id="REQ-001",
        expected_request_stream_version=99,  # Mismatch
        expected_scope_version=2,
        expected_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        rationale="Rationale",
        effectiveness_evidence_ids=("EVID-01",),
    )
    decision = authorize(close_cmd, closure_p, state)
    assert decision.allowed is False
    assert decision.code == "STALE_REQUEST_STREAM_VERSION"


def test_requester_approver_conflict_rejected():
    state = base_incident_state()
    req = ClosureRequest(
        request_id="REQ-001",
        tenant_id=TENANT,
        case_id=CASE,
        requester_principal_id="PERSON-A",
        case_version=5,
        requested_scope_version=2,
        requested_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        request_stream_version=6,
        is_consumed=False,
        requested_at=NOW,
    )
    state = state.model_copy(update={"closure_requests": (req,)})

    # Same person trying to approve as closure authority
    same_p = Principal(tenant_id=TENANT, principal_id="PERSON-A", roles=("closure_authority",))

    close_cmd = ApproveClosureCommand(
        kind="approve_closure",
        command_id="CMD-CLOSE-01",
        approval_id="APP-CLOSE-01",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="PERSON-A",
        case_version=5,
        request_id="REQ-001",
        expected_request_stream_version=6,
        expected_scope_version=2,
        expected_policy_version="EVAL-CLOSE-01",
        closure_id="EVAL-CLOSE-01",
        policy_version="EVAL-CLOSE-01",
        rationale="Attempting self-approval",
        effectiveness_evidence_ids=("EVID-01",),
    )
    decision = authorize(close_cmd, same_p, state)
    assert decision.allowed is False
    assert decision.code == "REQUESTER_APPROVER_CONFLICT"
