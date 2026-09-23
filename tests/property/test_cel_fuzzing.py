"""Property-based fuzzing tests for ContractAgent CEL invariant rules using Hypothesis."""

from hypothesis import given, settings, strategies as st

from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.testing.fuzzing import InvariantFuzzer


@given(amount=st.integers(min_value=-1_000_000, max_value=1_000_000))
@settings(max_examples=300)
def test_fuzz_financial_boundary_invariant(amount: int):
    """Mathematically verifies that args.amount_cents <= 25000 partitions integers correctly."""
    engine = CELEngine()
    rule = "args.amount_cents <= 25000"
    args = {"amount_cents": amount}

    result = engine.evaluate_rule(rule, args)
    expected = (amount <= 25000)

    assert result == expected, f"Discrepancy at amount={amount}: got {result}, expected {expected}"


@given(reason=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=150))
@settings(max_examples=300)
def test_fuzz_string_size_invariant(reason: str):
    """Verifies that size(args.reason.trim()) >= 10 handles whitespace and unicode cleanly."""
    engine = CELEngine()
    rule = "size(args.reason.trim()) >= 10"
    args = {"reason": reason}

    result = engine.evaluate_rule(rule, args)
    expected = (len(reason.strip()) >= 10)

    assert result == expected, f"Discrepancy for reason='{reason}': got {result}, expected {expected}"


def test_schema_strategy_fuzzing():
    """Verifies that InvariantFuzzer synthesizes valid dictionaries from JSON schemas."""
    schema = {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string"},
            "amount_cents": {"type": "integer", "minimum": 0, "maximum": 50000},
        }
    }
    strategy = InvariantFuzzer.strategy_for_json_schema(schema)
    sample = strategy.example()

    assert isinstance(sample, dict)
    assert "invoice_id" in sample
    assert "amount_cents" in sample
    assert 0 <= sample["amount_cents"] <= 50000
