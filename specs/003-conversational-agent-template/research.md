# Phase 0 Research: Conversational Agent Template & Interactive Execution

**Feature**: `003-conversational-agent-template`  
**Date**: 2026-09-24  
**Status**: Completed  

---

## 1. Architectural Decisions & Research Findings

### Decision 1: Stream-First Interaction Architecture with Synchronous Facades
- **Context**: Users interacting with conversational AI agents expect real-time feedback (streaming token chunks and visibility into tool lifecycle events), while headless CI and programmatic scripts often prefer simple blocking calls.
- **Decision**: Architect `ConversationalAgent` as stream-first:
  - Core execution method: `async def stream(self, message: str) -> AsyncIterator[ConversationEvent]`
  - Synchronous / Blocking facade: `def step(self, message: str) -> ConversationTurnResult` (runs the stream to completion and aggregates events into a structured turn result)
  - Convenience chat facade: `def chat(self, message: str) -> str` (returns the aggregated textual assistant reply)
- **Rationale**: Stream-first architecture allows UIs, terminals, and WebSockets to render text incrementally and show spinners when tools execute, while preserving full backward-compatibility with synchronous pipelines.
- **Alternatives Considered**:
  - *Sync-only blocking interface*: Simple to implement, but creates high-latency dead time during multi-step tool calls and prevents live UI updates.
  - *Callback-based event handler*: More complex to compose than async generators and harder to test deterministically in pytest.

---

### Decision 2: ReAct (Reasoning + Action) Dialogue Execution Loop
- **Context**: In conversational workflows, an agent must decide whether to answer directly, ask for missing details, or execute one or more contract tools.
- **Decision**: Implement a bounded ReAct execution loop within each turn:
  1. Append user message to `ConversationSession.messages`.
  2. Transition `AgentState` to `PROCESSING`.
  3. Prompt LLM provider with conversation history, tool definitions, and system guidelines.
  4. Parse response:
     - If the model emits thought tokens or partial text, yield `token` events.
     - If the model emits a tool call, yield `tool_call_start`, execute tool through `self.interceptor.wrap_tool()`, append `tool` result message to history, yield `tool_call_result`, and loop back to step 3 for subsequent reasoning.
     - If model completes response or signals completion, transition state to `AWAITING_INPUT` or `COMPLETED` and yield `turn_complete`.
  5. Enforce a hard turn loop ceiling (default 5 iterations) to prevent runaway infinite tool dispatching.
- **Rationale**: ReAct is the proven industry standard for tool-using agents. By embedding `self.interceptor.wrap_tool()` at the action dispatch stage, deterministic CEL enforcement is guaranteed on every step with zero LLM judge involvement.
- **Alternatives Considered**:
  - *One-tool-per-turn limitation*: Restricts multi-step workflows (e.g. `fetch_invoice` followed by `execute_refund` in a single user query).
  - *Pure state machine routing without reasoning*: Brittle for natural language dialogues; cannot handle conversational clarifications gracefully.

---

### Decision 3: Unbounded In-Memory Dialogue History with Full Serialization
- **Context**: In multi-turn workflows, the agent must recall facts and previous actions from earlier turns without premature context amnesia.
- **Decision**: Maintain chronological, unbounded list of `ConversationMessage` objects in `ConversationSession`. Support `session.model_dump()` and `ConversationSession.model_validate()` for serialization to JSON or dictionary format.
- **Rationale**: Clean separation of in-memory execution state from persistence storage. Host applications can persist session state in Redis, SQLite, or browser local storage, restoring it seamlessly before calling `agent.stream()`.
- **Alternatives Considered**:
  - *Sliding window truncation*: Discards older messages, which breaks workflows where invoice IDs or customer details were specified in turn 1 but referenced in turn 5.
  - *Automatic background summarization*: Adds extra LLM costs and risks summarizing away exact IDs or parameters needed for CEL invariant evaluation.

---

### Decision 4: Hybrid Invariant Escalation & Approval Model
- **Context**: Contract invariants with `on_violation: require_escalation` (e.g. refunds > $100) pause the workflow until approved.
- **Decision**: Implement a hybrid escalation model:
  1. When an invariant raises an escalation requirement, intercept it in the execution loop.
  2. Generate a secure, unique `approval_token` and store the pending tool execution payload in `ConversationSession.pending_approvals`.
  3. Transition `AgentState` to `AWAITING_APPROVAL`.
  4. Yield an `escalation_required` event containing the invariant description, token, and conversational explanation.
  5. Resolution path A (Programmatic): Caller invokes `agent.approve(approval_token, approver_id)`.
  6. Resolution path B (In-band conversational): In a multi-user or supervisor session, an authorized message (e.g. "Approved") matching the approval schema resumes the action.
- **Rationale**: Supports both automated supervisor dashboards/APIs and conversational chatroom approvals without modifying application logic.
- **Alternatives Considered**:
  - *Hard exception crash*: Terminating the process destroys conversational state and requires full restart.
  - *In-band only*: Prevents programmatic enterprise approvals from external workflow systems.

---

### Decision 5: Adversarial Multi-Turn Dialogue Test Generation
- **Context**: Existing test generation (`dist/test_contract.py`) generates unit tests calling `execute_action()` directly. Interactive conversational agents need tests that simulate sequential conversation turns.
- **Decision**: Update `generate_default_test_suite` in `templates.py` to synthesize conversational test cases:
  - Simulates multi-turn dialogue matching declared contract `scenarios` turn-by-turn.
  - Asserts intermediate `ConversationEvent` streams and final `agent.state`.
  - Injects adversarial conversational boundary probes (e.g. attempting to coax the agent into refunding $99,999 in chat) and asserts the guard blocks or escalates the action.
- **Rationale**: Verifies conversational integrity and ensures invariant enforcement is resilient to natural language prompt variations.
- **Alternatives Considered**:
  - *Retaining action-only tests*: Leaves conversational routing and streaming untested.
