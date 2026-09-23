# Tasks: ContractAgent Core CEL Invariant Engine & AST Parser

**Input**: Design documents from `/specs/001-core-engine/`

**Prerequisites**: [plan.md](file:///Users/stefano/Documents/contract-agent/specs/001-core-engine/plan.md), [spec.md](file:///Users/stefano/Documents/contract-agent/specs/001-core-engine/spec.md)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Python project packaging and environment configuration

- [ ] T001 Initialize `pyproject.toml` with dependencies (`pydantic>=2.7`, `cel-python`, `pyyaml`, `hypothesis`, `pytest`, `pytest-asyncio`).
- [ ] T002 Create package directories: `src/contract_agent/{core,runtime,testing}` and `tests/{unit,property,mutation}`.
- [ ] T003 Configure `pytest.ini` with test markers and strict asyncio mode.

---

## Phase 2: Foundational

**Purpose**: Core exception hierarchy and durable workflow context

- [ ] T004 Implement `src/contract_agent/core/exceptions.py` with `ContractValidationError`, `InvariantViolationError`, and `CompilationError`.
- [ ] T005 Implement `src/contract_agent/runtime/context.py` with `WorkflowContext` supporting turn call tracking and SQLite/memory approval store.

---

## Phase 3: User Story 1 - Declarative Contract Parsing & Validation (Priority: P1) 🎯

**Goal**: Parse and validate `agent.contract.yaml` into strongly typed Pydantic models.

- [ ] T006 [P] [US1] Implement `src/contract_agent/core/ast.py` defining Pydantic models for `Metadata`, `Invariant`, `ToolContract`, `Scenario`, and `ContractAST`.
- [ ] T007 [US1] Implement `src/contract_agent/core/parser.py` with `load_contract(path)` and semantic validation.
- [ ] T008 [US1] Create unit tests in `tests/unit/test_ast_parser.py` covering valid contracts and malformed/missing schema errors.

---

## Phase 4: User Story 2 - Deterministic CEL Invariant Evaluation (Priority: P1)

**Goal**: Compile and evaluate invariant rules using Google CEL with custom workflow functions.

- [ ] T009 [P] [US2] Implement `src/contract_agent/runtime/cel_engine.py` wrapping the CEL environment and registering `workflow.has_approval`, `workflow.called_before`, and `workflow.call_count`.
- [ ] T010 [US2] Implement invariant evaluation function `evaluate_invariant(invariant, args, context) -> InvariantResult`.
- [ ] T011 [US2] Create unit tests in `tests/unit/test_cel_engine.py` testing boundary arithmetic, logical operators, and custom functions.

---

## Phase 5: User Story 3 - Zero-LLM Property-Based Fuzzing with Hypothesis (Priority: P1)

**Goal**: Mathematically verify boundary conditions of CEL rules for $0 token cost.

- [ ] T012 [P] [US3] Implement `src/contract_agent/testing/fuzzing.py` creating Hypothesis strategies derived from tool parameter schemas.
- [ ] T013 [US3] Create property tests in `tests/property/test_cel_fuzzing.py` verifying that numeric boundaries (e.g. `<= 25000`) partition valid/invalid inputs with 100% precision.

---

## Phase 6: User Story 4 - Fail-Closed Runtime Guard Interceptor (Priority: P2)

**Goal**: Intercept tool executions at runtime and halt violating calls before execution.

- [ ] T014 [US4] Implement `src/contract_agent/runtime/guards.py` with `@guard_tool` decorator and `GuardInterceptor` class.
- [ ] T015 [US4] Create unit tests in `tests/unit/test_guards.py` asserting that illegal tool calls never invoke the target handler and raise `InvariantViolationError`.

---

## Phase 7: User Story 5 - Automated Mutation Testing Fixture (Priority: P2)

**Goal**: Guarantee 100% fail-closed trapping on deliberately rogue mutant agents in CI.

- [ ] T016 [P] [US5] Implement `src/contract_agent/testing/mutants.py` containing a hardcoded rogue agent that ignores invariants.
- [ ] T017 [US5] Create mutation test in `tests/mutation/test_rogue_mutant.py` asserting a 0% escape rate on unauthorized actions.
