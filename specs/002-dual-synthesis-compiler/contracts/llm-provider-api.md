# Contract: Pluggable LLM Provider API

**Target Module**: `contract_agent.compiler.providers`  
**Feature**: `002-dual-synthesis-compiler`  
**Date**: 2026-09-23  

---

## 1. Provider Protocol Interface

### 1.1 Class Signature: `LLMProvider`

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM synthesis backends."""

    name: str

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Synchronously invokes the LLM backend or offline mock."""
        ...

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Asynchronously invokes the LLM backend or offline mock."""
        ...
```

---

## 2. Concrete Implementations

### 2.1 `MockLLMProvider`
- **Purpose**: Zero-network CI runs, unit tests, and regression benchmarks.
- **Behavior**:
  - Matches prompt keywords or AST structure to return canned, syntactically valid state machine agent code or adversarial tests.
  - Supports configurable fault injection (e.g. inject deliberate syntax or logic error on turn 0, return valid fix on turn 1) to verify the self-healing verification loop.
  - Zero token cost ($0.00).

### 2.2 `GeminiFlashProvider`
- **Default Model**: `gemini-1.5-flash` or `gemini-2.0-flash`
- **Cost Rates**:
  - Prompt: $0.075 per 1,000,000 tokens
  - Completion: $0.30 per 1,000,000 tokens
- **Auth**: Reads `GEMINI_API_KEY` from environment.

### 2.3 `DeepSeekProvider`
- **Default Model**: `deepseek-chat` (DeepSeek-V3)
- **Cost Rates**:
  - Prompt: $0.14 per 1,000,000 tokens
  - Completion: $0.28 per 1,000,000 tokens
- **Auth**: Reads `DEEPSEEK_API_KEY` from environment; connects to `https://api.deepseek.com/v1`.

---

## 3. Provider Factory

```python
def get_provider(
    provider_name: str,
    api_key: str | None = None,
    model_name: str | None = None,
) -> LLMProvider:
    """Returns an instantiated LLMProvider matching provider_name ('mock', 'gemini-flash', 'deepseek')."""
    ...
```
