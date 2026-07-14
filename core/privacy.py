# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Privacy Proof network ledger (v0.6)

Aggregate counters for every outbound connection BixDot initiates, classified
by purpose. This powers the Privacy dashboard: a live, verifiable account of
where the app talks and why.

Honesty note (mirrored in the UI and threat model): this is BixDot's OWN
accounting of the connections its code makes — instrumented at every outbound
call seam — not an OS-level firewall. Its strongest claims are structural:
cloud AI is off by default, every connection purpose is enumerated below, and
the tamper-evident audit log holds the per-event trail.
"""

from datetime import datetime, timezone

from core.storage.db import get_connection

# kind -> (category, label, where)
# category: "local" (never leaves this machine) | "optin" (you enabled it)
#           | "cloud" (data leaves the device — off by default)
NET_KINDS: dict[str, tuple[str, str, str]] = {
    "ollama":    ("local", "Local AI (Ollama)",             "127.0.0.1 — this computer"),
    "cloud_llm": ("cloud", "Cloud AI (your own API key)",   "api.anthropic.com"),
    "telegram":  ("optin", "Telegram bridge",               "api.telegram.org"),
    "websearch": ("optin", "Web search (DuckDuckGo)",       "duckduckgo.com"),
    "research":  ("optin", "Deep-research page fetches",    "websites you asked to research"),
    "github":    ("optin", "GitHub (your account)",         "api.github.com"),
    "calendar":  ("optin", "Calendar (your account)",       "Google / Microsoft"),
    "setup":     ("optin", "Setup downloads (Ollama installer)", "ollama.com — one-time, you clicked it"),
}


def record_net(kind: str) -> None:
    """Count one outbound call of the given kind. Must never break the caller."""
    if kind not in NET_KINDS:
        kind = "research"  # unknown purposes surface in the most visible bucket
    try:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO net_ledger (kind, count, last_at) VALUES (?, 1, ?) "
                "ON CONFLICT(kind) DO UPDATE SET count = count + 1, last_at = excluded.last_at",
                (kind, now),
            )
    except Exception:
        pass  # accounting must never take down a request


def get_counters() -> list[dict]:
    """All known kinds with live counts (zero rows included — full disclosure)."""
    try:
        with get_connection() as conn:
            rows = {r["kind"]: r for r in conn.execute(
                "SELECT kind, count, last_at FROM net_ledger"
            ).fetchall()}
    except Exception:
        rows = {}
    out = []
    for kind, (category, label, where) in NET_KINDS.items():
        row = rows.get(kind)
        out.append({
            "kind": kind,
            "category": category,
            "label": label,
            "where": where,
            "count": row["count"] if row else 0,
            "last_at": row["last_at"] if row else None,
        })
    return out


def get_report() -> dict:
    """Full privacy report for the dashboard."""
    from core.config import settings
    from core.audit.logger import get_audit_logger
    from core.agent.permissions import get_permission_store
    from core.storage.db import get_setting

    counters = get_counters()
    totals = {"local": 0, "optin": 0, "cloud": 0}
    for c in counters:
        totals[c["category"]] += c["count"]

    audit = get_audit_logger()
    chain_valid, broken_at = audit.verify_chain()

    return {
        "counters": counters,
        "totals": totals,
        "audit": {
            "chain_valid": chain_valid,
            "broken_at": broken_at,
            "entries": audit.count(),
        },
        "config": {
            "bind_host": settings.host,
            "bind_port": settings.port,
            "cloud_llm_enabled": settings.cloud_llm_enabled,
            "telegram_enabled": get_setting("telegram_enabled") == "1",
        },
        "grants_active": len(get_permission_store().list_grants()),
    }
