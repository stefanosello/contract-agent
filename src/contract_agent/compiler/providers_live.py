"""Live LLM provider adapters for Gemini Flash and DeepSeek-V3."""

from __future__ import annotations

import os

from contract_agent.compiler.models import LLMResponse


class GeminiFlashProvider:
    """Google Gemini Flash provider adapter."""

    name: str = "gemini-flash"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name or "gemini-1.5-flash"

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # Stub to be fleshed out in T023 with live REST invocation
        raise NotImplementedError("Live Gemini Flash API invocation configured in Phase 6")

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self.generate(prompt, system_prompt, temperature)


class DeepSeekProvider:
    """DeepSeek-V3 provider adapter."""

    name: str = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model_name = model_name or "deepseek-chat"

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # Stub to be fleshed out in T023 with live REST invocation
        raise NotImplementedError("Live DeepSeek API invocation configured in Phase 6")

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self.generate(prompt, system_prompt, temperature)
