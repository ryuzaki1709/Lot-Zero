"""Consequential operations require explicit human or standing-policy authority."""

from __future__ import annotations

import re
from typing import Literal

from .commands import (
    AdvancePhaseCommand,
    ApprovalCommand,
    ApproveClosureCommand,
    ApproveContainmentCommand,
    ApproveNotificationCommand,
    ApproveReleaseCommand,
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
from .models import DomainRecord, Identifier, IncidentState, Role


class Principal(DomainRecord):
    tenant_id: Identifier
    principal_id: Identifier
    roles: tuple[Role, ...]


class AuthorizationDecision(DomainRecord):
    allowed: bool
    code: str
    explanation: str
    events: tuple[object, ...] = ()
    requested_effects: tuple[ActionIntent, ...] = ()


def _deny(code: str, explanation: str) -> AuthorizationDecision:
    return AuthorizationDecision(allowed=False, code=code, explanation=explanation)


def _allow(explanation: str, *, code: str = "ALLOWED", effects: tuple[ActionIntent, ...] = ()) -> AuthorizationDecision:
    return AuthorizationDecision(
        allowed=True,
        code=code,
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
    if state.case.phase == "closed" and not isinstance(command, RecordAcknowledgementCommand):
        return _deny("CASE_ALREADY_CLOSED", "mutations are not allowed on a closed incident case")
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
        and approval.case_version <= state.case.case_version
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
    if packet is not None:
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
    
    # Active refusals cannot be waived under non-response
    rejected = [ack for ack in state.acknowledgements if ack.status == "rejected"]
    if rejected:
        return _deny(
            "REJECTED_ACKNOWLEDGEMENT_REQUIRES_SEIZURE_REFERRAL",
            "Consignee actively refused recall notice. Cannot close under non-response; requires regulatory seizure/injunction referral."
        )

    # Outstanding acks check
    outstanding = [ack for ack in state.acknowledgements if ack.status == "outstanding"]
    if outstanding:
        # Check if certified good-faith non-response under 21 CFR § 7.49 is attached
        if not (command.non_response_filing_id and command.attempt_count and command.attempt_count >= 3):
            return _deny("OUTSTANDING_ACKNOWLEDGEMENT", "all consignee acknowledgements must be verified before closure")

    # Strict fallthrough: recovery and effectiveness evidence are unconditionally required
    if state.recovery is not None:
        return _deny("UNRESOLVED_BLOCKER", "closure requires all blockers to be resolved")
    if not command.effectiveness_evidence_ids:
        return _deny("MISSING_EFFECTIVENESS_EVIDENCE", "closure requires effectiveness evidence")
    return _allow("closure evidence and acknowledgement state are complete")


def _authorize_release(
    command: ApproveReleaseCommand, principal: Principal, state: IncidentState
) -> AuthorizationDecision:
    scope_denial = _check_scope(command, state)
    if scope_denial is not None:
        return scope_denial
    
    # Strictly validate 64-char SHA-256 hex string format
    if not re.fullmatch(r"^[a-fA-F0-9]{64}$", command.retest_doc_hash):
        return _deny("INVALID_RETEST_HASH", "retest_doc_hash must be a valid 64-character SHA-256 hex digest")
    if not command.retest_doc_id.strip():
        return _deny("MISSING_RETEST_DOC_ID", "release authorization requires a cited re-test document ID")

    # Must have an active hold on this scope to release
    matching_holds = [
        a for a in state.containment_actions
        if a.scope_id == command.scope_id and a.action_type == "provisional_hold"
    ]
    if not matching_holds:
        return _deny("NO_HOLD_TO_RELEASE", "cannot authorize release on a scope with no active containment holds")

    has_qa = _has_role(principal, "qa")
    has_closure = _has_role(principal, "closure_authority")

    # Reject dual-role ambiguity: principal cannot assert both roles simultaneously
    if has_qa and has_closure:
        return _deny("DUAL_ROLE_AMBIGUITY", "Principal holds both QA and Closure Authority roles; separation of duties requires distinct acting identities.")

    # Step 1: QA Lead biological clearance
    if has_qa:
        human_denial = _check_human_approval(command, principal, "qa")
        if human_denial is not None:
            return human_denial
        # If QA clearance is already recorded, Step 2 requires Closure Authority
        prior_qa_approval = next(
            (
                app
                for app in state.approvals
                if app.approval_type == "release"
                and app.decision == "approved"
                and app.approver_role == "qa"
                and app.scope_id == command.scope_id
                and app.scope_version == command.scope_version
                and app.retest_doc_hash == command.retest_doc_hash
            ),
            None,
        )
        if prior_qa_approval is not None:
            return _deny(
                "STEP_1_ALREADY_RECORDED",
                "QA biological clearance already recorded; step 2 requires Closure Authority signature.",
            )
        return _allow("QA lead may authorize biological re-test clearance", code="ALLOWED_RELEASE_QA_STEP")

    # Step 2: Closure / Operational Authority release (requires prior QA approval)
    if has_closure:
        human_denial = _check_human_approval(command, principal, "closure_authority")
        if human_denial is not None:
            return human_denial
        
        # Verify prior QA release approval exists for the exact same scope, scope_version, and re-test hash
        prior_qa_approval = next(
            (
                app
                for app in state.approvals
                if app.approval_type == "release"
                and app.decision == "approved"
                and app.approver_role == "qa"
                and app.scope_id == command.scope_id
                and app.scope_version == command.scope_version
                and app.retest_doc_hash == command.retest_doc_hash
            ),
            None,
        )
        if prior_qa_approval is None:
            return _deny(
                "MISSING_QA_RELEASE_APPROVAL",
                "operational inventory release requires prior biological clearance from QA Lead with matching re-test hash",
            )
        
        # Check if already consumed by an earlier final release
        already_consumed = any(
            app
            for app in state.approvals
            if app.approval_type == "release"
            and app.decision == "approved"
            and app.approver_role == "closure_authority"
            and app.scope_id == command.scope_id
            and app.scope_version == command.scope_version
            and app.retest_doc_hash == command.retest_doc_hash
        )
        if already_consumed:
            return _deny(
                "QA_APPROVAL_ALREADY_CONSUMED",
                "This QA clearance has already been consumed by an earlier operational release.",
            )

        # Enforce distinct human principals: QA Lead and Closure Authority must not be the same person
        if principal.principal_id == prior_qa_approval.approver_id:
            return _deny(
                "DUAL_SIGNATURE_SAME_PRINCIPAL",
                "Separation of duties violation: Closure Authority release cannot be signed by the same principal who provided QA clearance.",
            )

        return _allow("closure authority may finalize dual-signature inventory release", code="ALLOWED_RELEASE_FINAL_STEP")

    return _deny("ROLE_NOT_AUTHORIZED", "release authorization requires QA Lead or Closure Authority")


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
        return _deny("MISSING_CONTAINMENT_APPROVAL", "containment needs human approval")
    return None


def authorize(
    command: CommandRecord, principal: Principal, state: IncidentState
) -> AuthorizationDecision:
    """Authorize or deny an incoming command against the current incident state."""
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
    if isinstance(command, ApproveReleaseCommand):
        return _authorize_release(command, principal, state)
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
        if command.attestation_hash and not re.fullmatch(r"^[a-fA-F0-9]{64}$", command.attestation_hash):
            return _deny("INVALID_ATTESTATION_HASH", "attestation_hash must be a 64-character SHA-256 digest")
        
        # Prevent downgrading already verified acknowledgements
        existing_ack = next(
            (a for a in state.acknowledgements if a.acknowledgement_id == command.acknowledgement_id),
            None,
        )
        if existing_ack and existing_ack.status == "verified" and command.acknowledgement_status != "verified":
            return _deny(
                "CANNOT_DOWNGRADE_VERIFIED_ACKNOWLEDGEMENT",
                "Verified consignee acknowledgements cannot be erased or downgraded.",
            )

        return _allow("customer operations may record an acknowledgement")
    if isinstance(command, RequestClosureCommand):
        if not _has_role(principal, "recall_coordinator"):
            return _deny("ROLE_NOT_AUTHORIZED", "only a coordinator may request closure review")
        return _allow("closure review request is within coordinator authority")
    if isinstance(command, AdvancePhaseCommand):
        target = command.target_phase
        if target == "scope_review":
            if not _has_role(principal, "recall_coordinator"):
                return _deny("ROLE_NOT_AUTHORIZED", "Advancing to scope_review requires recall_coordinator role")
        elif target in ("provisional_containment", "action_review"):
            if not _has_role(principal, "qa") and not _has_role(principal, "recall_coordinator"):
                return _deny("ROLE_NOT_AUTHORIZED", f"Advancing to {target} requires qa or recall_coordinator role")
        elif target == "ack_monitoring":
            if not _has_role(principal, "customer_operations"):
                return _deny("ROLE_NOT_AUTHORIZED", "Advancing to ack_monitoring requires customer_operations role")
        elif target == "effectiveness_check":
            if not _has_role(principal, "customer_operations") and not _has_role(principal, "closure_authority"):
                return _deny("ROLE_NOT_AUTHORIZED", "Advancing to effectiveness_check requires customer_operations or closure_authority role")
        elif target == "closed":
            if not _has_role(principal, "closure_authority"):
                return _deny("ROLE_NOT_AUTHORIZED", "Advancing to closed requires closure_authority role")
        return _allow(f"Authorized phase transition to {target}")
    return _deny("COMMAND_NOT_SUPPORTED", "command is outside the closed authority boundary")
