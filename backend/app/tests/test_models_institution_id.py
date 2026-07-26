from uuid import uuid4

import pytest

from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageConnection, FinancialConnection
from app.db.session import create_engine, create_session_factory


@pytest.mark.anyio
async def test_connections_persist_institution_id():
    engine = create_engine(Settings(database_url="sqlite+aiosqlite:///:memory:"))
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as s:
        s.add(FinancialConnection(user_id=uuid4(), provider="plaid",
              provider_item_id="item-1", display_name="Bank", status="connected",
              institution_id="ins_1"))
        s.add(BrokerageConnection(user_id=uuid4(), provider="plaid_investments",
              display_name="Broker", status="connected", institution_id="ins_2"))
        await s.commit()
    await engine.dispose()
