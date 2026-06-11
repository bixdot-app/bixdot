# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Tests for commercial use detection."""

import pytest
from core.auth.license_check import (
    is_corporate_email,
    detect_commercial_use,
    PERSONAL_DOMAINS,
)


def test_personal_email_gmail():
    assert is_corporate_email("user@gmail.com") is False


def test_personal_email_outlook():
    assert is_corporate_email("user@outlook.com") is False


def test_personal_email_proton():
    assert is_corporate_email("user@proton.me") is False


def test_corporate_email_returns_true():
    assert is_corporate_email("alice@acmecorp.com") is True


def test_corporate_email_sg_company():
    assert is_corporate_email("shanker@digitechbusiness.sg") is True


def test_no_email_returns_false():
    assert is_corporate_email("") is False
    assert is_corporate_email(None) is False  # type: ignore


def test_malformed_email_returns_false():
    assert is_corporate_email("notanemail") is False


def test_education_domain_not_commercial():
    assert is_corporate_email("student@mit.edu") is False
    assert is_corporate_email("user@university.ac.uk") is False


def test_detect_no_email_not_commercial(monkeypatch):
    monkeypatch.setattr("core.auth.license_check.is_domain_joined_windows", lambda: False)
    result = detect_commercial_use(None)
    assert result["is_commercial"] is False
    assert result["signals"] == []
    assert result["message"] is None


def test_detect_personal_email_not_commercial(monkeypatch):
    monkeypatch.setattr("core.auth.license_check.is_domain_joined_windows", lambda: False)
    result = detect_commercial_use("user@gmail.com")
    assert result["is_commercial"] is False


def test_detect_corporate_email_is_commercial(monkeypatch):
    monkeypatch.setattr("core.auth.license_check.is_domain_joined_windows", lambda: False)
    result = detect_commercial_use("alice@bigcorp.com")
    assert result["is_commercial"] is True
    assert "corporate_email" in result["signals"]
    assert result["message"] is not None


def test_detect_domain_joined_is_commercial(monkeypatch):
    monkeypatch.setattr("core.auth.license_check.is_domain_joined_windows", lambda: True)
    result = detect_commercial_use("user@gmail.com")
    assert result["is_commercial"] is True
    assert "domain_joined_windows" in result["signals"]


def test_detect_both_signals(monkeypatch):
    monkeypatch.setattr("core.auth.license_check.is_domain_joined_windows", lambda: True)
    result = detect_commercial_use("cto@enterprise.io")
    assert result["is_commercial"] is True
    assert "corporate_email" in result["signals"]
    assert "domain_joined_windows" in result["signals"]
