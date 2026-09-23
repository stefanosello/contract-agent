"""Automated Mutation Safety Verification in CI: Rogue Mutant bypass prevention tests."""

from unittest.mock import MagicMock
import pytest

from contract_agent.core.parser import ContractParser
from contract_agent.runtime.guards import GuardInterceptor
from contract_agent.runtime.context import WorkflowContext
from contract_agent.testing.mutants import run_mutation_safety_suite

CONTRACT_WITH_GUARDS = {
    "spec_version": "0.3",
    "metadata": {"name": "mutation_defense_agent"},
    "invariants": [
        {
            "id": "INV-001",
            "target": "tool:execute_refund",
            "description": "Never exceed $250 without approval",
            "rule": "args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)",
        },
        {
            "id": "INV-002",
            "target": "session:call_sequence",
            "description": "Must fetch invoice first",
            "rule": "workflow.called_before('fetch_invoice', 'execute_refund', args.invoice_id)",
        },
        {
            "id": "INV-003",
            "target": "tool:execute_refund",
            "description": "Must provide a non-empty audit reason of at least 10 chars",
            "rule": "size(args.reason.trim()) >= 10",
        },
    ],
    "tools": [
        {"name": "fetch_invoice", "description": "Fetch invoice"},
        {"name": "execute_refund", "description": "Execute refund"},
    ],
}


def test_mutation_safety_suite_traps_all_attacks():
    """Validates that 100% of rogue mutant bypass attempts are trapped by GuardInterceptor."""
    ast = ContractParser.from_dict(CONTRACT_WITH_GUARDS)
    ctx = WorkflowContext()
    interceptor = GuardInterceptor(ast, context=ctx)

    # Real/Mock backend handlers that perform mutations
    refund_backend = MagicMock(return_value={"refund_id": "DANGEROUS_MUTATION"})
    fetch_backend = MagicMock(return_value={"status": "paid"})

    handlers = {
        "fetch_invoice": fetch_backend,
        "execute_refund": refund_backend,
    }

    report = run_mutation_safety_suite(interceptor, handlers)

    # Assert 0% escape rate!
    assert report.total_attacks == 4
    assert report.trapped_attacks == 4
    assert report.escaped_attacks == 0
    assert report.escape_rate == 0.0
    assert report.passed is True

    # Assert dangerous mutation handler was NEVER called by any rogue attack!
    refund_backend.assert_not_called()
