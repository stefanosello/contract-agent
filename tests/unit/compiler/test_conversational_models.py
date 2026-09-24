"""Unit tests for conversational data models and event schemas."""

from __future__ import annotations

from contract_agent.compiler.models import (
    AgentState,
    ConversationEvent,
    ConversationEventType,
    ConversationMessage,
    ConversationSession,
    ConversationTurnResult,
    MessageRole,
    PendingApproval,
)
from contract_agent.runtime.context import WorkflowContext


def test_agent_state_enum() -> None:
    states = [s.value for s in AgentState]
    assert "IDLE" in states
    assert "PROCESSING" in states
    assert "AWAITING_INPUT" in states
    assert "AWAITING_APPROVAL" in states
    assert "COMPLETED" in states
    assert "FAILED" in states


def test_conversation_event_type_enum() -> None:
    types = [t.value for t in ConversationEventType]
    assert "token" in types
    assert "thought" in types
    assert "tool_call_start" in types
    assert "tool_call_result" in types
    assert "state_change" in types
    assert "escalation_required" in types
    assert "turn_complete" in types
    assert "error" in types


def test_conversation_event_serialization() -> None:
    event = ConversationEvent(
        type=ConversationEventType.TOKEN,
        content="Hello world",
    )
    assert event.timestamp > 0
    data = event.model_dump_json()
    restored = ConversationEvent.model_validate_json(data)
    assert restored.type == ConversationEventType.TOKEN
    assert restored.content == "Hello world"


def test_conversation_message_and_roles() -> None:
    msg = ConversationMessage(
        role=MessageRole.USER,
        content="I need help with billing",
    )
    assert msg.id is not None
    assert msg.timestamp > 0
    assert msg.role == MessageRole.USER
    assert msg.content == "I need help with billing"
    json_data = msg.model_dump_json()
    restored = ConversationMessage.model_validate_json(json_data)
    assert restored.id == msg.id
    assert restored.role == MessageRole.USER


def test_pending_approval_serialization() -> None:
    approval = PendingApproval(
        invariant_id="INV-001",
        tool_name="issue_refund",
        tool_args={"amount": 150.0},
    )
    assert len(approval.token) > 0
    assert approval.status == "pending"
    json_data = approval.model_dump_json()
    restored = PendingApproval.model_validate_json(json_data)
    assert restored.token == approval.token
    assert restored.invariant_id == "INV-001"
    assert restored.tool_args["amount"] == 150.0


def test_conversation_session_lifecycle() -> None:
    session = ConversationSession()
    assert session.state == AgentState.IDLE
    assert len(session.messages) == 0

    session.messages.append(
        ConversationMessage(role=MessageRole.USER, content="Hello")
    )
    session.messages.append(
        ConversationMessage(role=MessageRole.ASSISTANT, content="Hi there!")
    )

    approval = PendingApproval(
        invariant_id="INV-002",
        tool_name="override_limit",
        tool_args={"user_id": "U123"},
    )
    session.pending_approvals[approval.token] = approval

    json_str = session.model_dump_json()
    restored = ConversationSession.model_validate_json(json_str)
    assert restored.session_id == session.session_id
    assert len(restored.messages) == 2
    assert approval.token in restored.pending_approvals


def test_conversation_turn_result() -> None:
    turn = ConversationTurnResult(
        reply="Refund processed",
        state=AgentState.IDLE,
        tools_executed=["process_refund"],
        requires_approval=False,
    )
    assert turn.reply == "Refund processed"
    assert turn.tools_executed == ["process_refund"]
    json_data = turn.model_dump_json()
    restored = ConversationTurnResult.model_validate_json(json_data)
    assert restored.reply == turn.reply


def test_workflow_context_session_extension() -> None:
    ctx = WorkflowContext(session_id="session-xyz", metadata={"channel": "web"})
    assert ctx.session_id == "session-xyz"
    assert ctx.metadata == {"channel": "web"}
