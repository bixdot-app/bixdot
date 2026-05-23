# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Path Resolution

Handles Windows-specific paths correctly:
- C:/Users/username/Documents (explicit Windows path)
- ~/Documents → C:/Users/username/Documents on Windows
- OneDrive paths → detected automatically
- Known Windows folders resolved by name
"""
import os
import sys
from pathlib import Path


def get_windows_user_dirs() -> dict[str, Path]:
    """
    Return known Windows user directories.
    Handles OneDrive-synced locations automatically.
    """
    home = Path.home()
    dirs = {
        "home":      home,
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "desktop":   home / "Desktop",
        "pictures":  home / "Pictures",
        "videos":    home / "Videos",
        "music":     home / "Music",
    }

    # Check for OneDrive — common on Windows 10/11
    # OneDrive syncs Documents/Desktop/Pictures by default
    onedrive = home / "OneDrive"
    if onedrive.exists():
        dirs["onedrive"] = onedrive
        # OneDrive versions take priority if they exist
        for folder in ("Documents", "Desktop", "Pictures", "Downloads"):
            od_path = onedrive / folder
            if od_path.exists():
                dirs[folder.lower()] = od_path

    # Also check USERPROFILE env var (Windows specific)
    if sys.platform == "win32":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            up = Path(userprofile)
            for name, folder in [
                ("documents", "Documents"),
                ("downloads", "Downloads"),
                ("desktop",   "Desktop"),
                ("pictures",  "Pictures"),
                ("videos",    "Videos"),
                ("music",     "Music"),
            ]:
                p = up / folder
                if p.exists():
                    dirs[name] = p
                # Also check OneDrive subfolder
                od = up / "OneDrive" / folder
                if od.exists():
                    dirs[name] = od  # OneDrive takes priority

    return dirs


def resolve_path(path: str) -> Path:
    """
    Resolve a path string to a Path object.

    Handles:
    - Explicit paths: C:\\Users\\psych\\Documents\\file.txt
    - Home shorthand: ~/Documents → actual Documents folder
    - Named folders: "documents", "downloads", "desktop", "videos"
    - Relative paths: resolved from home directory
    """
    if not path:
        return Path.home()

    # Explicit Windows or Unix absolute path — use as-is
    p = Path(path)
    if p.is_absolute():
        return p.resolve()

    # Expand ~ to home
    if path.startswith("~"):
        expanded = os.path.expanduser(path)
        return Path(expanded).resolve()

    # Named folder shortcuts
    user_dirs = get_windows_user_dirs()
    path_lower = path.lower().strip().rstrip("/\\")

    if path_lower in user_dirs:
        return user_dirs[path_lower]

    # Partial match — "my documents", "my videos" etc.
    for name in ("documents", "downloads", "desktop", "pictures", "videos", "music", "onedrive"):
        if name in path_lower:
            if name in user_dirs:
                return user_dirs[name]

    # Default: resolve from home
    return (Path.home() / path).resolve()


def get_system_context() -> str:
    """
    Return a description of the user's filesystem for the LLM system prompt.
    This helps the LLM know the actual paths to use.
    """
    user_dirs = get_windows_user_dirs()
    home = user_dirs["home"]

    lines = [f"User home directory: {home}"]
    for name, path in sorted(user_dirs.items()):
        if name != "home" and path.exists():
            lines.append(f"{name.capitalize()} folder: {path}")

    return "\n".join(lines)
