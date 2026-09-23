"""Runtime guard interceptor enforcing CEL invariants on agent tool calls."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Dict, List, Optional

from contract_agent.core.ast import ContractAST, Invariant
from contract_agent.core.exceptions import ApprovalRequiredError, InvariantViolationError
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext


class GuardInterceptor:
    """Intercepts tool executions, evaluating CEL invariants before underlying handlers run."""

    def __init__(
        self,
        contract: ContractAST,
        context: Optional[WorkflowContext] = None,
        cel_engine: Optional[CELEngine] = None,
    ) -> None:
        self.contract = contract
        self.context = context or WorkflowContext()
        self.cel_engine = cel_engine or CELEngine()

    def get_invariants_for_tool(self, tool_name: str) -> List[Invariant]:
        """Returns invariants that apply to this tool."""
        return self.contract.get_invariants_for_tool(tool_name)

    def check_invariants(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Evaluates all applicable invariants. Raises InvariantViolationError if any fail."""
        invariants = self.get_invariants_for_tool(tool_name)

        for inv in invariants:
            res = self.cel_engine.evaluate_invariant(inv, tool_name, args, self.context)
            if not res.is_valid:
                # Check if failure was due to missing approval
                if "has_approval" in inv.rule:
                    resource_id = str(args.get("invoice_id") or args.get("resource_id") or "unknown")
                    raise ApprovalRequiredError(
                        invariant_id=inv.id,
                        tool_name=tool_name,
                        approval_type="manager_signoff",
                        resource_id=resource_id,
                        args=args,
                    )
                raise InvariantViolationError(
                    invariant_id=inv.id,
                    message=res.error_message or f"Violated policy {inv.description}",
                    tool_name=tool_name,
                    args=args,
                    on_violation=inv.on_violation,
                )

    def wrap_tool(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        resource_id_param: Optional[str] = None,
    ) -> Callable[..., Any]:
        """Wraps a tool handler with fail-closed invariant interceptors."""
        is_async = inspect.iscoroutinefunction(handler)

        if is_async:
            @functools.wraps(handler)
            async def async_guarded(*args: Any, **kwargs: Any) -> Any:
                call_args = self._resolve_args(handler, args, kwargs)
                self.check_invariants(tool_name, call_args)

                # Execute original handler
                result = await handler(*args, **kwargs)

                # Record in workflow history on success
                res_id = call_args.get(resource_id_param) if resource_id_param else call_args.get("invoice_id")
                self.context.record_call(tool_name, call_args, resource_id=res_id)
                return result

            return async_guarded
        else:
            @functools.wraps(handler)
            def sync_guarded(*args: Any, **kwargs: Any) -> Any:
                call_args = self._resolve_args(handler, args, kwargs)
                self.check_invariants(tool_name, call_args)

                # Execute original handler
                result = handler(*args, **kwargs)

                # Record in workflow history on success
                res_id = call_args.get(resource_id_param) if resource_id_param else call_args.get("invoice_id")
                self.context.record_call(tool_name, call_args, resource_id=res_id)
                return result

            return sync_guarded

    @staticmethod
    def _resolve_args(
        handler: Callable[..., Any], args: tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maps positional and keyword args to a unified dictionary using function signature."""
        result: Dict[str, Any] = dict(kwargs)
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
        except Exception:
            pass
        return result
