"""Standing-policy evaluation with no implicit target, quantity, or expiry inference."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from .identifiers import ActionIntent
from .models import DomainRecord, IncidentState

_EVAL_HOLD_POLICY = "EVAL-HOLD-01"
_EVAL_HOLD_MAXIMUM = Decimal("200")
_EVAL_HOLD_EXPIRY = timedelta(minutes=30)


class PolicyDecision(DomainRecord):
    allowed: bool
    code: str
    explanation: str
    events: tuple[object, ...] = ()
    requested_effects: tuple[ActionIntent, ...] = ()


def _denied(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(allowed=False, code=code, explanation=explanation)


def _matching_scope(intent: ActionIntent, state: IncidentState):
    return next((scope for scope in state.scopes if scope.scope_id == intent.scope_id), None)


def evaluate_hold_policy(
    intent: ActionIntent, state: IncidentState, now: datetime
) -> PolicyDecision:
    """Allow only the authored, reversible 30-minute evaluation hold."""

    if now.tzinfo is None or now.utcoffset() is None:
        return _denied("NOW_NOT_AWARE", "policy evaluation requires an aware current time")
    if intent.policy_version != _EVAL_HOLD_POLICY:
        return _denied("POLICY_NOT_ALLOWED", "only EVAL-HOLD-01 is a standing hold policy")
    if intent.tenant_id != state.case.tenant_id:
        return _denied("TENANT_MISMATCH", "intent tenant does not match the incident")
    if intent.case_id != state.case.case_id:
        return _denied("CASE_MISMATCH", "intent case does not match the incident")
    if intent.effect_kind != "provisional_hold":
        return _denied("EFFECT_KIND_NOT_ALLOWED", "standing policy only permits provisional holds")
    scope = _matching_scope(intent, state)
    if scope is None:
        return _denied("MISSING_SCOPE", "the hold scope is not present in the incident")
    if scope.scope_version != intent.scope_version:
        return _denied("STALE_SCOPE_VERSION", "the hold intent is bound to an old scope version")
    if scope.status != "approved":
        return _denied("SCOPE_NOT_APPROVED", "the hold scope must already be approved")
    if not set(intent.target_record_ids).issubset(set(scope.affected_record_ids)):
        return _denied("TARGET_NOT_AFFECTED", "hold targets must already be affected finished lots")
    if len(set(intent.target_record_ids)) != len(intent.target_record_ids):
        return _denied("TARGET_NOT_AFFECTED", "hold targets must be distinct")
    if intent.quantity is None:
        return _denied("MISSING_QUANTITY", "standing policy never infers a hold quantity")
    if intent.quantity > _EVAL_HOLD_MAXIMUM:
        return _denied("QUANTITY_EXCEEDS_POLICY", "hold quantity exceeds the authored maximum")
    if intent.quantity <= Decimal("0"):
        return _denied("QUANTITY_NOT_POSITIVE", "hold quantity must be positive")
    if intent.reversible is None:
        return _denied("MISSING_REVERSIBILITY", "standing policy requires explicit reversibility")
    if not intent.reversible:
        return _denied("ACTION_NOT_REVERSIBLE", "standing policy permits only reversible actions")
    if intent.expires_at is None:
        return _denied("MISSING_EXPIRY", "standing policy never infers an expiry")
    if now >= intent.expires_at:
        return _denied("ACTION_EXPIRED", "the hold intent is already expired")
    if intent.expires_at - now != _EVAL_HOLD_EXPIRY:
        return _denied("EXPIRY_NOT_AUTHORED", "hold expiry must be exactly 30 minutes")
    return PolicyDecision(
        allowed=True,
        code="ALLOWED",
        explanation="the complete authored hold intent satisfies EVAL-HOLD-01",
        requested_effects=(intent,),
    )
