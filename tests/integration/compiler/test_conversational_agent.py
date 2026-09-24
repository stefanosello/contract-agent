"""Integration tests for multi-turn dialogue, message history, and session reset (T008)."""

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
def compiled_agent_module():
    """Compiles and dynamically loads the conversational agent and mock tools."""
    contract_file = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(contract_file)

    interface_code = generate_interface_code(ast)
    mocks_code = generate_mocks_code(ast)
    agent_code = generate_default_conversational_agent(ast)

    # 1. Execute interface
    interface_ns: dict[str, object] = {}
    exec(interface_code, interface_ns)  # noqa: S102

    # 2. Register mock module so import dist.interface succeeds
    fake_dist = types.ModuleType("dist")
    fake_interface = types.ModuleType("dist.interface")
    fake_interface.AgentToolsProtocol = interface_ns["AgentToolsProtocol"]
    fake_dist.interface = fake_interface
    import sys
    sys.modules["dist"] = fake_dist
    sys.modules["dist.interface"] = fake_interface

    # 3. Execute mocks
    mocks_ns: dict[str, object] = {
        "AgentToolsProtocol": interface_ns["AgentToolsProtocol"]
    }
    exec(mocks_code, mocks_ns)  # noqa: S102

    # 4. Execute agent code
    agent_ns: dict[str, object] = {
        "AgentToolsProtocol": interface_ns["AgentToolsProtocol"]
    }
    exec(agent_code, agent_ns)  # noqa: S102

    return {
        "ast": ast,
        "AgentClass": agent_ns["BillingDisputeAgent"],
        "MockToolsClass": mocks_ns["MockAgentTools"],
    }


def test_conversational_multi_turn_dialogue(compiled_agent_module) -> None:
    ast = compiled_agent_module["ast"]
    AgentClass = compiled_agent_module["AgentClass"]
    MockToolsClass = compiled_agent_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    assert agent.state == AgentState.IDLE
    assert len(agent.session.messages) == 0

    # Turn 1
    reply1 = agent.chat("Hi, I have a question about my invoice.")
    assert len(reply1) > 0
    assert agent.state == AgentState.AWAITING_INPUT
    assert len(agent.session.messages) == 2  # user + assistant

    # Turn 2
    reply2 = agent.chat("Can you check invoice INV-101?")
    assert len(reply2) > 0
    assert agent.state == AgentState.AWAITING_INPUT
    assert len(agent.session.messages) == 4


@pytest.mark.asyncio
async def test_conversational_streaming(compiled_agent_module) -> None:
    ast = compiled_agent_module["ast"]
    AgentClass = compiled_agent_module["AgentClass"]
    MockToolsClass = compiled_agent_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    events = []
    async for event in agent.stream("Hello there!"):
        events.append(event)

    event_types = [e.type for e in events]
    assert ConversationEventType.TURN_COMPLETE in event_types
    assert ConversationEventType.TOKEN in event_types or ConversationEventType.STATE_CHANGE in event_types


def test_session_reset(compiled_agent_module) -> None:
    ast = compiled_agent_module["ast"]
    AgentClass = compiled_agent_module["AgentClass"]
    MockToolsClass = compiled_agent_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    agent.chat("First message")
    assert len(agent.session.messages) == 2

    agent.reset()
    assert len(agent.session.messages) == 0
    assert agent.state == AgentState.IDLE


def test_session_export_and_restore(compiled_agent_module) -> None:
    ast = compiled_agent_module["ast"]
    AgentClass = compiled_agent_module["AgentClass"]
    MockToolsClass = compiled_agent_module["MockToolsClass"]

    tools = MockToolsClass()
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=ast, context=context)
    agent = AgentClass(tools=tools, interceptor=interceptor)

    agent.chat("Testing persistence")
    assert len(agent.session.messages) == 2

    data = agent.export_session()
    assert data["session_id"] == agent.session.session_id
    assert len(data["messages"]) == 2

    restored = AgentClass.from_session(data, tools=tools, interceptor=interceptor)
    assert restored.session.session_id == agent.session.session_id
    assert len(restored.session.messages) == 2
    assert restored.state == agent.state
