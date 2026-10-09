# API Contract: Conversational Agent Interface

**Feature**: `003-conversational-agent-template`  
**Date**: 2026-09-24  
**Status**: Ready for Implementation  

---

## 1. Class Overview: `ConversationalAgent`

The compiled agent class (e.g. `BillingDisputeAgent`) generated in `dist/agent.py` implements the conversational agent contract. It binds strictly to `AgentToolsProtocol` and `GuardInterceptor`.

```python
class ConversationalAgent:
    """Multi-turn conversational agent with streaming and invariant guardrail enforcement."""

    def __init__(
        self,
        tools: AgentToolsProtocol,
        interceptor: GuardInterceptor,
        provider: LLMProvider | None = None,
        session_id: str | None = None,
        max_turn_iterations: int = 5,
    ) -> None: ...
```

---

## 2. Public Methods

### 2.1 `stream(message: str) -> AsyncIterator[ConversationEvent]`
Asynchronously processes a user message, yielding incremental events (tokens, tool call lifecycle, state transitions).

- **Arguments**:
  - `message`: Natural language user prompt (`str`).
- **Yields**:
  - `ConversationEvent` instances in real time.
- **Side Effects**:
  - Appends user message and generated assistant/tool events to `self.session.messages`.
  - Updates `self.state`.
  - Invokes authorized tools through `interceptor.wrap_tool()`.
- **Preconditions**:
   - Hosts must authenticate and authorize supervisor confirmations before routing them in-band. In `AWAITING_APPROVAL`, confirmation adapters use the same durable approval transition; ordinary messages leave execution paused.
   - Agent must not be in `FAILED`.

---

### 2.2 `step(message: str) -> ConversationTurnResult`
Synchronous convenience method that runs `stream()` to completion and packages the turn outcome into a structured result.

- **Arguments**:
  - `message`: User input text (`str`).
- **Returns**:
  - `ConversationTurnResult`: Complete reply, events list, tools executed, and final state.

---

### 2.3 `chat(message: str) -> str`
High-level conversational helper returning the assistant's textual response.

- **Arguments**:
  - `message`: User input text (`str`).
- **Returns**:
  - Aggregated assistant textual response (`str`).

---

### 2.4 `approve(token: str, approver_id: str | None = None) -> ConversationTurnResult`
Trusted host adapter for a tool execution suspended by `on_violation: require_escalation`. Grants the authoritative SQLite approval keyed by the persisted request's `(approval_type, resource_id)`, then calls `resume_approval(token)`. The optional identifier is an audit label, not authentication.

- **Arguments**:
  - `token`: Unique approval token emitted in the `escalation_required` event.
  - `approver_id`: Optional identifier of the supervisor granting approval.
- **Returns**:
  - `ConversationTurnResult`: Resumed turn outcome following tool execution.
- **Raises**:
  - `KeyError`: If `token` is not found or not in `pending` status.
  - `StateError`: If agent is not in `AWAITING_APPROVAL` state.

---

### 2.5 `reset() -> None`
Clears session and workflow call history, cancels durable pending request tokens, and resets agent state to `AgentState.IDLE`. Old snapshots cannot reactivate cancelled tokens.

---

### 2.6 `export_session() -> dict[str, Any]`
Serializes current conversation state (`session_id`, `state`, `messages`, `pending_approvals`, `workflow_calls`, `metadata`) into a JSON-compatible dictionary for trusted host persistence. This snapshot does not confer approval authority.

---

### 2.7 `from_session(...) -> ConversationalAgent` (classmethod)
Reconstitutes an active agent instance from exported session data, restores workflow prerequisites, and validates active request payloads against the same durable approval database. Missing, consumed, cancelled, or altered pending requests fail closed. Legacy pending-token snapshots without durable records cannot resume automatically.

```python
@classmethod
def from_session(
    cls,
    data: dict[str, Any],
    tools: AgentToolsProtocol,
    interceptor: GuardInterceptor,
    provider: LLMProvider | None = None,
) -> ConversationalAgent: ...
```

### 2.8 `resume_approval(token: str) -> ConversationTurnResult`

Resumes a request after an external supervisor asynchronously calls `ApprovalStore.grant_approval(approval_type, resource_id, granted_by)`. Requires an exact durable pending request and approved keyed decision. Atomically consumes the token before routing the action through `GuardInterceptor`; a competing or replayed claim fails. No approval is granted by this method.

Storage defaults to file-backed SQLite at `~/.local/share/contract-agent/approvals.sqlite3`; hosts can configure `CONTRACT_AGENT_APPROVAL_DB` or pass an explicit store to `WorkflowContext`. Explicit in-memory stores are test-only. Failed/interrupted consumed dispatch requires host reconciliation rather than automatic retry.
