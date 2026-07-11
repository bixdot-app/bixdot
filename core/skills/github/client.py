# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Async GitHub API client."""

import httpx

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "BixDot/0.3",
        }

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        from core.privacy import record_net
        record_net("github")
        async with httpx.AsyncClient(base_url=GITHUB_API, timeout=15) as client:
            r = await client.get(path, headers=self._headers, params=params or {})
            r.raise_for_status()
            return r.json()

    async def post(self, path: str, body: dict) -> dict:
        from core.privacy import record_net
        record_net("github")
        async with httpx.AsyncClient(base_url=GITHUB_API, timeout=15) as client:
            r = await client.post(path, headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    async def get_user(self) -> dict:
        return await self.get("/user")

    async def list_repos(self, limit: int = 20) -> list:
        data = await self.get("/user/repos", {"per_page": min(limit, 100), "sort": "updated"})
        return [
            {"full_name": r["full_name"], "description": r.get("description", ""),
             "private": r["private"], "stars": r["stargazers_count"],
             "language": r.get("language", ""), "updated_at": r["updated_at"]}
            for r in (data if isinstance(data, list) else [])
        ]

    async def list_issues(self, repo: str, state: str = "open", limit: int = 10) -> list:
        data = await self.get(f"/repos/{repo}/issues", {"state": state, "per_page": min(limit, 100)})
        return [
            {"number": i["number"], "title": i["title"], "state": i["state"],
             "user": i["user"]["login"], "created_at": i["created_at"],
             "labels": [lb["name"] for lb in i.get("labels", [])]}
            for i in (data if isinstance(data, list) else [])
            if "pull_request" not in i  # exclude PRs from issues list
        ]

    async def get_issue(self, repo: str, number: int) -> dict:
        data = await self.get(f"/repos/{repo}/issues/{number}")
        return {
            "number": data["number"], "title": data["title"], "state": data["state"],
            "body": data.get("body", ""), "user": data["user"]["login"],
            "created_at": data["created_at"], "labels": [lb["name"] for lb in data.get("labels", [])],
        }

    async def create_comment(self, repo: str, issue_number: int, body: str) -> dict:
        return await self.post(f"/repos/{repo}/issues/{issue_number}/comments", {"body": body})
