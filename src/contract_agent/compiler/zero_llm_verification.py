"""Mandatory bounded property/mutation gate, independent of synthesized code."""

from __future__ import annotations

import time
from typing import Any

from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from contract_agent.compiler.models import TestFailureDetail, VerificationReport
from contract_agent.core.ast import ContractAST, Invariant, ToolContract
from contract_agent.core.exceptions import ContractAgentError
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import ApprovalStore, WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor
from contract_agent.testing.fuzzing import InvariantFuzzer
from contract_agent.testing.mutants import MutationAttack, run_mutation_safety_suite
from contract_agent.testing.verification_probes import boundary_probes


class ZeroLLMVerificationRunner:
    """Verify guard behavior against CEL decisions; never execute host handlers.

    Finite property checks are not a proof of arbitrary policy correctness. Each
    invariant is isolated so an earlier blocking rule cannot mask a guard bug.
    """

    def __init__(self, max_examples: int = 25) -> None:
        if max_examples < 1:
            raise ValueError("max_examples must be positive")
        self.max_examples = max_examples

    def run_verification(self, contract: ContractAST) -> VerificationReport:
        start = time.perf_counter()
        checks = 0
        mutations = 0
        active_id: str | None = None
        try:
            for invariant in contract.invariants:
                active_id = invariant.id
                CELEngine().compile_rule(invariant.rule)
                targets = [tool for tool in contract.tools
                           if invariant in contract.get_invariants_for_tool(tool.name)]
                if not targets:
                    raise ValueError(f"Invariant {invariant.id} has no applicable tool target")
                for tool in targets:
                    count, attacks = self._verify_invariant(contract, tool, invariant)
                    checks += count
                    mutations += attacks
        except Exception as exc:  # noqa: BLE001 - Any verification error must fail closed before synthesis.
            message = f"Zero-LLM verification failed ({active_id}): {exc}"
            return VerificationReport(
                passed=False, total_tests=checks + 1, passed_tests=checks, failed_tests=1,
                failures=[TestFailureDetail(test_name="zero_llm_gate", assertion_error=message,
                                            cel_invariant_id=active_id)],
                execution_time_seconds=time.perf_counter() - start, raw_output=message,
            )
        return VerificationReport(
            passed=True, total_tests=checks + mutations, passed_tests=checks + mutations,
            execution_time_seconds=time.perf_counter() - start,
            raw_output=f"Zero-LLM gate: {checks} property checks; {mutations} mutation attacks trapped",
        )

    def _verify_invariant(
        self, contract: ContractAST, tool: ToolContract, invariant: Invariant
    ) -> tuple[int, int]:
        isolated = contract.model_copy(update={"invariants": [invariant]})
        store = ApprovalStore(":memory:")
        context = WorkflowContext(approval_store=store)
        engine = CELEngine()
        interceptor = GuardInterceptor(isolated, context)
        calls: list[dict[str, Any]] = []
        attacks: list[MutationAttack] = []
        checks = 0

        def backend(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"executed": True}

        guarded = interceptor.wrap_tool(tool.name, backend)

        def check(args: dict[str, Any], with_history: bool = False) -> None:
            nonlocal checks
            context.call_history.clear()
            if with_history:
                self._seed_history(contract, tool.name, args, context)
            calls.clear()
            allowed = engine.evaluate_rule(invariant.rule, args, context)
            try:
                guarded(**args)
            except ContractAgentError:
                assert not allowed, "Guard rejected a CEL-permitted action"
            assert bool(calls) == allowed, "Guard execution disagrees with CEL decision"
            checks += 1
            if not allowed and not with_history and len(attacks) < 64:
                attacks.append(MutationAttack(f"{invariant.id}-{len(attacks)}", tool.name, args))

        try:
            for args in boundary_probes(contract, tool, invariant):
                check(args)
                check(args, with_history=True)

            strategy = InvariantFuzzer().strategy_for_json_schema(tool.parameters, tool.name)

            @settings(max_examples=self.max_examples, derandomize=True, database=None,
                      deadline=None, phases=(Phase.generate,))
            @given(args=strategy, with_history=st.booleans())
            def property_check(args: dict[str, Any], with_history: bool) -> None:
                check(args, with_history)

            property_check()
            context.call_history.clear()
            calls.clear()
            if attacks:
                report = run_mutation_safety_suite(interceptor, {tool.name: backend}, attacks)
                assert report.total_attacks == len(attacks), "Mutation attacks were skipped"
                assert report.passed and not calls, "Mutation attack escaped the guard"
            return checks, len(attacks)
        finally:
            store.conn.close()

    @staticmethod
    def _seed_history(
        contract: ContractAST, tool_name: str, args: dict[str, Any], context: WorkflowContext
    ) -> None:
        for scenario in contract.scenarios:
            for step in scenario.expected_flow:
                if step.tool_call == tool_name:
                    break
                if step.tool_call is not None:
                    prior_args = dict(step.with_args or {})
                    for key in ("invoice_id", "account_id", "resource_id"):
                        if key in prior_args and key in args:
                            prior_args[key] = args[key]
                    context.record_call(step.tool_call, prior_args)
