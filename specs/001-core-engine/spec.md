# Feature Specification: ContractAgent Core CEL Invariant Engine & AST Parser

**Feature Branch**: `001-core-engine`

**Created**: 2026-09-23

**Status**: Ready for Planning

**Input**: User description: "ContractAgent MVP: Core CEL Invariant Engine and AST Parser"

## Clarifications

### Session 2026-09-23
- Q: Should `ContractParser` statically parse and type-check all CEL invariant expressions against the declared tool parameter schemas during contract loading, or defer CEL compilation until runtime initialization? → A: Option A — Static CEL & schema validation at parse time (`ContractParser` validates CEL syntax and parameter references against tool schemas, raising `ContractValidationError` on syntax errors or invalid fields).
- Q: How should the runtime `GuardInterceptor` dispatch the three invariant violation actions (`raise_invariant_violation`, `block_tool_call`, and `require_escalation`) when an invariant evaluates to `False`? → A: Option A — Differentiated dispatch (`raise_invariant_violation` raises `InvariantViolationError`, `block_tool_call` returns a blocked tool error payload to the agent, and `require_escalation` raises `EscalationRequiredError` with approval metadata).
- Q: Should the custom CEL workflow functions (`workflow.called_before` and `workflow.call_count`) support both resource-correlated and global sequence overloads? → A: Option A — Overloaded signatures (support both global checks and resource-correlated overloads matching parameter values).
- Q: How should the Hypothesis property-based fuzzer generate test inputs for tool invariants during Zero-LLM verification? → A: Schema-driven with custom override (automatic JSON Schema strategy synthesis by default, with support for manual developer-supplied strategy overrides).
- Q: Which mutation vectors should the built-in Rogue Mutant Agent test fixture simulate during automated CI mutation testing? → A: Option A — Comprehensive multi-vector suite (test numerical threshold exceedance, out-of-order/skipped prerequisites, and missing human approval tokens).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declarative Contract Parsing & Validation (Priority: P1)

As a developer, I want to define my agent's identity, tools, invariants, and scenarios in an `agent.contract.yaml` file and have it statically validated so syntax and schema errors are caught immediately before any code generation occurs.

**Why this priority**: Without a validated Abstract Syntax Tree (AST), no compilation, synthesis, or verification can proceed.

**Independent Test**: Load valid and invalid `agent.contract.yaml` files via `ContractParser.load()` and assert that valid specs produce typed Pydantic models while invalid ones produce actionable diagnostics.

**Acceptance Scenarios**:

1. **Given** a well-formed `agent.contract.yaml` with CEL invariants, tools, and scenarios, **When** parsed, **Then** returns a typed `ContractAST` object with 100% field type validation.
2. **Given** a malformed YAML or a contract missing required fields (e.g. tool parameter types), **When** parsed, **Then** raises `ContractValidationError` with the exact path and issue.

---

### User Story 2 - Deterministic CEL Invariant Evaluation (Priority: P1)

As a developer, I want my agent's invariants to be evaluated using Google Common Expression Language (CEL) with custom workflow functions, ensuring non-Turing-complete, linear-time, fail-closed enforcement with zero LLM hallucination risk.

**Why this priority**: This is the load-bearing foundation of ContractAgent's safety guarantees.

**Independent Test**: Compile CEL rules and evaluate them against mock `args` and `workflow` contexts, asserting correct boolean resolution across boundaries.

**Acceptance Scenarios**:

1. **Given** the rule `"args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)"`, **When** evaluated with `amount_cents = 35000` and no approval, **Then** returns `False`.
2. **Given** the same rule, **When** evaluated with `amount_cents = 35000` and an approved record for `args.invoice_id`, **Then** returns `True`.
3. **Given** the rule `"workflow.called_before('fetch_invoice', 'execute_refund', args.invoice_id)"`, **When** `execute_refund` is called without prior `fetch_invoice`, **Then** returns `False`.

---

### User Story 3 - Zero-LLM Property-Based Fuzzing with Hypothesis (Priority: P1)

As a developer, I want the framework to automatically generate boundary-value property tests for my CEL rules before any LLM is called, so I can mathematically verify invariant behavior for $0 token cost.

**Why this priority**: Prevents buggy invariant expressions from being passed into the LLM synthesis loop.

