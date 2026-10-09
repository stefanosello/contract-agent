"""Generated and repaired agents must reuse the durable approval runtime."""

from contract_agent.compiler.personas import (
    ADVERSARIAL_TESTER_SYSTEM_PROMPT,
    AGENT_IMPLEMENTER_SYSTEM_PROMPT,
    REPAIR_SYNTHESIZER_SYSTEM_PROMPT,
    build_implementer_prompt,
)
from contract_agent.core.ast import ContractAST, Metadata


def test_implementer_reuses_durable_runtime() -> None:
    assert "BaseConversationalAgent" in AGENT_IMPLEMENTER_SYSTEM_PROMPT
    assert "resume_approval" in AGENT_IMPLEMENTER_SYSTEM_PROMPT
    assert "durable" in AGENT_IMPLEMENTER_SYSTEM_PROMPT
    prompt = build_implementer_prompt(ContractAST(metadata=Metadata(name="test_agent")))
    assert "BaseConversationalAgent" in prompt


def test_repairs_preserve_durable_runtime() -> None:
    assert "BaseConversationalAgent" in REPAIR_SYNTHESIZER_SYSTEM_PROMPT
    assert "durable" in REPAIR_SYNTHESIZER_SYSTEM_PROMPT


def test_tester_requests_recovery_and_replay_coverage() -> None:
    for term in ("restart", "resume_approval", "replay"):
        assert term in ADVERSARIAL_TESTER_SYSTEM_PROMPT
