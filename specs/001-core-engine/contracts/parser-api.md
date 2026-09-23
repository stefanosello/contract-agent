# Contract: Parser API

**Module**: `contract_agent.core.parser`

## Interface Specification

```python
class ContractParser:
    """Loads, parses, and semantically validates contract specifications."""

    @classmethod
    def from_file(cls, path: Path | str) -> ContractAST:
        """
        Load and validate an agent.contract.yaml file.
        
        Raises:
            ContractValidationError: If YAML is invalid, Pydantic validation fails,
                                     referential integrity fails, or CEL expressions
                                     fail static compilation and schema binding.
        """
        ...

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContractAST:
        """
        Validate and semantically inspect contract dictionary.
        
        Raises:
            ContractValidationError: On schema or semantic check failure.
        """
        ...


def load_contract(path: Path | str) -> ContractAST:
    """Convenience wrapper for ContractParser.from_file."""
    ...
```

## Static Validation Invariants
1. **Schema Validation**: Must conform to `ContractAST` Pydantic V2 schema.
2. **Referential Integrity**: All `Invariant.target` referencing `tool:<name>` and scenario `tool_call`/`never_call` must refer to defined tools in `ast.tools`.
3. **CEL Static Compilation**: Every `Invariant.rule` must successfully parse into a CEL AST without syntax errors.
4. **Parameter Schema Binding**: For tool-scoped invariants (`tool:<name>`), any `args.<field>` referenced in the CEL rule must exist in `ToolContract.parameters["properties"]`.
