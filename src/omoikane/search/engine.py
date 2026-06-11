from __future__ import annotations

import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omoikane.api.schemas import MemoryResponse, SearchResult
from omoikane.config.settings import settings
from omoikane.db.models import Embedding, Memory


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
        await self.embed_text(text)
        embedding = Embedding(
            memory_id=memory_id,
            chunk_index="0",
            chunk_text=text,
            token_count=str(len(text.split())),
            model=settings.embedding_model,
            vector_id="",
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

        stmt = (
            select(Memory, Embedding)
            .join(Embedding, Memory.id == Embedding.memory_id)
        )
        if project_id:
            stmt = stmt.where(Memory.project_id == project_id)
        if memory_type:
            stmt = stmt.where(Memory.type == memory_type)

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        scored: list[SearchResult] = []
        for memory, embedding in rows:
            zeros = [0.0] * settings.embedding_dimensions
            score = self._cosine_similarity(query_embedding, zeros)
            scored.append(
                SearchResult(
                    memory=MemoryResponse.model_validate(memory),
                    score=score,
                    chunk_text=embedding.chunk_text,
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        import math

        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
