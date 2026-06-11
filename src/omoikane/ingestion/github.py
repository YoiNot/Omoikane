from __future__ import annotations

from typing import Any

import httpx

from omoikane.config.settings import settings


class GitHubIngestor:
    def __init__(self):
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            **({"Authorization": f"token {self.token}"} if self.token else {}),
        }

    def _get(self, path: str) -> Any:
        response = httpx.get(f"{self.base_url}{path}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _get_paginated(self, path: str, max_pages: int = 5) -> list[Any]:
        items = []
        url = f"{self.base_url}{path}"
        for _ in range(max_pages):
            response = httpx.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                items.extend(data)
                if len(data) < 30:
                    break
                url = response.headers.get("Link", "")
                if 'rel="next"' not in url:
                    break
                url = url.split(";")[0].strip("<>")
            else:
                items.append(data)
                break
        return items

    def ingest_repo(self, repo: str) -> dict[str, int]:
        commits = self._get_paginated(f"/repos/{repo}/commits")
        prs = self._get_paginated(f"/repos/{repo}/pulls?state=all")
        issues = self._get_paginated(f"/repos/{repo}/issues?state=all")

        memories = 0
        memories += len(commits)
        memories += len(prs)
        memories += len(issues)

        return {
            "commits": len(commits),
            "prs": len(prs),
            "issues": len(issues),
            "memories": memories,
        }

    def extract_commit_memory(self, commit: dict) -> dict:
        return {
            "type": "context",
            "title": commit.get("commit", {}).get("message", "").split("\n")[0][:200],
            "content": commit.get("commit", {}).get("message", ""),
            "source_type": "github",
            "source_url": commit.get("html_url", ""),
            "source_author": commit.get("commit", {}).get("author", {}).get("name", ""),
            "source_created_at": commit.get("commit", {}).get("author", {}).get("date"),
        }

    def extract_pr_memory(self, pr: dict) -> dict:
        body = pr.get("body") or ""
        return {
            "type": "discussion" if "decision" in body.lower() else "context",
            "title": pr.get("title", ""),
            "content": body,
            "source_type": "github",
            "source_url": pr.get("html_url", ""),
            "source_author": pr.get("user", {}).get("login", ""),
            "source_created_at": pr.get("created_at"),
        }

    def extract_issue_memory(self, issue: dict) -> dict:
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
            "source_created_at": issue.get("created_at"),
        }
