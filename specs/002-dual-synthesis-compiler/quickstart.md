# Quickstart & Validation Guide: Dual-Synthesis Compiler & Self-Healing Loop

**Feature**: `002-dual-synthesis-compiler`  
**Date**: 2026-09-23  
**Status**: Ready for Validation  

---

## 1. Overview & Prerequisites

This guide provides end-to-end validation scenarios for the Dual-Synthesis Compiler and Self-Healing Verification Loop.

### Prerequisites
- Python 3.11 virtual environment initialized (`.venv/bin/python`).
- Dependencies installed via `uv sync` or `pip install -e .`.
- Benchmark contract files located in `tests/fixtures/benchmarks/`.

---

## 2. Validation Scenario 1: De-Correlated Dual-Synthesis (Headless CI Mode)

Validate that the compiler compiles an `agent.contract.yaml` file into isolated `dist/` artifacts using decoupled personas without human intervention in CI mode.

### Command
```bash
contract-agent compile tests/fixtures/benchmarks/01_billing_dispute.contract.yaml \
  --output-dir dist \
  --provider mock \
  --headless-ci
```

### Expected Outcome
- Exit code: `0`
- Verified build artifacts generated in `dist/`:
  - `dist/interface.py` (Typed Protocol definitions)
  - `dist/mocks.py` (Synthetic test doubles)
  - `dist/agent.py` (Finite State Machine implementation binding to `GuardInterceptor`)
  - `dist/test_contract.py` (Adversarial test suite)
- `services/` contains 0 modifications.
- Console output logs token telemetry and compilation cost:
  ```text
  [SUCCESS] All 100% invariant checks & adversarial tests passed.
  [CI] Auto-promoting artifacts from dist/.staging to dist.
  [TELEMETRY] Total tokens: 3,420 | Cost: $0.0000 | Compile Time: 0.82s
  ```

---

## 3. Validation Scenario 2: Automated Self-Healing Verification Loop

Validate that when initial candidate code contains a defect or invariant violation, the self-healing loop catches the error, enriches the repair prompt with CEL diagnostics, and converges within 3 retries.

### Command
```bash
# Run compiler with simulated initial defect injection
contract-agent compile tests/fixtures/benchmarks/01_billing_dispute.contract.yaml \
  --output-dir dist \
  --provider mock \
  --max-retries 3 \
  --headless-ci
```

### Expected Outcome
- Iteration 0: Candidate agent fails invariant check or scenario assertion.
- Loop captures failure traceback + CEL violation diagnostic.
- Iteration 1: Repaired agent is synthesized, re-tested, and achieves 100% pass rate.
- Status transitions to `CONVERGED` and proceeds to promotion.
- Console shows:
  ```text
  [VERIFY] Iteration 0: 1 failed, 3 passed. Initiating self-healing repair...
  [REPAIR] Invariant INV-001 violated: refund amount over limit.
  [VERIFY] Iteration 1: 4 passed, 0 failed (100% pass rate). Converged!
  ```

---

## 4. Validation Scenario 3: Interactive Unified Git Diff Review Gate

Validate that in interactive mode, the compiler pauses before promotion and requires explicit developer confirmation.

### Command
```bash
contract-agent compile tests/fixtures/benchmarks/01_billing_dispute.contract.yaml \
  --output-dir dist \
  --provider mock
```

### Expected Outcome
- Compilation runs, passes 100% verification in `dist/.staging/`.
- Terminal presents formatted unified git diff of proposed additions:
  ```diff
  --- /dev/null
  +++ b/dist/agent.py
  @@ -0,0 +1,85 @@
  +class BillingDisputeAgent:
  ...
  ```
- Terminal prompts: `Promote verified artifacts to dist/? [y/N]: `
- Responding `n` aborts promotion without modifying `dist/`.
- Responding `y` promotes files to `dist/` and exits code `0`.

---

## 5. Validation Scenario 4: Service Path Traversal & Isolation Guard

Validate that the compiler actively blocks any attempt to modify human service code.

### Command
```bash
uv run pytest tests/unit/compiler/test_isolation.py -v
```

### Expected Outcome
- Test asserts `ContractCompiler` raises `SecurityError` if any generation attempt targets paths outside `dist/` or targets `services/`.
- 100% pass rate on path protection tests.
