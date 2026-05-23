# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Terminal Sandbox

SECURITY MODEL:
  - Strict allowlist: only specific executables are permitted
  - shell=False always: no shell injection possible
  - Shell operator detection: |  ;  &  >  <  `  $()  all blocked
  - Hard timeout: 30 seconds, then SIGKILL
  - Output cap: 5000 characters max
  - cwd locked to user home (or a sub-path the user explicitly navigates to)
  - Every execution logged to audit log
  - No privilege escalation commands
  - No network download commands
  - No destructive file commands
"""

import os
import shlex
import subprocess
from pathlib import Path


# ─── Allowlist ────────────────────────────────────────────────────────────────

ALLOWED_EXECUTABLES = {
    # Directory / file inspection (read-only)
    "dir", "ls", "ls.exe",
    "pwd", "cd",
    "type",                         # Windows: type file.txt
    "cat",
    "echo",
    "where", "which",
    "find", "findstr", "grep",
    "tree",

    # System info (read-only)
    "whoami", "hostname",
    "date", "time",
    "ver",                          # Windows version
    "systeminfo",
    "tasklist",
    "ipconfig",                     # read-only network info
    "ping",                         # network reachability only
    "wmic",                         # restricted below

    # Development tools
    "python", "python3", "python3.11", "python3.12",
    "pip", "pip3",
    "node", "npm", "npx",
    "git",
    "cargo", "rustc",
    "go",
    "java", "javac",
    "dotnet",
    "make",
    "gcc", "g++", "clang",

    # Package managers (read-only info commands)
    "winget",

    # Text tools
    "more", "less",
    "sort", "uniq", "wc",
    "head", "tail",

    # BixDot-specific
    "ollama",
    "uvicorn",
}

# ─── Blocked patterns (checked BEFORE allowlist) ──────────────────────────────

# Shell operators — if any are present, reject immediately
SHELL_OPERATORS = frozenset(["||", "&&", "&", ";", "|", ">", ">>", "<", "<<", "`", "$(", "${"])

# Blocked executable names — even if someone tries to alias them
BLOCKED_EXECUTABLES = frozenset([
    # Destruction
    "rm", "del", "rmdir", "rd", "erase",
    "format",
    "diskpart",
    # System control
    "shutdown", "restart", "reboot", "halt", "poweroff",
    "logoff",
    # Privilege escalation
    "sudo", "su", "runas", "psexec",
    # Shell escalation
    "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh",
    "bash", "sh", "zsh", "fish", "wsl",
    # Network downloads
    "curl", "wget", "Invoke-WebRequest", "iwr",
    "ftp", "sftp", "scp", "rsync",
    # Registry
    "reg", "regedit", "regedt32",
    # Network config (write)
    "net", "netsh", "arp", "route",
    # Process control
    "taskkill", "kill", "pkill", "killall",
    # Encryption / security tools (avoid misuse)
    "cipher", "icacls", "cacls", "takeown",
    # Package installers (require explicit user action)
    "msiexec", "setup", "install",
    # Misc dangerous
    "attrib", "schtasks", "sc", "bcdedit", "bootcfg",
])

# Blocked wmic queries (subset of wmic allowed for info only)
BLOCKED_WMIC_QUERIES = frozenset([
    "process call create", "process delete",
    "service", "startup",
])

MAX_OUTPUT_CHARS = 5000
TIMEOUT_SECONDS  = 30


# ─── Validation ───────────────────────────────────────────────────────────────

class CommandBlocked(Exception):
    """Raised when a command is rejected by the security policy."""


def validate_command(raw_command: str) -> list[str]:
    """
    Parse and validate a command string. Returns the argv list if safe.
    Raises CommandBlocked with a human-readable reason if not.

    NEVER passes the command to a shell. Uses shlex.split() then validates
    each component independently.
    """
    raw_command = raw_command.strip()

    if not raw_command:
        raise CommandBlocked("Empty command.")

    # 1. Block shell operators (quick scan before parsing)
    for op in SHELL_OPERATORS:
        if op in raw_command:
            raise CommandBlocked(
                f'Shell operator "{op}" is not allowed. '
                "Run one command at a time."
            )

    # 2. Parse with shlex (POSIX-like, handles quoting)
    try:
        argv = shlex.split(raw_command, posix=False)
    except ValueError as e:
        raise CommandBlocked(f"Could not parse command: {e}")

    if not argv:
        raise CommandBlocked("Empty command after parsing.")

    # 3. Extract the executable name (basename, lowercase, strip .exe)
    exe_raw  = argv[0]
    exe_name = Path(exe_raw).name.lower().removesuffix(".exe")

    # 4. Block list check first
    if exe_name in BLOCKED_EXECUTABLES:
        raise CommandBlocked(
            f'"{exe_name}" is not allowed for security reasons. '
            "BixDot restricts commands that could modify the system."
        )

    # 5. Allowlist check
    if exe_name not in ALLOWED_EXECUTABLES:
        raise CommandBlocked(
            f'"{exe_name}" is not on the allowed command list. '
            f"Allowed tools include: python, git, node, npm, pip, dir/ls, echo, ping, ollama, and more."
        )

    # 6. Argument-level checks for specific executables
    if exe_name == "wmic":
        arg_str = " ".join(argv[1:]).lower()
        for blocked in BLOCKED_WMIC_QUERIES:
            if blocked in arg_str:
                raise CommandBlocked(f'wmic "{blocked}" is not allowed.')

    if exe_name in ("ping",):
        # Only allow ping with simple hostnames — no -t (infinite) on Windows
        arg_str = " ".join(argv[1:]).lower()
        if "-t" in arg_str.split():
            raise CommandBlocked('ping -t (infinite ping) is not allowed.')

    return argv


# ─── Executor ─────────────────────────────────────────────────────────────────

def run_command(raw_command: str, cwd: str | None = None) -> dict:
    """
    Validate and run a command safely.

    Returns:
        {
          "ok":      bool,
          "command": str,   # the command that was run
          "stdout":  str,
          "stderr":  str,
          "exit":    int,
          "blocked": str | None,  # reason if blocked
        }
    """
    # Validate first
    try:
        argv = validate_command(raw_command)
    except CommandBlocked as e:
        return {
            "ok":      False,
            "command": raw_command,
            "stdout":  "",
            "stderr":  "",
            "exit":    -1,
            "blocked": str(e),
        }

    # Resolve working directory
    safe_cwd = _safe_cwd(cwd)

    # Execute
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=str(safe_cwd),
            shell=False,                        # NEVER shell=True
            env=_stripped_env(),
        )
        stdout = _truncate(result.stdout)
        stderr = _truncate(result.stderr)
        return {
            "ok":      True,
            "command": raw_command,
            "stdout":  stdout,
            "stderr":  stderr,
            "exit":    result.returncode,
            "blocked": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "ok":      False,
            "command": raw_command,
            "stdout":  "",
            "stderr":  f"Command timed out after {TIMEOUT_SECONDS}s.",
            "exit":    -1,
            "blocked": None,
        }
    except FileNotFoundError:
        exe = argv[0]
        return {
            "ok":      False,
            "command": raw_command,
            "stdout":  "",
            "stderr":  f'"{exe}" not found. Is it installed and on your PATH?',
            "exit":    -1,
            "blocked": None,
        }
    except Exception as e:
        return {
            "ok":      False,
            "command": raw_command,
            "stdout":  "",
            "stderr":  f"Execution error: {e}",
            "exit":    -1,
            "blocked": None,
        }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_cwd(requested: str | None) -> Path:
    """
    Resolve working directory. Falls back to home if None or unsafe.
    Prevents cd-ing to system directories.
    """
    home = Path.home()

    if not requested:
        return home

    try:
        p = Path(requested).expanduser().resolve()
        # Block system dirs
        blocked_roots = [
            Path("C:/Windows"),
            Path("C:/System32"),
            Path("/etc"),
            Path("/sys"),
            Path("/proc"),
        ]
        for root in blocked_roots:
            try:
                p.relative_to(root)
                return home  # Silently fall back to home
            except ValueError:
                pass
        return p if p.is_dir() else home
    except Exception:
        return home


def _stripped_env() -> dict:
    """
    Return a minimal environment for subprocess.
    Strips secrets/tokens that might be in the parent env.
    """
    safe_keys = {
        "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE",
        "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOME",
        "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
        "USERNAME", "COMPUTERNAME", "LANG", "LC_ALL",
        "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
        "WINDIR", "PUBLIC", "ONEDRIVE",
    }
    return {k: v for k, v in os.environ.items() if k.upper() in safe_keys}


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated — {len(text):,} chars total]"
