"""In-memory event repository with compare-and-set semantics for local execution."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from ..domain.models import IncidentState
from ..domain.reducer import rehydrate
from ..ports.repositories import ConcurrencyError, IncidentRepository


class InMemoryIncidentRepository(IncidentRepository):
    """Stores incidents as event streams in memory with optimistic locking."""

    def __init__(self, initial_state: IncidentState | None = None):
        self._lock = asyncio.Lock()
        self._initial_state = initial_state
        self._states: dict[str, IncidentState] = {}
        self._events: dict[str, list[object]] = {}
        if initial_state is not None:
            self._states[initial_state.case.case_id] = initial_state
            self._events[initial_state.case.case_id] = []

    async def seed(self, state: IncidentState) -> None:
        """Seed the repository with an initial incident state."""
        async with self._lock:
            self._states[state.case.case_id] = state
            self._events[state.case.case_id] = []

    async def load(self, case_id: str) -> IncidentState | None:
        """Retrieve the current state for the given case ID."""
        async with self._lock:
            return self._states.get(case_id)

    async def append(
        self,
        case_id: str,
        expected_version: int,
        events: Sequence[object],
    ) -> IncidentState:
        """Append events with compare-and-set version verification."""
        async with self._lock:
            current_state = self._states.get(case_id)
            if current_state is None:
                raise KeyError(f"Case {case_id} does not exist")

            if current_state.case.case_version != expected_version:
                raise ConcurrencyError(
                    case_id=case_id,
                    expected_version=expected_version,
                    actual_version=current_state.case.case_version,
                )

            # Apply events in sequence
            updated_state = rehydrate(current_state, events)
            self._states[case_id] = updated_state
            self._events.setdefault(case_id, []).extend(events)
            return updated_state

    async def get_events(
        self,
        case_id: str,
        after_sequence: int = 0,
    ) -> Sequence[object]:
        """Fetch all recorded events for a case after a given sequence index."""
        async with self._lock:
            events = self._events.get(case_id, [])
            return tuple(events[after_sequence:])
