from collections.abc import AsyncContextManager, Sequence
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.domain.models import PositionObservation, ProviderEventEnvelope


class Clock(Protocol):
    def now(self) -> datetime: ...


class BrokerageSnapshot(Protocol):
    @property
    def observations(self) -> tuple[PositionObservation, ...]: ...

    @property
    def complete(self) -> bool: ...


class BrokeragePort(Protocol):
    async def fetch_complete_snapshot(self, connection_id: UUID) -> BrokerageSnapshot: ...


class TrackedSecurity(Protocol):
    @property
    def security_id(self) -> UUID: ...

    @property
    def symbol(self) -> str: ...


class EventCursor(Protocol):
    @property
    def value(self) -> str: ...


class ProviderEventBatch(Protocol):
    @property
    def events(self) -> tuple[ProviderEventEnvelope, ...]: ...

    @property
    def next_cursor(self) -> str | None: ...


class EventProviderPort(Protocol):
    name: str
    required: bool

    async def fetch_events(
        self,
        securities: Sequence[TrackedSecurity],
        cursor: EventCursor | None,
    ) -> ProviderEventBatch: ...


class LockLease(Protocol):
    async def renew(self, ttl: timedelta) -> None: ...


class DistributedLock(Protocol):
    def acquire(self, key: str, ttl: timedelta) -> AsyncContextManager[LockLease]: ...


class UnitOfWork(Protocol):
    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, *args: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
