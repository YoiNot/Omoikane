from __future__ import annotations

import uuid
from typing import Any

import httpx

from omoikane.config.settings import settings
from omoikane.db.models import Memory, Source, async_session
from omoikane.search.engine import SearchEngine


class SlackIngestor:
    def __init__(self) -> None:
        self.token = settings.slack_token
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def ingest_channel(
        self,
        channel_id: str,
        project_id: uuid.UUID,
        max_messages: int = 100,
    ) -> dict[str, int]:
        messages = await self._get_messages(channel_id, max_messages)
        decisions = self._filter_decision_messages(messages)

        async with async_session() as session:
            engine = SearchEngine(session)
            memories_created = 0

            for msg in decisions:
                data = self._extract_memory(msg, channel_id)
                memory = Memory(project_id=project_id, **data)
                session.add(memory)
                await session.flush()
                await engine.store_embedding(
                    memory.id,  # type: ignore[arg-type]
                    f"{data['title']}\n\n{data['content']}",
                )
                memories_created += 1

            source = Source(
                project_id=project_id,
                type="slack",
                external_id=channel_id,
                url=f"https://slack.com/channel/{channel_id}",
            )
            session.add(source)
            await session.commit()

        return {
            "messages": len(messages),
            "decisions": len(decisions),
            "memories": memories_created,
        }

    async def _get_messages(
        self,
        channel_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor = ""

        async with httpx.AsyncClient() as client:
            for _ in range(5):
                params: dict[str, Any] = {
                    "channel": channel_id,
                    "limit": min(limit - len(messages), 100),
                }
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    f"{self.base_url}/conversations.history",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("ok"):
                    break

                messages.extend(data.get("messages", []))
                cursor = data.get("response_metadata", {}).get("next_cursor", "")
                if not cursor or len(messages) >= limit:
                    break

        return messages[:limit]

    def _filter_decision_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decision_keywords = [
            "decided", "decision", "we'll go with", "chosen",
            "resolved", "conclusion", "agreed", "final answer",
            "adr", "architecture", "design decision",
        ]
        return [
            msg for msg in messages
            if any(
                keyword in (msg.get("text") or "").lower()
                for keyword in decision_keywords
            )
        ]

    def _extract_memory(self, msg: dict[str, Any], channel_id: str) -> dict[str, str]:
        text = msg.get("text", "")
        user = msg.get("user", "unknown")
        ts = msg.get("ts", "")

        return {
            "type": "discussion",
            "title": text[:200].split("\n")[0],
            "content": text,
            "source_type": "slack",
            "source_url": f"https://slack.com/channel/{channel_id}/p{ts}",
            "source_author": user,
        }
