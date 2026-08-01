# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — minimal hardware capability check (v0.6.3).

Purpose: stop users pulling a model their machine cannot run. We read RAM
and free disk only, and we RECOMMEND — never block. The model picker keeps
every model selectable; a recommendation is advice, not a gate.

GPU/VRAM detection is deliberately out of scope: it needs vendor-specific
tooling on three platforms and gets the answer wrong often enough to be
worse than silence.
TODO(v0.7): GPU/VRAM detection for a finer recommendation.
"""
import sys
from pathlib import Path

import psutil

GB = 1024 ** 3

# Disk headroom a model download needs before we suggest anything above the
# smallest tier (a 7B model plus its working files does not fit in less).
MIN_DISK_GB_FOR_STANDARD = 10.0

# Tier definitions. These names must stay free of the `:cloud`/`-cloud` tag —
# cloud models are blocked at session creation (v0.4 classification), so
# recommending one would surface a model the picker refuses. Every entry here
# is a local, tool-capable chat model, i.e. it passes the existing filters.
TIER_MODELS = {
    "light": ["llama3.2:3b"],
    "standard": ["llama3.2", "qwen2.5:7b"],
    "large": ["qwen2.5:14b", "llama3.1:8b"],
}


def _os_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _tier_for(total_ram_gb: float, free_disk_gb: float) -> str:
    """
    RAM picks the tier; short disk degrades it. Boundaries: under 12 GB is
    light, 12–24 GB inclusive is standard, above 24 GB is large.
    """
    if total_ram_gb < 12:
        tier = "light"
    elif total_ram_gb <= 24:
        tier = "standard"
    else:
        tier = "large"

    # Anything above the light tier needs real disk headroom to download into.
    if tier != "light" and free_disk_gb < MIN_DISK_GB_FOR_STANDARD:
        tier = "light"
    return tier


def get_hardware_info() -> dict:
    """Read RAM + free disk and derive a recommended model tier."""
    mem = psutil.virtual_memory()
    # Free space where Ollama actually writes models (the user's home).
    disk = psutil.disk_usage(str(Path.home()))

    total_ram_gb = round(mem.total / GB, 1)
    available_ram_gb = round(mem.available / GB, 1)
    free_disk_gb = round(disk.free / GB, 1)
    tier = _tier_for(total_ram_gb, free_disk_gb)

    return {
        "total_ram_gb": total_ram_gb,
        "available_ram_gb": available_ram_gb,
        "free_disk_gb": free_disk_gb,
        "os": _os_name(),
        "recommended_tier": tier,
        "recommended_models": list(TIER_MODELS[tier]),
    }
