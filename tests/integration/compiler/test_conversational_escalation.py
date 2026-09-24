"""Integration tests for conversational escalation pause and hybrid resumption (T017)."""

from __future__ import annotations

from pathlib import Path
import types

import pytest

from contract_agent.compiler.code_generator import (
    generate_interface_code,
    generate_mocks_code,
)
from contract_agent.compiler.models import AgentState
from contract_agent.compiler.templates import generate_default_conversational_agent
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor


@pytest.fixture
def escalation_system():
    """Sets up a compiled agent with mock tools for escalation integration tests."""
    contract_file = Path("tests/fixtures/benchmarks/04_conversational_service.contract.yaml")
    ast = ContractParser.from_file(contract_file)

    interface_code = generate_interface_code(ast)
    mocks_code = generate_mocks_code(ast)
    agent_code = generate_default_conversational_agent(ast)

    interface_ns: dict[str, object] = {}
    exec(interface_code, interface_ns)  # noqa: S102

    fake_dist = types.ModuleType("dist")
    fake_interface = types.ModuleType("dist.interface")
    fake_interface.AgentToolsProtocol = interface_ns["AgentToolsProtocol"]
    fake_dist.interface = fake_interface
    import sys
    sys.modules["dist"] = fake_dist
    sys.modules["dist.interface"] = fake_interface

    mocks_ns: dict[str, object] = {
        "AgentToolsProtocol": interface_ns["AgentToolsProtocol"]
    }
    exec(mocks_code, mocks_ns)  # noqa: S102

    agent_ns: dict[str, object] = {
        "AgentToolsProtocol": interface_ns["AgentToolsProtocol"]
    }
    exec(agent_code, agent_ns)  # noqa: S102

    tools = mocks_ns["MockAgentTools"]()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = agent_ns["ConversationalCustomerService"](tools=tools, interceptor=interceptor)

    return {
        "agent": agent,
        "tools": tools,
        "context": context,
    }


def test_programmatic_approval_flow(escalation_system) -> None:
    """Verify programmatic approve() resumes execution of suspended tool call."""
    agent = escalation_system["agent"]
    tools = escalation_system["tools"]

    # Step 1: lookup account so INV-002 sequence check passes
    agent.step("Please lookup account ACC-990")
    assert agent.state == AgentState.AWAITING_INPUT

    # Step 2: request high value credit ($100 > $50 limit -> INV-001 escalation)
    turn_result = agent.step("Please grant $100 credit on account ACC-990")
    assert turn_result.requires_approval is True
    assert agent.state == AgentState.AWAITING_APPROVAL
    assert turn_result.approval_token is not None

    # Step 3: programmatic approval via approve()
    approval_result = agent.approve(turn_result.approval_token, approver_id="manager_dan")
    assert approval_result.requires_approval is False
    assert agent.state == AgentState.AWAITING_INPUT
    assert "grant_account_credit" in approval_result.tools_executed

    # Assert underlying tool was actually executed
    executed_tools = [c["tool"] for c in tools.calls]
    assert "grant_account_credit" in executed_tools


def test_in_band_conversational_supervisor_approval(escalation_system) -> None:
    """Verify conversational supervisor sending 'Approved' resumes suspended execution."""
    agent = escalation_system["agent"]
    tools = escalation_system["tools"]

    # Step 1: lookup account
    agent.step("Please lookup account ACC-990")

    # Step 2: request high value credit
    turn_result = agent.step("Please grant $100 credit on account ACC-990")
    assert turn_result.requires_approval is True
    assert agent.state == AgentState.AWAITING_APPROVAL

    # Step 3: in-band supervisor message
    supervisor_turn = agent.step("Approved by supervisor")
    assert supervisor_turn.requires_approval is False
    assert agent.state == AgentState.AWAITING_INPUT
    assert "grant_account_credit" in supervisor_turn.tools_executed
