import inspect

import pytest

from app.sync.orchestrator import PortfolioSyncOrchestrator

pytestmark = pytest.mark.user_owned


def test_orchestrator_stub_has_been_replaced() -> None:
    """Keep the capstone red until its deliberate implementation begins."""
    source = inspect.getsource(PortfolioSyncOrchestrator.run)
    assert "raise NotImplementedError" not in source
