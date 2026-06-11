from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omoikane.api.schemas import MemoryResponse, SearchResult
from omoikane.config.settings import settings
from omoikane.db.models import Embedding, Memory, ProjectLink


class SearchEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self.client = None

    async def embed_text(self, text: str) -> list[float]:
        if not self.client:
            raise RuntimeError("OpenAI API key not configured")
        response = await self.client.embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def store_embedding(self, memory_id: uuid.UUID, text: str) -> Embedding:
        vector = await self.embed_text(text)
        embedding = Embedding(
            memory_id=memory_id,
            chunk_index="0",
            chunk_text=text,
            token_count=str(len(text.split())),
            model=settings.embedding_model,
            embedding=vector,
        )
        self.session.add(embedding)
        await self.session.flush()
        return embedding

    async def search(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        query_embedding = await self.embed_text(query)

        distance = Embedding.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Memory, Embedding, distance.label("distance"))
            .join(Embedding, Memory.id == Embedding.memory_id)
            .where(Embedding.embedding.isnot(None))
        )
        if project_id:
            stmt = stmt.where(Memory.project_id == project_id)
        if memory_type:
            stmt = stmt.where(Memory.type == memory_type)

        stmt = stmt.order_by(distance).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.fetchall()

        return [
            SearchResult(
                memory=MemoryResponse.model_validate(memory),
                score=1.0 - row.distance,
                chunk_text=embedding.chunk_text,
            )
            for memory, embedding, row_distance in rows
            for row in [type("Row", (), {"distance": row_distance})()]
        ]

    async def assemble_context(
        self,
        task: str,
        project_id: uuid.UUID,
        limit: int = 5,
    ) -> str:
        results = await self.search(query=task, project_id=project_id, limit=limit)

        if not results:
            return f"# Context for: {task}\n\nNo relevant memories found.\n"

        lines = [f"# Context for: {task}\n"]
        lines.append(f"Found {len(results)} relevant memories:\n")

        for i, r in enumerate(results, 1):
            memory = r.memory
            lines.append(f"## {i}. [{memory.type.upper()}] {memory.title}")
            lines.append(f"Relevance: {r.score:.2f} | Source: {memory.source_type}")
            if memory.source_url:
                lines.append(f"URL: {memory.source_url}")
            lines.append(f"\n{memory.content}\n")
            lines.append("---\n")

        return "\n".join(lines)

    async def get_recent_memories(
        self,
        project_id: uuid.UUID,
        days: int = 7,
        limit: int = 10,
    ) -> list[MemoryResponse]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Memory)
            .where(Memory.project_id == project_id)
            .where(Memory.created_at >= cutoff)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [MemoryResponse.model_validate(m) for m in result.scalars().all()]

    async def _get_linked_project_ids(self, project_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(ProjectLink).where(
            (ProjectLink.source_project_id == project_id)
            | (ProjectLink.target_project_id == project_id)
        )
        result = await self.session.execute(stmt)
        links = result.scalars().all()

        linked_ids: list[uuid.UUID] = []
        for link in links:
            if link.source_project_id == project_id:
                linked_ids.append(link.target_project_id)
            else:
                linked_ids.append(link.source_project_id)
        return linked_ids

    async def search_cross_project(
        self,
        query: str,
        project_id: uuid.UUID,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        linked_ids = await self._get_linked_project_ids(project_id)
        all_project_ids = [project_id] + linked_ids

        query_embedding = await self.embed_text(query)
        distance = Embedding.embedding.cosine_distance(query_embedding)

        stmt = (
            select(Memory, Embedding, distance.label("distance"))
            .join(Embedding, Memory.id == Embedding.memory_id)
            .where(Embedding.embedding.isnot(None))
            .where(Memory.project_id.in_(all_project_ids))
        )
        if memory_type:
            stmt = stmt.where(Memory.type == memory_type)

        stmt = stmt.order_by(distance).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.fetchall()

        return [
            SearchResult(
                memory=MemoryResponse.model_validate(memory),
                score=1.0 - row.distance,
                chunk_text=embedding.chunk_text,
            )
            for memory, embedding, row_distance in rows
            for row in [type("Row", (), {"distance": row_distance})()]
        ]

    async def assemble_cross_project_context(
        self,
        task: str,
        project_id: uuid.UUID,
        limit: int = 5,
    ) -> str:
        results = await self.search_cross_project(
            query=task,
            project_id=project_id,
            limit=limit,
        )

        if not results:
            return f"# Context for: {task}\n\nNo relevant memories found.\n"

        lines = [f"# Context for: {task}\n"]
        lines.append(f"Found {len(results)} relevant memories across projects:\n")

        for i, r in enumerate(results, 1):
            memory = r.memory
            lines.append(f"## {i}. [{memory.type.upper()}] {memory.title}")
            lines.append(f"Relevance: {r.score:.2f} | Source: {memory.source_type}")
            lines.append(f"Project: {memory.project_id}")
            if memory.source_url:
                lines.append(f"URL: {memory.source_url}")
            lines.append(f"\n{memory.content}\n")
            lines.append("---\n")

        return "\n".join(lines)
