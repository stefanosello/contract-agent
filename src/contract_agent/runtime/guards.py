"""Runtime guard interceptor enforcing CEL invariants on agent tool calls."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from contract_agent.core.ast import ContractAST, Invariant
from contract_agent.core.exceptions import (
    EscalationRequiredError,
    InvariantViolationError,
)
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext


class GuardInterceptor:
    """Intercepts tool executions, evaluating CEL invariants before underlying handlers run."""

    def __init__(
        self,
        contract: ContractAST,
        context: WorkflowContext | None = None,
        cel_engine: CELEngine | None = None,
    ) -> None:
        self.contract = contract
        self.context = context or WorkflowContext()
        self.cel_engine = cel_engine or CELEngine()

    def get_invariants_for_tool(self, tool_name: str) -> list[Invariant]:
        """Returns invariants that apply to this tool."""
        return self.contract.get_invariants_for_tool(tool_name)

    def check_invariants(
        self, tool_name: str, args: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Evaluates all applicable invariants.

        Returns:
            Optional[Dict[str, Any]]: Error payload if on_violation is 'block_tool_call'.

        Raises:
            InvariantViolationError: If on_violation is 'raise_invariant_violation'.
            EscalationRequiredError: If on_violation is 'require_escalation' or missing approval.
        """
        invariants = self.get_invariants_for_tool(tool_name)

        for inv in invariants:
            res = self.cel_engine.evaluate_invariant(inv, tool_name, args, self.context)
            if not res.is_valid:
                # Dispatch violation actions based on Invariant.on_violation
                if inv.on_violation == "block_tool_call":
                    return {
                        "error": f"Tool call blocked by invariant {inv.id}",
                        "invariant_id": inv.id,
                        "tool_name": tool_name,
                        "remedy": f"Action blocked by policy {inv.id}: {inv.description}",
                    }
                elif (
                    inv.on_violation == "require_escalation"
                    or "has_approval" in inv.rule
                ):
                    resource_id = str(
                        args.get("invoice_id") or args.get("resource_id") or "unknown"
                    )
                    raise EscalationRequiredError(
                        invariant_id=inv.id,
                        tool_name=tool_name,
                        approval_type="manager_signoff",
                        resource_id=resource_id,
                        args=args,
                    )
                else:
                    raise InvariantViolationError(
                        invariant_id=inv.id,
                        message=res.error_message
                        or f"Violated policy {inv.description}",
                        tool_name=tool_name,
                        args=args,
                        on_violation=inv.on_violation,
                    )
        return None

    def wrap_tool(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        resource_id_param: str | None = None,
    ) -> Callable[..., Any]:
        """Wraps a tool handler with fail-closed invariant interceptors."""
        is_async = inspect.iscoroutinefunction(handler)

        if is_async:

            @functools.wraps(handler)
            async def async_guarded(*args: Any, **kwargs: Any) -> Any:
                call_args = self._resolve_args(handler, args, kwargs)
                blocked_payload = self.check_invariants(tool_name, call_args)
                if blocked_payload is not None:
                    return blocked_payload

                # Execute original handler
                result = await handler(*args, **kwargs)

                # Record in workflow history on success
                res_id = (
                    call_args.get(resource_id_param)
                    if resource_id_param
                    else call_args.get("invoice_id")
                )
                self.context.record_call(tool_name, call_args, resource_id=res_id)
                return result

            return async_guarded
        else:

            @functools.wraps(handler)
            def sync_guarded(*args: Any, **kwargs: Any) -> Any:
                call_args = self._resolve_args(handler, args, kwargs)
                blocked_payload = self.check_invariants(tool_name, call_args)
                if blocked_payload is not None:
                    return blocked_payload

                # Execute original handler
                result = handler(*args, **kwargs)

                # Record in workflow history on success
                res_id = (
                    call_args.get(resource_id_param)
                    if resource_id_param
                    else call_args.get("invoice_id")
                )
                self.context.record_call(tool_name, call_args, resource_id=res_id)
                return result

            return sync_guarded

    def wrap_tool_async(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        resource_id_param: str | None = None,
    ) -> Callable[..., Any]:
        """Explicit async wrapper variant for wrap_tool."""
        return self.wrap_tool(tool_name, handler, resource_id_param=resource_id_param)

    @staticmethod
    def _resolve_args(
        handler: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Maps positional and keyword args to a unified dictionary using function signature."""
        result: dict[str, Any] = dict(kwargs)
        try:
            sig = inspect.signature(handler)
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            for k, v in bound.arguments.items():
                if k == "args" and isinstance(v, tuple):
                    continue
                if k == "kwargs" and isinstance(v, dict):
                    result.update(v)
                elif k not in ("self", "cls"):
                    result[k] = v
        except (TypeError, ValueError):
            pass
        return result
