# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot backend entry point.
Used both by `python -m core.main` and the PyInstaller bundle.
"""
import sys
import os

# When running as a PyInstaller bundle, sys._MEIPASS points to the
# temporary extraction directory. We add it to sys.path so our modules resolve.
if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    sys.path.insert(0, bundle_dir)
    # Set BIXDOT_BASE so core/main.py can locate the frontend
    os.environ.setdefault("BIXDOT_BASE", bundle_dir)

from core.logging_setup import setup_process_logging

# Harden stdio BEFORE anything can print: under the Tauri shell the handles
# are absent or cp1252 pipes, either of which used to lose or kill startup.
setup_process_logging()

import uvicorn
from core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "core.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
    )
