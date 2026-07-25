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


from types import SimpleNamespace

from app.services.assistant import AssistantTurnResult, _extract_sources


def test_extract_sources_collects_citations_from_text_blocks() -> None:
    blocks = [
        SimpleNamespace(
            type="text",
            text="The Fed funds rate is 5.25%-5.50%.",
            citations=[
                SimpleNamespace(url="https://www.federalreserve.gov/x", title="Federal Reserve"),
            ],
        )
    ]

    assert _extract_sources(blocks) == [
        {"title": "Federal Reserve", "url": "https://www.federalreserve.gov/x"}
    ]


def test_extract_sources_dedupes_by_url_and_falls_back_to_url_as_title() -> None:
    blocks = [
        SimpleNamespace(
            type="text",
            text="First mention.",
            citations=[
                SimpleNamespace(url="https://www.reuters.com/x", title="Reuters"),
                SimpleNamespace(url="https://www.reuters.com/x", title="Reuters"),
            ],
        ),
        SimpleNamespace(
            type="text",
            text="Second mention.",
            citations=[SimpleNamespace(url="https://www.bls.gov/y", title=None)],
        ),
    ]

    assert _extract_sources(blocks) == [
        {"title": "Reuters", "url": "https://www.reuters.com/x"},
        {"title": "https://www.bls.gov/y", "url": "https://www.bls.gov/y"},
    ]


def test_extract_sources_ignores_blocks_without_citations() -> None:
    blocks = [
        SimpleNamespace(type="text", text="No citation here.", citations=None),
        SimpleNamespace(type="tool_use", name="get_money_overview"),
    ]

    assert _extract_sources(blocks) == []


def test_assistant_turn_result_sources_defaults_to_empty_list() -> None:
    result = AssistantTurnResult(reply="hi", tool_calls_made=0)

    assert result.sources == []
