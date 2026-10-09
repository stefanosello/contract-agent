# Feature Specification: Conversational Agent Template & Interactive Execution

**Feature Branch**: `003-conversational-agent-template`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "improve agent template in order to allow interactive conversational agents creation"

## Clarifications

### Session 2026-09-23
- Q: What API interface should the generated conversational agent expose for driving conversation turns and inspecting state? → A: Stream-first interface (`stream(message: str)` yielding token chunks and tool lifecycle events).
- Q: How should the conversational agent handle and resume from invariant escalation events requiring human approval? → A: Hybrid approval model (transitions to `AWAITING_APPROVAL`, resolving either via programmatic `approve(token)` call or via an in-band supervisor confirmation message).
- Q: How should the conversational agent manage dialogue history and context window retention across long-running sessions? → A: Unbounded in-memory history (retain all messages for the lifetime of the session without truncation).
- Q: What reasoning architecture should the conversational agent template use to decide between replying vs invoking tools? → A: ReAct reasoning loop (the agent alternates between reasoning thoughts, guarded tool executions, and user responses within each turn).
- Q: How should the conversational agent determine when a multi-turn workflow has reached completion? → A: Explicit completion signal (the agent emits a `complete_session` event or invokes a completion marker when workflow objectives are met or user confirms satisfaction).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Turn Conversational Interaction (Priority: P1) 🎯 MVP

As an agent engineer, I want the compiler to generate agent templates that support multi-turn conversational dialogue, so that end users can interact with the agent naturally via messages while preserving conversational context and session state across turns.

**Why this priority**: Transforming the agent from a single-shot tool dispatcher into a conversational entity is the foundation of interactive agent creation. It directly addresses the user request and enables interactive chat workflows.

**Independent Test**: Instantiate a compiled conversational agent, send sequential user messages, and assert that the agent maintains context, records turn history, and returns coherent conversational responses across multiple turns.

**Acceptance Scenarios**:

1. **Given** a compiled conversational agent in an idle state, **When** a user submits an initial message, **Then** the agent initializes a session, processes the message, appends it to conversation history, and returns a conversational response.
2. **Given** an ongoing conversation session with existing history, **When** the user sends a follow-up message referencing prior context, **Then** the agent uses the accumulated message history to formulate its response and advances the session state.

---

### User Story 2 - Invariant-Guarded Conversational Tool Execution (Priority: P1)

As an agent developer, I want the conversational agent to invoke contract tools dynamically during conversation turns while enforcing all invariant rules via the deterministic runtime guard, so that the agent can perform real tasks during conversation without compromising safety or data integrity.

**Why this priority**: An interactive agent must be able to act on behalf of the user. Enforcing contract invariants during conversational turns upholds Constitution Principle I (Spec-as-Source) and Principle II (Deterministic CEL Enforcement).

**Independent Test**: Simulate a conversational exchange where user requests trigger tool calls; assert that authorized tool calls execute with results incorporated into the assistant reply, and unauthorized tool calls are intercepted and blocked by runtime guards.

**Acceptance Scenarios**:

1. **Given** a user message requesting an action that maps to a declared tool, **When** the tool call satisfies all invariant rules, **Then** the tool executes through the guard interceptor, its return payload is captured in the conversation history, and the agent confirms execution to the user.
2. **Given** a user message requesting an action that violates an invariant rule, **When** the tool call is evaluated by the guard, **Then** the tool execution is blocked, the violation is logged, and the agent informs the user of the constraint in its conversational reply without crashing.

---

### User Story 3 - Conversational Escalation & Approval Workflows (Priority: P2)

As a workflow supervisor, I want the conversational agent to handle invariant escalation triggers gracefully within dialogue, pausing execution and prompting the user for approval or informing them of pending review, so that sensitive operations are never executed without proper authorization.

**Why this priority**: Production conversational agents routinely encounter actions requiring human-in-the-loop approval. Handling escalations within conversation maintains user trust and transparency.

**Independent Test**: Trigger a conversational turn requiring manager escalation (e.g. refund over threshold); assert the agent transitions to an awaiting-approval state, presents an escalation notification, and refrains from executing until approved.

**Acceptance Scenarios**:

1. **Given** a tool invocation that triggers an escalation invariant, **When** executed during a conversation turn, **Then** the agent pauses execution, generates an approval token, transitions session state to `AWAITING_APPROVAL`, and emits an `escalation_required` event with a conversational explanation.
2. **Given** an agent awaiting approval, **When** approved via programmatic `approve(token)` call or when an authorized in-band supervisor message is received, **Then** the agent resumes the paused tool execution, completes the requested action, and transitions state back to `PROCESSING` or `COMPLETED`.

---

### User Story 4 - Multi-Turn Dialogue Testing & Scenario Simulation (Priority: P2)

As a QA engineer, I want the adversarial test generator to synthesize multi-turn conversational dialogue test suites, so that we can verify conversational state transitions, context retention, and invariant enforcement under interactive multi-turn conditions before deployment.

**Why this priority**: Testing must reflect how users interact with the agent. Multi-turn dialogue testing prevents regressions in state management and conversational guardrail evasion.

