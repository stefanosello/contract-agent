"""Exceptions for the ContractAgent framework."""

from typing import Any, Dict, Optional


class ContractAgentError(Exception):
    """Base exception for all ContractAgent errors."""


class ContractValidationError(ContractAgentError):
    """Raised when a contract specification fails syntax or schema validation."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}


class InvariantViolationError(ContractAgentError):
    """Raised deterministically at runtime when a tool call violates a CEL invariant rule."""

    def __init__(
        self,
        invariant_id: str,
        message: str,
        tool_name: str,
        args: Dict[str, Any],
        on_violation: str = "raise_invariant_violation",
    ) -> None:
        formatted_message = f"Invariant {invariant_id} violated for tool '{tool_name}': {message}"
        super().__init__(formatted_message)
        self.invariant_id = invariant_id
        self.tool_name = tool_name
        self.tool_args = args
        self.on_violation = on_violation

    def to_diagnostic_payload(self) -> Dict[str, Any]:
        """Returns structured diagnostic dictionary for agent scratchpad or telemetry."""
        return {
            "error_type": "INVARIANT_VIOLATION",
            "invariant_id": self.invariant_id,
            "tool_name": self.tool_name,
            "attempted_args": self.tool_args,
            "remedy": f"Action blocked by policy {self.invariant_id}. Must satisfy invariant rule.",
        }


class ApprovalRequiredError(InvariantViolationError):
    """Raised when an invariant requires asynchronous manager or human sign-off."""

    def __init__(
        self,
        invariant_id: str,
        tool_name: str,
        approval_type: str,
        resource_id: str,
        args: Dict[str, Any],
    ) -> None:
        message = (
            f"Action requires verified '{approval_type}' approval for resource '{resource_id}'."
        )
        super().__init__(
            invariant_id=invariant_id,
            message=message,
            tool_name=tool_name,
            args=args,
            on_violation="require_escalation",
        )
        self.approval_type = approval_type
        self.resource_id = resource_id
