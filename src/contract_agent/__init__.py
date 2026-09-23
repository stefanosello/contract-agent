"""ContractAgent: A Spec-Driven Behavioral Contract & Verification Engine."""

from contract_agent.cli.review import ReviewGate
from contract_agent.compiler.models import (
    CompilationConfig,
    CompilationResult,
    CostTelemetry,
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
from contract_agent.runtime.guards import GuardInterceptor

__version__ = "0.1.0"

__all__ = [
    "BudgetExceededError",
    "CELEngine",
    "CompilationConfig",
    "CompilationResult",
    "ContractAST",
    "ContractAgentError",
    "ContractCompiler",
    "ContractParser",
    "ContractValidationError",
    "CostTelemetry",
    "EscalationRequiredError",
    "GuardInterceptor",
    "Invariant",
    "InvariantViolationError",
    "IsolationSecurityError",
    "LLMProvider",
    "MockLLMProvider",
    "ReviewGate",
    "ToolContract",
    "VerificationReport",
    "WorkflowContext",
    "get_provider",
    "load_contract",
]
