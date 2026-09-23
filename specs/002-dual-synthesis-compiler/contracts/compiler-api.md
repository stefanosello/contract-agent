# Contract: Compiler API & CLI Interface

**Target Module**: `contract_agent.compiler` & `contract_agent.cli.main`  
**Feature**: `002-dual-synthesis-compiler`  
**Date**: 2026-09-23  

---

## 1. Programmatic Compiler API

### 1.1 Class Signature: `ContractCompiler`

```python
class ContractCompiler:
    """Orchestrates dual-synthesis, sandboxed verification, self-healing, and review gate promotion."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        budget_ceiling: float = 0.05,
        per_test_timeout: float = 10.0,
    ) -> None:
        ...

    def compile(
        self,
        contract_path: Path | str,
        output_dir: Path | str = Path("dist"),
        staging_dir: Path | str = Path("dist/.staging"),
        max_retries: int = 3,
        headless_ci: bool = False,
    ) -> CompilationResult:
        """Executes full compilation pipeline:
        1. Parse and validate contract AST.
        2. Deterministically generate dist/.staging/interface.py and dist/.staging/mocks.py.
        3. Dual-synthesize dist/.staging/agent.py and dist/.staging/test_contract.py.
        4. Execute self-healing verification loop until 100% tests pass or retries exhausted.
        5. Present unified git diff review gate (or auto-promote in headless CI).
        6. Return CompilationResult.
        """
        ...
```

### 1.2 Path Traversal & Service Isolation Guarantee

```python
def validate_output_path(target_path: Path, workspace_root: Path) -> None:
    """Verifies target_path is strictly within 'dist/' and does not collide with 'services/' or system paths.
    
    Raises:
        SecurityError: If target path traverses outside dist/ or targets human code in services/.
    """
```

---

## 2. CLI Command Specification

### 2.1 Command: `contract-agent compile`

```text
Usage: contract-agent compile [OPTIONS] CONTRACT_PATH

Arguments:
  CONTRACT_PATH     Path to the input agent.contract.yaml [required]

Options:
  --output-dir PATH         Directory for verified artifacts [default: dist]
  --provider TEXT           LLM provider to use (mock, gemini-flash, deepseek) [default: mock]
  --model TEXT              Specific model identifier override
  --max-retries INTEGER     Maximum self-healing retry iterations [default: 3]
  --budget-ceiling FLOAT    Maximum compilation expenditure in USD [default: 0.05]
  --headless-ci             Run non-interactively in CI mode (auto-promote on 100% pass)
  --help                    Show this message and exit.
```

### 2.2 CLI Exit Codes
- `0`: Compilation succeeded and verified artifacts promoted to `dist/`.
- `1`: Validation or contract syntax error.
- `2`: Verification failed (self-healing retries exhausted).
- `3`: Budget ceiling exceeded.
- `4`: Promotion rejected by human review gate.
- `5`: Security violation (attempted write outside `dist/`).
