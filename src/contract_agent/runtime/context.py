"""Workflow execution context and durable approval store for ContractAgent."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ToolCallRecord:
    """Record of an executed tool call."""
    tool_name: str
    args: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    resource_id: Optional[str] = None


class ApprovalStore:
    """Durable approval store backed by SQLite (or in-memory for testing)."""

    def __init__(self, db_path: Optional[str | Path] = ":memory:") -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    granted_by TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(approval_type, resource_id)
                )
                """
            )

    def request_approval(self, approval_type: str, resource_id: str) -> str:
        """Register a pending approval request."""
        now = time.time()
        ticket_id = f"TICKET-{approval_type}-{resource_id}"
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO approvals (approval_type, resource_id, status, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?)
                ON CONFLICT(approval_type, resource_id) DO UPDATE SET
                    status = 'pending',
                    updated_at = excluded.updated_at
                """,
                (approval_type, resource_id, now, now),
            )
        return ticket_id

    def grant_approval(
        self, approval_type: str, resource_id: str, granted_by: str = "manager"
    ) -> None:
        """Grant an approval for a specific resource."""
        now = time.time()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO approvals (approval_type, resource_id, status, granted_by, created_at, updated_at)
                VALUES (?, ?, 'approved', ?, ?, ?)
                ON CONFLICT(approval_type, resource_id) DO UPDATE SET
                    status = 'approved',
                    granted_by = excluded.granted_by,
                    updated_at = excluded.updated_at
                """,
                (approval_type, resource_id, granted_by, now, now),
            )

    def has_approval(self, approval_type: str, resource_id: str) -> bool:
        """Check if a verified approval exists for a given resource."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM approvals
            WHERE approval_type = ? AND resource_id = ? AND status = 'approved'
            """,
            (approval_type, resource_id),
        )
        return cursor.fetchone() is not None

    def revoke_approval(self, approval_type: str, resource_id: str) -> None:
        """Revoke a previously granted approval."""
        with self.conn:
            self.conn.execute(
                """
                DELETE FROM approvals
                WHERE approval_type = ? AND resource_id = ?
                """,
                (approval_type, resource_id),
            )


class WorkflowContext:
    """Manages multi-turn execution state, tool call history, and approval verification."""

    def __init__(self, approval_store: Optional[ApprovalStore] = None) -> None:
        self.call_history: List[ToolCallRecord] = []
        self.approval_store = approval_store or ApprovalStore(":memory:")
        self.session_data: Dict[str, Any] = {}

    def record_call(
        self, tool_name: str, args: Dict[str, Any], resource_id: Optional[str] = None
    ) -> None:
        """Records a successful tool execution in the workflow history."""
        self.call_history.append(
            ToolCallRecord(tool_name=tool_name, args=args, resource_id=resource_id)
        )

    def has_approval(self, approval_type: str, resource_id: str) -> bool:
        """Exposed to CEL: workflow.has_approval(type, resource_id)."""
        return self.approval_store.has_approval(approval_type, str(resource_id))

    def called_before(
        self, prior_tool: str, target_tool: str, resource_id: Optional[str] = None
    ) -> bool:
        """Exposed to CEL: workflow.called_before(prior, target, resource_id).
        
        Returns True if `prior_tool` was called prior to this point. If `resource_id`
        is specified, requires that `prior_tool` was called for that matching resource.
        """
        for record in self.call_history:
            if record.tool_name == prior_tool:
                if resource_id is None or str(record.resource_id) == str(resource_id):
                    return True
        return False

    def call_count(self, tool_name: str) -> int:
        """Exposed to CEL: workflow.call_count(tool_name)."""
        return sum(1 for r in self.call_history if r.tool_name == tool_name)
