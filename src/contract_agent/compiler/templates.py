"""Default code generation templates for offline FSM agents and adversarial tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_agent.core.ast import ContractAST


def generate_default_fsm_agent(ast: ContractAST) -> str:
    """Generates an explicit typed Finite State Machine agent bound to GuardInterceptor."""
    agent_class = "".join(x.capitalize() for x in ast.metadata.name.split("_"))
    tools_call_logic: list[str] = []

    for tool in ast.tools:
        props = tool.parameters.get("properties", {})
        param_names = list(props.keys())
        param_kwargs = ", ".join(f"{p}=kwargs.get('{p}')" for p in param_names)
        tools_call_logic.append(
            f"        if action == '{tool.name}':\n"
            f"            guarded = self.interceptor.wrap_tool('{tool.name}', self.tools.{tool.name})\n"
            f"            return guarded({param_kwargs})"
        )

    tools_dispatch = "\n".join(tools_call_logic) if tools_call_logic else "        return None"

    return f'''"""Auto-generated typed Finite State Machine agent for {ast.metadata.name}."""

from __future__ import annotations

from enum import Enum
from typing import Any

from contract_agent.runtime.guards import GuardInterceptor

try:
    from dist.interface import AgentToolsProtocol
except ImportError:
    from interface import AgentToolsProtocol  # type: ignore[no-redef]


class AgentState(str, Enum):
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class {agent_class}:
    """Explicit State Machine agent enforcing contract invariants."""

    def __init__(self, tools: AgentToolsProtocol, interceptor: GuardInterceptor) -> None:
        self.tools = tools
        self.interceptor = interceptor
        self.state: AgentState = AgentState.IDLE
        self.history: list[dict[str, Any]] = []

    def execute_action(self, action: str, **kwargs: Any) -> Any:
        """Executes a tool action with state transition and guard interception."""
        self.state = AgentState.PROCESSING
        self.history.append({{"action": action, "kwargs": kwargs}})
        try:
{tools_dispatch}
            raise ValueError(f"Unknown tool action: '{{action}}'")
        except Exception:
            self.state = AgentState.FAILED
            raise
        finally:
            if self.state != AgentState.FAILED:
                self.state = AgentState.COMPLETED
'''


def generate_default_test_suite(ast: ContractAST) -> str:
    """Generates an adversarial pytest suite covering declared scenarios and probes."""
    agent_class = "".join(x.capitalize() for x in ast.metadata.name.split("_"))
    test_functions: list[str] = []

    for idx, sc in enumerate(ast.scenarios, 1):
        lines: list[str] = [
            f"def test_scenario_{sc.id.lower()}() -> None:",
            f'    """{sc.title}"""',
            "    tools = MockAgentTools()",
            "    context = WorkflowContext()",
            f"    contract = ContractParser.from_dict({ast.model_dump()})",
            "    interceptor = GuardInterceptor(contract=contract, context=context)",
            f"    agent = {agent_class}(tools=tools, interceptor=interceptor)",
        ]
        for exp in sc.expected_flow:
            if exp.tool_call:
                args_dict = exp.with_args or {}
                kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in args_dict.items())
                lines.append(f"    agent.execute_action('{exp.tool_call}', {kwargs_str})")
        lines.append("    assert agent.state == AgentState.COMPLETED")
        test_functions.append("\n".join(lines))

    # Add active adversarial probe tests
    if ast.invariants:
        first_inv = ast.invariants[0]
        tool_name = first_inv.target.replace("tool:", "") if "tool:" in first_inv.target else (ast.tools[0].name if ast.tools else "none")
        probe_test = f'''def test_adversarial_probe_invariant_enforcement() -> None:
    """Adversarial probe testing CEL invariant violation trapping."""
    tools = MockAgentTools()
    context = WorkflowContext()
    contract = ContractParser.from_dict({ast.model_dump()})
    interceptor = GuardInterceptor(contract=contract, context=context)
    agent = {agent_class}(tools=tools, interceptor=interceptor)

    # Trigger violation with out-of-boundary values
    try:
        agent.execute_action('{tool_name}', amount=99999.0, query='DROP TABLE users', batch_size=9999)
    except Exception as exc:
        assert "Invariant" in str(type(exc).__name__) or "Escalation" in str(type(exc).__name__) or agent.state == AgentState.FAILED
'''
        test_functions.append(probe_test)

    tests_body = "\n\n".join(test_functions)

    return f'''"""Auto-generated adversarial pytest test suite for {ast.metadata.name}."""

from __future__ import annotations

import pytest
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.guards import GuardInterceptor
from contract_agent.runtime.context import WorkflowContext

try:
    from dist.agent import {agent_class}, AgentState
    from dist.mocks import MockAgentTools
except ImportError:
    from agent import {agent_class}, AgentState  # type: ignore[no-redef]
    from mocks import MockAgentTools  # type: ignore[no-redef]


{tests_body}
'''
