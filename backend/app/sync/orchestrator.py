"""Human-owned synchronization orchestration exercise.

Implementation contract: guides/04-SYNC-ORCHESTRATOR.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from uuid import UUID

from app.domain.models import SyncPortfolioCommand, SyncPortfolioResult


def _connection_lock_key(connection_id: UUID) -> str:
    """Return the one-lock-per-brokerage-connection key used by sync runs."""

    return f"portfolio-sync:{connection_id}"


class PortfolioSyncOrchestrator:
    """Coordinate brokerage, events, scoring, persistence, and durable alerts."""

    def __init__(self, **dependencies: object) -> None:
        self._dependencies = dependencies

    async def run(self, command: SyncPortfolioCommand) -> SyncPortfolioResult:
        """Synchronize one brokerage connection using the Guide 04 state machine."""
        raise NotImplementedError("Follow guides/04-SYNC-ORCHESTRATOR.md")
