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
  - Agent must not be in `AWAITING_APPROVAL` (must call `approve()` first) or `FAILED`.

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
Resumes a tool execution that was suspended by an invariant with `on_violation: require_escalation`.

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
Clears session history, cancels pending approvals, and resets agent state to `AgentState.IDLE`.

---

### 2.6 `export_session() -> dict[str, Any]`
Serializes current conversation state (`session_id`, `state`, `messages`, `metadata`) into a JSON-compatible dictionary for persistence.

---

### 2.7 `from_session(...) -> ConversationalAgent` (classmethod)
Reconstitutes an active agent instance from exported session data.

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
