"""Deterministic contract boundary seeds for bounded Hypothesis verification."""

from __future__ import annotations

import re
from typing import Any

from contract_agent.core.ast import ContractAST, Invariant, ToolContract


def _schema_seed(schema: dict[str, Any]) -> Any:
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type", "string")
    if kind in ("integer", "int"):
        return int(schema.get("minimum", 0))
    if kind in ("number", "float"):
        return float(schema.get("minimum", 0.0))
    if kind in ("boolean", "bool"):
        return False
    if kind == "array":
        items: list[Any] = []
        return items
    if kind == "object":
        return {name: _schema_seed(prop) for name, prop in schema.get("properties", {}).items()}
    return "x" * schema.get("minLength", 1)


def boundary_probes(
    ast: ContractAST, tool: ToolContract, invariant: Invariant
) -> list[dict[str, Any]]:
    """Include scenario examples, literal numeric boundaries, and string attacks.

    These adversarial seeds supplement schema-valid generated samples; they are
    not an independent proof that the contract expresses the author's intent.
    """
    properties = tool.parameters.get("properties", {})
    base = {name: _schema_seed(prop) for name, prop in properties.items()}
    examples = [base]
    for scenario in ast.scenarios:
        for step in scenario.expected_flow:
            if step.tool_call == tool.name and step.with_args is not None:
                examples.append({**base, **step.with_args})

    probes = list(examples)
    comparisons = re.findall(
        r"args\.(\w+)\s*(?:<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)", invariant.rule
    )
    for name, literal in comparisons:
        if name not in properties:
            continue
        integer = properties[name].get("type") in ("integer", "int")
        bound: int | float = int(float(literal)) if integer else float(literal)
        delta = 1 if integer else 0.01
        for example in examples:
            for value in (bound - delta, bound, bound + delta):
                probes.append({**example, name: value})

    for name, schema in properties.items():
        if schema.get("type", "string") == "string":
            for text in ("", " ", "x" * 9, "x" * 10, "x" * 11,
                         "SELECT id FROM users", "DROP TABLE users", "DELETE FROM users"):
                probes.append({**base, name: text})
    return probes
