"""ContractAgent: A Spec-Driven Behavioral Contract & Verification Engine."""

from contract_agent.core.ast import ContractAST, Invariant, ToolContract
from contract_agent.core.exceptions import (
    ContractAgentError,
    ContractValidationError,
    EscalationRequiredError,
    InvariantViolationError,
)
from contract_agent.core.parser import ContractParser, load_contract
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor

__version__ = "0.1.0"

__all__ = [
    "CELEngine",
    "ContractAST",
    "ContractAgentError",
    "ContractParser",
    "ContractValidationError",
    "EscalationRequiredError",
    "GuardInterceptor",
    "Invariant",
    "InvariantViolationError",
    "ToolContract",
    "WorkflowContext",
    "load_contract",
]
