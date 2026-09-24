"""ContractAgent: A Spec-Driven Behavioral Contract & Verification Engine."""

from contract_agent.cli.review import ReviewGate
from contract_agent.compiler.models import (
    AgentState,
    CompilationConfig,
    CompilationResult,
    ConversationEvent,
    ConversationEventType,
    ConversationMessage,
    ConversationSession,
    ConversationTurnResult,
    CostTelemetry,
    MessageRole,
    PendingApproval,
    VerificationReport,
)
from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import (
    LLMProvider,
    MockLLMProvider,
    get_provider,
)
from contract_agent.core.ast import ContractAST, Invariant, ToolContract
from contract_agent.core.exceptions import (
    BudgetExceededError,
    ContractAgentError,
    ContractValidationError,
    EscalationRequiredError,
    InvariantViolationError,
    IsolationSecurityError,
)
from contract_agent.core.parser import ContractParser, load_contract
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.conversational import BaseConversationalAgent
from contract_agent.runtime.guards import GuardInterceptor

ConversationalAgent = BaseConversationalAgent

__version__ = "0.2.6"

__all__ = [
    "AgentState",
    "BaseConversationalAgent",
    "BudgetExceededError",
    "CELEngine",
    "CompilationConfig",
    "CompilationResult",
    "ContractAST",
    "ContractAgentError",
    "ContractCompiler",
    "ContractParser",
    "ContractValidationError",
    "ConversationEvent",
    "ConversationEventType",
    "ConversationMessage",
    "ConversationSession",
    "ConversationTurnResult",
    "ConversationalAgent",
    "CostTelemetry",
    "EscalationRequiredError",
    "GuardInterceptor",
    "Invariant",
    "InvariantViolationError",
    "IsolationSecurityError",
    "LLMProvider",
    "MessageRole",
    "MockLLMProvider",
    "PendingApproval",
    "ReviewGate",
    "ToolContract",
    "VerificationReport",
    "WorkflowContext",
    "get_provider",
    "load_contract",
]

