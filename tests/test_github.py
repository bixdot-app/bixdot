# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Tests for GitHub integration skill."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def test_token_store_roundtrip(monkeypatch):
    store = {}
    monkeypatch.setattr("keyring.set_password", lambda s, u, p: store.__setitem__((s, u), p))
    monkeypatch.setattr("keyring.get_password", lambda s, u: store.get((s, u)))

    from core.skills.github.store import save_github_token, load_github_token
    save_github_token("user1", "ghp_testtoken")
    assert load_github_token("user1") == "ghp_testtoken"


def test_token_delete(monkeypatch):
    store = {"bixdot-github|user1": "token"}
    monkeypatch.setattr("keyring.set_password", lambda s, u, p: store.__setitem__(f"{s}|{u}", p))
    monkeypatch.setattr("keyring.get_password", lambda s, u: store.get(f"{s}|{u}"))

    class FakeDeleteError(Exception):
        pass

    def fake_delete(s, u):
        key = f"{s}|{u}"
        if key not in store:
            raise FakeDeleteError()
        del store[key]

    import keyring.errors
    monkeypatch.setattr("keyring.delete_password", fake_delete)
    monkeypatch.setattr("keyring.errors.PasswordDeleteError", FakeDeleteError)

    from core.skills.github.store import delete_github_token, load_github_token
    delete_github_token("user1")
    assert load_github_token("user1") is None


@pytest.mark.asyncio
async def test_client_list_repos():
    import httpx
    from unittest.mock import patch, AsyncMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"full_name": "user/repo1", "description": "Test repo", "private": False,
         "stargazers_count": 5, "language": "Python", "updated_at": "2026-01-01"}
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from core.skills.github.client import GitHubClient
        client = GitHubClient("fake_token")
        repos = await client.list_repos()
        assert len(repos) == 1
        assert repos[0]["full_name"] == "user/repo1"
