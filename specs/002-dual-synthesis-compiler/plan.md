# Implementation Plan: Dual-Synthesis Compiler & Self-Healing Verification Loop

**Branch**: `002-dual-synthesis-compiler` | **Date**: 2026-09-23 | **Spec**: [specs/002-dual-synthesis-compiler/spec.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/spec.md)

**Input**: Feature specification from `/specs/002-dual-synthesis-compiler/spec.md` with integrated clarifications.

## Summary

Implement the Dual-Synthesis Compiler and Self-Healing Verification Loop for ContractAgent:
1. Deterministic AST code generator for typed Python Protocols (`dist/interface.py`) and synthetic test mocks (`dist/mocks.py`).
2. Decoupled dual-synthesis personas: an Agent Implementer synthesizing typed Finite State Machines in `dist/agent.py` bound to `GuardInterceptor`, and an Adversarial Test Generator producing golden scenarios and adversarial probes in `dist/test_contract.py`.
3. Pluggable `LLMProvider` interface with native adapters for Gemini Flash, DeepSeek-V3, and a zero-network deterministic mock provider for CI.
4. Sandboxed verification runner that executes tests in an isolated subprocess with 10s per-test execution timeouts.
5. Automated self-healing loop that enriches repair prompts with assertion traces and CEL invariant violation diagnostics, converging within 3 retries.
6. Isolated build staging in `dist/.staging/`, strict protection forbidding writes to `services/`, and an interactive unified git diff review gate (with `--headless-ci` auto-promotion).
7. Comprehensive token and financial cost telemetry guaranteeing expenditure remains under $0.05 per verified compile.

## Technical Context

**Language/Version**: Python 3.11+ (with strict typing enforced by Pyrefly and Mypy).

**Primary Dependencies**:
- `pydantic>=2.7.0`: AST schema validation & compiler configuration models
- `cel-python>=0.5.0`: Non-Turing complete runtime invariant evaluation
- `pyyaml>=6.0.0`: Contract parsing
- `typer>=0.12.0`: CLI command interface (`contract-agent compile`)
- `rich>=13.7.0`: Terminal formatting, tables, and unified diff syntax highlighting
- `pytest`, `pytest-asyncio`: Sandboxed test verification harness
- `hypothesis>=6.100.0`: Property testing for generated CEL rules

**Storage**: Ephemeral build files staged in `dist/.staging/` and promoted atomically to `dist/`. In-memory `WorkflowContext` for test run tracking.

**Testing**: Pytest unit tests, compiler integration tests with offline mock provider, 3-contract convergence benchmark suite (`01_billing_dispute`, `02_sql_read_only_agent`, `03_api_sync_agent`).

**Target Platform**: macOS (Apple Silicon / Intel), Linux x86_64/arm64.

**Project Type**: Python CLI tool & compiler library.

**Performance Goals**: < 1.0s compilation & verification using offline mock provider; < 10s per test execution timeout; < $0.05 compilation cost ceiling.

**Constraints**: Zero LLM involvement in CEL invariant evaluation; 100% isolation protecting human code in `services/`; sandboxed zero-network CI operation.

**Scale/Scope**: 4 generated artifacts (`interface.py`, `mocks.py`, `agent.py`, `test_contract.py`); 3 benchmark contracts.

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`*

| Principle | Compliance Notes | Status |
| :--- | :--- | :--- |
| **I. Spec-as-Source** | `agent.contract.yaml` is the immutable source of truth. All files in `dist/` are disposable, reproducible build artifacts. | PASS |
| **II. Deterministic CEL** | All invariant rules evaluated strictly with `GuardInterceptor` and `CELEngine`. Zero LLM involvement in runtime rule evaluation. | PASS |
| **III. Strict Protocol Binding** | Generates typed Protocols in `dist/interface.py`. Human code in `services/` is never touched (strictly enforced by path guards). | PASS |
| **IV. Layered Verification** | Sandboxed test execution verifies scenario assertions, boundary limits, and rogue mutant trapping before human gate. | PASS |
| **V. De-Correlated Synthesis & Review Gates** | Implementer and tester personas operate independently. Interactive unified git diff review gate intercepts all promotions. | PASS |
| **VI. Atomic Commits & Small-Step Discipline** | Sized for atomic commits under 200 LOC and 10 files per task. | PASS |
| **VII. Feature Branch Isolation** | Developed on branch `002-dual-synthesis-compiler`. | PASS |
| **VIII. Protected Main & PR Protocol** | Verified via Pyrefly (0 errors) and automated PR creation at convergence. | PASS |

## Design Artifacts

- **Phase 0 Research**: [research.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/research.md)
- **Data Model**: [data-model.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/data-model.md)
- **Contracts**:
  - [compiler-api.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/contracts/compiler-api.md)
  - [llm-provider-api.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/contracts/llm-provider-api.md)
  - [self-healing-api.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/contracts/self-healing-api.md)
- **Quickstart & Validation Guide**: [quickstart.md](file:///Users/stefano/Documents/contract-agent/specs/002-dual-synthesis-compiler/quickstart.md)

## Project Structure

### Documentation (this feature)

```text
specs/002-dual-synthesis-compiler/
├── spec.md              # Feature specification with clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 research & architectural decisions
├── data-model.md        # Entities, value objects & state machine
├── contracts/           # Interface contracts
│   ├── compiler-api.md
│   ├── llm-provider-api.md
│   └── self-healing-api.md
├── quickstart.md        # End-to-end validation scenarios
└── tasks.md             # Actionable tasks (generated in Phase 2)
```

### Source Code (repository root)

```text
src/
└── contract_agent/
    ├── cli/
    │   ├── __init__.py
    │   ├── main.py              # Typer CLI application (contract-agent compile)
    │   └── review.py            # Interactive unified git diff review gate
    ├── compiler/
    │   ├── __init__.py
    │   ├── orchestrator.py      # ContractCompiler orchestration engine
    │   ├── code_generator.py    # Deterministic Protocol & Mock code generator
    │   ├── personas.py          # Decoupled Implementer & Tester persona templates
    │   ├── providers.py         # LLMProvider protocol, Mock, Gemini & DeepSeek
    │   ├── telemetry.py         # Token counting & dollar cost accounting
    │   ├── verification.py      # Sandboxed subprocess test runner with timeouts
    │   └── self_healing.py      # Diagnostic-enriched repair loop engine
    └── ... (existing core & runtime modules)

tests/
├── fixtures/
│   └── benchmarks/
│       ├── 01_billing_dispute.contract.yaml
│       ├── 02_sql_read_only_agent.contract.yaml
│       └── 03_api_sync_agent.contract.yaml
├── unit/
│   └── compiler/
│       ├── test_code_generator.py
│       ├── test_providers.py
│       ├── test_telemetry.py
│       ├── test_isolation.py
│       └── test_review_gate.py
└── integration/
    └── compiler/
        ├── test_compiler_pipeline.py
        ├── test_self_healing_loop.py
        └── test_benchmark_convergence.py
```

**Structure Decision**: Integrated within the single `src/contract_agent` project structure under a new `compiler/` subsystem, with CLI commands in `contract_agent.cli` and benchmark fixtures in `tests/fixtures/benchmarks/`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations detected. All constitution principles satisfied.*
