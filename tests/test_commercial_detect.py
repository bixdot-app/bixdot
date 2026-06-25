# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).
from core.services.commercial_detect import detect


def test_no_email_is_personal():
    r = detect(None)
    assert r["is_commercial"] is False
    assert r["reason"] == "no_email"


def test_empty_email_is_personal():
    r = detect("")
    assert r["is_commercial"] is False


def test_gmail_is_personal():
    r = detect("user@gmail.com")
    assert r["is_commercial"] is False
    assert r["reason"] == "free_provider"


def test_protonmail_is_personal():
    r = detect("user@protonmail.com")
    assert r["is_commercial"] is False


def test_corporate_email_is_commercial():
    r = detect("alice@acme.com")
    assert r["is_commercial"] is True
    assert r["email_domain"] == "acme.com"


def test_corporate_sg_email_is_commercial():
    r = detect("bob@lawfirm.com.sg")
    assert r["is_commercial"] is True


def test_invalid_email_is_not_commercial():
    r = detect("notanemail")
    assert r["is_commercial"] is False


def test_domain_extracted_lowercase():
    r = detect("User@ACME.COM")
    assert r["email_domain"] == "acme.com"
