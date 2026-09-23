# ContractAgent Constitution
<!-- The foundational principles and governance rules of the ContractAgent framework -->

## Core Principles

### I. Spec-as-Source for Agent Behaviors
The behavioral specification (`agent.contract.yaml`) is the durable, immutable source of truth. Generated Python code, state machine graphs, and test suites are disposable, reproducible build artifacts. Humans modify the contract; the compiler reconciles the implementation.

### II. Deterministic Runtime Enforcement via CEL
Behavioral invariants and guardrails are compiled into Google Common Expression Language (CEL) predicates evaluated with **zero LLM involvement** at runtime. Evaluators are non-Turing complete, memory-bounded, and fail-closed. LLMs are never entrusted with judging whether an action violates a hard invariant.

### III. Strict Protocol Binding (Interface vs. Implementation)
The compiler strictly generates typed Python Protocols (`dist/interface.py`). The agent core binds to these protocols. Human developers author live production handlers (`services/`) independently. Synthetic mocks (`dist/mocks.py`) implement the exact same protocol for evaluation. Generated code never overwrites human backend services.

### IV. Layered Mathematical & Mutation Verification
Before any LLM-synthesized code is tested, the compiler executes Zero-LLM verification:
1. Hypothesis property-based fuzzing mathematically validates CEL guard boundary conditions against the contract schema.
2. Automated mutation testing fixtures inject rogue agent mutants to verify 100% fail-closed trapping in CI.

### V. De-Correlated Synthesis & Human Review Gates
The Agent Synthesizer and Adversarial Test Generator operate under decoupled, adversarial system personas (and distinct models where possible) to prevent correlated blindspots. Self-healing patches require an interactive unified Git diff review before being promoted to verified status; silent auto-promotion is prohibited except when explicitly flagged for headless CI.

## Architectural Constraints

- **Language & Runtime**: Python 3.11+ with strict type annotations enforced by Pyrefly (`pyrefly check`).
- **Expression Engine**: Pure CEL (no Python `ast` or `eval` execution for rules).
- **Asynchronous Human Escalation**: Approvals are first-class, out-of-band asynchronous state transitions stored in durable state (SQLite/Postgres) keyed by `(approval_type, resource_id)`.
- **Cost Discipline**: Compilation is architected for budget efficiency (< $0.05 per verified compile using DeepSeek-V3 and Gemini Flash).

## Quality Gates & Verification

- Every compile must satisfy 100% of invariant checks across all defined scenarios.
- The 3-contract Convergence Benchmark Suite (`01_billing_dispute`, `02_sql_read_only_agent`, `03_api_sync_agent`) must pass on every CI run.
- Network access is disabled by default during sandboxed test execution.

## Governance

This Constitution governs all design decisions, code generation templates, and pull requests in the ContractAgent repository. Any proposed deviation from deterministic invariant enforcement or the human review gate must be documented and justified via an Architecture Decision Record (ADR).

**Version**: 1.0.0 | **Ratified**: 2026-09-23 | **Last Amended**: 2026-09-23
