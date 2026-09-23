"""Pluggable LLMProvider interface and mock provider implementation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from contract_agent.compiler.models import LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM synthesis and repair engines."""

    name: str

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Synchronously invokes the LLM provider."""
        ...

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Asynchronously invokes the LLM provider."""
        ...


class MockLLMProvider:
    """Deterministic, zero-network mock provider for testing and sandboxed CI."""

    name: str = "mock"

    def __init__(
        self,
        default_response: str = "# Mock generated code\n",
        canned_responses: dict[str, str] | None = None,
        fault_schedule: dict[int, str] | None = None,
        response_generator: Callable[[str, str | None, int], str] | None = None,
    ) -> None:
        self.default_response = default_response
        self.canned_responses = canned_responses or {}
        self.fault_schedule = fault_schedule or {}
        self.response_generator = response_generator
        self.call_count = 0
        self.recorded_prompts: list[tuple[str, str | None]] = []

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.recorded_prompts.append((prompt, system_prompt))
        current_turn = self.call_count
        self.call_count += 1

        # Check fault schedule first (for testing self-healing verification loops)
        if current_turn in self.fault_schedule:
            content = self.fault_schedule[current_turn]
        elif self.response_generator:
            content = self.response_generator(prompt, system_prompt, current_turn)
        else:
            # Check canned responses by substring match
            content = self.default_response
            for keyword, canned in self.canned_responses.items():
                if keyword in prompt or (system_prompt and keyword in system_prompt):
                    content = canned
                    break

        return LLMResponse(
            content=content,
            prompt_tokens=len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0),
            completion_tokens=len(content.split()),
            cost_usd=0.0,
            model_name="mock-model",
        )

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self.generate(prompt, system_prompt, temperature)


def get_provider(
    provider_name: str = "mock",
    api_key: str | None = None,
    model_name: str | None = None,
) -> LLMProvider:
    """Factory to instantiate LLM providers based on name."""
    normalized = provider_name.strip().lower()
    if normalized in ("mock", "offline", "ci"):
        return MockLLMProvider()
    if normalized in ("gemini", "gemini-flash"):
        from contract_agent.compiler.providers_live import GeminiFlashProvider

        return GeminiFlashProvider(api_key=api_key, model_name=model_name)
    if normalized in ("deepseek", "deepseek-v3"):
        from contract_agent.compiler.providers_live import DeepSeekProvider

        return DeepSeekProvider(api_key=api_key, model_name=model_name)

    raise ValueError(f"Unknown or unsupported LLM provider: '{provider_name}'")
