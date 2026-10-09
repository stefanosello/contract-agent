"""Durable request identity and asynchronous approval recovery (C1)."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from contract_agent.compiler.models import AgentState
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.conversational import BaseConversationalAgent
from contract_agent.runtime.guards import GuardInterceptor


class CreditAgent(BaseConversationalAgent):
    def _resolve_tool_call(
        self, message: str, executed_in_turn: set[str]
    ) -> tuple[str | None, dict[str, Any]]:
        if not executed_in_turn:
            return "grant_account_credit", {
                "account_id": "ACC-990", "amount": 100.0, "reason": "Loyalty credit"
            }
        return None, {}


def make_agent() -> CreditAgent:
    contract = ContractParser.from_file(
        Path("tests/fixtures/benchmarks/04_conversational_service.contract.yaml")
    )
    tools = SimpleNamespace(grant_account_credit=Mock(return_value={"credit_id": "C1"}))
    return CreditAgent(tools, GuardInterceptor(contract, WorkflowContext()))


def suspend(agent: CreditAgent) -> str:
    agent.interceptor.context.record_call("lookup_account", {"account_id": "ACC-990"})
    result = agent.step("Please credit my account")
    assert result.requires_approval
    assert result.approval_token is not None
    agent.tools.grant_account_credit.assert_not_called()
    return result.approval_token


def test_default_store_and_request_survive_restart() -> None:
    agent = make_agent()
    token = suspend(agent)
    store = agent.interceptor.context.approval_store
    assert store.db_path != ":memory:"
    pending = store.requests.get(token, agent.session.session_id)
    assert pending["approval_type"] == "manager_signoff"
    assert pending["resource_id"] == "ACC-990"
    snapshot = agent.export_session()
    store.conn.close()

    fresh = make_agent()
    restored = CreditAgent.from_session(snapshot, fresh.tools, fresh.interceptor)
    assert restored.state == AgentState.AWAITING_APPROVAL
    restored.approve(token, "manager_dan")
    fresh.tools.grant_account_credit.assert_called_once()
    assert fresh.interceptor.context.has_approval("manager_signoff", "ACC-990")


def test_external_approval_requires_durable_transition() -> None:
    agent = make_agent()
    token = suspend(agent)
    with pytest.raises(ValueError, match="approved"):
        agent.resume_approval(token)
    agent.tools.grant_account_credit.assert_not_called()
    external = WorkflowContext()
    external.approval_store.grant_approval("manager_signoff", "ACC-990", "external_manager")
    assert agent.resume_approval(token).requires_approval is False
    agent.tools.grant_account_credit.assert_called_once()


def test_consumed_request_cannot_be_replayed_from_old_snapshot() -> None:
    agent = make_agent()
    token = suspend(agent)
    snapshot = agent.export_session()
    agent.approve(token, "manager")
    fresh = make_agent()
    with pytest.raises(ValueError, match="pending"):
        CreditAgent.from_session(snapshot, fresh.tools, fresh.interceptor)
    fresh.tools.grant_account_credit.assert_not_called()


def test_snapshot_cannot_change_persisted_tool_payload() -> None:
    agent = make_agent()
    token = suspend(agent)
    snapshot = deepcopy(agent.export_session())
    snapshot["pending_approvals"][token]["tool_args"]["amount"] = 999999.0
    fresh = make_agent()
    with pytest.raises(ValueError, match="match"):
        CreditAgent.from_session(snapshot, fresh.tools, fresh.interceptor)
    fresh.tools.grant_account_credit.assert_not_called()


def test_reset_cancels_durable_request() -> None:
    agent = make_agent()
    suspend(agent)
    snapshot = agent.export_session()
    agent.reset()
    fresh = make_agent()
    with pytest.raises(ValueError, match="pending"):
        CreditAgent.from_session(snapshot, fresh.tools, fresh.interceptor)
