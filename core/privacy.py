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
#
# BXD-001: the "ollama" row here is a PLACEHOLDER and is never shown as-is.
# Its disclosure is resolved at read time by _ollama_disclosure() from the URL
# inference actually uses, because a hardcoded "127.0.0.1" would keep claiming
# the traffic stayed home after the user pointed Ollama at a remote host.
NET_KINDS: dict[str, tuple[str, str, str]] = {
    "ollama":    ("local", "Local AI (Ollama)",             "127.0.0.1 — this computer"),
    "cloud_llm": ("cloud", "Cloud AI (your own API key)",   "api.anthropic.com"),
    "telegram":  ("optin", "Telegram bridge",               "api.telegram.org"),
    "websearch": ("optin", "Web search (DuckDuckGo)",       "duckduckgo.com"),
    "research":  ("optin", "Deep-research page fetches",    "websites you asked to research"),
    "github":    ("optin", "GitHub (your account)",         "api.github.com"),
    "calendar":  ("optin", "Calendar (your account)",       "Google / Microsoft"),
    "setup":     ("optin", "Setup downloads (Ollama installer)", "ollama.com — one-time, you clicked it"),
    # BXD-010: a call site that records a kind never added here used to be
    # silently folded into "research" — a real, disclosed, opt-in purpose. A
    # dashboard that promises full disclosure must not let an unregistered
    # outbound call hide inside a legitimate bucket, so it lands here instead:
    # loudest category (cloud), and a label that tells the user something is
    # wrong. tests/test_constraints.py::test_C_1_6_all_record_net_kinds_registered
    # keeps every literal record_net(...) call site in the source registered
    # above, so this bucket should stay empty in practice.
    "unknown":   ("cloud", "Unregistered outbound call — please report", "unclassified — treat as leaving this device until reviewed"),
}


def record_net(kind: str) -> None:
    """Count one outbound call of the given kind. Must never break the caller."""
    if kind not in NET_KINDS:
        kind = "unknown"  # BXD-010: surface loudly, never mislabel as a real purpose
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


def _ollama_disclosure() -> tuple[str, str, str]:
    """
    Resolve (category, label, where) for Ollama traffic from the URL actually
    in use — never from a constant.

    A remote Ollama server means every prompt leaves the device, so it is
    reported in the "cloud" category with its real hostname. Saying "local"
    here would put a false statement inside a tamper-evident log that still
    verifies perfectly, which is worse than no dashboard at all.
    """
    from core.config import settings

    if settings.ollama_is_local:
        return ("local", "Local AI (Ollama)", "127.0.0.1 — this computer")
    host = settings.ollama_host or "unknown host"
    return ("cloud", "Remote AI (Ollama)", f"{host} — leaves this device")


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
        if kind == "ollama":
            category, label, where = _ollama_disclosure()
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
