# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Tests for deep research skill."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_fetch_page_text_fallback():
    """fetch_page_text falls back to regex strip when trafilatura not available."""
    import sys

    mock_response = MagicMock()
    mock_response.text = "<html><body><p>Hello world</p></body></html>"

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.dict(sys.modules, {"trafilatura": None}):
            from importlib import reload
            import core.skills.research.researcher as researcher
            reload(researcher)
            text = await researcher.fetch_page_text("http://example.com")
            assert "Hello world" in text


@pytest.mark.asyncio
async def test_run_search_returns_list():
    with patch("ddgs.DDGS") as mock_ddgs:
        mock_ddgs.return_value.__enter__ = MagicMock(return_value=mock_ddgs.return_value)
        mock_ddgs.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs.return_value.text = MagicMock(return_value=[
            {"title": "Result 1", "href": "http://example.com", "body": "content"}
        ])
        from core.skills.research.researcher import run_search
        results = await run_search("test query", max_results=1)
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_deep_research_returns_report():
    """deep_research should return a non-empty string."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value={
        "content": [{"type": "text", "text": "Sub-query 1\nSub-query 2\nSub-query 3"}]
    })

    with patch("core.skills.research.researcher.run_search", AsyncMock(return_value=[])):
        with patch("core.skills.research.researcher.fetch_page_text", AsyncMock(return_value="")):
            # Second call to llm.chat (synthesis)
            mock_llm.chat = AsyncMock(side_effect=[
                {"content": [{"type": "text", "text": "q1\nq2\nq3"}]},
                {"content": [{"type": "text", "text": "This is the research report."}]},
            ])
            from core.skills.research.researcher import deep_research
            result = await deep_research("What is quantum computing?", mock_llm, "user1")
            assert isinstance(result, str)
            assert len(result) > 0
