"""YAML loader and semantic validator for ContractAgent specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Set
import yaml
from pydantic import ValidationError

from contract_agent.core.ast import ContractAST
from contract_agent.core.exceptions import ContractValidationError


class ContractParser:
    """Loads, parses, and semantically validates contract specification files."""

    @classmethod
    def from_file(cls, path: Path | str) -> ContractAST:
        """Load and validate an agent.contract.yaml file."""
        file_path = Path(path)
        if not file_path.exists():
            raise ContractValidationError(f"Contract file not found at: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ContractValidationError(
                f"YAML parsing error in {file_path}: {exc}", details={"raw_error": str(exc)}
            ) from exc

        if not isinstance(raw_data, dict):
            raise ContractValidationError(
                f"Expected top-level dictionary in contract file, got {type(raw_data).__name__}"
            )

        return cls.from_dict(raw_data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContractAST:
        """Validate and semantically inspect contract dictionary."""
        try:
            ast = ContractAST.model_validate(data)
        except ValidationError as err:
            errors_summary = []
            for e in err.errors():
                loc = ".".join(str(x) for x in e["loc"])
                errors_summary.append(f"{loc}: {e['msg']}")
            raise ContractValidationError(
                "Contract schema validation failed:\n  - " + "\n  - ".join(errors_summary),
                details={"errors": err.errors()},
            ) from err

        cls._perform_semantic_checks(ast)
        return ast

    @classmethod
    def _perform_semantic_checks(cls, ast: ContractAST) -> None:
        """Verifies cross-field referential integrity."""
        tool_names: Set[str] = {tool.name for tool in ast.tools}

        # 1. Check duplicate invariant IDs
        seen_inv_ids: Set[str] = set()
        for inv in ast.invariants:
            if inv.id in seen_inv_ids:
                raise ContractValidationError(f"Duplicate invariant ID detected: '{inv.id}'")
            seen_inv_ids.add(inv.id)

            # Check target tool existence if target starts with 'tool:'
            if inv.target.startswith("tool:"):
                target_tool = inv.target.split("tool:", 1)[1]
                if target_tool not in tool_names:
                    raise ContractValidationError(
                        f"Invariant '{inv.id}' references undefined tool '{target_tool}'"
                    )

        # 2. Check duplicate scenario IDs & tool call references
        seen_scen_ids: Set[str] = set()
        for scen in ast.scenarios:
            if scen.id in seen_scen_ids:
                raise ContractValidationError(f"Duplicate scenario ID detected: '{scen.id}'")
            seen_scen_ids.add(scen.id)

            for step in scen.expected_flow:
                if step.tool_call and step.tool_call not in tool_names:
                    raise ContractValidationError(
                        f"Scenario '{scen.id}' expects tool '{step.tool_call}' which is not defined in tools"
                    )
                if step.never_call and step.never_call not in tool_names:
                    raise ContractValidationError(
                        f"Scenario '{scen.id}' references never_call on tool '{step.never_call}' which is not defined in tools"
                    )


def load_contract(path: Path | str) -> ContractAST:
    """Convenience functional wrapper for loading contracts."""
    return ContractParser.from_file(path)
