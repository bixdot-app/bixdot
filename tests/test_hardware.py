# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.6.3 hardware check (/system/hardware).

Rules under test: tiers follow RAM, short disk degrades the tier, JWT is
mandatory, every call is audited, and no recommended model can be one the
picker would reject (cloud-tagged or embedding).
"""
import pytest

from core.system.hardware import TIER_MODELS, _tier_for, get_hardware_info


class FakeMem:
    def __init__(self, total_gb, available_gb):
        self.total = int(total_gb * 1024 ** 3)
        self.available = int(available_gb * 1024 ** 3)


class FakeDisk:
    def __init__(self, free_gb):
        self.free = int(free_gb * 1024 ** 3)


@pytest.mark.parametrize(
    "ram_gb,expected",
    [
        (4, "light"),      # low-end laptop
        (8, "light"),
        (11.9, "light"),   # just under the boundary
        (12, "standard"),  # boundary is inclusive
        (16, "standard"),
        (24, "standard"),  # upper boundary stays standard
        (24.1, "large"),
        (64, "large"),
    ],
)
def test_tier_follows_ram(ram_gb, expected):
    assert _tier_for(ram_gb, free_disk_gb=500) == expected


def test_short_disk_degrades_tier():
    # Plenty of RAM, no room to download into → recommend the small model.
    assert _tier_for(64, free_disk_gb=5) == "light"
    assert _tier_for(16, free_disk_gb=9.9) == "light"
    # At the threshold the tier survives.
    assert _tier_for(16, free_disk_gb=10) == "standard"


def test_light_tier_unaffected_by_disk():
    """A light machine already recommends the smallest model — nothing to degrade."""
    assert _tier_for(8, free_disk_gb=1) == "light"


def test_get_hardware_info_shape(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: FakeMem(16, 9.5))
    monkeypatch.setattr("psutil.disk_usage", lambda p: FakeDisk(120))
    info = get_hardware_info()
    assert info["total_ram_gb"] == 16.0
    assert info["available_ram_gb"] == 9.5
    assert info["free_disk_gb"] == 120.0
    assert info["recommended_tier"] == "standard"
    assert info["recommended_models"] == ["llama3.2", "qwen2.5:7b"]
    assert info["os"] in ("windows", "macos", "linux")


def test_recommended_models_pass_the_existing_picker_filters():
    """
    Cloud models are blocked at session creation and embedding models are
    filtered out of the picker — recommending either would surface a model
    the user cannot select.
    """
    for tier, models in TIER_MODELS.items():
        assert models, f"tier {tier} must recommend at least one model"
        for name in models:
            assert not name.endswith(":cloud") and not name.endswith("-cloud")
            assert "embed" not in name.lower()


def test_recommendations_never_return_an_empty_list(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: FakeMem(2, 0.5))
    monkeypatch.setattr("psutil.disk_usage", lambda p: FakeDisk(0.2))
    info = get_hardware_info()
    assert info["recommended_models"]  # a struggling machine still gets advice


# ─── Route ─────────────────────────────────────────────────────────────────────

def test_hardware_route_requires_jwt(client):
    """
    This route specifically requires a JWT.

    NOTE: this asserts one route only. It used to claim to be the C-3 check
    ("no unauthenticated routes outside PUBLIC_ROUTES") and passed while the
    allowlist and reality were six routes apart (BXD-002). The actual
    constraint is enforced by
    tests/test_route_auth.py::test_every_route_is_authenticated_or_allowlisted,
    which enumerates every registered route. Do not re-broaden this docstring.
    """
    r = client.get("/system/hardware")
    assert r.status_code in (401, 403)


def test_hardware_route_returns_full_shape(client, auth_headers, monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: FakeMem(32, 20))
    monkeypatch.setattr("psutil.disk_usage", lambda p: FakeDisk(200))
    r = client.get("/system/hardware", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_tier"] == "large"
    assert body["recommended_models"] == ["qwen2.5:14b", "llama3.1:8b"]
    assert set(body) == {
        "total_ram_gb", "available_ram_gb", "free_disk_gb",
        "os", "recommended_tier", "recommended_models",
    }


def test_hardware_route_writes_audit_event(client, auth_headers, monkeypatch):
    from core.audit.logger import get_audit_logger

    monkeypatch.setattr("psutil.virtual_memory", lambda: FakeMem(16, 8))
    monkeypatch.setattr("psutil.disk_usage", lambda p: FakeDisk(50))
    before = get_audit_logger().count()
    client.get("/system/hardware", headers=auth_headers)
    logger = get_audit_logger()
    assert logger.count() == before + 1
    assert logger.verify_chain()[0] is True  # chain still intact