**Independent Test**: Run the generated conversational test suite against the compiled agent and verify that multi-step contract scenarios evaluate turn-by-turn with 100% invariant verification pass rate.

**Acceptance Scenarios**:

1. **Given** a contract with multi-step scenario flows, **When** compiled, **Then** the test suite generates conversational test fixtures simulating dialogue turns matching the expected flow.
2. **Given** an adversarial test probe injecting boundary violations conversationally, **When** executed, **Then** the test verifies that the agent refuses or escalates the action rather than executing out-of-bounds tools.

---

### Edge Cases

- **Empty or Whitespace-Only Messages**: System MUST ignore or prompt the user for clarification without mutating conversation state or invoking tools.
- **Runaway Conversational Loops**: System MUST enforce a maximum tool-call iteration limit per conversation turn (default 5 tool iterations) to prevent infinite loops.
- **Session Memory Overflow**: System MUST preserve a structured message window or summary when message history exceeds configured token thresholds.
- **Mid-Conversation Disconnection / State Recovery**: The agent MUST support serialization and deserialization of the conversation session state to permit persistence across stateless HTTP/API boundaries.
- **Adversarial Prompt Injection**: Conversational inputs attempting to bypass invariants MUST be constrained by deterministic CEL guards regardless of LLM reasoning output.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST synthesize an agent template providing a stream-first conversational interface (`stream(message: str)`) yielding real-time token chunks and tool lifecycle events, along with an execution wrapper (`step` or `chat`) for non-streaming consumers.
- **FR-002**: The conversational agent MUST maintain an unbounded, chronological in-memory history of all dialogue messages (user, assistant, tool, system) and tool events for the entire lifetime of the session without truncation.
- **FR-003**: The conversational agent MUST support multi-turn dialogue where context from prior turns informs subsequent reasoning and action selection.
- **FR-004**: During a conversation turn, the agent MUST use a ReAct (Reasoning + Action) execution loop to alternate between reasoning thoughts, guarded tool invocations, and user-facing conversational replies.
- **FR-005**: All tool executions initiated during conversational turns MUST be routed through the deterministic runtime guard interceptor (`GuardInterceptor`) before execution.
- **FR-006**: The agent MUST track explicit conversational session states (`IDLE`, `PROCESSING`, `AWAITING_INPUT`, `AWAITING_APPROVAL`, `COMPLETED`, `FAILED`), transitioning to `COMPLETED` when the agent emits an explicit `complete_session` event upon fulfilling workflow objectives or receiving user confirmation.
- **FR-007**: When a tool execution is blocked or requires escalation by a CEL invariant rule, the agent MUST catch the guard outcome and explain the constraint conversationally in its response.
- **FR-008**: The agent MUST support exporting and restoring the complete session state (messages, current state, metadata) to enable persistent multi-turn sessions across requests.
- **FR-009**: The test generator MUST synthesize multi-turn dialogue test cases in `dist/test_contract.py` that validate conversational progression and invariant preservation across successive messages.
- **FR-010**: The agent MUST provide a session reset mechanism that clears dialogue history and restores initial state for new interactions.
- **FR-011**: The agent MUST support a hybrid approval mechanism for escalations, exposing an `approve(token: str, approver_id: str | None = None)` method for out-of-band resolution and recognizing authorized in-band confirmation messages to resume execution.

### Key Entities

- **ConversationEvent**: A typed stream event emitted during interaction, such as `token` (partial text), `tool_call_start`, `tool_call_result`, `state_change`, or `escalation_required`.
- **ConversationMessage**: An immutable record of a single communication turn, containing `role` (user, assistant, system, tool), `content` (text), and optional `tool_calls` / `tool_results`.
- **ConversationSession**: The stateful container for an ongoing interaction, holding a unique session ID, ordered list of `ConversationMessage` records, current `AgentState`, and workflow context.
- **ConversationTurnResult**: The structured result of a dialogue turn, containing the assistant's textual response, any tool calls executed during the turn, and the updated session status.
- **ConversationalAgent**: The generated agent class encapsulating dialogue management, reasoning prompt orchestration, and invariant-guarded tool dispatching.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of benchmark contracts compile successfully into conversational agents capable of multi-turn dialogue.
- **SC-002**: Invariant violations triggered via conversational prompts are blocked or escalated with 100% reliability, resulting in 0 unauthorized tool executions.
- **SC-003**: Conversational agents preserve context and execute multi-step contract workflows across at least 10 consecutive turns without state corruption or session loss.
- **SC-004**: Developers can initialize and converse with a compiled agent in 3 or fewer lines of code.
- **SC-005**: Generated conversational test suites execute and pass 100% of defined scenarios in under 15 seconds per contract.

---

## Assumptions

- Users provide textual inputs in UTF-8 string format.
- The underlying LLM provider provides text completion and supports tool selection / function calling or prompt-guided JSON dispatching.
- Runtime invariant evaluation remains strictly deterministic via Google CEL, independent of language model output.
- Transport mechanisms (CLI loop, WebSocket, REST API, UI widget) are host application responsibilities; the compiled agent exposes a clean, embeddable Python interface.
- Default conversation session state is stored in memory, with JSON-serializable export/import for optional durable persistence.
