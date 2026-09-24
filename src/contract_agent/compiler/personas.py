"""Decoupled synthesizer personas and prompt templates for dual-synthesis."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_agent.compiler.models import VerificationReport
    from contract_agent.core.ast import ContractAST


AGENT_IMPLEMENTER_SYSTEM_PROMPT = """You are the Senior Agent Implementer persona in ContractAgent.
Your objective is to synthesize a stream-first conversational agent class in `dist/agent.py`.
Rules:
1. Bind strictly to `dist.interface.AgentToolsProtocol`.
2. Wrap all tool executions using `GuardInterceptor` from `contract_agent.runtime.guards`.
3. Implement core conversational methods: `stream(message)`, `step(message)`, `chat(message)`, `approve(token)`, `reset()`, `export_session()`, `from_session()`, and `execute_action()`.
4. Handle CEL invariant escalation scenarios (e.g. EscalationRequiredError, InvariantViolationError, blocked payloads) via state transitions.
5. Bound internal ReAct execution loop to prevent runaway iterations.
6. Output ONLY valid, executable Python code enclosed in a ```python block.
"""

ADVERSARIAL_TESTER_SYSTEM_PROMPT = """You are the Adversarial QA & Security persona in ContractAgent.
Your objective is to synthesize an adversarial test suite in `dist/test_contract.py` using pytest.
Rules:
1. Test all declared contract scenarios faithfully using `MockAgentTools` from `dist.mocks`.
2. Generate adversarial probe tests:
   - Boundary tests pushing invariants to limit values.
   - Out-of-order sequence bypass tests (calling dependent tools before prerequisite tools).
   - Malformed parameter values to verify fail-closed invariant trapping.
3. Assert that GuardInterceptor raises InvariantViolationError or EscalationRequiredError when policies are violated.
4. Output ONLY valid, executable Python code enclosed in a ```python block.
"""

REPAIR_SYNTHESIZER_SYSTEM_PROMPT = """You are the Autonomous Self-Healing Repair persona in ContractAgent.
Your objective is to inspect the current `agent.py` implementation, failing test assertions, and structured CEL invariant violations, then generate a complete, corrected replacement `agent.py`.
Rules:
1. Address the exact root cause identified in the test tracebacks and CEL violation diagnostics.
2. Preserve all existing state transitions and valid behaviors.
3. Output the FULL replacement code for `dist/agent.py` enclosed in a ```python block.
"""


def extract_code_block(raw_text: str) -> str:
    """Extracts python code from markdown code blocks or returns raw text."""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    match = re.search(pattern, raw_text, re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    return raw_text.strip() + "\n"


def build_implementer_prompt(ast: ContractAST) -> str:
    """Constructs prompt for the Agent Implementer persona."""
    tool_descriptions = "\n".join(
        f"- {t.name}: {t.description} (params: {list(t.parameters.get('properties', {}).keys())})"
        for t in ast.tools
    )
    invariants = "\n".join(
        f"- [{inv.id}] target: {inv.target} | rule: {inv.rule} | on_violation: {inv.on_violation}"
        for inv in ast.invariants
    )
    return f"""Synthesize the conversational stream-first agent implementation for '{ast.metadata.name}'.

Specification Summary:
Role: {ast.system.role if ast.system else 'Agent'}
Tools:
{tool_descriptions}

Invariants to enforce:
{invariants}

Generate class '{_to_camel_case(ast.metadata.name)}' with methods to initialize with (tools: AgentToolsProtocol, interceptor: GuardInterceptor) and support stream(message), step(message), chat(message), approve(token), reset(), export_session(), from_session(), and execute_action()."""


def build_tester_prompt(ast: ContractAST) -> str:
    """Constructs prompt for the Adversarial Tester persona."""
    scenarios = "\n".join(
        f"- [{s.id}] {s.title}: '{s.user_input}'"
        for s in ast.scenarios
    )
    invariants = "\n".join(
        f"- [{inv.id}] {inv.rule} ({inv.on_violation})"
        for inv in ast.invariants
    )
    return f"""Synthesize the adversarial test suite for '{ast.metadata.name}'.

Declared Scenarios:
{scenarios}

Contract Invariants:
{invariants}

Generate pytest test functions in test_contract.py testing declared scenarios and adversarial probes."""


def build_repair_prompt(
    ast: ContractAST, current_agent_code: str, report: VerificationReport
) -> str:
    """Constructs diagnostic repair prompt for the Self-Healing engine."""
    failures_summary: list[str] = []
    for f in report.failures:
        entry = f"Test '{f.test_name}' FAILED: {f.assertion_error}"
        if f.cel_invariant_id:
            entry += f"\n  -> CEL Invariant Violation [{f.cel_invariant_id}]: rule '{f.cel_violation_rule}'"
            entry += f"\n  -> Violated args: {f.cel_args}"
        failures_summary.append(entry)

    failures_text = "\n\n".join(failures_summary)

    return f"""The candidate agent for '{ast.metadata.name}' failed verification tests.

FAILURE DIAGNOSTICS:
{failures_text}

CURRENT AGENT CODE:
```python
{current_agent_code}
```

Please fix the agent code to satisfy 100% of invariant checks and test scenarios."""


def _to_camel_case(snake_str: str) -> str:
    """Converts snake_case to CamelCase."""
    components = snake_str.split("_")
    return "".join(x.capitalize() for x in components)
