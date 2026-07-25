from uuid import uuid4

from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.models import AssistantMessage, User
from app.db.session import create_engine, create_session_factory


async def test_assistant_message_persists_and_serializes_sources() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    user_id = uuid4()
    sources = [{"title": "Federal Reserve", "url": "https://www.federalreserve.gov/x"}]

    async with session_factory() as session:
        session.add(User(id=user_id, email="assistant-test@example.com", display_name="Test User"))
        session.add(
            AssistantMessage(
                user_id=user_id,
                role="assistant",
                content="The Fed funds rate is 5.25%-5.50%.",
                section="general",
                sources=sources,
            )
        )
        await session.commit()

    async with session_factory() as session:
        row = (
            await session.scalars(
                select(AssistantMessage).where(AssistantMessage.user_id == user_id)
            )
        ).one()
        assert row.sources == sources

    await engine.dispose()
