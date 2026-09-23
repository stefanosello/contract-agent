# Contract: Guard Interceptor API

**Module**: `contract_agent.runtime.guards`

## Interface Specification

```python
class GuardInterceptor:
    """Fail-closed runtime interceptor for tool executions."""

    def __init__(
        self, ast: ContractAST, cel_engine: Optional[CELEngine] = None
    ) -> None: ...

    def wrap_tool(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        context: WorkflowContext,
    ) -> Callable[..., Any]:
        """
        Wrap a tool function with pre-execution CEL invariant checks.

        Evaluates:
        1. Tool-scoped invariants (`tool:<tool_name>`)
        2. Wildcard invariants (`*`)
        3. Applicable session invariants

        Dispatches violations according to Invariant.on_violation:
        - "raise_invariant_violation" -> raises InvariantViolationError
        - "block_tool_call" -> returns {"error": "...", "invariant_id": ...}
        - "require_escalation" -> raises EscalationRequiredError
        """
        ...

    async def wrap_tool_async(
        self,
        tool_name: str,
        async_handler: Callable[..., Awaitable[Any]],
        context: WorkflowContext,
    ) -> Callable[..., Awaitable[Any]]:
        """Asynchronous variant of tool wrapper."""
        ...
```