**Independent Test**: Run `pytest tests/test_cel_fuzzing.py` and verify Hypothesis executes 100+ randomized iterations testing edge cases (e.g., negative numbers, exact limit `25000`, `25001`, extreme strings).

**Acceptance Scenarios**:

1. **Given** an invariant with a numerical boundary (`<= 25000`), **When** fuzzed with Hypothesis, **Then** values $\le 25000$ evaluate to True and $> 25000$ evaluate to False without exceptions.

---

### User Story 4 - Fail-Closed Runtime Guard Interceptor (Priority: P2)

As an engineer, I want `guards.py` to wrap tool invocations, evaluating CEL rules before any network/handler execution, and failing closed if an invariant is violated.

**Why this priority**: Protects against model drift and hallucinations at runtime.

**Independent Test**: Wrap a mock tool with `GuardInterceptor` and attempt an illegal invocation; assert that the underlying tool function is never called and an `InvariantViolationError` is raised.

**Acceptance Scenarios**:

1. **Given** an illegal tool call attempt that violates an invariant, **When** intercepted by `guards.py`, **Then** the underlying handler is NOT called and an `InvariantViolationError` is raised with a structured diagnostic payload.

---

### User Story 5 - Automated Mutation Testing Fixture (Priority: P2)

As a CI pipeline, I want an automated Rogue Mutant test fixture that deliberately attempts to bypass guards, verifying that the interceptor traps the execution 100% of the time.

**Why this priority**: Guarantees that internal framework refactors do not accidentally cause guards to fail open.

**Independent Test**: Run `pytest tests/test_mutation_safety.py` in CI; assert that 100% of mutant attempts are trapped.

**Acceptance Scenarios**:

1. **Given** a mutant agent attempting unapproved financial mutations or out-of-order calls, **When** run through the guard runtime, **Then** 0% of illegal calls reach the handler.

---

## Edge Cases

- **Malformed CEL Expression**: Caught statically at `validate` time before runtime.
- **Missing Resource Correlation Key**: If an invariant references `args.invoice_id` but the tool args lack that parameter, the validator raises an informative schema mismatch error.
- **CEL Evaluation Timeout / Recursion**: CEL is non-Turing complete by definition; evaluation terminates in linear time.
- **Null / None Values**: Expressions handle null coalescence gracefully (e.g. `has(args.reason) && size(args.reason) >= 10`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load and parse YAML contract files into typed Pydantic V2 AST models, performing static CEL syntax compilation and parameter schema validation at parse time.
- **FR-002**: System MUST compile CEL expressions using a verified CEL environment.
- **FR-003**: System MUST provide custom CEL functions with overloaded signatures: `workflow.has_approval(type, resource_id)`, `workflow.called_before(prior, target)` / `workflow.called_before(prior, target, correlation_id)`, and `workflow.call_count(tool)` / `workflow.call_count(tool, correlation_id)`.
- **FR-004**: System MUST evaluate invariants deterministically with zero network calls or LLM queries.
- **FR-005**: System MUST provide a `GuardInterceptor` that intercepts tool calls before execution and dispatches violation actions accordingly (`raise_invariant_violation` raises `InvariantViolationError`, `block_tool_call` returns a blocked payload, `require_escalation` raises `EscalationRequiredError`).
- **FR-006**: System MUST fail closed on any invariant violation or evaluation error.
- **FR-007**: System MUST provide automated Hypothesis fuzzing utilities that synthesize input strategies directly from tool parameter schemas by default, while supporting custom user-defined strategy overrides.
- **FR-008**: System MUST include a checked-in Rogue Mutant Agent fixture for automated mutation testing in CI covering numerical threshold exceedance, out-of-order sequence violations, and missing approval tokens.

### Key Entities

- **ContractAST**: Root object representing `agent.contract.yaml`.
- **Invariant**: Rule definition containing `id`, `target`, `rule` (CEL string), and `on_violation`.
- **WorkflowContext**: Durable/ephemeral state tracking tool execution history and granted approval tokens.
- **GuardInterceptor**: Runtime decorator/wrapper around tool execution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of benchmark CEL invariants evaluate deterministically in < 1 millisecond per check.
- **SC-002**: Zero-LLM Hypothesis property fuzzer completes 500 boundary test iterations in < 2 seconds.
- **SC-003**: Automated mutation test fixture traps 100% of rogue mutant bypass attempts (0% escape rate).
- **SC-004**: Token cost for Phase 1 verification is exactly \$0.000.
