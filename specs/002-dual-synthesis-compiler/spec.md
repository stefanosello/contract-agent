# Feature Specification: Dual-Synthesis Compiler & Self-Healing Verification Loop

**Feature Branch**: `002-dual-synthesis-compiler`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Dual-synthesis compiler and self-healing verification loop"

## Clarifications

### Session 2026-09-23
- Q: What core runtime execution pattern should the compiler synthesize for the agent in `dist/agent.py`? → A: Option A — Explicit State Machine (synthesizes a typed Finite State Machine class where states model workflow stages, transitions trigger tool calls, and execution binds to `GuardInterceptor`).
- Q: What test vectors should the de-correlated Adversarial Test Generator synthesize in `dist/test_contract.py` beyond declared contract scenarios? → A: Option A — Golden Scenarios + Adversarial Probes (generate tests for declared scenarios plus probe tests testing boundary limits, skipped prerequisites, and malformed mock payloads).
- Q: How should the self-healing verification loop structure repair prompts when a candidate agent fails invariant checks or tests? → A: Option A — Diagnostic-Enriched Full Module Repair (send the current agent code, failing test assertion traces, and structured invariant violation payloads, requesting a corrected replacement `dist/agent.py`).
- Q: How should the compiler configure LLM backends to support both budget-efficient live models (DeepSeek-V3, Gemini Flash) and zero-network CI execution? → A: Option A — Pluggable multi-backend with offline mock (implement an `LLMProvider` interface supporting Gemini Flash, DeepSeek-V3, and a deterministic offline mock provider for sandboxed CI runs).
- Q: Where should candidate artifacts be staged during synthesis and self-healing before passing the human review gate? → A: Option A — Isolated Staging Directory with Atomic Promotion (stage files in a temporary build directory `dist/.staging/` during synthesis and self-healing; atomically promote to `dist/` only after verification passes and human approval is granted).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - De-Correlated Dual-Synthesis Compilation (Priority: P1) 🎯 MVP

As an agent engineer, I want the compiler to process my behavioral contract (`agent.contract.yaml`) and generate both the agent implementation and an adversarial test suite using decoupled, independent synthesizer personas, so that implementation bugs are not hidden by correlated blindspots in test generation.

**Why this priority**: Dual-synthesis is the core generation mechanism that transforms declarative contracts into executable agents and test suites, upholding Constitution Principle I (Spec-as-Source), Principle III (Strict Protocol Binding), and Principle V (De-Correlated Synthesis).

**Independent Test**: Run `contract-agent compile agent.contract.yaml` on a valid specification and assert that:
1. Typed protocol definitions (`dist/interface.py`) and synthetic mocks (`dist/mocks.py`) are produced.
2. Agent implementation (`dist/agent.py`) is generated binding strictly to protocols.
3. Adversarial test suite (`dist/test_contract.py`) is generated using a distinct adversarial persona.
4. Human backend services (`services/`) remain completely untouched.

**Acceptance Scenarios**:

1. **Given** a valid contract with tools and invariants, **When** compiled, **Then** generates typed protocols, mocks, agent implementation, and adversarial tests in the designated output directory without touching human service files.
2. **Given** tools declared in the contract, **When** compiled, **Then** generated synthetic mocks implement the exact protocol signatures required by the agent.

---

### User Story 2 - Automated Self-Healing Verification Loop (Priority: P1)

As a developer, I want the compiler to automatically run the synthesized agent against the adversarial test suite and CEL runtime guards, capturing test failures or invariant breaches and feeding the diagnostics into a self-healing loop to iteratively correct the agent code before presenting the result.

**Why this priority**: Autonomous self-healing prevents developers from having to manually debug transient LLM synthesis mistakes, ensuring high first-time pass rates.

**Independent Test**: Execute compilation on a contract where initial synthesized agent logic contains a simulated logic defect; assert the verification runner captures the failure, prompts the self-healing engine, and produces a passing agent within the maximum retry limit (default 3 iterations).

**Acceptance Scenarios**:

1. **Given** a synthesized candidate that fails a scenario assertion or violates a CEL guard, **When** executed by the verification runner, **Then** the failure diagnostics and execution trace are captured and dispatched to the self-healing loop.
2. **Given** an active self-healing attempt within the retry limit, **When** the repaired candidate satisfies 100% of invariant checks and scenario tests, **Then** compilation proceeds to the review gate.
3. **Given** a candidate that fails all retry iterations (e.g. 3 attempts), **When** exhausted, **Then** the compiler halts with a detailed diagnostic report and does not promote unverified code.

---

### User Story 3 - Interactive Unified Git Diff Review Gate (Priority: P2)

As a developer, I want the compiler to present an interactive unified git diff of all proposed code modifications before promoting them to verified status, requiring explicit developer approval unless running in headless CI mode.

**Why this priority**: Enforces Constitution Principle V (Human Review Gates), guaranteeing that AI-synthesized code is never promoted or deployed silently without human oversight.

**Independent Test**: Run compilation interactively and assert execution pauses at the review gate displaying a unified diff; confirm that typing "yes" promotes the code while "no" discards it. In headless mode (`--headless-ci`), verify auto-promotion occurs only when all verification gates pass with zero errors.

**Acceptance Scenarios**:

