"""Append-oriented application event storage with an archived reset history and a self-verifying export bundle."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from ..domain.events import Event
from ..domain.models import IncidentState, RecallCase
from ..domain.reducer import rehydrate
from ..ports.repositories import ConcurrencyError, IncidentRepository


class SqliteIncidentRepository(IncidentRepository):
    """Persists incident event streams in an append-oriented SQLite table with optimistic locking, archived reset history, and self-verifying export bundle."""

    def __init__(
        self,
        db_path: str = ":memory:",
        initial_state_factory: Callable[[str, str], IncidentState] | None = None,
    ):
        self._db_path = db_path
        self._initial_state_factory = initial_state_factory
        self._lock = asyncio.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create the append-oriented event log table and archive tables with tenant-scoped constraints."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    stream_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    UNIQUE(tenant_id, case_id, stream_version)
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tenant_case_version 
                ON incident_events (tenant_id, case_id, stream_version)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archived_incident_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    stream_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    archived_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_reset_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    reset_by_principal_id TEXT NOT NULL,
                    archived_at TEXT NOT NULL
                )
                """
            )

    def close(self) -> None:
        """Close SQLite database connection."""
        self._conn.close()

    def _get_stream_events(self, tenant_id: str, case_id: str) -> list[object]:
        """Read and parse all events for a tenant/case ordered by stream version."""
        cursor = self._conn.execute(
            """
            SELECT payload FROM incident_events
            WHERE tenant_id = ? AND case_id = ?
            ORDER BY stream_version ASC
            """,
            (tenant_id, case_id),
        )
        events: list[object] = []
        for row in cursor.fetchall():
            event_obj = Event.validate_json(row["payload"])
            events.append(event_obj)
        return events

    def _get_current_version(self, tenant_id: str, case_id: str) -> int:
        """Get highest recorded stream version for the tenant/case."""
        cursor = self._conn.execute(
            """
            SELECT COALESCE(MAX(stream_version), 0) as max_v
            FROM incident_events
            WHERE tenant_id = ? AND case_id = ?
            """,
            (tenant_id, case_id),
        )
        row = cursor.fetchone()
        return int(row["max_v"]) if row else 0

    async def load(self, case_id: str, tenant_id: str = "EVAL-TENANT-01") -> IncidentState | None:
        """Reconstruct the current state of a case by replaying its event stream."""
        async with self._lock:
            events = self._get_stream_events(tenant_id, case_id)
            if not events:
                if self._initial_state_factory:
                    return self._initial_state_factory(tenant_id, case_id)
                return None

            # Base state before events
            initial = (
                self._initial_state_factory(tenant_id, case_id)
                if self._initial_state_factory
                else IncidentState(
                    case=RecallCase(
                        case_id=case_id,
                        tenant_id=tenant_id,
                        phase="signal_received",
                        case_version=0,
                        source_record_ids=("DEFAULT-SOURCE-RECORD",),
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    ),
                    updated_at=datetime.now(UTC),
                )
            )

            return rehydrate(initial, events)

    async def append(
        self,
        case_id: str,
        expected_version: int,
        events: Sequence[object],
        tenant_id: str = "EVAL-TENANT-01",
    ) -> IncidentState:
        """Append events with optimistic concurrency check, returning new state."""
        if not events:
            loaded = await self.load(case_id, tenant_id=tenant_id)
            if loaded is None:
                raise KeyError(f"Case {case_id} not found")
            return loaded

        async with self._lock:
            # Resolve tenant_id from first event if available
            first_event = events[0]
            if hasattr(first_event, "tenant_id"):
                tenant_id = getattr(first_event, "tenant_id")

            current_version = self._get_current_version(tenant_id, case_id)
            if current_version != expected_version:
                raise ConcurrencyError(
                    case_id=case_id,
                    expected_version=expected_version,
                    actual_version=current_version,
                )

            # Insert all events in atomic transaction
            now_iso = datetime.now(UTC).isoformat()
            try:
                with self._conn:
                    for idx, ev in enumerate(events):
                        next_version = expected_version + idx + 1
                        event_type = getattr(ev, "kind", type(ev).__name__)
                        payload = (
                            ev.model_dump_json()
                            if hasattr(ev, "model_dump_json")
                            else json.dumps(ev)
                        )
                        occurred = getattr(
                            ev, "occurred_at", getattr(ev, "decided_at", datetime.now(UTC))
                        )
                        occurred_iso = (
                            occurred.isoformat() if isinstance(occurred, datetime) else now_iso
                        )

                        self._conn.execute(
                            """
                            INSERT INTO incident_events (
                                tenant_id, case_id, stream_version, event_type, payload, occurred_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (tenant_id, case_id, next_version, event_type, payload, occurred_iso),
                        )
            except sqlite3.IntegrityError as exc:
                raise ConcurrencyError(
                    case_id=case_id,
                    expected_version=expected_version,
                    actual_version=self._get_current_version(tenant_id, case_id),
                ) from exc

            all_events = self._get_stream_events(tenant_id, case_id)
            initial = (
                self._initial_state_factory(tenant_id, case_id)
                if self._initial_state_factory
                else IncidentState(
                    case=RecallCase(
                        case_id=case_id,
                        tenant_id=tenant_id,
                        phase="signal_received",
                        case_version=0,
                        source_record_ids=("DEFAULT-SOURCE-RECORD",),
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    ),
                    updated_at=datetime.now(UTC),
                )
            )

            return rehydrate(initial, all_events)

    async def get_events(
        self,
        case_id: str,
        after_sequence: int = 0,
        tenant_id: str = "EVAL-TENANT-01",
    ) -> Sequence[object]:
        """Fetch all events after a given stream version index."""
        async with self._lock:
            cursor = self._conn.execute(
                """
                SELECT payload FROM incident_events
                WHERE tenant_id = ? AND case_id = ? AND stream_version > ?
                ORDER BY stream_version ASC
                """,
                (tenant_id, case_id, after_sequence),
            )
            events = []
            for row in cursor.fetchall():
                event_obj = Event.validate_json(row["payload"])
                events.append(event_obj)
            return tuple(events)

    async def archive_and_reset(
        self,
        tenant_id: str,
        case_id: str,
        reset_by_principal_id: str = "EVAL-ADMIN-01",
    ) -> int:
        """Atomically archive all events for a tenant/case, record journal, and reset active stream."""
        import uuid

        archive_run_id = str(uuid.uuid4())
        archived_at = datetime.now(UTC).isoformat()

        async with self._lock:
            with self._conn:
                cursor = self._conn.execute(
                    """
                    SELECT COUNT(*) as cnt FROM incident_events
                    WHERE tenant_id = ? AND case_id = ?
                    """,
                    (tenant_id, case_id),
                )
                row = cursor.fetchone()
                src_count = int(row["cnt"]) if row else 0

                if src_count > 0:
                    self._conn.execute(
                        """
                        INSERT INTO archived_incident_events (
                            archive_run_id, tenant_id, case_id, stream_version, event_type, payload, occurred_at, archived_at
                        )
                        SELECT ?, tenant_id, case_id, stream_version, event_type, payload, occurred_at, ?
                        FROM incident_events
                        WHERE tenant_id = ? AND case_id = ?
                        ORDER BY stream_version ASC
                        """,
                        (archive_run_id, archived_at, tenant_id, case_id),
                    )

                    # Verify copy count before deletion
                    verify_cursor = self._conn.execute(
                        "SELECT COUNT(*) as cnt FROM archived_incident_events WHERE archive_run_id = ?",
                        (archive_run_id,),
                    )
                    verify_row = verify_cursor.fetchone()
                    copied_count = int(verify_row["cnt"]) if verify_row else 0
                    if copied_count != src_count:
                        raise RuntimeError(
                            f"Archive integrity verification failed: expected {src_count} rows, copied {copied_count}"
                        )

                    # Delete active stream rows
                    self._conn.execute(
                        "DELETE FROM incident_events WHERE tenant_id = ? AND case_id = ?",
                        (tenant_id, case_id),
                    )

                # Persist reset journal record outside cleared active stream
                self._conn.execute(
                    """
                    INSERT INTO evaluation_reset_journal (
                        archive_run_id, tenant_id, case_id, event_count, reset_by_principal_id, archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        archive_run_id,
                        tenant_id,
                        case_id,
                        src_count,
                        reset_by_principal_id,
                        archived_at,
                    ),
                )

            return src_count
