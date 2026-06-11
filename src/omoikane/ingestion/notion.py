from __future__ import annotations

import uuid
from typing import Any

import httpx

from omoikane.config.settings import settings
from omoikane.db.models import Memory, Source, async_session
from omoikane.search.engine import SearchEngine


class NotionIngestor:
    def __init__(self):
        self.token = settings.notion_token
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    async def ingest_database(
        self,
        database_id: str,
        project_id: uuid.UUID,
        max_pages: int = 100,
    ) -> dict[str, int]:
        pages = await self._query_database(database_id, max_pages)

        async with async_session() as session:
            engine = SearchEngine(session)
            memories_created = 0

            for page in pages:
                data = self._extract_page(page, database_id)
                memory = Memory(project_id=project_id, **data)
                session.add(memory)
                await session.flush()
                await engine.store_embedding(
                    memory.id,
                    f"{data['title']}\n\n{data['content']}",
                )
                memories_created += 1

            source = Source(
                project_id=project_id,
                type="notion",
                external_id=database_id,
                url=f"https://notion.so/{database_id.replace('-', '')}",
            )
            session.add(source)
            await session.commit()

        return {
            "pages": len(pages),
            "memories": memories_created,
        }

    async def _query_database(
        self,
        database_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        start_cursor = ""

        async with httpx.AsyncClient() as client:
            for _ in range(5):
                body: dict[str, Any] = {"page_size": min(limit - len(pages), 100)}
                if start_cursor:
                    body["start_cursor"] = start_cursor

                response = await client.post(
                    f"{self.base_url}/databases/{database_id}/query",
                    headers=self.headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

                pages.extend(data.get("results", []))
                start_cursor = data.get("next_cursor", "")
                if not start_cursor or len(pages) >= limit:
                    break

        return pages[:limit]

    def _extract_page(self, page: dict, database_id: str) -> dict:
        properties = page.get("properties", {})
        title = self._extract_title(properties)
        content = self._extract_content(properties)
        page_id = page.get("id", "")

        return {
            "type": "context",
            "title": title[:200],
            "content": content,
            "source_type": "notion",
            "source_url": f"https://notion.so/{page_id.replace('-', '')}",
            "source_author": "",
        }

    def _extract_title(self, properties: dict) -> str:
        for prop in properties.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(part.get("plain_text", "") for part in title_parts)
        return "Untitled"

    def _extract_content(self, properties: dict) -> str:
        parts: list[str] = []
        for key, prop in properties.items():
            prop_type = prop.get("type", "")
            if prop_type == "rich_text":
                text_parts = prop.get("rich_text", [])
                text = "".join(p.get("plain_text", "") for p in text_parts)
                if text:
                    parts.append(f"**{key}**: {text}")
            elif prop_type == "select":
                select_val = prop.get("select")
                if select_val:
                    parts.append(f"**{key}**: {select_val.get('name', '')}")
            elif prop_type == "multi_select":
                values = prop.get("multi_select", [])
                names = [v.get("name", "") for v in values]
                if names:
                    parts.append(f"**{key}**: {', '.join(names)}")
        return "\n".join(parts)
