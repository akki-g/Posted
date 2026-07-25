"""Provider-neutral portfolio synchronization orchestration."""

import asyncio
from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from app.domain.enums import SyncRunStatus
from app.domain.models import (
    DedupePolicy,
    EventAssessmentInput,
    ImpactPolicy,
    ProviderWarning,
    RejectedEvent,
    SyncPortfolioCommand,
    SyncPortfolioResult,
)
from app.events.dedupe import deduplicate_events
from app.events.normalize import EventSecurityResolver, normalize_event
from app.impact.scoring import assess_impact
from app.portfolio.reconcile import SecurityResolver, reconcile_positions
from app.sync.ports import (
    BrokeragePort,
    Clock,
    DistributedLock,
    EventProviderPort,
    UnitOfWorkFactory,
)


def _connection_lock_key(connection_id: UUID) -> str:
    """Return the one-lock-per-brokerage-connection key used by sync runs."""

    return f"portfolio-sync:{connection_id}"


class PortfolioSyncOrchestrator:
    """Coordinate brokerage, event, scoring, and alert stages through injected ports.

    The SQLAlchemy Schwab MVP uses ``services/schwab_sync.py`` directly. This
    orchestrator remains provider-neutral and is the boundary for adding durable
    event-provider repositories and a distributed worker without coupling the
    domain logic to Schwab, FastAPI, or SQLAlchemy.
    """

    def __init__(
        self,
        *,
        clock: Clock,
        lock: DistributedLock,
        brokerage: BrokeragePort,
        event_providers: Sequence[EventProviderPort],
        uow_factory: UnitOfWorkFactory,
        resolve_position_security: SecurityResolver,
        resolve_event_securities: EventSecurityResolver,
        event_id_factory: Callable[[], UUID],
        dedupe_policy: DedupePolicy,
        impact_policy: ImpactPolicy,
        lock_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if lock_ttl <= timedelta(0):
            raise ValueError("lock_ttl must be positive")
        self._clock = clock
        self._lock = lock
        self._brokerage = brokerage
        self._event_providers = tuple(event_providers)
        self._uow_factory = uow_factory
        self._resolve_position_security = resolve_position_security
        self._resolve_event_securities = resolve_event_securities
        self._event_id_factory = event_id_factory
        self._dedupe_policy = dedupe_policy
        self._impact_policy = impact_policy
        self._lock_ttl = lock_ttl

    async def run(self, command: SyncPortfolioCommand) -> SyncPortfolioResult:
        """Synchronize one brokerage connection using explicit durable stages."""

        if len(command.idempotency_key.strip()) < 8:
            raise ValueError("idempotency_key must contain at least eight characters")

        async with self._uow_factory() as uow:
            await uow.connections.require_owner(command.user_id, command.connection_id)
            prior = await uow.sync_runs.find_completed(
                command.user_id,
                command.idempotency_key,
            )
            if prior is not None:
                return prior

        async with self._lock.acquire(
            _connection_lock_key(command.connection_id),
            self._lock_ttl,
        ):
            async with self._uow_factory() as uow:
                prior = await uow.sync_runs.find_completed(
                    command.user_id,
                    command.idempotency_key,
                )
                if prior is not None:
                    return prior
                sync_run_id = await uow.sync_runs.create(command, self._clock.now())
                await uow.sync_runs.set_status(
                    sync_run_id,
                    SyncRunStatus.LOCKED,
                    self._clock.now(),
                )
                await uow.commit()

            try:
                return await self._run_locked(command, sync_run_id)
            except asyncio.CancelledError:
                await self._record_failure(sync_run_id, "cancelled")
                raise
            except Exception:
                await self._record_failure(sync_run_id, "synchronization failed")
                raise

    async def _run_locked(
        self,
        command: SyncPortfolioCommand,
        sync_run_id: UUID,
    ) -> SyncPortfolioResult:
        # External brokerage I/O happens before a UnitOfWork is opened.
        snapshot = await self._brokerage.fetch_complete_snapshot(command.connection_id)
        if not snapshot.complete:
            raise ValueError("brokerage snapshot is incomplete")

        async with self._uow_factory() as uow:
            await uow.sync_runs.set_status(
                sync_run_id,
                SyncRunStatus.BROKERAGE_FETCHED,
                self._clock.now(),
            )
            previous = await uow.portfolios.list_previous(command.connection_id)
            reconciliation = reconcile_positions(
                observations=snapshot.observations,
                previous=previous,
                resolve_security=self._resolve_position_security,
            )
            await uow.portfolios.replace_current(
                command.connection_id,
                reconciliation.positions,
            )
            await uow.portfolios.add_deltas(sync_run_id, reconciliation.deltas)
            await uow.portfolios.add_rejections(sync_run_id, reconciliation.rejected)
            tracked = await uow.portfolios.list_tracked(command.connection_id)
            await uow.sync_runs.set_status(
                sync_run_id,
                SyncRunStatus.PORTFOLIO_PERSISTED,
                self._clock.now(),
            )
            await uow.commit()

        batches: list[tuple[EventProviderPort, Any]] = []
        warnings: list[ProviderWarning] = []
        events_fetched = 0
        for provider in self._event_providers:
            async with self._uow_factory() as uow:
                cursor = await uow.events.get_cursor(provider.name)
            try:
                # Provider I/O is outside the short cursor-read UnitOfWork.
                batch = await provider.fetch_events(tracked, cursor)
            except Exception as exc:
                if provider.required:
                    raise
                warnings.append(
                    ProviderWarning(
                        provider=provider.name,
                        code="provider_fetch_failed",
                        message=str(exc) or f"{provider.name} fetch failed",
                        retryable=True,
                    )
                )
                continue
            batches.append((provider, batch))
            events_fetched += len(batch.events)

        normalized = []
        rejected: list[RejectedEvent] = []
        for _provider, batch in batches:
            for envelope in batch.events:
                result = normalize_event(
                    envelope,
                    resolve_securities=self._resolve_event_securities,
                    event_id=self._event_id_factory(),
                )
                if isinstance(result, RejectedEvent):
                    rejected.append(result)
                else:
                    normalized.append(result)

        async with self._uow_factory() as uow:
            recent = await uow.events.list_recent(
                tracked,
                self._dedupe_policy.fuzzy_window,
            )
        dedupe = deduplicate_events(
            (*normalized, *recent),
            policy=self._dedupe_policy,
        )

        async with self._uow_factory() as uow:
            persistence = await uow.events.persist(dedupe, tuple(rejected))
            for provider, batch in batches:
                await uow.events.advance_cursor(provider.name, batch.next_cursor)
            await uow.sync_runs.set_status(
                sync_run_id,
                SyncRunStatus.EVENTS_PERSISTED,
                self._clock.now(),
            )
            await uow.commit()

        changed_events = tuple(
            getattr(persistence, "new_or_changed_events", dedupe.events)
        )
        assessments_created = 0
        alerts_created = 0
        async with self._uow_factory() as uow:
            for event in changed_events:
                exposures = await uow.assessments.load_exposures(
                    command.connection_id,
                    event,
                )
                previous_related = None
                if hasattr(uow.assessments, "previous_related_event_at"):
                    previous_related = await uow.assessments.previous_related_event_at(
                        command.connection_id,
                        event,
                    )
                source_confidence = max(
                    (source.confidence for source in event.sources),
                    default=1.0,
                )
                impact = assess_impact(
                    EventAssessmentInput(
                        event=event,
                        exposures=tuple(exposures),
                        source_confidence=source_confidence,
                        entity_match_confidence=1.0 if event.security_ids else 0.0,
                        assessed_at=self._clock.now(),
                        previous_related_event_at=previous_related,
                    ),
                    policy=self._impact_policy,
                )
                await uow.assessments.add(impact)
                assessments_created += 1
                if impact.eligible_for_immediate_alert:
                    created = await uow.alerts.create_if_absent(
                        command.user_id,
                        event,
                        impact,
                    )
                    alerts_created += int(bool(created))
            await uow.sync_runs.set_status(
                sync_run_id,
                SyncRunStatus.ASSESSMENTS_PERSISTED,
                self._clock.now(),
            )
            await uow.commit()

        final_status = (
            SyncRunStatus.COMPLETED_WITH_WARNINGS
            if warnings
            else SyncRunStatus.COMPLETED
        )
        result = SyncPortfolioResult(
            sync_run_id=sync_run_id,
            status=final_status,
            positions_seen=len(snapshot.observations),
            positions_changed=sum(
                delta.kind.value != "unchanged" for delta in reconciliation.deltas
            ),
            events_fetched=events_fetched,
            events_created=int(getattr(persistence, "created_count", len(normalized))),
            events_merged=int(
                getattr(persistence, "merged_count", len(dedupe.clusters))
            ),
            assessments_created=assessments_created,
            alerts_created=alerts_created,
            provider_warnings=tuple(warnings),
        )
        async with self._uow_factory() as uow:
            await uow.sync_runs.complete(result, self._clock.now())
            await uow.commit()
        return result

    async def _record_failure(self, sync_run_id: UUID, message: str) -> None:
        """Persist a safe failure without leaking provider payloads or tokens."""

        async with self._uow_factory() as uow:
            await uow.sync_runs.fail(
                sync_run_id,
                SyncRunStatus.FAILED,
                message,
                self._clock.now(),
            )
            await uow.commit()
