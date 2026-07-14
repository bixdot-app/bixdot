# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Ollama installer bootstrap (v0.6.1)

Downloads the OFFICIAL Ollama installer, verifies its code signature, and
opens Ollama's own installer UI. Design rules (CLAUDE.md §18 — do not relax):

- User-initiated only: nothing downloads until the wizard button is clicked.
- Hardcoded official URLs — no user input can ever influence what is fetched.
- Every hop (including redirects) must stay on ollama.com or
  githubusercontent.com (Ollama serves binaries via the GitHub releases CDN).
- Signature is verified BEFORE launch: Authenticode on Windows, codesign +
  Gatekeeper (spctl) on macOS. Any failure deletes the download.
- The installer opens its normal interactive UI — never silent-install flags.
- Linux is out of scope by design: Ollama's Linux install is a
  curl-pipe-to-shell script we will not execute on a user's behalf.
- Each download is counted in the Privacy ledger ("setup") and audit-logged
  by the calling route.
"""
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

import httpx

from core.privacy import record_net

OFFICIAL_URLS = {
    "windows": "https://ollama.com/download/OllamaSetup.exe",
    "darwin": "https://ollama.com/download/Ollama-darwin.zip",
}
DOWNLOAD_DIR = Path.home() / ".bixdot" / "downloads"
MAX_BYTES = 2_000_000_000  # hard safety cap — abort any download beyond it
ALLOWED_REDIRECT_HOSTS = ("ollama.com", "githubusercontent.com")


class InstallerError(Exception):
    """Download/verification cannot proceed; the message is safe to show users."""


def platform_key() -> Optional[str]:
    """"windows" / "darwin" for supported platforms, None otherwise."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return None


def _host_allowed(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    # Exact or dot-boundary suffix match — "evilollama.com" must NOT pass.
    return any(host == d or host.endswith("." + d) for d in ALLOWED_REDIRECT_HOSTS)


async def _check_request_host(request) -> None:
    """httpx request hook: runs for the initial request AND every redirect hop."""
    if not _host_allowed(request.url.host):
        raise InstallerError(f"Refused redirect to untrusted host: {request.url.host}")


async def download(progress_cb: Callable[[dict], None]) -> Path:
    """
    Stream the official installer to DOWNLOAD_DIR. Emits {completed, total}
    dicts via progress_cb. Returns the finished file path; raises
    InstallerError (with the .part file removed) on any failure.
    """
    key = platform_key()
    if key is None:
        raise InstallerError("Automatic Ollama download is not available on this platform.")
    url = OFFICIAL_URLS[key]
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOWNLOAD_DIR / url.rsplit("/", 1)[-1]
    part = dest.with_name(dest.name + ".part")

    record_net("setup")  # Privacy ledger — one count per user-initiated download
    written = 0
    try:
        timeout = httpx.Timeout(connect=15, read=60, write=30, pool=10)
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            event_hooks={"request": [_check_request_host]},
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                if total > MAX_BYTES:
                    raise InstallerError("Installer download exceeds the safety size cap — aborted.")
                with open(part, "wb") as fh:
                    async for chunk in resp.aiter_bytes():
                        written += len(chunk)
                        if written > MAX_BYTES:
                            raise InstallerError("Installer download exceeds the safety size cap — aborted.")
                        fh.write(chunk)
                        progress_cb({"completed": written, "total": total})
    except InstallerError:
        part.unlink(missing_ok=True)
        raise
    except Exception as e:
        part.unlink(missing_ok=True)
        raise InstallerError(f"Download failed: {e}") from e
    part.replace(dest)
    return dest


def file_sha256(path: Path) -> str:
    """SHA-256 of the downloaded artifact — recorded in the audit log."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cleanup(*paths: Path) -> None:
    """Delete downloaded artifacts after a failed verification."""
    for p in paths:
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
        except Exception:
            pass


def _extract_dir() -> Path:
    return DOWNLOAD_DIR / "Ollama-darwin"


def _extracted_app_path() -> Optional[Path]:
    hits = sorted(_extract_dir().glob("**/Ollama.app"))
    return hits[0] if hits else None


def verify_signature(path: Path) -> tuple[bool, str]:
    """
    Verify the platform code signature BEFORE anything is launched.
    On failure the downloaded file(s) are deleted and (False, reason) returned.
    """
    path = Path(path)
    key = platform_key()
    try:
        if key == "windows":
            return _verify_windows(path)
        if key == "darwin":
            return _verify_macos(path)
        _cleanup(path)
        return False, "Signature verification is not supported on this platform."
    except Exception as e:
        _cleanup(path, _extract_dir())
        return False, f"Signature verification failed: {e}"


def _verify_windows(exe_path: Path) -> tuple[bool, str]:
    # exe_path is generated by download() from a hardcoded URL — never user input.
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"(Get-AuthenticodeSignature -FilePath '{exe_path}').Status",
        ],
        shell=False, capture_output=True, text=True, timeout=120,
    )
    status = (result.stdout or "").strip()
    if result.returncode == 0 and status == "Valid":
        return True, "Valid"
    _cleanup(exe_path)
    return False, f"Authenticode signature status: {status or 'unknown'}"


def _verify_macos(zip_path: Path) -> tuple[bool, str]:
    extract_dir = _extract_dir()
    shutil.rmtree(extract_dir, ignore_errors=True)
    unsafe_entry = None
    try:
        # Close the archive before any cleanup — Windows cannot delete open files.
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                pure = PurePosixPath(name)
                if name.startswith("/") or pure.is_absolute() or ".." in pure.parts:
                    unsafe_entry = name
                    break
            if unsafe_entry is None:
                extract_dir.mkdir(parents=True, exist_ok=True)
                zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        _cleanup(zip_path, extract_dir)
        return False, "Downloaded file is not a valid archive."
    if unsafe_entry is not None:
        _cleanup(zip_path, extract_dir)
        return False, f"Archive contains an unsafe path: {unsafe_entry}"

    app = _extracted_app_path()
    if app is None:
        _cleanup(zip_path, extract_dir)
        return False, "Ollama.app not found inside the archive."

    # Both Apple checks must pass: signature integrity AND Gatekeeper assessment.
    for argv in (
        ["codesign", "--verify", "--deep", "--strict", str(app)],
        ["spctl", "--assess", "--type", "execute", str(app)],
    ):
        result = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            _cleanup(zip_path, extract_dir)
            reason = (result.stderr or "").strip() or f"exit {result.returncode}"
            return False, f"{argv[0]} rejected the app: {reason}"
    return True, "codesign + Gatekeeper valid"


def launch(path: Path) -> None:
    """
    Open the OFFICIAL installer UI and return immediately — never wait on the
    child, never pass silent-install flags. The wizard's /health/onboarding
    poll detects the finished install and advances on its own.
    """
    key = platform_key()
    if key == "windows":
        subprocess.Popen([str(path)], shell=False)  # NSIS UI — user clicks through
    elif key == "darwin":
        app = _extracted_app_path()
        if app is None:
            raise InstallerError("Verified Ollama.app is missing — please download again.")
        subprocess.Popen(["open", str(app)], shell=False)
    else:
        raise InstallerError("Launching the installer is not supported on this platform.")
