# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — process-level stdio hardening + crash observability (v0.6.2)

Under the Tauri desktop shell the backend is spawned with no console, so
stdout/stderr are either None (handles absent) or a cp1252-encoded pipe.
Both modes used to be hazardous:

- cp1252 pipe: the first Unicode print (the startup banner) raised
  UnicodeEncodeError inside the lifespan and killed the server at startup.
- None: every print and traceback vanished — backend deaths left no trace
  anywhere (no file, no Event Log), making crashes undiagnosable.

This module makes stdio unable to kill the process and gives every crash a
durable home in ~/.bixdot/backend.log. Called ONLY from the process entry
points (core/__main__.py and core/main.py __main__) — never at import time,
so the test suite and library imports touch nothing in the real home dir.

The log contains operational output only (startup lines, tracebacks, uvicorn
messages) — never tokens, passwords, or message content. Sensitive-data rules
for the audit log apply here too.
"""
import faulthandler
import logging
import sys
from pathlib import Path

LOG_PATH = Path.home() / ".bixdot" / "backend.log"
MAX_LOG_BYTES = 5 * 1024 * 1024  # rotate to backend.log.1 at startup beyond this


def _rotate() -> None:
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_LOG_BYTES:
            LOG_PATH.replace(LOG_PATH.with_name(LOG_PATH.name + ".1"))
    except Exception:
        pass  # rotation is best-effort; logging must still come up


def setup_process_logging() -> None:
    """
    Harden stdio and open the persistent backend log. Never raises — a
    logging failure must not stop the server from starting.
    """
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate()
        log_file = open(  # noqa: SIM115 — deliberately held for process lifetime
            LOG_PATH, "a", encoding="utf-8", errors="replace", buffering=1
        )
    except Exception:
        return  # e.g. unwritable home — run with whatever stdio we have

    # 1. Native crashes (segfaults, aborts) and hung-thread dumps become visible.
    try:
        faulthandler.enable(file=log_file)
    except Exception:
        pass

    # 2. stdio can never kill the process again:
    #    - real console/pipe → re-encode as UTF-8 with replacement characters
    #    - missing handles (Tauri spawn) → route prints into the log file
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is None:
            setattr(sys, name, log_file)
        else:
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                setattr(sys, name, log_file)

    # 3. Mirror all logging (uvicorn's loggers do not propagate to root, so
    #    they get the handler explicitly) into the file.
    handler = logging.StreamHandler(log_file)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).addHandler(handler)
