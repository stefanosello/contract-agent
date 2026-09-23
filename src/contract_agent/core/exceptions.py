"""Exceptions for the ContractAgent framework."""

from __future__ import annotations

from typing import Any


class ContractAgentError(Exception):
    """Base exception for all ContractAgent errors."""


class ContractValidationError(ContractAgentError):
    """Raised when a contract specification fails syntax or schema validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class InvariantViolationError(ContractAgentError):
    """Raised deterministically at runtime when a tool call violates a CEL invariant rule."""

    def __init__(
        self,
        invariant_id: str,
        message: str,
        tool_name: str,
        args: dict[str, Any],
        on_violation: str = "raise_invariant_violation",
    ) -> None:
        formatted_message = (
            f"Invariant {invariant_id} violated for tool '{tool_name}': {message}"
        )
        super().__init__(formatted_message)
        self.invariant_id = invariant_id
        self.tool_name = tool_name
        self.tool_args = args
        self.on_violation = on_violation

    def to_diagnostic_payload(self) -> dict[str, Any]:
        """Returns structured diagnostic dictionary for agent scratchpad or telemetry."""
        return {
            "error_type": "INVARIANT_VIOLATION",
            "invariant_id": self.invariant_id,
            "tool_name": self.tool_name,
            "attempted_args": self.tool_args,
            "remedy": f"Action blocked by policy {self.invariant_id}. Must satisfy invariant rule.",
        }


class EscalationRequiredError(InvariantViolationError):
    """Raised when an invariant requires asynchronous manager or human sign-off."""

    def __init__(
        self,
        invariant_id: str,
        tool_name: str,
        approval_type: str,
        resource_id: str,
        args: dict[str, Any],
        prompt: str | None = None,
    ) -> None:
        message = f"Action requires verified '{approval_type}' approval for resource '{resource_id}'."
        super().__init__(
            invariant_id=invariant_id,
            message=message,
            tool_name=tool_name,
            args=args,
            on_violation="require_escalation",
        )
        self.approval_type = approval_type
        self.resource_id = resource_id
        self.prompt = prompt or f"Sign-off required: {approval_type} on {resource_id}"

    def to_diagnostic_payload(self) -> dict[str, Any]:
        """Returns structured diagnostic dictionary including escalation requirements."""
        payload = super().to_diagnostic_payload()
        payload.update(
            {
                "error_type": "ESCALATION_REQUIRED",
                "approval_type": self.approval_type,
                "resource_id": self.resource_id,
                "prompt": self.prompt,
            }
        )
        return payload


# Backward compatibility alias
ApprovalRequiredError = EscalationRequiredError


class CELEvaluationError(ContractAgentError):
    """Raised on internal CEL runtime execution fault."""

    def __init__(self, message: str, rule: str | None = None) -> None:
        super().__init__(message)
        self.rule = rule
