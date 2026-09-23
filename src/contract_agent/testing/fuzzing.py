"""Zero-LLM Property-based fuzzing utilities for ContractAgent CEL invariant rules using Hypothesis."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from hypothesis import strategies as st

from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext


class InvariantFuzzer:
    """Uses Hypothesis strategies to mathematically verify CEL invariant boundaries."""

    def __init__(self, cel_engine: Optional[CELEngine] = None) -> None:
        self.cel_engine = cel_engine or CELEngine()

    @staticmethod
    def strategy_for_json_schema(schema: Dict[str, Any]) -> st.SearchStrategy[Dict[str, Any]]:
        """Synthesizes a Hypothesis dictionary strategy matching a JSON Schema object."""
        schema_type = schema.get("type", "object")
        if schema_type != "object":
            raise ValueError(f"Expected object schema, got {schema_type}")

        properties = schema.get("properties", {})
        strategy_dict: Dict[str, st.SearchStrategy[Any]] = {}

        for prop_name, prop_spec in properties.items():
            prop_type = prop_spec.get("type", "string")
            if prop_type in ("integer", "int"):
                min_val = prop_spec.get("minimum", -1_000_000)
                max_val = prop_spec.get("maximum", 1_000_000)
                strategy_dict[prop_name] = st.integers(min_value=min_val, max_value=max_val)
            elif prop_type in ("number", "float"):
                strategy_dict[prop_name] = st.floats(allow_nan=False, allow_infinity=False)
            elif prop_type == "string":
                strategy_dict[prop_name] = st.text(max_size=200)
            elif prop_type in ("boolean", "bool"):
                strategy_dict[prop_name] = st.booleans()
            else:
                strategy_dict[prop_name] = st.text()

        return st.fixed_dictionaries(strategy_dict)

    def test_invariant_soundness(
        self,
        rule_str: str,
        input_args: Dict[str, Any],
        expected_predicate: Callable[[Dict[str, Any]], bool],
        context: Optional[WorkflowContext] = None,
    ) -> bool:
        """Evaluates CEL rule and asserts it matches the mathematical ground truth predicate."""
        actual = self.cel_engine.evaluate_rule(rule_str, input_args, context)
        expected = expected_predicate(input_args)
        assert actual == expected, (
            f"Fuzzing failure for rule '{rule_str}' on input {input_args}: "
            f"expected {expected}, got {actual}"
        )
        return True
