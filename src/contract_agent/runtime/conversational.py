"""Runtime base class for stream-first conversational contract agents."""

from __future__ import annotations

import asyncio
import concurrent.futures
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

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
from contract_agent.runtime.conversation_stream import execute_turn_stream
from contract_agent.runtime.context import ToolCallRecord
from contract_agent.runtime.guards import GuardInterceptor


class BaseConversationalAgent:
    """Base runtime engine for interactive conversational contract agents."""

    def __init__(
        self,
        tools: Any,
        interceptor: GuardInterceptor,
        provider: Any | None = None,
        session_id: str | None = None,
        max_turn_iterations: int = 5,
    ) -> None:
        self.tools = tools
        self.interceptor = interceptor
        self.provider = provider
        self.max_turn_iterations = max_turn_iterations
        self.session = ConversationSession(
            session_id=session_id or str(uuid.uuid4()),
            state=AgentState.IDLE,
        )
        self.state: AgentState = AgentState.IDLE
        self.history: list[dict[str, Any]] = []
        self.interceptor.context.session_id = self.session.session_id

    def execute_action(self, action: str, **kwargs: Any) -> Any:
        """Executes a tool action with state transition and guard interception."""
        raise NotImplementedError("Subclasses must implement execute_action")

    async def stream(self, message: str) -> AsyncIterator[ConversationEvent]:
        """Asynchronously processes user message, yielding incremental turn events."""
        async for evt in execute_turn_stream(self, message):
            yield evt

    def step(self, message: str) -> ConversationTurnResult:
        """Synchronous facade running stream() to completion."""
        events: list[ConversationEvent] = []

        async def _collect() -> None:
            async for evt in self.stream(message):
                events.append(evt)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(lambda: asyncio.run(_collect())).result()
        else:
            asyncio.run(_collect())

        tokens = [e.content for e in events if e.type == ConversationEventType.TOKEN and e.content]
        reply = "".join(tokens) if tokens else (events[-2].content if len(events) > 1 and events[-2].content else "Done.")
        tools_executed = [e.tool_name for e in events if e.type == ConversationEventType.TOOL_CALL_RESULT and e.tool_name]
        escalation_event = next((e for e in events if e.type == ConversationEventType.ESCALATION_REQUIRED), None)

        return ConversationTurnResult(
            reply=reply,
            state=self.state,
            events=events,
            tools_executed=tools_executed,
            requires_approval=escalation_event is not None,
            approval_token=escalation_event.approval_token if escalation_event else None,
        )

    def chat(self, message: str) -> str:
        """Convenience facade returning textual response."""
        return self.step(message).reply

    def approve(self, token: str, approver_id: str | None = None) -> ConversationTurnResult:
        """Trusted host adapter: grant a durable approval and resume the request."""
        pending = self._pending_approval(token)
        if pending.resource_id is None:
            raise ValueError("Approval request has no resource identity")
        self.interceptor.context.approval_store.grant_approval(
            approval_type=pending.approval_type,
            resource_id=pending.resource_id,
            granted_by=approver_id or "manager",
        )
        return self.resume_approval(token)

    def _pending_approval(self, token: str) -> PendingApproval:
        """Reject unregistered, stale, or modified session-snapshot requests."""
        if self.state != AgentState.AWAITING_APPROVAL:
            raise ValueError(f"Agent state is {self.state}, expected AWAITING_APPROVAL")
        if token not in self.session.pending_approvals:
            raise KeyError(f"Approval token '{token}' not found")
        pending = self.session.pending_approvals[token]
        if pending.status != "pending":
            raise ValueError(f"Approval token '{token}' has status '{pending.status}', expected 'pending'")

        persisted = self.interceptor.context.approval_store.requests.get(
            token, self.session.session_id
        )
        if persisted["status"] != "pending":
            raise ValueError("Durable approval request is no longer pending")
        if persisted != pending.model_dump(mode="json"):
            raise ValueError("Session approval payload does not match durable request")
        return pending

    def resume_approval(self, token: str) -> ConversationTurnResult:
        """Resume an action approved asynchronously by an external supervisor."""
        pending = self._pending_approval(token)
        self.interceptor.context.approval_store.requests.claim(token, self.session.session_id)
        pending.status = "consumed"

        self.state = AgentState.PROCESSING
        self.session.state = AgentState.PROCESSING
        guarded = self.interceptor.wrap_tool(pending.tool_name, getattr(self.tools, pending.tool_name))
        try:
            tool_res = guarded(**pending.tool_args)
            if isinstance(tool_res, dict) and "error" in tool_res and "invariant_id" in tool_res:
                raise ValueError(f"Approved action remains blocked: {tool_res['error']}")
        except Exception:
            self.state = AgentState.FAILED
            self.session.state = AgentState.FAILED
            raise
        self.state = AgentState.AWAITING_INPUT
        self.session.state = AgentState.AWAITING_INPUT

        reply = f"Durable approval granted. Executed {pending.tool_name}: {tool_res}"
        self.session.messages.append(ConversationMessage(role=MessageRole.ASSISTANT, content=reply))

        events = [
            ConversationEvent(type=ConversationEventType.STATE_CHANGE, new_state=AgentState.PROCESSING),
            ConversationEvent(type=ConversationEventType.TOOL_CALL_START, tool_name=pending.tool_name, tool_args=pending.tool_args),
            ConversationEvent(type=ConversationEventType.TOOL_CALL_RESULT, tool_name=pending.tool_name, tool_result=tool_res),
            ConversationEvent(type=ConversationEventType.TOKEN, content=reply),
            ConversationEvent(type=ConversationEventType.STATE_CHANGE, new_state=AgentState.AWAITING_INPUT),
            ConversationEvent(type=ConversationEventType.TURN_COMPLETE),
        ]
        return ConversationTurnResult(
            reply=reply,
            state=self.state,
            events=events,
            tools_executed=[pending.tool_name],
            requires_approval=False,
            approval_token=None,
        )

    def complete_session(self) -> ConversationTurnResult:
        """Explicitly signals completion of the conversational session."""
        self.state = AgentState.COMPLETED
        self.session.state = AgentState.COMPLETED
        reply = "Session completed successfully."
        self.session.messages.append(
            ConversationMessage(role=MessageRole.ASSISTANT, content=reply)
        )
        events = [
            ConversationEvent(
                type=ConversationEventType.STATE_CHANGE,
                new_state=AgentState.COMPLETED,
            ),
            ConversationEvent(type=ConversationEventType.TOKEN, content=reply),
            ConversationEvent(type=ConversationEventType.TURN_COMPLETE),
        ]
        return ConversationTurnResult(
            reply=reply,
            state=self.state,
            events=events,
            tools_executed=[],
            requires_approval=False,
        )

    def reset(self) -> None:
        """Clears conversation session history, pending approvals, and resets state."""
        self.interceptor.context.approval_store.requests.cancel(self.session.session_id)
        self.session = ConversationSession()
        self.state = AgentState.IDLE
        self.history.clear()
        self.interceptor.context.call_history.clear()
        self.interceptor.context.session_id = self.session.session_id

    def export_session(self) -> dict[str, Any]:
        """Exports session history and state to a JSON-compatible dictionary."""
        self.session.state = self.state
        self.session.workflow_calls = [asdict(call) for call in self.interceptor.context.call_history]
        return self.session.model_dump(mode="json")

    @classmethod
    def from_session(
        cls,
        data: dict[str, Any],
        tools: Any,
        interceptor: GuardInterceptor,
        provider: Any | None = None,
    ) -> Any:
        """Restores an active agent instance from exported session data."""
        session = ConversationSession.model_validate(data)
        agent = cls(tools=tools, interceptor=interceptor, provider=provider, session_id=session.session_id)
        agent.session = session
        agent.state = session.state
        for token, pending in session.pending_approvals.items():
            if pending.status == "pending":
                agent._pending_approval(token)
        if session.state == AgentState.AWAITING_APPROVAL and not session.pending_approvals:
            raise ValueError("Awaiting-approval session has no pending request")
        interceptor.context.call_history = [ToolCallRecord(**call) for call in session.workflow_calls]
        return agent

    def _resolve_tool_call(
        self, message: str, executed_in_turn: set[str]
    ) -> tuple[str | None, dict[str, Any]]:
        return None, {}

    def _generate_conversational_reply(
        self, message: str, executed_in_turn: set[str]
    ) -> str:
        return "Done."
