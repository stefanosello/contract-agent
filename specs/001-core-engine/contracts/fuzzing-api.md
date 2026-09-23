# Contract: Fuzzing & Mutation API

**Modules**: `contract_agent.testing.fuzzing`, `contract_agent.testing.mutants`

## Interface Specification

```python
class InvariantFuzzer:
    """Hypothesis property-based boundary test generator for CEL invariants."""

    def __init__(self, ast: ContractAST) -> None: ...

    def register_strategy_override(
        self,
        tool_name: str,
        param_name: str,
        strategy: SearchStrategy[Any],
    ) -> None:
        """Register custom Hypothesis strategy override for a parameter."""
        ...

    def fuzz_tool_invariants(
        self,
        tool_name: str,
        iterations: int = 100,
    ) -> FuzzResult:
        """
        Run property-based fuzzing across all invariants for a given tool.

        Returns:
            FuzzResult with execution statistics and any falsified boundary inputs.
        """
        ...


class RogueMutantRunner:
    """Automated mutation testing fixture simulating adversarial agent bypasses."""

    def __init__(self, ast: ContractAST, interceptor: GuardInterceptor) -> None: ...

    def run_all_mutants(self) -> MutationTestSuiteResult:
        """
        Execute standard rogue mutants across all attack vectors:
        1. Numerical boundary overages
        2. Sequence skips
        3. Missing approval tokens

        Asserts 100% trap rate (0% escape).
        """
        ...
```
