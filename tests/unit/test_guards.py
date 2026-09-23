"""Unit tests for GuardInterceptor runtime enforcement."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from contract_agent.core.parser import ContractParser
from contract_agent.core.exceptions import ApprovalRequiredError, InvariantViolationError
from contract_agent.runtime.guards import GuardInterceptor
from contract_agent.runtime.context import WorkflowContext

SAMPLE_CONTRACT = {
    "spec_version": "0.3",
    "metadata": {"name": "test_agent"},
    "invariants": [
        {
            "id": "INV-001",
            "target": "tool:execute_refund",
            "description": "Refund limit $250 without approval",
            "rule": "args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)",
        },
        {
            "id": "INV-002",
            "target": "session:call_sequence",
            "description": "Must fetch invoice first",
            "rule": "workflow.called_before('fetch_invoice', 'execute_refund', args.invoice_id)",
        },
    ],
    "tools": [
        {"name": "fetch_invoice", "description": "Fetch invoice"},
        {"name": "execute_refund", "description": "Execute refund"},
    ],
}


def test_guard_blocks_unauthorized_call_before_execution():
    ast = ContractParser.from_dict(SAMPLE_CONTRACT)
    ctx = WorkflowContext()
    interceptor = GuardInterceptor(ast, context=ctx)

    mock_handler = MagicMock(return_value={"status": "refunded"})
    guarded_refund = interceptor.wrap_tool("execute_refund", mock_handler)

    # 1. Attempt refund without fetch_invoice -> Should fail INV-002 (called_before)
    with pytest.raises(InvariantViolationError) as exc:
        guarded_refund(invoice_id="INV-10", amount_cents=1000)

    # Assert underlying tool was NEVER called
    mock_handler.assert_not_called()
    assert "INV-002" in str(exc.value)


def test_guard_allows_valid_call_and_records_history():
    ast = ContractParser.from_dict(SAMPLE_CONTRACT)
    ctx = WorkflowContext()
    interceptor = GuardInterceptor(ast, context=ctx)

    fetch_mock = MagicMock(return_value={"invoice_id": "INV-10", "status": "paid"})
    refund_mock = MagicMock(return_value={"refund_id": "REF-1"})

    guarded_fetch = interceptor.wrap_tool("fetch_invoice", fetch_mock)
    guarded_refund = interceptor.wrap_tool("execute_refund", refund_mock)

    # Call fetch_invoice
    res_fetch = guarded_fetch(invoice_id="INV-10")
    assert res_fetch["status"] == "paid"
    fetch_mock.assert_called_once_with(invoice_id="INV-10")
    assert len(ctx.call_history) == 1

    # Call refund ($200 <= $250)
    res_refund = guarded_refund(invoice_id="INV-10", amount_cents=20000)
    assert res_refund["refund_id"] == "REF-1"
    refund_mock.assert_called_once_with(invoice_id="INV-10", amount_cents=20000)
    assert len(ctx.call_history) == 2


def test_guard_requires_escalation_for_high_amount():
    ast = ContractParser.from_dict(SAMPLE_CONTRACT)
    ctx = WorkflowContext()
    interceptor = GuardInterceptor(ast, context=ctx)

    fetch_mock = MagicMock(return_value={"invoice_id": "INV-10"})
    refund_mock = MagicMock()

    guarded_fetch = interceptor.wrap_tool("fetch_invoice", fetch_mock)
    guarded_refund = interceptor.wrap_tool("execute_refund", refund_mock)

    guarded_fetch(invoice_id="INV-10")

    # Attempt $350 refund
    with pytest.raises(ApprovalRequiredError) as exc:
        guarded_refund(invoice_id="INV-10", amount_cents=35000)

    refund_mock.assert_not_called()
    assert exc.value.approval_type == "manager_signoff"
    assert exc.value.resource_id == "INV-10"

    # Grant approval out-of-band
    ctx.approval_store.grant_approval("manager_signoff", "INV-10", granted_by="vp_finance")

    # Retry -> Should succeed now
    guarded_refund(invoice_id="INV-10", amount_cents=35000)
    refund_mock.assert_called_once()


@pytest.mark.asyncio
async def test_async_guard_wrapper():
    ast = ContractParser.from_dict(SAMPLE_CONTRACT)
    ctx = WorkflowContext()
    interceptor = GuardInterceptor(ast, context=ctx)

    async_fetch_mock = AsyncMock(return_value={"invoice_id": "INV-1"})
    guarded_async_fetch = interceptor.wrap_tool("fetch_invoice", async_fetch_mock)

    res = await guarded_async_fetch(invoice_id="INV-1")
    assert res["invoice_id"] == "INV-1"
    async_fetch_mock.assert_called_once_with(invoice_id="INV-1")
    assert ctx.called_before("fetch_invoice", "execute_refund", "INV-1") is True