1. **Given** a successfully verified compile in interactive mode, **When** the review gate triggers, **Then** a unified diff is displayed and developer approval is required to promote generated artifacts.
2. **Given** a compile run with `--headless-ci`, **When** all tests pass 100%, **Then** artifacts are promoted automatically without interactive prompts.
3. **Given** a compile run with `--headless-ci`, **When** any invariant or test fails, **Then** compilation exits with a non-zero error code and artifacts are not promoted.

---

### User Story 4 - Multi-Model Cost & Budget Tracking (Priority: P2)

As a team lead, I want the compiler to track token usage and synthesis expenses per compilation run, ensuring compilation costs remain under target budget thresholds (< $0.05 per verified compile).

**Why this priority**: Enforces cost discipline and transparency across multiple synthesis iterations and adversarial test generation.

**Independent Test**: Compile benchmark contracts and inspect the telemetry summary; assert token counts, model identifiers, and dollar costs are logged and within threshold limits.

**Acceptance Scenarios**:

1. **Given** a compilation run with multiple synthesis and self-healing turns, **When** compilation finishes, **Then** a breakdown of prompt tokens, completion tokens, and dollar cost is reported.
2. **Given** a configured budget ceiling, **When** token usage exceeds the limit, **Then** the compiler gracefully aborts rather than incurring runaway expenses.

---

## Edge Cases

- **Self-Healing Loop Exhaustion**: If the synthesizer cannot pass all tests within the configured retry limit (default 3 iterations), compilation terminates with status `FAILED_VERIFICATION`, outputs the diff of the highest-scoring candidate, and logs actionable diagnostics.
- **Accidental Path Traversal / Overwrite Protection**: The compiler strictly forbids write operations outside the target artifact build directory (`dist/`). Any attempt to overwrite files in `services/` or project configuration triggers an immediate abort.
- **Infinite Loop / Execution Timeout**: Test execution during the self-healing loop runs with per-scenario timeouts (e.g. 10 seconds per test) to prevent hanging synthesized code from stalling the pipeline.
- **Flaky or Non-Deterministic Synthesizer Outputs**: Scenarios and invariants must pass consistently across verification runs before promotion.
- **Offline / Sandbox Operation**: Supports mock and offline synthesizer fixtures so CI pipelines can verify compiler and self-healing loop mechanics with zero external network access.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compile `agent.contract.yaml` specifications into typed Python Protocol definitions in `dist/interface.py`.
- **FR-002**: System MUST generate synthetic test mocks implementing the exact generated protocols in `dist/mocks.py`.
- **FR-003**: System MUST synthesize the agent implementation in `dist/agent.py` as an explicit, typed Finite State Machine whose state transitions trigger tool calls and bind strictly to generated protocols and `GuardInterceptor`.
- **FR-004**: System MUST generate an adversarial test suite in `dist/test_contract.py` covering declared contract scenarios plus automated probe tests targeting boundary limits, skipped prerequisites, and malformed mock payloads using a distinct adversarial persona.
- **FR-005**: System MUST strictly isolate generated code to `dist/` and MUST NEVER overwrite human service files in `services/`.
- **FR-006**: System MUST execute a self-healing verification loop upon test failure, providing the current agent code, failing test assertion traces, and structured CEL invariant violation payloads to prompt full module repair up to a configurable maximum retry limit (default 3).
- **FR-007**: System MUST stage synthesized candidates in an isolated build directory (`dist/.staging/`), presenting a unified Git diff against active artifacts and requiring explicit confirmation before atomically promoting to `dist/` in interactive mode.
- **FR-008**: System MUST support a `--headless-ci` flag that bypasses interactive diff confirmation only when 100% of invariant checks and tests pass.
- **FR-009**: System MUST track prompt tokens, completion tokens, and estimated financial cost per compilation run, logging a summary upon completion.
- **FR-010**: System MUST enforce per-test execution timeouts during verification to terminate hanging or runaway code safely.
- **FR-011**: System MUST provide a pluggable `LLMProvider` interface supporting Gemini Flash, DeepSeek-V3, and a deterministic offline mock provider for sandboxed CI runs.

### Key Entities

- **CompilationJob**: Configuration and state for a single contract compilation run (contract path, target directory, model config, retry limits, budget ceiling).
- **LLMProvider**: Pluggable backend adapter protocol for LLM API invocation and offline mock synthesis.
- **SynthesizerPersona**: Prompt template and persona specification differentiating the Agent Implementer from the Adversarial Test Generator.
- **VerificationReport**: Structured test execution output detailing passed/failed scenarios, invariant breaches, execution timings, and error stack traces.
- **SelfHealingSession**: State machine tracking iteration count, candidate diffs, error history, and convergence status across repair attempts.
- **CostTelemetry**: Financial and token accounting record tracking prompt/completion tokens and dollar cost by model and phase.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of benchmark contracts compile and pass invariant verification tests.
- **SC-002**: Self-healing loop repairs transient implementation defects within 3 iterations for at least 80% of fixable code errors.
- **SC-003**: Average compilation expense across benchmark contracts remains strictly below $0.05 per verified compile.
- **SC-004**: 0% of human service files in `services/` are modified or overwritten during compilation (100% isolation).
- **SC-005**: Interactive review gate intercepts 100% of candidate promotions in interactive mode, requiring explicit human approval.

---

## Assumptions

- Contracts supplied to the compiler have been validated by `ContractParser` (Feature 001) and are free of schema errors.
- Synthesizer backends support structured JSON or markdown code block responses.
- The environment provides Git for generating unified diffs.
- Sandboxed test execution operates locally with network access disabled by default during CI runs.
