"""Unit tests for compiler LLMProvider protocol and MockLLMProvider."""

from __future__ import annotations

import pytest

from contract_agent.compiler.providers import (
    LLMProvider,
    MockLLMProvider,
    get_provider,
)


def test_mock_provider_implements_protocol() -> None:
    """Assert MockLLMProvider satisfies LLMProvider Protocol."""
    provider = MockLLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.name == "mock"


def test_mock_provider_canned_matching() -> None:
    """Assert canned responses trigger on matching keywords."""
    provider = MockLLMProvider(
        default_response="DEFAULT",
        canned_responses={"billing": "BILLING_CODE", "sql": "SQL_CODE"},
    )
    res1 = provider.generate("Generate billing agent")
    assert res1.content == "BILLING_CODE"

    res2 = provider.generate("Generate something else")
    assert res2.content == "DEFAULT"


def test_mock_provider_fault_schedule() -> None:
    """Assert fault schedule overrides output based on turn count."""
    provider = MockLLMProvider(
        default_response="GOOD_CODE",
        fault_schedule={0: "DEFECTIVE_CODE", 1: "REPAIRED_CODE"},
    )
    turn0 = provider.generate("Initial compile")
    assert turn0.content == "DEFECTIVE_CODE"

    turn1 = provider.generate("Repair compile")
    assert turn1.content == "REPAIRED_CODE"

    turn2 = provider.generate("Subsequent compile")
    assert turn2.content == "GOOD_CODE"


@pytest.mark.asyncio
async def test_mock_provider_agenerate() -> None:
    """Assert async agenerate returns valid LLMResponse."""
    provider = MockLLMProvider(default_response="ASYNC_RESPONSE")
    res = await provider.agenerate("Test async")
    assert res.content == "ASYNC_RESPONSE"
    assert res.cost_usd == 0.0


def test_get_provider_factory() -> None:
    """Assert factory instantiates expected provider."""
    mock = get_provider("mock")
    assert isinstance(mock, MockLLMProvider)

    with pytest.raises(ValueError, match="Unknown or unsupported LLM provider"):
        get_provider("invalid-provider")
