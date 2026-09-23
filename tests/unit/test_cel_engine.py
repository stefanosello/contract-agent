"""Unit tests for ContractAgent CEL Engine."""

import pytest

from contract_agent.core.ast import Invariant
from contract_agent.runtime.cel_engine import CELEngine
from contract_agent.runtime.context import WorkflowContext


@pytest.fixture
def cel_engine():
    return CELEngine()


def test_numerical_boundary_rule(cel_engine):
    rule = "args.amount_cents <= 25000"
    assert cel_engine.evaluate_rule(rule, {"amount_cents": 24999}) is True
    assert cel_engine.evaluate_rule(rule, {"amount_cents": 25000}) is True
    assert cel_engine.evaluate_rule(rule, {"amount_cents": 25001}) is False


def test_approval_rule_without_approval(cel_engine):
    rule = "args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)"
    ctx = WorkflowContext()

    # 350.00 without approval -> False
    args = {"amount_cents": 35000, "invoice_id": "INV-100"}
    assert cel_engine.evaluate_rule(rule, args, ctx) is False


def test_approval_rule_with_approval(cel_engine):
    rule = "args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)"
    ctx = WorkflowContext()

    # Grant approval
    ctx.approval_store.grant_approval(
        "manager_signoff", "INV-100", granted_by="vp_finance"
    )

    args = {"amount_cents": 35000, "invoice_id": "INV-100"}
    assert cel_engine.evaluate_rule(rule, args, ctx) is True

    # Another invoice without approval should still be False
    other_args = {"amount_cents": 35000, "invoice_id": "INV-200"}
    assert cel_engine.evaluate_rule(rule, other_args, ctx) is False


def test_called_before_sequence_rule(cel_engine):
    rule = "workflow.called_before('fetch_invoice', 'execute_refund', args.invoice_id)"
    ctx = WorkflowContext()
    args = {"invoice_id": "INV-99"}

    # Initially False
    assert cel_engine.evaluate_rule(rule, args, ctx) is False

    # After calling fetch_invoice for INV-99 -> True
    ctx.record_call("fetch_invoice", {"invoice_id": "INV-99"}, resource_id="INV-99")
    assert cel_engine.evaluate_rule(rule, args, ctx) is True

    # But for INV-100 -> False
    assert cel_engine.evaluate_rule(rule, {"invoice_id": "INV-100"}, ctx) is False


def test_call_count_rate_limit(cel_engine):
    rule = "workflow.call_count('execute_refund') < 2"
    ctx = WorkflowContext()
    args = {}

    assert cel_engine.evaluate_rule(rule, args, ctx) is True
    ctx.record_call("execute_refund", {})
    assert cel_engine.evaluate_rule(rule, args, ctx) is True
    ctx.record_call("execute_refund", {})
    assert cel_engine.evaluate_rule(rule, args, ctx) is False


def test_string_trim_and_size_rule(cel_engine):
    rule = "size(args.reason.trim()) >= 10"
    assert cel_engine.evaluate_rule(rule, {"reason": "Short"}) is False
    assert cel_engine.evaluate_rule(rule, {"reason": "   Spaces   "}) is False
    assert (
        cel_engine.evaluate_rule(
            rule, {"reason": "Valid reason exceeding ten characters"}
        )
        is True
    )


def test_evaluate_invariant_helper(cel_engine):
    inv = Invariant(
        id="INV-001",
        target="tool:execute_refund",
        description="Limit test",
        rule="args.amount <= 100",
    )
    res_pass = cel_engine.evaluate_invariant(inv, "execute_refund", {"amount": 50})
    assert res_pass.is_valid is True
    assert res_pass.evaluation_time_ms < 5.0  # Must be fast

    res_fail = cel_engine.evaluate_invariant(inv, "execute_refund", {"amount": 150})
    assert res_fail.is_valid is False
    assert "evaluated to False" in res_fail.error_message


def test_called_before_global_overload(cel_engine):
    rule = "workflow.called_before('init_session', 'execute_action')"
    ctx = WorkflowContext()
    assert cel_engine.evaluate_rule(rule, {}, ctx) is False

    ctx.record_call("init_session", {"user": "admin"})
    assert cel_engine.evaluate_rule(rule, {}, ctx) is True


def test_call_count_resource_correlated_overload(cel_engine):
    rule = "workflow.call_count('execute_refund', args.invoice_id) < 1"
    ctx = WorkflowContext()
    args_inv1 = {"invoice_id": "INV-1"}
    args_inv2 = {"invoice_id": "INV-2"}

    assert cel_engine.evaluate_rule(rule, args_inv1, ctx) is True
    ctx.record_call("execute_refund", args_inv1, resource_id="INV-1")

    # INV-1 has 1 call, so < 1 evaluates to False
    assert cel_engine.evaluate_rule(rule, args_inv1, ctx) is False

    # INV-2 has 0 calls, so < 1 evaluates to True
    assert cel_engine.evaluate_rule(rule, args_inv2, ctx) is True
