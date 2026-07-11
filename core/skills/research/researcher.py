# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Deep research pipeline: plan → search → fetch → synthesise."""

import re
from typing import List

MAX_PAGE_CHARS = 3000


async def fetch_page_text(url: str, timeout: int = 10) -> str:
    try:
        import httpx
        from core.privacy import record_net
        record_net("research")
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "BixDot/0.3 research-agent"})
            html = r.text
        try:
            import trafilatura
            text = trafilatura.extract(html) or ""
        except Exception:
            # Fallback: strip HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_PAGE_CHARS]
    except Exception as e:
        return f"[fetch error: {e}]"


async def run_search(query: str, max_results: int = 3) -> List[dict]:
    try:
        from ddgs import DDGS
        from core.privacy import record_net
        record_net("websearch")
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []


async def deep_research(question: str, llm, user_id: str) -> str:
    # Step 1 — plan sub-queries
    plan_prompt = (
        f"You are a research assistant. The user wants to research: '{question}'\n\n"
        "Generate exactly 3 specific search queries that together would give a comprehensive answer. "
        "Output ONLY the 3 queries, one per line, no numbering, no explanation."
    )
    plan_resp = await llm.chat(
        messages=[{"role": "user", "content": plan_prompt}],
        system="You are a research planning assistant. Output only the requested content.",
        tools=None,
    )
    plan_text = " ".join(
        b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "")
        for b in plan_resp["content"]
        if (b.get("type") if isinstance(b, dict) else getattr(b, "type", None)) == "text"
    ).strip()
    sub_queries = [q.strip() for q in plan_text.splitlines() if q.strip()][:3]
    if not sub_queries:
        sub_queries = [question]

    # Step 2 — search each query
    all_results = []
    for q in sub_queries:
        results = await run_search(q, max_results=2)
        all_results.extend(results)

    # Step 3 — fetch top pages (up to 4)
    pages_fetched = []
    seen_urls = set()
    for r in all_results:
        url = r.get("href") or r.get("url", "")
        if url and url not in seen_urls and len(pages_fetched) < 4:
            seen_urls.add(url)
            text = await fetch_page_text(url)
            if text and not text.startswith("[fetch error"):
                pages_fetched.append({"url": url, "title": r.get("title", url), "text": text})

    # Step 4 — synthesise
    if pages_fetched:
        context_parts = []
        for p in pages_fetched:
            context_parts.append(f"Source: {p['title']}\nURL: {p['url']}\n{p['text']}")
        context = "\n\n---\n\n".join(context_parts)
    else:
        # Fallback: use search snippets
        context = "\n\n".join(
            f"{r.get('title','')}: {r.get('body','')}" for r in all_results[:6]
        )

    synthesis_prompt = (
        f"Research question: {question}\n\n"
        f"Here is the information gathered from multiple sources:\n\n{context}\n\n"
        "Write a comprehensive, well-structured research report answering the question. "
        "Include key findings, notable details, and a brief source summary at the end."
    )
    synth_resp = await llm.chat(
        messages=[{"role": "user", "content": synthesis_prompt}],
        system="You are a research analyst. Write clear, factual reports based on provided sources.",
        tools=None,
    )
    report = " ".join(
        b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "")
        for b in synth_resp["content"]
        if (b.get("type") if isinstance(b, dict) else getattr(b, "type", None)) == "text"
    ).strip()

    sources_summary = "\n\nSources consulted:\n" + "\n".join(
        f"- {p['title']}: {p['url']}" for p in pages_fetched
    ) if pages_fetched else ""

    return report + sources_summary
