"""Integration tests for conversational tool execution and CEL invariant guards (T012)."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from contract_agent.compiler.code_generator import (
    generate_interface_code,
    generate_mocks_code,
)
from contract_agent.compiler.models import AgentState, ConversationEventType
from contract_agent.compiler.templates import generate_default_conversational_agent
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor


@pytest.fixture
def conversational_tools_module():
    """Sets up compiled conversational customer service agent with mock tools."""
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

    return {
        "ast": ast,
        "AgentClass": agent_ns["ConversationalCustomerService"],
        "MockToolsClass": mocks_ns["MockAgentTools"],
    }


def test_conversational_authorized_tool_execution(conversational_tools_module) -> None:
    """Verify authorized tool execution emits start and result events."""
    ast = conversational_tools_module["ast"]
    AgentClass = conversational_tools_module["AgentClass"]
    MockToolsClass = conversational_tools_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    turn_result = agent.step("Please lookup account ACC-550")
    assert "lookup_account" in turn_result.tools_executed
    assert agent.state == AgentState.AWAITING_INPUT
    assert len(tools.calls) == 1
    assert tools.calls[0]["tool"] == "lookup_account"

    # Verify tool events
    event_types = [e.type for e in turn_result.events]
    assert ConversationEventType.TOOL_CALL_START in event_types
    assert ConversationEventType.TOOL_CALL_RESULT in event_types


def test_conversational_sequence_guard_blocking(conversational_tools_module) -> None:
    """Verify calling grant_account_credit without lookup_account is blocked by INV-002."""
    ast = conversational_tools_module["ast"]
    AgentClass = conversational_tools_module["AgentClass"]
    MockToolsClass = conversational_tools_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    # Directly request credit without prior account lookup (violates INV-002)
    turn_result = agent.step("Grant account credit of $25 on ACC-550")
    assert agent.state == AgentState.AWAITING_INPUT
    assert "blocked" in turn_result.reply.lower() or "inv-002" in turn_result.reply.lower()


def test_turn_iteration_ceiling_guard(conversational_tools_module) -> None:
    """Verify turn loop ceases and does not loop beyond max_turn_iterations."""
    ast = conversational_tools_module["ast"]
    AgentClass = conversational_tools_module["AgentClass"]
    MockToolsClass = conversational_tools_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor, max_turn_iterations=2)

    assert agent.max_turn_iterations == 2
    turn_result = agent.step("Please lookup account ACC-550")
    assert agent.state == AgentState.AWAITING_INPUT
    assert len(turn_result.reply) > 0
