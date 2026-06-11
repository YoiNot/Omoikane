from __future__ import annotations

import uuid
from typing import Any

import httpx

from omoikane.config.settings import settings
from omoikane.db.models import Memory, Source, async_session
from omoikane.search.engine import SearchEngine


class GitHubIngestor:
    def __init__(self) -> None:
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            **({"Authorization": f"token {self.token}"} if self.token else {}),
        }

    def _get_paginated(self, path: str, max_pages: int = 5) -> list[Any]:
        items: list[Any] = []
        url = f"{self.base_url}{path}"
        for _ in range(max_pages):
            response = httpx.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                items.extend(data)
                if len(data) < 30:
                    break
                link_header = response.headers.get("Link", "")
                if 'rel="next"' not in link_header:
                    break
                url = link_header.split(";")[0].strip("<>")
            else:
                items.append(data)
                break
        return items

    async def ingest_repo(self, repo: str, project_id: uuid.UUID) -> dict[str, int]:
        commits = self._get_paginated(f"/repos/{repo}/commits")
        prs = self._get_paginated(f"/repos/{repo}/pulls?state=all")
        issues = self._get_paginated(f"/repos/{repo}/issues?state=all")

        async with async_session() as session:
            engine = SearchEngine(session)

            memories_created = 0
            for commit in commits:
                data = self._extract_commit(commit)
                memory = Memory(project_id=project_id, **data)
                session.add(memory)
                await session.flush()
                await engine.store_embedding(memory.id, f"{data['title']}\n\n{data['content']}")  # type: ignore[arg-type]
                memories_created += 1

            for pr in prs:
                data = self._extract_pr(pr)
                memory = Memory(project_id=project_id, **data)
                session.add(memory)
                await session.flush()
                await engine.store_embedding(memory.id, f"{data['title']}\n\n{data['content']}")  # type: ignore[arg-type]
                memories_created += 1

            for issue in issues:
                data = self._extract_issue(issue)
                memory = Memory(project_id=project_id, **data)
                session.add(memory)
                await session.flush()
                await engine.store_embedding(memory.id, f"{data['title']}\n\n{data['content']}")  # type: ignore[arg-type]
                memories_created += 1

            source = Source(
                project_id=project_id,
                type="github",
                external_id=repo,
                url=f"https://github.com/{repo}",
            )
            session.add(source)
            await session.commit()

        return {
            "commits": len(commits),
            "prs": len(prs),
            "issues": len(issues),
            "memories": memories_created,
        }

    def _extract_commit(self, commit: dict[str, Any]) -> dict[str, str]:
        return {
            "type": "context",
            "title": commit.get("commit", {}).get("message", "").split("\n")[0][:200],
            "content": commit.get("commit", {}).get("message", ""),
            "source_type": "github",
            "source_url": commit.get("html_url", ""),
            "source_author": commit.get("commit", {}).get("author", {}).get("name", ""),
        }

    def _extract_pr(self, pr: dict[str, Any]) -> dict[str, str]:
        body = pr.get("body") or ""
        return {
            "type": "discussion" if "decision" in body.lower() else "context",
            "title": pr.get("title", ""),
            "content": body,
            "source_type": "github",
            "source_url": pr.get("html_url", ""),
            "source_author": pr.get("user", {}).get("login", ""),
        }

    def _extract_issue(self, issue: dict[str, Any]) -> dict[str, str]:
        body = issue.get("body") or ""
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        memory_type = "decision" if "adr" in labels or "decision" in labels else "context"
        return {
            "type": memory_type,
            "title": issue.get("title", ""),
            "content": body,
            "source_type": "github",
            "source_url": issue.get("html_url", ""),
            "source_author": issue.get("user", {}).get("login", ""),
        }
