# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""GitHub PAT storage using OS keyring — never stored in DB or config."""

import keyring

SERVICE = "bixdot-github"


def save_github_token(user_id: str, token: str):
    keyring.set_password(SERVICE, user_id, token)


def load_github_token(user_id: str) -> str | None:
    return keyring.get_password(SERVICE, user_id)


def delete_github_token(user_id: str):
    try:
        keyring.delete_password(SERVICE, user_id)
    except keyring.errors.PasswordDeleteError:
        pass
