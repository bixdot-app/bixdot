# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.6.2 stdio hardening + backend.log (core/logging_setup.py).

The regression this guards: under the Tauri shell, stdout/stderr are either
None or cp1252 pipes — the Unicode startup banner used to kill the backend
at startup, and crash tracebacks vanished without a trace.
"""
import faulthandler
import logging
import sys

import pytest

from core import logging_setup


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Never touch the real ~/.bixdot/backend.log; undo global side effects."""
    monkeypatch.setattr(logging_setup, "LOG_PATH", tmp_path / "backend.log")
    yield
    # setup_process_logging() mutates process-global state — restore it.
    faulthandler.disable()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for h in list(logger.handlers):
            if isinstance(h, logging.StreamHandler) and getattr(h.stream, "name", "").endswith("backend.log"):
                logger.removeHandler(h)
                h.close()


def test_none_stdio_is_routed_to_log_file(tmp_path, monkeypatch):
    """Tauri spawn: no console handles — prints must land in backend.log."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    logging_setup.setup_process_logging()
    print("hello from the void ✓╔═╗")  # Unicode included — must not raise
    assert sys.stdout is not None and sys.stderr is not None
    content = (tmp_path / "backend.log").read_text(encoding="utf-8")
    assert "hello from the void" in content


def test_unicode_banner_cannot_kill_startup(tmp_path, monkeypatch):
    """cp1252 pipe: the box-drawing banner must print without raising."""
    target = tmp_path / "pipe.txt"
    stream = open(target, "w", encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    logging_setup.setup_process_logging()
    # This exact class of output killed v0.5/v0.6 backends under redirect:
    print("╔" + "═" * 46 + "╗ BixDot ✓")
    stream.flush()
    assert "BixDot" in target.read_text(encoding="utf-8", errors="replace")
    stream.close()


def test_log_rotation_at_cap(tmp_path, monkeypatch):
    log = tmp_path / "backend.log"
    log.write_bytes(b"x" * (logging_setup.MAX_LOG_BYTES + 1))
    logging_setup.setup_process_logging()
    assert (tmp_path / "backend.log.1").exists()      # old log rotated aside
    assert log.stat().st_size < logging_setup.MAX_LOG_BYTES


def test_uvicorn_loggers_mirrored_to_file(tmp_path):
    logging_setup.setup_process_logging()
    logging.getLogger("uvicorn.error").error("boom-marker-42")
    content = (tmp_path / "backend.log").read_text(encoding="utf-8")
    assert "boom-marker-42" in content


def test_setup_never_raises_on_unwritable_home(monkeypatch):
    """A logging failure must not prevent the server from starting."""
    monkeypatch.setattr(logging_setup, "LOG_PATH", None)  # forces an exception
    logging_setup.setup_process_logging()  # must swallow, not raise
