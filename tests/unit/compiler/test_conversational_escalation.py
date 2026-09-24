"""Unit tests for approve() validation, tokens, and approval state transitions (T016)."""

from __future__ import annotations

import types
import uuid
from pathlib import Path

import pytest

from contract_agent.compiler.code_generator import (
    generate_interface_code,
    generate_mocks_code,
)
from contract_agent.compiler.models import AgentState, PendingApproval
from contract_agent.compiler.templates import generate_default_conversational_agent
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor


@pytest.fixture
def escalation_agent():
    """Sets up a compiled agent instance for escalation unit testing."""
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
    return agent


def test_approve_not_awaiting_approval_raises(escalation_agent) -> None:
    """Assert calling approve() when agent is IDLE raises ValueError."""
    assert escalation_agent.state == AgentState.IDLE
    with pytest.raises(ValueError, match="AWAITING_APPROVAL"):
        escalation_agent.approve("token-123")


def test_approve_unknown_token_raises(escalation_agent) -> None:
    """Assert calling approve() with invalid token raises KeyError."""
    escalation_agent.state = AgentState.AWAITING_APPROVAL
    with pytest.raises(KeyError, match="not found"):
        escalation_agent.approve("invalid-token")


def test_approve_already_approved_raises(escalation_agent) -> None:
    """Assert calling approve() on an already approved token raises ValueError."""
    escalation_agent.state = AgentState.AWAITING_APPROVAL
    token = str(uuid.uuid4())
    escalation_agent.session.pending_approvals[token] = PendingApproval(
        token=token,
        invariant_id="INV-001",
        tool_name="grant_account_credit",
        tool_args={"account_id": "ACC-1", "amount": 100.0, "reason": "Test"},
        status="approved",
    )
    with pytest.raises(ValueError, match="status 'approved'"):
        escalation_agent.approve(token)
