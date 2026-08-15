"""Port definitions for external action adapters and idempotency."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..domain.identifiers import ActionIntent
from ..domain.models import Identifier


class ActionReceipt(BaseModel):
    """Immutable proof returned by an external action adapter.

    The adapter knows nothing about domain action IDs; it is keyed purely by the
    stable idempotency token so the same approved payload can never deliver twice.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    idempotency_token: Identifier
    status: Literal["succeeded", "failed", "unknown"]
    provider_reference: Identifier
    payload_hash: Identifier
    error_code: str | None = None
    error_message: str | None = None


class ActionAdapter(ABC):
    """Interface for safe, idempotent external connectors."""

    @abstractmethod
    async def execute(self, intent: ActionIntent, *, idempotency_token: str) -> ActionReceipt:
        """Execute the external effect idempotently."""
        raise NotImplementedError

    @abstractmethod
    async def reconcile(self, idempotency_token: str) -> ActionReceipt | None:
        """Query the remote provider for prior outcome by idempotency token."""
        raise NotImplementedError
