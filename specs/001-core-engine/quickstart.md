# Quickstart & Validation Guide: ContractAgent Core Engine

**Branch**: `001-core-engine` | **Feature**: Core CEL Invariant Engine & AST Parser

This guide provides end-to-end scenarios to validate that the ContractAgent Core Engine, CEL evaluation environment, property fuzzer, and guard interceptor operate correctly.

---

## 1. Prerequisites & Environment Setup

Ensure Python 3.11+ and dependencies are installed in your virtual environment:

```bash
uv sync --all-extras
```

Verify type-checking and linting tools are ready:

```bash
uv run ruff check .
uv run pyrefly check
```

---

## 2. Validation Scenarios

### Scenario 1: Contract Parsing & Static CEL Validation

**Objective**: Verify that valid contracts parse into typed AST objects and invalid/malformed contracts fail fast.

```bash
# Run unit tests for contract loading and static CEL compilation
uv run pytest tests/unit/test_ast_parser.py -v
```

**Expected Outcome**:
- Valid YAML contracts parse into `ContractAST` with 100% field type validation.
- Malformed CEL expressions or invalid parameter references raise `ContractValidationError` with detailed diagnostics.

---

### Scenario 2: Deterministic CEL Invariant Evaluation

**Objective**: Verify linear-time, fail-closed CEL boolean evaluations and custom workflow functions (`has_approval`, `called_before`, `call_count`).

```bash
# Run unit tests for CEL evaluation and workflow extensions
uv run pytest tests/unit/test_cel_engine.py -v
```

**Expected Outcome**:
- Numerical comparisons, boolean logic, and overloaded workflow extensions evaluate deterministically in < 1ms.

---

### Scenario 3: Zero-LLM Property-Based Fuzzing with Hypothesis

**Objective**: Verify automated schema-driven boundary fuzzing across invariant rules without any LLM token usage.

```bash
# Run property-based boundary test suite
uv run pytest tests/property/test_cel_fuzzing.py -v
```

**Expected Outcome**:
- 500+ randomized boundary iterations execute in < 2 seconds.
- Valid parameter boundaries evaluate accurately without uncaught runtime exceptions.

---

### Scenario 4: Fail-Closed Runtime Guard Interception

**Objective**: Verify that `GuardInterceptor` intercepts tool calls, evaluates CEL rules, and dispatches the correct violation action.

```bash
# Run runtime guard interceptor unit tests
uv run pytest tests/unit/test_guards.py -v
```

**Expected Outcome**:
- `raise_invariant_violation` raises `InvariantViolationError` and prevents tool execution.
- `block_tool_call` returns a structured error payload to the agent loop.
- `require_escalation` raises `EscalationRequiredError` with approval metadata.

---

### Scenario 5: CI Mutation Testing with Rogue Mutants

**Objective**: Verify that 100% of rogue mutant bypass attempts (limits, sequence skips, missing approvals) are trapped.

```bash
# Run rogue mutant mutation suite
uv run pytest tests/mutation/test_rogue_mutant.py -v
```

**Expected Outcome**:
- 0% escape rate: 100% of mutant execution attempts are trapped before handler execution.

---

## 3. Full Verification Suite

To run all quality gates in a single command:

```bash
uv run pytest
```
