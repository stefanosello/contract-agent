"""Live LLM provider adapters for Gemini Flash and DeepSeek-V3."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from contract_agent.compiler.models import LLMResponse
from contract_agent.compiler.telemetry import calculate_cost, estimate_tokens


class DeepSeekProvider:
    """OpenAI-compatible REST client for DeepSeek-V3."""

    name: str = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str = "https://api.deepseek.com/v1",
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.model_name = model_name or "deepseek-chat"
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable or api_key parameter is required.")

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek API call failed: {exc}") from exc

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens") or estimate_tokens(prompt + (system_prompt or ""))
        completion_tokens = usage.get("completion_tokens") or estimate_tokens(content)

        cost = calculate_cost(prompt_tokens, completion_tokens, self.model_name)

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model_name=self.model_name,
        )

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self.generate(prompt, system_prompt, temperature)


class GeminiFlashProvider:
    """REST client for Google Gemini Flash."""

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
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable or api_key parameter is required.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini Flash API call failed: {exc}") from exc

        candidates = result.get("candidates", [])
        content = ""
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            content = "".join(p.get("text", "") for p in parts)

        meta = result.get("usageMetadata", {})
        prompt_tokens = meta.get("promptTokenCount") or estimate_tokens(prompt + (system_prompt or ""))
        completion_tokens = meta.get("candidatesTokenCount") or estimate_tokens(content)

        cost = calculate_cost(prompt_tokens, completion_tokens, self.model_name)

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model_name=self.model_name,
        )

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self.generate(prompt, system_prompt, temperature)
