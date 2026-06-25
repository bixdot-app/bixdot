# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
Migration 0001 — Add email column to users table.

Safe to run multiple times (idempotent).
SQLite does not support ADD COLUMN NOT NULL without a default,
so email is nullable. Existing users (email=NULL) are treated
as unknown — never flagged as commercial.

This migration is also applied inline inside init_db() so it runs
automatically on every startup. This file exists as the canonical
migration record and for manual invocation.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".bixdot" / "data.db"


def run(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]

    if "email" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
        conn.commit()
        print("Migration 0001: email column added to users table.")
    else:
        print("Migration 0001: already applied, skipping.")

    conn.close()


if __name__ == "__main__":
    run()
