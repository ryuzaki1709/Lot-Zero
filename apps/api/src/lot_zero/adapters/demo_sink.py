"""Deterministic demo sink for safe notification delivery and failure injection."""

from __future__ import annotations

import asyncio

from ..domain.identifiers import ActionIntent
from ..ports.actions import ActionAdapter, ActionReceipt


class DemoNotificationSink(ActionAdapter):
    """Synthetic notification sink: records receipts and supports bounded-retry demos."""

    def __init__(self, *, fail_before_effect: bool = False):
        self._lock = asyncio.Lock()
        self.fail_before_effect = fail_before_effect
        self._failed_once = False
        self._receipts: dict[str, ActionReceipt] = {}

    @property
    def receipts(self) -> tuple[ActionReceipt, ...]:
        return tuple(self._receipts.values())

    async def execute(self, intent: ActionIntent, *, idempotency_token: str) -> ActionReceipt:
        async with self._lock:
            # Idempotency: a completed delivery is never repeated. A prior success is
            # returned verbatim so a retry produces no second externally visible effect.
            if idempotency_token in self._receipts:
                return self._receipts[idempotency_token]

            # Injected retryable failure BEFORE any external effect. Critically, this
            # records no receipt: nothing left the sink, so a later retry may still
            # deliver exactly once. It is a transient outcome, not a terminal one.
            if self.fail_before_effect and not self._failed_once:
                self._failed_once = True
                return ActionReceipt(
                    idempotency_token=idempotency_token,
                    status="failed",
                    provider_reference=f"SINK-FAIL-{idempotency_token[:8]}",
                    payload_hash=intent.payload_hash,
                    error_code="TRANSIENT_SINK_TIMEOUT",
                    error_message="Injected transient network timeout before downstream delivery",
                )

            # Successful delivery: persist exactly one receipt keyed by idempotency token.
            receipt = ActionReceipt(
                idempotency_token=idempotency_token,
                status="succeeded",
                provider_reference=f"SINK-OK-{idempotency_token[:8]}",
                payload_hash=intent.payload_hash,
            )
            self._receipts[idempotency_token] = receipt
            return receipt

    async def reconcile(self, idempotency_token: str) -> ActionReceipt | None:
        async with self._lock:
            return self._receipts.get(idempotency_token)
