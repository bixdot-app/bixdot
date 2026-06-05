# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared rate limiter — applied to auth routes to prevent brute-force attacks.
# Keyed by client IP address (localhost only, so this targets local process isolation).
limiter = Limiter(key_func=get_remote_address)
