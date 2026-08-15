"""Port definitions for incident persistence and state repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..domain.events import EventRecord
from ..domain.models import IncidentState


class ConcurrencyError(Exception):
    """Raised when an append fails compare-and-set preconditions."""

    def __init__(self, case_id: str, expected_version: int, actual_version: int):
        super().__init__(
            f"Case {case_id} concurrency conflict: "
            f"expected v{expected_version}, found v{actual_version}"
        )
        self.case_id = case_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class IncidentRepository(ABC):
    """Abstract store for event-sourced incident streams."""

    @abstractmethod
    async def load(self, case_id: str) -> IncidentState | None:
        """Reconstruct the current state of a case by replaying events, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    async def append(
        self,
        case_id: str,
        expected_version: int,
        events: Sequence[EventRecord],
    ) -> IncidentState:
        """Append events with optimistic concurrency check, returning new state."""
        raise NotImplementedError

    @abstractmethod
    async def get_events(
        self,
        case_id: str,
        after_sequence: int = 0,
    ) -> Sequence[EventRecord]:
        """Fetch all events after a given sequence number."""
        raise NotImplementedError
