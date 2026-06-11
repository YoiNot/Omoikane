from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from omoikane.config.settings import settings


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    settings = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memories = relationship("Memory", back_populates="project", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="project", cascade="all, delete-orphan")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, default="")
    source_type = Column(String, default="")
    source_url = Column(String, default="")
    source_author = Column(String, default="")
    source_created_at = Column(DateTime, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="memories")
    embeddings = relationship("Embedding", back_populates="memory", cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_id = Column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(String, default="0")
    chunk_text = Column(Text, nullable=False)
    token_count = Column(String, default="0")
    model = Column(String, default="")
    embedding = Column(Vector(settings.embedding_dimensions))
    created_at = Column(DateTime, default=datetime.utcnow)

    memory = relationship("Memory", back_populates="embeddings")


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = Column(String, nullable=False)
    external_id = Column(String, default="")
    url = Column(String, default="")
    config = Column(JSONB, default=dict)
    status = Column(String, default="active")
    last_synced = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="sources")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_id = Column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String, nullable=False)
    context = Column(Text, default="")
    decision = Column(Text, nullable=False)
    consequences = Column(Text, default="")
    alternatives = Column(JSONB, default=list)
    status = Column(String, default="accepted")
    participants = Column(JSONB, default=list)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memory = relationship("Memory")
    project = relationship("Project")


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
