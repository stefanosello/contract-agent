# Phase 0 Research: ContractAgent Core Engine & AST Parser

**Branch**: `001-core-engine` | **Feature**: Core CEL Invariant Engine & AST Parser

This document details the architectural and technology decisions for Phase 1 of ContractAgent, resolving all technical context and implementation considerations.

---

## 1. CEL Evaluation Engine & Custom Function Binding

### Decision
Use `cel-python` (Google Common Expression Language implementation in Python) to parse, compile, and evaluate invariant expressions deterministically. Register custom workflow functions (`workflow.has_approval`, `workflow.called_before`, `workflow.call_count`) via custom function activation bindings.

### Rationale
- **Deterministic & Non-Turing Complete**: CEL guarantees linear-time execution, terminating without unbounded loops or recursion risks.
- **Zero LLM Involvement**: Evaluates expressions using pure mathematical logic and structured execution context, eliminating hallucinations.
- **Fast Evaluation**: Sub-millisecond (< 1ms) execution per invariant check in Python.
- **Overloaded Workflow Signatures**:
  - `workflow.has_approval(type: string, resource_id: string) -> bool`
  - `workflow.called_before(prior_tool: string, target_tool: string) -> bool`
  - `workflow.called_before(prior_tool: string, target_tool: string, correlation_id: string) -> bool`
  - `workflow.call_count(tool_name: string) -> int`
  - `workflow.call_count(tool_name: string, correlation_id: string) -> int`

### Alternatives Considered
- `eval()` or Python AST: Rejected due to security vulnerabilities, non-deterministic execution, and violation of Constitution Principle II.
- `simpleeval` / `asteval`: Lacks native CEL syntax compatibility, standard CEL operators (`has()`, `size()`), and industry portability.

---

## 2. Parse-Time CEL & Parameter Schema Validation

### Decision
`ContractParser` validates CEL expressions statically at contract load time (`from_file` and `from_dict`). The parser:
1. Compiles the CEL expression to catch syntax errors immediately.
2. Cross-checks variable identifiers referenced in the expression (e.g., `args.amount_cents`) against the target `ToolContract.parameters` JSON Schema.
3. Validates that referenced tools and scenario expectations exist in the contract declaration.
4. Raises `ContractValidationError` with path and error diagnostics if validation fails.

### Rationale
- **Fail-Fast**: Catches invalid invariants, typos, and schema mismatches during static contract loading before synthesis, compilation, or runtime execution.
- **Spec & Constitution Alignment**: Enforces Constitution Principle I (Spec-as-Source) and Principle IV (Zero-LLM Verification).

### Alternatives Considered
- Deferred Runtime Compilation: Only compiling CEL when tools are executed. Rejected because contract syntax bugs would be discovered too late in production or during LLM synthesis.

---

## 3. Hypothesis Property-Based Fuzzing Strategy Synthesis

### Decision
Implement an automated Hypothesis strategy generator (`fuzzing.py`) that:
1. Synthesizes Hypothesis search strategies directly from `ToolContract.parameters` JSON Schema definitions (`type: integer`, `type: number`, `minimum`, `maximum`, `type: string`, `enum`, `type: boolean`).
2. Provides a strategy override registry so developers can supply custom Hypothesis composite strategies for complex or domain-specific types.
3. Automatically executes 500+ randomized iterations testing invariant boundary transitions (e.g., limit thresholds, edge-case strings, null safety).

### Rationale
- **Zero Token Cost**: Mathematically proves invariant behavior and boundary conditions with $0 LLM spend.
- **Developer Ergonomics**: Out-of-the-box automatic generation for standard contracts, with manual override flexibility when domain-specific constraints are required.

### Alternatives Considered
- Manual Hypothesis tests only: Increases developer friction and risks untested invariant edge cases.
- Pure random fuzzing: Lacks boundary-value targeting (e.g. min, max, min-1, max+1) provided by Hypothesis.

---

## 4. Fail-Closed Runtime Guard Interceptor & Violation Actions

### Decision
Implement `GuardInterceptor` as a runtime wrapper/decorator around tool executions with differentiated violation dispatch:
1. **Target Invariant Scoping**: When a tool is called, interceptor evaluates:
   - Specific tool invariants (`target == f"tool:{tool_name}"`)
   - Global wildcard invariants (`target == "*"`)
   - Session sequence invariants (`target == "session:call_sequence"` or session rules gating the tool)
2. **Action Dispatch**:
   - `raise_invariant_violation`: Raises `InvariantViolationError` (fail-closed, aborts tool handler).
   - `block_tool_call`: Returns a structured error dictionary `{"error": "Tool call blocked by invariant <id>", "invariant_id": ...}` to allow the agent to self-correct.
   - `require_escalation`: Raises `EscalationRequiredError` containing approval metadata `{"approval_type": ..., "resource_id": ...}` to suspend execution for asynchronous human sign-off.
3. **Fail-Closed on Error**: Any CEL evaluation error or missing context parameter treats the invariant as violated (`False`).

### Rationale
- Guarantees strict boundary enforcement before any handler or external network call occurs.
- Supports both autonomous agent recovery (via soft tool blocks) and human-in-the-loop governance (via escalation).

---

## 5. Rogue Mutant Agent Fixture for CI Verification

### Decision
Provide a checked-in Rogue Mutant Agent test fixture (`mutants.py`) in CI that injects rogue agent behaviors across 3 attack vectors:
1. **Numerical Boundary Violations**: Exceeding monetary/rate limits (e.g., amount > $250.00).
2. **Sequence Skips / Out-of-Order Calls**: Invoking sensitive tools without prerequisite discovery/fetch tools.
3. **Missing Human Approvals**: Attempting high-privilege operations without required approval tokens.

Asserts a 100% trap rate (0% escape to backend handlers) on every CI run.

### Rationale
- Enforces Constitution Principle IV (Layered Mathematical & Mutation Verification).
- Protects against framework regressions that could cause guards to fail open.
