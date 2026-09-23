# Phase 0 Research: Dual-Synthesis Compiler & Self-Healing Verification Loop

**Feature**: `002-dual-synthesis-compiler`  
**Date**: 2026-09-23  
**Status**: Completed  

---

## 1. Synthesizer Personas & Prompt Architecture

### Decision
Implement two strictly decoupled system personas for code and test generation, supplemented by a deterministic AST code generator for protocol and mock interfaces:
1. **Interface & Mock Generator**: Deterministic AST-to-code generator that translates `ToolContract` schemas directly into `dist/interface.py` (typed `typing.Protocol` classes) and `dist/mocks.py` (synthetic test doubles).
2. **Agent Implementer Persona (`dist/agent.py`)**: An LLM synthesizer persona specialized in constructing explicit, typed Finite State Machines (FSM). The generated class binds to `dist/interface.py` and decorates every tool execution with `GuardInterceptor`.
3. **Adversarial Test Generator Persona (`dist/test_contract.py`)**: An adversarial QA persona instructed to probe the agent implementation. In addition to transcribing declared `Scenario` fixtures from the contract, it generates adversarial probe tests (boundary limit violations, out-of-order tool sequences, and malformed payload injection).

### Rationale
- **Constitution Principle V (De-Correlated Synthesis)** requires that the implementer and the tester do not share prompt context or biases. Generating tests with the same model prompt that wrote the agent risks mirroring the agent's logic flaws into the test assertions.
- Deterministic AST generation for `interface.py` and `mocks.py` guarantees 100% adherence to parameter JSON schemas and types without risking LLM hallucinations or syntax quirks in standard interfaces.
- The State Machine architecture for `dist/agent.py` simplifies validation, making agent execution inspectable and deterministic across discrete states (`INITIALIZING`, `PROCESSING`, `AWAITING_APPROVAL`, `COMPLETED`, `FAILED`).

### Alternatives Considered
- *Single-prompt generation of all files*: Rejected because errors in the agent's understanding of the contract propagate directly into the tests, blinding the verification loop to defects.
- *LLM generation of protocols and mocks*: Rejected because the contract already provides rigid JSON Schemas and types; deterministic code generation is faster, zero-cost, and completely immune to syntax hallucination.

---

## 2. Pluggable LLM Provider Architecture & Cost Discipline

### Decision
Define a lightweight, async `LLMProvider` protocol with three concrete implementations:
1. `MockLLMProvider`: Deterministic, offline provider driven by configurable canned response maps or AST templates. Required for zero-network CI runs, unit testing, and reproducible regression benchmarks.
2. `GeminiFlashProvider`: Direct REST adapter for Google Gemini Flash (`gemini-1.5-flash` / `gemini-2.0-flash`) via standard HTTP client (`urllib.request` / `httpx`).
3. `DeepSeekProvider`: OpenAI-compatible REST adapter for DeepSeek-V3 (`deepseek-chat`).

Every provider returns a structured `LLMResponse`:
```python
class LLMResponse(BaseModel):
    content: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    model_name: str
```

### Rationale
- Enables offline sandboxed execution for CI environments where external API calls are disabled or forbidden.
- Strict cost tracking guarantees compliance with **Constitution Architectural Constraint: Cost Discipline (< $0.05 per verified compile)**. Token costs are computed per turn based on standard pricing tables (DeepSeek-V3: $0.14/1M prompt, $0.28/1M completion; Gemini Flash: $0.075/1M prompt, $0.30/1M completion).

### Alternatives Considered
- *Heavy frameworks (e.g. LangChain, LiteLLM)*: Rejected to avoid unnecessary dependency bloat, fragile version drift, and overhead in the core compiler. Direct lightweight REST clients provide maximum control and auditability.

---

## 3. Sandboxed Verification Execution & Test Isolation

