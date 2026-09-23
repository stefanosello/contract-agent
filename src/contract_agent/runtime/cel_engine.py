"""Google Common Expression Language (CEL) deterministic invariant evaluation engine."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import celpy
from celpy import celtypes

from contract_agent.core.ast import Invariant
from contract_agent.core.exceptions import ContractValidationError, InvariantViolationError
from contract_agent.runtime.context import WorkflowContext


@dataclass
class InvariantResult:
    """Result of an invariant evaluation."""
    invariant_id: str
    is_valid: bool
    evaluation_time_ms: float
    error_message: Optional[str] = None


class CELEngine:
    """Compiles and executes CEL invariant rules deterministically with zero LLM queries."""

    def __init__(self) -> None:
        self.env = celpy.Environment()
        self._compiled_cache: Dict[str, celpy.Runner] = {}

    def compile_rule(self, rule_str: str) -> celpy.Runner:
        """Compile a CEL rule expression into an executable program."""
        if rule_str not in self._compiled_cache:
            try:
                ast = self.env.compile(rule_str)
                # We register the standard extension functions
                functions: Dict[str, Callable[..., Any]] = {
                    # Custom workflow functions
                    "has_approval": self._make_has_approval_fn(),
                    "called_before": self._make_called_before_fn(),
                    "call_count": self._make_call_count_fn(),
                    # String extensions
                    "trim": lambda s: celtypes.StringType(str(s).strip()),
                    "lower": lambda s: celtypes.StringType(str(s).lower()),
                    "upper": lambda s: celtypes.StringType(str(s).upper()),
                }
                prgm = self.env.program(ast, functions=functions)
                self._compiled_cache[rule_str] = prgm
            except Exception as exc:
                raise ContractValidationError(
                    f"CEL rule compilation failed for '{rule_str}': {exc}"
                ) from exc
        return self._compiled_cache[rule_str]

    def evaluate_rule(
        self,
        rule_str: str,
        args: Dict[str, Any],
        context: Optional[WorkflowContext] = None,
    ) -> bool:
        """Evaluate a compiled CEL rule against tool args and workflow context."""
        prgm = self.compile_rule(rule_str)
        wf_ctx = context or WorkflowContext()

        # Build activation context
        activation = {
            "args": celpy.json_to_cel(args),
            "workflow": celpy.json_to_cel({"id": "current_workflow"}),
            "_wf_instance": wf_ctx,
        }

        try:
            # Inject context into functions dynamically via thread/instance reference
            self._active_context = wf_ctx
            result = prgm.evaluate(activation)
            return bool(result)
        except Exception as exc:
            # CEL evaluation error fails closed
            raise InvariantViolationError(
                invariant_id="CEL_EVAL_ERROR",
                message=f"Evaluation failed closed: {exc}",
                tool_name="unknown",
                args=args,
            ) from exc

    def evaluate_invariant(
        self,
        invariant: Invariant,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[WorkflowContext] = None,
    ) -> InvariantResult:
        """Evaluates a single invariant against tool args and context."""
        start_time = time.perf_counter()
        wf_ctx = context or WorkflowContext()

        try:
            is_valid = self.evaluate_rule(invariant.rule, args, wf_ctx)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            if not is_valid:
                return InvariantResult(
                    invariant_id=invariant.id,
                    is_valid=False,
                    evaluation_time_ms=duration_ms,
                    error_message=f"Rule evaluated to False: '{invariant.rule}' ({invariant.description})",
                )
            return InvariantResult(
                invariant_id=invariant.id,
                is_valid=True,
                evaluation_time_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return InvariantResult(
                invariant_id=invariant.id,
                is_valid=False,
                evaluation_time_ms=duration_ms,
                error_message=f"Invariant evaluation error (failed closed): {exc}",
            )

    def _make_has_approval_fn(self) -> Callable[..., celtypes.BoolType]:
        """Supports both has_approval(type, id) and workflow.has_approval(type, id)."""
        def _fn(*args: Any) -> celtypes.BoolType:
            ctx = getattr(self, "_active_context", None)
            if not ctx:
                return celtypes.BoolType(False)
            if len(args) == 2:
                appr_type, res_id = str(args[0]), str(args[1])
            elif len(args) == 3:
                appr_type, res_id = str(args[1]), str(args[2])
            else:
                return celtypes.BoolType(False)
            return celtypes.BoolType(ctx.has_approval(appr_type, res_id))
        return _fn

    def _make_called_before_fn(self) -> Callable[..., celtypes.BoolType]:
        """Supports both called_before(prior, target, res_id) and workflow.called_before(...)."""
        def _fn(*args: Any) -> celtypes.BoolType:
            ctx = getattr(self, "_active_context", None)
            if not ctx:
                return celtypes.BoolType(False)
            if len(args) == 2:
                prior, target = str(args[0]), str(args[1])
                res_id = None
            elif len(args) == 3:
                if isinstance(args[0], (celtypes.MapType, dict)):
                    prior, target = str(args[1]), str(args[2])
                    res_id = None
                else:
                    prior, target, res_id = str(args[0]), str(args[1]), str(args[2])
            elif len(args) >= 4:
                prior, target, res_id = str(args[1]), str(args[2]), str(args[3])
            else:
                return celtypes.BoolType(False)
            return celtypes.BoolType(ctx.called_before(prior, target, res_id))
        return _fn

    def _make_call_count_fn(self) -> Callable[..., celtypes.IntType]:
        """Supports both call_count(tool_name) and workflow.call_count(tool_name)."""
        def _fn(*args: Any) -> celtypes.IntType:
            ctx = getattr(self, "_active_context", None)
            if not ctx:
                return celtypes.IntType(0)
            tool_name = str(args[0]) if len(args) == 1 else str(args[1])
            return celtypes.IntType(ctx.call_count(tool_name))
        return _fn
