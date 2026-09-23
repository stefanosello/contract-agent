"""YAML loader and semantic validator for ContractAgent specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
                f"YAML parsing error in {file_path}: {exc}",
                details={"raw_error": str(exc)},
            ) from exc

        if not isinstance(raw_data, dict):
            raise ContractValidationError(
                f"Expected top-level dictionary in contract file, got {type(raw_data).__name__}"
            )

        return cls.from_dict(raw_data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractAST:
        """Validate and semantically inspect contract dictionary."""
        try:
            ast = ContractAST.model_validate(data)
        except ValidationError as err:
            errors_summary = []
            for e in err.errors():
                loc = ".".join(str(x) for x in e["loc"])
                errors_summary.append(f"{loc}: {e['msg']}")
            raise ContractValidationError(
                "Contract schema validation failed:\n  - "
                + "\n  - ".join(errors_summary),
                details={"errors": err.errors()},
            ) from err

        cls._perform_semantic_checks(ast)
        return ast

    @classmethod
    def _perform_semantic_checks(cls, ast: ContractAST) -> None:
        """Verifies cross-field referential integrity, CEL syntax, and parameter bindings."""
        import re

        import celpy

        tool_names: set[str] = {tool.name for tool in ast.tools}
        tools_by_name = {tool.name: tool for tool in ast.tools}
        cel_env = celpy.Environment()

        # 1. Check duplicate invariant IDs & static CEL compilation & parameter binding
        seen_inv_ids: set[str] = set()
        for inv in ast.invariants:
            if inv.id in seen_inv_ids:
                raise ContractValidationError(
                    f"Duplicate invariant ID detected: '{inv.id}'"
                )
            seen_inv_ids.add(inv.id)

            # Check target tool existence if target starts with 'tool:'
            target_tool = None
            if inv.target.startswith("tool:"):
                target_tool = inv.target.split("tool:", 1)[1]
                if target_tool not in tool_names:
                    raise ContractValidationError(
                        f"Invariant '{inv.id}' references undefined tool '{target_tool}'"
                    )

            # Static CEL compilation check
            try:
                cel_env.compile(inv.rule)
            except Exception as exc:
                raise ContractValidationError(
                    f"Invariant '{inv.id}' contains invalid CEL expression '{inv.rule}': {exc}"
                ) from exc

            # Static parameter schema binding check for tool-scoped invariants
            if target_tool and target_tool in tools_by_name:
                tool_contract = tools_by_name[target_tool]
                param_schema = tool_contract.parameters or {}
                properties = param_schema.get("properties", {})
                referenced_args = set(
                    re.findall(r"\bargs\.([a-zA-Z_][a-zA-Z0-9_]*)", inv.rule)
                )
                if properties:
                    for arg in referenced_args:
                        if arg not in properties:
                            raise ContractValidationError(
                                f"Invariant '{inv.id}' references undefined parameter 'args.{arg}' "
                                f"which is not declared in tool '{target_tool}' parameters schema"
                            )

        # 2. Check duplicate scenario IDs & tool call references
        seen_scen_ids: set[str] = set()
        for scen in ast.scenarios:
            if scen.id in seen_scen_ids:
                raise ContractValidationError(
                    f"Duplicate scenario ID detected: '{scen.id}'"
                )
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