### Decision
Execute verification of candidate artifacts via a sandboxed subprocess running `pytest`:
- The compiler stages all generated artifacts in `dist/.staging/`.
- The verification runner invokes `python -m pytest dist/.staging/test_contract.py -v --tb=short` in a subprocess with a strict per-scenario timeout (default 10s per test, 60s total suite timeout).
- Network access is disabled by default via environment variables or mock injection.
- Test failures, standard error traces, and assertion errors are parsed and captured in a structured `VerificationReport`.

### Rationale
- Subprocess execution completely isolates compiler memory from candidate agent code execution, protecting against rogue agent side-effects, resource leaks, or infinite loops.
- Per-test timeout prevents runaway state machines from stalling the compilation pipeline (satisfies **FR-010**).
- Pytest integration produces rich, standardized tracebacks that feed directly into the self-healing loop.

### Alternatives Considered
- *In-process execution (`importlib.import_module` + `pytest.main()`)*: Rejected because running untrusted, freshly synthesized code within the compiler process risks polluting global state, hanging the compiler, or failing to cleanly reload modified modules across repair iterations.

---

## 4. Self-Healing Verification Loop & Diagnostic Payloads

### Decision
Structure the self-healing verification loop as a diagnostic-enriched full-module replacement cycle:
1. **Initial Synthesis**: Synthesizer outputs initial `dist/.staging/agent.py`.
2. **Verification Run**: `VerificationRunner` executes test suite against candidate agent.
3. **Evaluation**:
   - If 100% tests pass: Exit loop with status `CONVERGED`.
   - If failures occur: Collect failing test names, assertion tracebacks, and structured CEL invariant violation payloads (`invariant_id`, `rule`, `on_violation`, `violated_args`).
4. **Repair Synthesis**: Dispatch repair prompt containing:
   - The contract specification summary.
   - The current `agent.py` code.
   - The exact failure diagnostic traces and CEL invariant violation details.
   - Instruction to return the complete, corrected `agent.py` module.
5. **Iteration & Termination**:
   - Repeat up to `max_retries` (default 3).
   - If retry limit exhausted without convergence, terminate with status `FAILED_VERIFICATION` and log actionable repair history.

### Rationale
- Full module replacement is significantly more reliable for LLM code generation than git diff patches, which frequently suffer from line-offset drift and rejected hunks when synthesized by smaller/fast models.
- Enriching the prompt with exact CEL violation diagnostics directly guides the LLM to identify the precise guard rule that triggered fail-closed trapping.

### Alternatives Considered
- *Unified git diff patch synthesis*: Rejected due to high failure rate of LLMs generating syntactically valid unidiff patches against moving code targets.

---

## 5. Candidate Staging, Review Gate & Service Isolation

### Decision
1. **Strict Staging Isolation**:
   - All synthesis and self-healing operations occur strictly inside `dist/.staging/`.
   - The compiler enforces a path boundary check: any write outside `dist/` raises `SecurityError`. The human code directory `services/` is hard-coded as read-only to the compiler (satisfies **FR-005** and **SC-004**).
2. **Unified Git Diff Review Gate**:
   - Once verification achieves 100% pass status, the compiler generates a unified git diff between active `dist/` and `dist/.staging/`.
   - In interactive mode (default), the diff is rendered in the terminal using `rich.syntax.Syntax`, and the developer is prompted: `Promote verified artifacts to dist/? [y/N]`.
   - If approved, files are atomically moved from `dist/.staging/` to `dist/`.
   - If rejected, `dist/.staging/` is preserved or discarded as requested, and active `dist/` remains unchanged.
3. **Headless CI Mode (`--headless-ci`)**:
   - Bypasses interactive prompt and automatically promotes artifacts **only** if verification succeeded with 100% passing tests and zero invariant breaches.

### Rationale
- Enforces **Constitution Principle V (Human Review Gates)** and **Principle III (Strict Protocol Binding)**.
- Prevents silent overwrites and ensures developers maintain complete visibility over synthesized code before production promotion.
