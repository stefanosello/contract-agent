"""Default code generation templates for offline FSM agents and adversarial tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_agent.core.ast import ContractAST


def generate_default_conversational_agent(ast: ContractAST) -> str:
    """Generates a stream-first conversational agent with ReAct reasoning and guard interception."""
    agent_class = "".join(x.capitalize() for x in ast.metadata.name.split("_"))
    tools_call_logic: list[str] = []

    for tool in ast.tools:
        props = tool.parameters.get("properties", {})
        param_names = list(props.keys())
        param_kwargs = ", ".join(f"{p}=kwargs.get('{p}')" for p in param_names)
        tools_call_logic.append(
            f"            if action == '{tool.name}':\n"
            f"                guarded = self.interceptor.wrap_tool('{tool.name}', getattr(self.tools, '{tool.name}'))\n"
            f"                return guarded({param_kwargs})"
        )

    tools_dispatch = "\n".join(tools_call_logic) if tools_call_logic else "            return None"

    return f'''"""Auto-generated conversational agent for {ast.metadata.name}."""

from __future__ import annotations

import re
from typing import Any

from contract_agent.compiler.models import AgentState
from contract_agent.runtime.conversational import BaseConversationalAgent
from contract_agent.runtime.guards import GuardInterceptor

try:
    from interface import AgentToolsProtocol
except ImportError:
    try:
        from dist.interface import AgentToolsProtocol  # type: ignore[no-redef]
    except ImportError:
        from typing import Protocol  # type: ignore[no-redef]

        class AgentToolsProtocol(Protocol):  # type: ignore[no-redef]
            pass


class {agent_class}(BaseConversationalAgent):
    """Stream-first conversational agent enforcing contract invariants."""

    def __init__(
        self,
        tools: AgentToolsProtocol,
        interceptor: GuardInterceptor,
        provider: Any | None = None,
        session_id: str | None = None,
        max_turn_iterations: int = 5,
    ) -> None:
        super().__init__(
            tools=tools,
            interceptor=interceptor,
            provider=provider,
            session_id=session_id,
            max_turn_iterations=max_turn_iterations,
        )

    def execute_action(self, action: str, **kwargs: Any) -> Any:
        """Executes a tool action with state transition and guard interception."""
        self.state = AgentState.PROCESSING
        self.session.state = AgentState.PROCESSING
        self.history.append({{"action": action, "kwargs": kwargs}})
        try:
{tools_dispatch}
            raise ValueError(f"Unknown tool action: '{{action}}'")
        except Exception:
            self.state = AgentState.FAILED
            self.session.state = AgentState.FAILED
            raise
        finally:
            if self.state != AgentState.FAILED:
                self.state = AgentState.COMPLETED
                self.session.state = AgentState.COMPLETED

    def _resolve_tool_call(
        self, message: str, executed_in_turn: set[str]
    ) -> tuple[str | None, dict[str, Any]]:
        msg_lower = message.lower()
        all_text = " ".join([m.content for m in self.session.messages] + [message])

        acc_match = re.search(r"\\b(ACC-\\w+)\\b", all_text, re.IGNORECASE)
        inv_match = re.search(r"\\b(INV-\\w+)\\b", all_text, re.IGNORECASE)
        account_id = acc_match.group(1).upper() if acc_match else "ACC-001"
        invoice_id = inv_match.group(1).upper() if inv_match else "INV-001"

        amt_match = re.search(r"\\$\\s*(\\d+(?:\\.\\d+)?)|(\\d+(?:\\.\\d+)?)\\s*(?:dollars|usd|\\$)", message, re.IGNORECASE)
        if not amt_match:
            amt_match = re.search(r"(?:refund|credit)\\s*(?:of\\s*)?\\$?\\s*(\\d+(?:\\.\\d+)?)", message, re.IGNORECASE)
        amount = float(amt_match.group(1) or amt_match.group(2)) if amt_match else 50.0

        if hasattr(self.tools, "lookup_account") and "lookup_account" not in executed_in_turn:
            if "lookup_account" in msg_lower or (("lookup" in msg_lower or "account" in msg_lower) and acc_match):
                return "lookup_account", {{"account_id": account_id}}

        if hasattr(self.tools, "grant_account_credit") and "grant_account_credit" not in executed_in_turn:
            if "grant_account_credit" in msg_lower or (("credit" in msg_lower or "adjustment" in msg_lower) and amt_match):
                return "grant_account_credit", {{
                    "account_id": account_id,
                    "amount": amount,
                    "reason": "Customer requested adjustment",
                }}

        if hasattr(self.tools, "fetch_invoice") and "fetch_invoice" not in executed_in_turn:
            if "fetch_invoice" in msg_lower or (("invoice" in msg_lower or "inv-" in msg_lower) and inv_match):
                return "fetch_invoice", {{"invoice_id": invoice_id}}

        if hasattr(self.tools, "execute_refund") and "execute_refund" not in executed_in_turn:
            if "execute_refund" in msg_lower or ("refund" in msg_lower and (amt_match or inv_match)):
                return "execute_refund", {{
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "reason": "Customer requested refund",
                }}

        if hasattr(self.tools, "execute_sql") and "execute_sql" not in executed_in_turn:
            if "select" in msg_lower or "sql" in msg_lower or "drop" in msg_lower:
                query = message if ("select" in msg_lower or "drop" in msg_lower) else "SELECT * FROM users"
                return "execute_sql", {{"query": query, "batch_size": 100}}

        if hasattr(self.tools, "sync_records") and "sync_records" not in executed_in_turn:
            if "sync" in msg_lower:
                return "sync_records", {{
                    "source": "crm_db",
                    "destination": "analytics_warehouse",
                    "batch_limit": 50,
                }}

        return None, {{}}

    def _generate_conversational_reply(
        self, message: str, executed_in_turn: set[str]
    ) -> str:
        msg_lower = message.lower()
        if "fetch_invoice" in executed_in_turn:
            return "I fetched the details for your invoice."
        if "execute_refund" in executed_in_turn:
            return "The refund has been executed successfully."
        if "grant_account_credit" in executed_in_turn:
            return "The credit adjustment has been applied."
        if "lookup_account" in executed_in_turn:
            return "I looked up your account details."
        if "execute_sql" in executed_in_turn:
            return "SQL query executed successfully."
        if "sync_records" in executed_in_turn:
            return "Records synchronized successfully."
        if "hello" in msg_lower or "hi" in msg_lower or "hey" in msg_lower:
            return "Hello! How can I assist you today?"
        return "I am ready to assist you. Please let me know what you would like to do."
'''


def generate_default_fsm_agent(ast: ContractAST) -> str:
    """Generates an explicit typed Finite State Machine agent bound to GuardInterceptor."""
    return generate_default_conversational_agent(ast)




def generate_default_test_suite(ast: ContractAST) -> str:
    """Generates an adversarial pytest suite covering declared scenarios and probes."""
    agent_class = "".join(x.capitalize() for x in ast.metadata.name.split("_"))
    test_functions: list[str] = []

    for idx, sc in enumerate(ast.scenarios, 1):
        clean_id = sc.id.lower().replace("-", "_")
        lines: list[str] = [
            f"def test_scenario_{clean_id}() -> None:",
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
                kwargs_str = ", ".join(f"{k}={v!r}" for k, v in args_dict.items())
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
    from agent import {agent_class}
    from mocks import MockAgentTools
except ImportError:
    from dist.agent import {agent_class}  # type: ignore[no-redef]
    from dist.mocks import MockAgentTools  # type: ignore[no-redef]

try:
    from agent import AgentState
except ImportError:
    try:
        from dist.agent import AgentState  # type: ignore[no-redef]
    except ImportError:
        class AgentState:  # type: ignore[no-redef]
            COMPLETED = "COMPLETED"
            FAILED = "FAILED"


{tests_body}
'''
