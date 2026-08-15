"""The safe-retry protocol: persist before effect, reconcile before retry, one receipt."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from lot_zero.adapters.demo_sink import DemoNotificationSink
from lot_zero.adapters.memory_repository import InMemoryIncidentRepository
from lot_zero.domain.identifiers import ActionIntent, action_key
from lot_zero.domain.kernel import ContainmentExecutor
from lot_zero.domain.models import IncidentState, RecallCase

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
LATER = datetime(2026, 8, 14, 12, 5, tzinfo=UTC)
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
    # Quantity 200 is the fixture's real affected quantity — no fabricated number.
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


class RetryHarness:
    def __init__(self, *, fail_before_effect: bool) -> None:
        self.repository = InMemoryIncidentRepository(initial_state=seed_state())
        self.sink = DemoNotificationSink(fail_before_effect=fail_before_effect)
        self.executor = ContainmentExecutor(self.repository, self.sink)
        self.intent = hold_intent()

    async def dispatch(self):
        return await self.executor.dispatch(
            case_id=CASE, intent=self.intent, actor_id="AGENT-001", now=NOW
        )

    async def resume(self):
        return await self.executor.resume(
            case_id=CASE, intent=self.intent, actor_id="AGENT-001", now=LATER
        )


def test_retry_reuses_payload_and_creates_one_receipt() -> None:
    async def scenario():
        harness = RetryHarness(fail_before_effect=True)
        first = await harness.dispatch()
        second = await harness.resume()
        return harness, first, second

    harness, first, second = asyncio.run(scenario())

    assert first.status == "failed"
    assert second.status == "succeeded"
    # The identical approved payload is reused by hash and idempotency token across attempts.
    assert first.payload_hash == second.payload_hash == "hold-payload-sha256"
    assert first.idempotency_token == second.idempotency_token == action_key(harness.intent)
    # Exactly one externally visible effect despite the injected failure and the retry.
    assert len(harness.sink.receipts) == 1
    assert harness.sink.receipts[0].status == "succeeded"


def test_reserved_action_is_persisted_before_the_effect_is_attempted() -> None:
    async def scenario():
        harness = RetryHarness(fail_before_effect=True)
        first = await harness.dispatch()
        # After a pre-effect failure, the in-flight reservation is durably persisted
        # even though no receipt exists yet.
        state = await harness.repository.load(CASE)
        return harness, first, state

    harness, first, state = asyncio.run(scenario())

    assert harness.sink.receipts == ()  # nothing left the sink
    assert len(state.containment_actions) == 1
    action = state.containment_actions[0]
    assert action.status == "in_flight"
    assert action.quantity == Decimal("200")  # authentic, from the intent
    assert action.idempotency_token == action_key(harness.intent)


def test_resume_reconciles_and_does_not_deliver_twice() -> None:
    async def scenario():
        harness = RetryHarness(fail_before_effect=False)
        first = await harness.dispatch()  # succeeds, one receipt recorded
        second = await harness.resume()  # must reconcile, not deliver again
        return harness, first, second

    harness, first, second = asyncio.run(scenario())

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert len(harness.sink.receipts) == 1  # resume adopted the prior effect
