# Contract: Self-Healing Verification Loop & Diagnostic API

**Target Module**: `contract_agent.compiler.verification` & `contract_agent.compiler.self_healing`  
**Feature**: `002-dual-synthesis-compiler`  
**Date**: 2026-09-23  

---

## 1. Sandboxed Verification Runner API

### 1.1 Class Signature: `SandboxedVerificationRunner`

```python
class SandboxedVerificationRunner:
    """Executes synthesized test suites in an isolated subprocess with timeouts."""

    def __init__(self, per_test_timeout: float = 10.0) -> None:
        self.per_test_timeout = per_test_timeout

    def run_verification(
        self,
        test_file: Path,
        working_dir: Path,
    ) -> VerificationReport:
        """Executes pytest against test_file within working_dir.
        
        Returns:
            VerificationReport: Aggregate test results, individual failure traces, and CEL violation details.
        """
        ...
```

---

## 2. Self-Healing Loop Engine API

### 2.1 Class Signature: `SelfHealingEngine`

```python
class SelfHealingEngine:
    """Coordinates iterative repair of synthesized candidate agents."""

    def __init__(
        self,
        provider: LLMProvider,
        runner: SandboxedVerificationRunner,
        max_retries: int = 3,
        budget_ceiling: float = 0.05,
    ) -> None:
        ...

    def run_loop(
        self,
        contract: ContractAST,
        staging_dir: Path,
        initial_agent_code: str,
        test_file: Path,
        telemetry: CostTelemetry,
    ) -> tuple[bool, str, VerificationReport]:
        """Runs the iterative repair cycle:
        1. Evaluates candidate agent with runner.
        2. If passed, returns (True, current_agent_code, report).
        3. If failed and iterations < max_retries, crafts diagnostic repair prompt:
           - Sends current code + failing assertion traces + CEL violation details.
           - Invokes provider to synthesize replacement agent.py.
           - Writes new code to staging_dir/agent.py and re-tests.
        4. If budget exceeded or retries exhausted, returns (False, latest_code, report).
        """
        ...
```

---

## 3. Review Gate & Promotion Engine API

### 3.1 Class Signature: `ReviewGate`

```python
class ReviewGate:
    """Generates unified git diffs and coordinates human or headless promotion."""

    def __init__(self, output_dir: Path, staging_dir: Path) -> None:
        self.output_dir = output_dir
        self.staging_dir = staging_dir

    def generate_diff(self) -> str:
        """Generates unified git diff between output_dir and staging_dir."""
        ...

    def prompt_and_promote(self, headless_ci: bool = False) -> bool:
        """Presents diff and prompts human developer.
        In headless_ci mode, auto-promotes immediately.
        Returns True if promoted, False if rejected.
        """
        ...

    def promote_artifacts(self) -> list[Path]:
        """Atomically moves verified files from staging_dir to output_dir."""
        ...
```
