# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).
"""Download React 18 UMD bundles for offline serving at /static/."""
import os
import urllib.request

BASE = "https://unpkg.com/react@18/umd/"
DEST = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")
FILES = ["react.production.min.js", "react-dom.production.min.js"]

os.makedirs(DEST, exist_ok=True)
for fname in FILES:
    dest = os.path.join(DEST, fname)
    if os.path.exists(dest):
        print(f"Already exists: {fname}")
    else:
        print(f"Downloading {fname}...")
        urllib.request.urlretrieve(BASE + fname, dest)
        print(f"  -> {dest}")
