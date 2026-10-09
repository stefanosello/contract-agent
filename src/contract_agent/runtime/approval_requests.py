"""Session-bound suspended actions backed by the authoritative approval database."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


class ApprovalRequestStore:
    """Persist immutable request payloads and atomically prevent token replay."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        with connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS approval_requests (
                    token TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    approval_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                )"""
            )

    def register(self, session_id: str, payload: dict[str, Any]) -> None:
        """Commit the keyed approval transition and suspended payload together."""
        now = time.time()
        with self.connection:
            self.connection.execute(
                """INSERT INTO approvals
                   (approval_type, resource_id, status, created_at, updated_at)
                   VALUES (?, ?, 'pending', ?, ?)
                   ON CONFLICT(approval_type, resource_id) DO UPDATE SET
                   status = 'pending', granted_by = NULL, updated_at = excluded.updated_at""",
                (payload["approval_type"], payload["resource_id"], now, now),
            )
            self.connection.execute(
                """INSERT INTO approval_requests
                   (token, session_id, approval_type, resource_id, payload)
                   VALUES (?, ?, ?, ?, ?)""",
                (payload["token"], session_id, payload["approval_type"],
                 payload["resource_id"], json.dumps(payload, allow_nan=False)),
            )

    def get(self, token: str, session_id: str) -> dict[str, Any]:
        """Load a request only within its originating session."""
        row = self.connection.execute(
            "SELECT payload, status FROM approval_requests WHERE token = ? AND session_id = ?",
            (token, session_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"Approval token '{token}' not found in durable session")
        payload: dict[str, Any] = json.loads(row[0])
        payload["status"] = row[1]
        return payload

    def claim(self, token: str, session_id: str) -> None:
        """Consume only a pending request with an externally approved keyed record.

        Claiming precedes dispatch: crashes cannot replay a side effect automatically.
        Recovery of an interrupted dispatch requires explicit host reconciliation.
        """
        with self.connection:
            cursor = self.connection.execute(
                """UPDATE approval_requests SET status = 'consumed'
                   WHERE token = ? AND session_id = ? AND status = 'pending'
                   AND EXISTS (SELECT 1 FROM approvals
                       WHERE approvals.approval_type = approval_requests.approval_type
                       AND approvals.resource_id = approval_requests.resource_id
                       AND approvals.status = 'approved')""",
                (token, session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Request must be pending and durably approved before resumption")

    def cancel(self, session_id: str) -> None:
        """Invalidate unconsumed tokens for a reset session."""
        with self.connection:
            self.connection.execute(
                "UPDATE approval_requests SET status = 'cancelled' WHERE session_id = ? AND status = 'pending'",
                (session_id,),
            )
