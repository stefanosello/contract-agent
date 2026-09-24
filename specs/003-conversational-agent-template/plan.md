# Implementation Plan: Conversational Agent Template & Interactive Execution

**Branch**: `003-conversational-agent-template` | **Date**: 2026-09-24 | **Spec**: [specs/003-conversational-agent-template/spec.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/spec.md)

**Input**: Feature specification from `/specs/003-conversational-agent-template/spec.md` with integrated clarifications.

## Summary

Enhance the agent compilation template to synthesize interactive, multi-turn conversational agents:
1. **Stream-First Execution & Synchronous Facades**: Generate `stream(message: str) -> AsyncIterator[ConversationEvent]` for real-time token/tool event streaming, alongside `step()` and `chat()` synchronous facades.
2. **ReAct Reasoning Loop**: Implement bounded ReAct dialogue execution alternating between thoughts, guarded tool invocations, and conversational responses.
3. **Unbounded In-Memory Dialogue Session**: Track full conversation timeline in `ConversationSession` with JSON export/restore capabilities.
4. **Hybrid Invariant Escalation**: Transition to `AWAITING_APPROVAL` with cryptographically unique tokens, resumable via `approve(token)` or conversational approval.
5. **Conversational Test Generation**: Upgrade `dist/test_contract.py` templates to synthesize multi-turn dialogue verification suites and conversational adversarial probes.

## Technical Context

**Language/Version**: Python 3.11+ (strict type annotations checked by Meta Pyrefly and Mypy).

**Primary Dependencies**:
- `pydantic>=2.7.0`: Data modeling for `ConversationEvent`, `ConversationMessage`, and `ConversationSession`.
- `cel-python>=0.5.0`: Non-Turing complete runtime invariant evaluation via `GuardInterceptor`.
- `pyyaml>=6.0.0`: Behavioral contract schema parsing.
- `typer>=0.12.0`, `rich>=13.7.0`: CLI compiler command and terminal rendering.
- `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`: Testing harness for async streaming and sync execution.

**Storage**: In-memory `ConversationSession` with JSON dictionary serialization (`export_session` / `from_session`).

**Testing**: Pytest unit tests for conversational models and templates, compiler integration tests with offline mock provider, 3-contract convergence benchmark validation.

**Target Platform**: macOS (Apple Silicon / Intel), Linux x86_64/arm64.

**Project Type**: Agent compiler & runtime framework.

**Performance Goals**: < 100ms turn overhead excluding LLM network latency; < 10s per-test timeout ceiling; < $0.05 compilation budget ceiling.

**Constraints**: Pure deterministic CEL enforcement (zero LLM judging of invariants); 100% path isolation protecting human code in `services/`; sandboxed zero-network CI operation.

**Scale/Scope**: Conversational templates in `src/contract_agent/compiler/templates.py`, schemas in `src/contract_agent/compiler/models.py`, prompt personas in `src/contract_agent/compiler/personas.py`, and test generators in `dist/test_contract.py`.

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`*

| Principle | Compliance Notes | Status |
| :--- | :--- | :--- |
| **I. Spec-as-Source** | `agent.contract.yaml` remains the immutable source of truth. All conversational templates and test suites are reproducible build artifacts in `dist/`. | PASS |
| **II. Deterministic CEL** | All tool calls triggered during conversational turns are routed through `GuardInterceptor`. Zero LLM involvement in invariant evaluation. | PASS |
| **III. Strict Protocol Binding** | Conversational agents bind strictly to typed `AgentToolsProtocol` in `dist/interface.py`. Human services in `services/` are never modified. | PASS |
| **IV. Layered Verification** | Invariant rules mathematically verified via property fuzzing; conversational tests verify turn-by-turn state transitions in sandboxed runners. | PASS |
| **V. De-Correlated Synthesis & Review Gates** | Implementer and tester personas operate independently. Interactive unified Git diff review gate intercepts all promotions. | PASS |
| **VI. Atomic Commits & Small-Step Discipline** | Tasks sized for atomic commits $\le$ 200 LOC and $\le$ 10 files per commit. | PASS |
| **VII. Feature Branch Isolation** | Developed on branch `003-conversational-agent-template`. | PASS |
| **VIII. Protected Main & PR Protocol** | Direct pushes to `main` blocked; automated PR created via `gh pr create` upon convergence. | PASS |

## Design Artifacts

- **Phase 0 Research**: [research.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/research.md)
- **Data Model**: [data-model.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/data-model.md)
- **Contracts**:
  - [conversational-agent-api.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/contracts/conversational-agent-api.md)
  - [conversation-events-api.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/contracts/conversation-events-api.md)
- **Quickstart & Validation Guide**: [quickstart.md](file:///Users/stefano/Documents/contract-agent/specs/003-conversational-agent-template/quickstart.md)

## Project Structure

### Documentation (this feature)

```text
specs/003-conversational-agent-template/
├── spec.md              # Feature specification with clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 architectural research
├── data-model.md        # Entities, session schemas & state transitions
├── contracts/           # Interface contracts
│   ├── conversational-agent-api.md
│   └── conversation-events-api.md
├── quickstart.md        # Validation scenarios
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/
└── contract_agent/
    ├── compiler/
    │   ├── models.py            # Add ConversationEvent, ConversationMessage, ConversationSession schemas
    │   ├── templates.py         # Update generate_default_fsm_agent and generate_default_test_suite
    │   ├── personas.py          # Update AgentImplementer and AdversarialTester system prompts
    │   ├── orchestrator.py      # Pass session configuration to compiler pipeline
    │   └── ...
    └── runtime/
        └── context.py           # Extend WorkflowContext with conversational session metadata

tests/
├── unit/
│   └── compiler/
│       ├── test_conversational_models.py
│       └── test_conversational_templates.py
└── integration/
    └── compiler/
        ├── test_conversational_agent.py
        └── test_conversational_escalation.py
```

**Structure Decision**: Fully integrated within the existing `src/contract_agent/compiler` subsystem without introducing unnecessary packages or breaking existing APIs.

## Complexity Tracking

*No violations detected. All constitution principles satisfied.*
