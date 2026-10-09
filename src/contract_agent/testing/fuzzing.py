"""Zero-LLM Property-based fuzzing utilities for ContractAgent CEL invariant rules using Hypothesis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hypothesis import strategies as st

from contract_agent.core.ast import ContractAST
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext


@dataclass
class FuzzResult:
    """Outcome of an invariant fuzzing run."""

    tool_name: str
    iterations: int
    passed: bool
    failures: list[dict[str, Any]]


class InvariantFuzzer:
    """Uses Hypothesis strategies to mathematically verify CEL invariant boundaries."""

    def __init__(
        self,
        ast: ContractAST | None = None,
        cel_engine: CELEngine | None = None,
    ) -> None:
        self.ast = ast
        self.cel_engine = cel_engine or CELEngine()
        self._strategy_overrides: dict[str, st.SearchStrategy[Any]] = {}

    def register_strategy_override(
        self,
        tool_name: str,
        param_name: str,
        strategy: st.SearchStrategy[Any],
    ) -> None:
        """Register custom Hypothesis strategy override for a parameter."""
        key = f"{tool_name}.{param_name}"
        self._strategy_overrides[key] = strategy

    def strategy_for_json_schema(
        self,
        schema: dict[str, Any],
        tool_name: str | None = None,
    ) -> st.SearchStrategy[dict[str, Any]]:
        """Synthesizes a Hypothesis dictionary strategy matching a JSON Schema object,

        checking for user-registered strategy overrides first.
        """
        schema_type = schema.get("type", "object")
        if schema_type != "object":
            raise ValueError(f"Expected object schema, got {schema_type}")

        properties = schema.get("properties", {})
        strategy_dict: dict[str, st.SearchStrategy[Any]] = {}

        for prop_name, prop_spec in properties.items():
            override_key = f"{tool_name}.{prop_name}" if tool_name else None
            if override_key and override_key in self._strategy_overrides:
                strategy_dict[prop_name] = self._strategy_overrides[override_key]
                continue

            if prop_spec.get("enum"):
                strategy_dict[prop_name] = st.sampled_from(prop_spec["enum"])
                continue

            prop_type = prop_spec.get("type", "string")
            if prop_type in ("integer", "int"):
                min_val = prop_spec.get("minimum", -1_000_000)
                max_val = prop_spec.get("maximum", 1_000_000)
                strategy_dict[prop_name] = st.integers(
                    min_value=min_val, max_value=max_val
                )
            elif prop_type in ("number", "float"):
                strategy_dict[prop_name] = st.floats(
                    min_value=prop_spec.get("minimum"),
                    max_value=prop_spec.get("maximum"),
                    allow_nan=False, allow_infinity=False,
                )
            elif prop_type == "string":
                strategy_dict[prop_name] = st.text(
                    min_size=prop_spec.get("minLength", 0),
                    max_size=prop_spec.get("maxLength", max(200, prop_spec.get("minLength", 0))),
                )
            elif prop_type in ("boolean", "bool"):
                strategy_dict[prop_name] = st.booleans()
            elif prop_type == "array":
                item_schema = {"type": "object", "properties": {"item": prop_spec.get("items", {})}}
                items = self.strategy_for_json_schema(item_schema).map(lambda sample: sample["item"])
                strategy_dict[prop_name] = st.lists(
                    items, min_size=prop_spec.get("minItems", 0),
                    max_size=prop_spec.get("maxItems", max(5, prop_spec.get("minItems", 0))),
                )
            elif prop_type == "object":
                strategy_dict[prop_name] = self.strategy_for_json_schema(prop_spec)
            else:
                raise ValueError(f"Unsupported schema type for {prop_name}: {prop_type}")

        return st.fixed_dictionaries(strategy_dict)

    def test_invariant_soundness(
        self,
        rule_str: str,
        input_args: dict[str, Any],
        expected_predicate: Callable[[dict[str, Any]], bool],
        context: WorkflowContext | None = None,
    ) -> bool:
        """Evaluates CEL rule and asserts it matches the mathematical ground truth predicate."""
        actual = self.cel_engine.evaluate_rule(rule_str, input_args, context)
        expected = expected_predicate(input_args)
        assert actual == expected, (
            f"Fuzzing failure for rule '{rule_str}' on input {input_args}: "
            f"expected {expected}, got {actual}"
        )
        return True
