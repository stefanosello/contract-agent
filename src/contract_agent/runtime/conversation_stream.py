"""Turn execution stream generator for conversational agents."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from contract_agent.compiler.models import (
    AgentState,
    ConversationEvent,
    ConversationEventType,
    ConversationMessage,
    MessageRole,
    PendingApproval,
)
from contract_agent.core.exceptions import (
    EscalationRequiredError,
    InvariantViolationError,
)


async def execute_turn_stream(
    agent: Any, message: str
) -> AsyncIterator[ConversationEvent]:
    """Asynchronously processes user message, yielding incremental turn events."""
    if agent.state == AgentState.AWAITING_APPROVAL:
        pending_tokens = list(agent.session.pending_approvals.keys())
        if pending_tokens:
            token = pending_tokens[-1]
            msg_lower = message.strip().lower()
            if "approve" in msg_lower or token.lower() in msg_lower or "yes" in msg_lower:
                res = agent.approve(token, approver_id="supervisor")
                for evt in res.events:
                    yield evt
                return
        yield ConversationEvent(
            type=ConversationEventType.ESCALATION_REQUIRED,
            content="Action paused: awaiting manager approval.",
            new_state=AgentState.AWAITING_APPROVAL,
        )
        yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
        return

    agent.state = AgentState.PROCESSING
    agent.session.state = AgentState.PROCESSING
    agent.session.messages.append(
        ConversationMessage(role=MessageRole.USER, content=message)
    )
    yield ConversationEvent(
        type=ConversationEventType.STATE_CHANGE,
        new_state=AgentState.PROCESSING,
    )

    turn_iteration = 0
    executed_in_turn: set[str] = set()
    turn_tool_calls: list[dict[str, Any]] = []

    while turn_iteration < agent.max_turn_iterations:
        turn_iteration += 1
        tool_name, tool_args = agent._resolve_tool_call(message, executed_in_turn)

        if tool_name is None:
            reply = agent._generate_conversational_reply(message, executed_in_turn)
            agent.session.messages.append(
                ConversationMessage(
                    role=MessageRole.ASSISTANT,
                    content=reply,
                    tool_calls=turn_tool_calls,
                )
            )
            yield ConversationEvent(type=ConversationEventType.TOKEN, content=reply)
            agent.state = AgentState.AWAITING_INPUT
            agent.session.state = AgentState.AWAITING_INPUT
            yield ConversationEvent(
                type=ConversationEventType.STATE_CHANGE,
                new_state=AgentState.AWAITING_INPUT,
            )
            yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
            return

        executed_in_turn.add(tool_name)
        yield ConversationEvent(
            type=ConversationEventType.TOOL_CALL_START,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        guarded = agent.interceptor.wrap_tool(tool_name, getattr(agent.tools, tool_name))
        try:
            tool_result = guarded(**tool_args)
        except EscalationRequiredError as exc:
            token = str(uuid.uuid4())
            pending = PendingApproval(
                token=token,
                invariant_id=exc.invariant_id,
                tool_name=tool_name,
                tool_args=tool_args,
            )
            agent.session.pending_approvals[token] = pending
            agent.state = AgentState.AWAITING_APPROVAL
            agent.session.state = AgentState.AWAITING_APPROVAL
            escalation_msg = (
                f"Action paused: {tool_name} requires supervisor escalation "
                f"under policy {exc.invariant_id}. Approval token: {token}"
            )
            agent.session.messages.append(
                ConversationMessage(role=MessageRole.ASSISTANT, content=escalation_msg)
            )
            yield ConversationEvent(
                type=ConversationEventType.ESCALATION_REQUIRED,
                content=escalation_msg,
                tool_name=tool_name,
                tool_args=tool_args,
                approval_token=token,
                new_state=AgentState.AWAITING_APPROVAL,
            )
            yield ConversationEvent(type=ConversationEventType.TOKEN, content=escalation_msg)
            yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
            return
        except InvariantViolationError as exc:
            error_msg = f"Policy violation [{exc.invariant_id}]: {exc.message}"
            agent.session.messages.append(
                ConversationMessage(role=MessageRole.ASSISTANT, content=error_msg)
            )
            yield ConversationEvent(type=ConversationEventType.ERROR, content=error_msg)
            yield ConversationEvent(type=ConversationEventType.TOKEN, content=error_msg)
            agent.state = AgentState.AWAITING_INPUT
            agent.session.state = AgentState.AWAITING_INPUT
            yield ConversationEvent(
                type=ConversationEventType.STATE_CHANGE,
                new_state=AgentState.AWAITING_INPUT,
            )
            yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
            return
        except Exception as exc:
            agent.state = AgentState.FAILED
            agent.session.state = AgentState.FAILED
            yield ConversationEvent(
                type=ConversationEventType.ERROR,
                content=str(exc),
                new_state=AgentState.FAILED,
            )
            yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
            raise

        if isinstance(tool_result, dict) and "error" in tool_result and "invariant_id" in tool_result:
            blocked_msg = f"Action blocked by policy [{tool_result['invariant_id']}]: {tool_result.get('remedy', tool_result['error'])}"
            agent.session.messages.append(
                ConversationMessage(role=MessageRole.ASSISTANT, content=blocked_msg)
            )
            yield ConversationEvent(
                type=ConversationEventType.TOOL_CALL_RESULT,
                tool_name=tool_name,
                tool_result=tool_result,
            )
            yield ConversationEvent(type=ConversationEventType.TOKEN, content=blocked_msg)
            agent.state = AgentState.AWAITING_INPUT
            agent.session.state = AgentState.AWAITING_INPUT
            yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
            return

        yield ConversationEvent(
            type=ConversationEventType.TOOL_CALL_RESULT,
            tool_name=tool_name,
            tool_result=tool_result,
        )
        turn_tool_calls.append({"name": tool_name, "args": tool_args, "result": tool_result})

    agent.state = AgentState.AWAITING_INPUT
    agent.session.state = AgentState.AWAITING_INPUT
    yield ConversationEvent(
        type=ConversationEventType.TOKEN,
        content="Iteration limit reached for current turn.",
    )
    yield ConversationEvent(type=ConversationEventType.TURN_COMPLETE)
