"""Data models and telemetry schemas for the ContractAgent compiler."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentState(str, Enum):
    """Lifecycle states of the conversational agent."""

    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    AWAITING_INPUT = "AWAITING_INPUT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConversationEventType(str, Enum):
    """Discriminator types for stream events."""

    TOKEN = "token"
    THOUGHT = "thought"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    STATE_CHANGE = "state_change"
    ESCALATION_REQUIRED = "escalation_required"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"


class ConversationEvent(BaseModel):
    """Discrete event yielded across an asynchronous stream."""

    type: ConversationEventType
    content: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: Any | None = None
    new_state: AgentState | None = None
    approval_token: str | None = None
    timestamp: float = Field(default_factory=time.time)

    model_config = ConfigDict(extra="forbid")


class MessageRole(str, Enum):
    """Canonical message authorship roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationMessage(BaseModel):
    """Individual dialogue turn stored in session history."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None
    timestamp: float = Field(default_factory=time.time)

    model_config = ConfigDict(extra="forbid")


class PendingApproval(BaseModel):
    """Suspended tool execution requiring human approval."""

    token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invariant_id: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    status: str = "pending"

    model_config = ConfigDict(extra="forbid")


class ConversationSession(BaseModel):
    """Container for stateful multi-turn interactions."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: AgentState = AgentState.IDLE
    messages: list[ConversationMessage] = Field(default_factory=list)
    pending_approvals: dict[str, PendingApproval] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ConversationTurnResult(BaseModel):
    """Structured result returned from a synchronous turn execution."""

    reply: str
    state: AgentState
    events: list[ConversationEvent] = Field(default_factory=list)
    tools_executed: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    approval_token: str | None = None

    model_config = ConfigDict(extra="forbid")


class CompilationConfig(BaseModel):
    """Configuration options for a compiler execution run."""

    contract_path: Path
    output_dir: Path = Field(default_factory=lambda: Path("dist"))
    staging_dir: Path = Field(default_factory=lambda: Path("dist/.staging"))
    provider_name: str = "mock"
    model_name: str | None = None
    max_retries: int = 3
    budget_ceiling: float = 0.05
    per_test_timeout: float = 10.0
    headless_ci: bool = False

    model_config = ConfigDict(extra="forbid")


class LLMResponse(BaseModel):
    """Output from an LLM synthesis turn."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model_name: str = "mock"

    model_config = ConfigDict(extra="forbid")


class CostTelemetry(BaseModel):
    """Cumulative usage and financial telemetry across compilation turns."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    by_persona: dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def record_call(self, response: LLMResponse, persona: str | None = None) -> None:
        """Accumulates token counts and dollar expenses."""
        self.total_prompt_tokens += response.prompt_tokens
        self.total_completion_tokens += response.completion_tokens
        self.total_cost_usd += response.cost_usd
        self.call_count += 1
        if persona:
            self.by_persona[persona] = (
                self.by_persona.get(persona, 0.0) + response.cost_usd
            )


class TestFailureDetail(BaseModel):
    """Detailed diagnosis for a single test assertion or CEL failure."""

    test_name: str
    assertion_error: str
    traceback: str = ""
    cel_invariant_id: str | None = None
    cel_violation_rule: str | None = None
    cel_args: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class VerificationReport(BaseModel):
    """Structured report produced by the sandboxed test runner."""

    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    failures: list[TestFailureDetail] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    raw_output: str = ""

    model_config = ConfigDict(extra="forbid")


class CompilationResult(BaseModel):
    """Final output and promotion status from a contract compilation run."""

    success: bool
    promoted: bool
    iterations_used: int = 0
    telemetry: CostTelemetry = Field(default_factory=CostTelemetry)
    verification_report: VerificationReport | None = None
    generated_files: list[Path] = Field(default_factory=list)
    diff_summary: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(extra="forbid")
