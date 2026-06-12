from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from omoikane.db.models import Memory
from omoikane.search.engine import SearchEngine


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1] * 1536)]

    with patch("omoikane.search.engine.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.embedding_model = "text-embedding-3-small"

        with patch("omoikane.search.engine.AsyncOpenAI") as mock_oai:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_oai.return_value = mock_client

            engine = SearchEngine.__new__(SearchEngine)
            engine.session = AsyncMock(spec=AsyncSession)
            engine.client = mock_client

            result = await engine.embed_text("hello world")
            assert len(result) == 1536
            assert all(v == 0.1 for v in result)


@pytest.mark.asyncio
async def test_embed_text_raises_without_client():
    engine = SearchEngine.__new__(SearchEngine)
    engine.session = AsyncMock(spec=AsyncSession)
    engine.client = None

    with pytest.raises(RuntimeError, match="OpenAI API key not configured"):
        await engine.embed_text("test")


@pytest.mark.asyncio
async def test_store_embedding(session: AsyncSession):
    project_id = uuid.uuid4()
    memory = Memory(
        project_id=project_id,
        type="context",
        title="Test memory",
        content="Some content here.",
    )
    session.add(memory)
    await session.flush()

    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.05] * 1536)]

    with patch("omoikane.search.engine.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.embedding_model = "text-embedding-3-small"

        with patch("omoikane.search.engine.AsyncOpenAI") as mock_oai:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_oai.return_value = mock_client

            engine = SearchEngine(session)
            embedding = await engine.store_embedding(memory.id, "Test memory\n\nSome content here.")  # type: ignore[arg-type]

            assert embedding.chunk_text == "Test memory\n\nSome content here."
            assert embedding.model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_assemble_context_no_results(session: AsyncSession):
    engine = SearchEngine.__new__(SearchEngine)
    engine.session = session
    engine.client = None

    with patch.object(engine, "search", new_callable=AsyncMock, return_value=[]):
        result = await engine.assemble_context(
            task="test task",
            project_id=uuid.uuid4(),
            limit=5,
        )
        assert "No relevant memories found" in result


@pytest.mark.asyncio
async def test_search_cross_project_no_results(session: AsyncSession):
    engine = SearchEngine.__new__(SearchEngine)
    engine.session = session
    engine.client = None

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    with (
        patch.object(engine, "_get_linked_project_ids", new_callable=AsyncMock, return_value=[]),
        patch.object(engine, "embed_text", new_callable=AsyncMock, return_value=[0.0] * 1536),
        patch.object(session, "execute", new_callable=AsyncMock, return_value=mock_result),
    ):
        results = await engine.search_cross_project(
            query="test",
            project_id=uuid.uuid4(),
        )
        assert results == []
