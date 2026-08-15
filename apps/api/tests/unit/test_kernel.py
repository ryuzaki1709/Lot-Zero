"""Kernel event-sourcing: authentic reduction, idempotency, and compare-and-set."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lot_zero.adapters.demo_sink import DemoNotificationSink
from lot_zero.adapters.memory_repository import InMemoryIncidentRepository
from lot_zero.domain.events import AcknowledgementRecordedEvent
from lot_zero.domain.identifiers import ActionIntent, action_key
from lot_zero.domain.kernel import ContainmentExecutor
from lot_zero.domain.models import IncidentState, RecallCase
from lot_zero.domain.reducer import apply_event, rehydrate

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"
TARGETS = ("FP-100-L240814-A", "FP-100-L240814-B")


def seed_state() -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=CASE,
            tenant_id=TENANT,
            phase="provisional_containment",
            case_version=0,
            source_record_ids=("LAB-SIGNAL-20260814-001",),
            created_at=NOW,
            updated_at=NOW,
        ),
        updated_at=NOW,
    )


def hold_intent() -> ActionIntent:
    return ActionIntent(
        tenant_id=TENANT,
        case_id=CASE,
        effect_kind="provisional_hold",
        scope_id="SCOPE-EVAL-01",
        scope_version=2,
        payload_version="HOLD-PAYLOAD-001",
        policy_version="EVAL-HOLD-01",
        target_record_ids=TARGETS,
        payload_hash="hold-payload-sha256",
        quantity=Decimal("200"),
        reversible=True,
    )


def ack_event() -> AcknowledgementRecordedEvent:
    return AcknowledgementRecordedEvent(
        kind="acknowledgement_recorded",
        event_id="EVT-ACK-1",
        tenant_id=TENANT,
        case_id=CASE,
        actor_id="OPS-001",
        case_version=0,
        occurred_at=NOW,
        packet_id="PACKET-001",
        acknowledgement_id="ACK-001",
        recipient_id="RECIPIENT-001",
        acknowledgement_status="verified",
    )


def test_containment_reduction_uses_authentic_intent_quantity() -> None:
    async def scenario():
        repository = InMemoryIncidentRepository(initial_state=seed_state())
        executor = ContainmentExecutor(repository, DemoNotificationSink())
        result = await executor.dispatch(
            case_id=CASE, intent=hold_intent(), actor_id="AGENT-001", now=NOW
        )
        return result, await repository.load(CASE)

    result, state = asyncio.run(scenario())

    assert result.status == "succeeded"
    assert len(state.containment_actions) == 1
    action = state.containment_actions[0]
    assert action.quantity == Decimal("200")  # from the intent, never a literal
    assert action.status == "succeeded"
    assert action.provider_reference is not None
    assert action.idempotency_token == action_key(hold_intent())


def test_duplicate_dispatch_suppresses_the_second_effect() -> None:
    async def scenario():
        repository = InMemoryIncidentRepository(initial_state=seed_state())
        sink = DemoNotificationSink()
        executor = ContainmentExecutor(repository, sink)
        first = await executor.dispatch(
            case_id=CASE, intent=hold_intent(), actor_id="AGENT-001", now=NOW
        )
        second = await executor.dispatch(
            case_id=CASE, intent=hold_intent(), actor_id="AGENT-001", now=NOW
        )
        return sink, first, second

    sink, first, second = asyncio.run(scenario())

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert len(sink.receipts) == 1


def test_rehydrate_is_deterministic() -> None:
    first = rehydrate(seed_state(), [ack_event()])
    second = rehydrate(seed_state(), [ack_event()])

    assert first == second
    assert len(first.acknowledgements) == 1
    assert first.acknowledgements[0].status == "verified"
    assert len(first.ledger) == 1
    assert first.case.case_version == 1


def test_append_rejects_a_stale_expected_version() -> None:
    from lot_zero.ports.repositories import ConcurrencyError

    repository = InMemoryIncidentRepository(initial_state=seed_state())

    with pytest.raises(ConcurrencyError):
        asyncio.run(repository.append(CASE, 5, ()))


def test_reducer_rejects_an_unsupported_event() -> None:
    from lot_zero.domain.errors import InvariantViolation

    with pytest.raises(InvariantViolation):
        apply_event(seed_state(), object())
