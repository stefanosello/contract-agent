# Contract: CEL Engine API

**Module**: `contract_agent.runtime.cel_engine`

## Interface Specification

```python
class CELEngine:
    """Deterministic CEL expression compiler and evaluator."""

    def compile(self, rule_str: str) -> CompiledCELProgram:
        """
        Compile a CEL string into an executable program.

        Raises:
            ContractValidationError: If syntax is invalid or type binding fails.
        """
        ...

    def evaluate(
        self,
        program: CompiledCELProgram,
        args: Dict[str, Any],
        context: WorkflowContext,
    ) -> bool:
        """
        Evaluate a compiled CEL program against invocation arguments and workflow context.

        Returns:
            bool: True if invariant holds, False if violated.

        Raises:
            CELEvaluationError: If internal evaluation fault occurs (fail-closed caller catches this).
        """
        ...


class CompiledCELProgram:
    """Encapsulates a parsed and compiled CEL expression."""

    raw_rule: str
```

## Custom Functions Available in CEL
- `workflow.has_approval(type: string, resource_id: string) -> bool`
- `workflow.called_before(prior_tool: string, target_tool: string) -> bool`
- `workflow.called_before(prior_tool: string, target_tool: string, correlation_id: string) -> bool`
- `workflow.call_count(tool_name: string) -> int`
- `workflow.call_count(tool_name: string, correlation_id: string) -> int`
