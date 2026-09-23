"""Unit tests for ContractAgent AST models and YAML parser."""

import pytest
import yaml

from contract_agent.core.exceptions import ContractValidationError
from contract_agent.core.parser import ContractParser, load_contract

VALID_CONTRACT_YAML = """
spec_version: "0.3"

metadata:
  name: "billing_resolution_agent"
  version: "1.0.0"
  description: "Handles customer billing disputes within policy."

system:
  role: "Senior Customer Billing Specialist"
  guidelines:
    - "Never guess invoice details; always query the billing database."

invariants:
  - id: "INV-001"
    target: "tool:execute_refund"
    description: "Refunds > $250 require verified manager sign-off."
    rule: "args.amount_cents <= 25000 || workflow.has_approval('manager_signoff', args.invoice_id)"
    on_violation: "raise_invariant_violation"

  - id: "INV-002"
    target: "session:call_sequence"
    description: "Must inspect the invoice before executing a refund."
    rule: "workflow.called_before('fetch_invoice', 'execute_refund', args.invoice_id)"
    on_violation: "block_tool_call"

tools:
  - name: "fetch_invoice"
    description: "Retrieves invoice status."
    parameters:
      type: object
      properties:
        invoice_id: { type: string }
      required: ["invoice_id"]
    returns:
      type: object

  - name: "execute_refund"
    description: "Processes a refund."
    parameters:
      type: object
      properties:
        invoice_id: { type: string }
        amount_cents: { type: integer }
      required: ["invoice_id", "amount_cents"]
    returns:
      type: object

scenarios:
  - id: "SCEN-001"
    title: "Valid refund"
    context:
      invoice_id: "INV-1"
    user_input: "Refund invoice INV-1"
    expected_flow:
      - tool_call: "fetch_invoice"
        with_args: { invoice_id: "INV-1" }
      - tool_call: "execute_refund"
        with_args: { invoice_id: "INV-1", amount_cents: 2000 }
"""


def test_parse_valid_contract():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    ast = ContractParser.from_dict(data)

    assert ast.metadata.name == "billing_resolution_agent"
    assert ast.metadata.version == "1.0.0"
    assert len(ast.invariants) == 2
    assert len(ast.tools) == 2
    assert len(ast.scenarios) == 1

    tool = ast.get_tool("execute_refund")
    assert tool is not None
    assert tool.name == "execute_refund"

    invariants = ast.get_invariants_for_tool("execute_refund")
    assert (
        len(invariants) == 2
    )  # INV-001 (tool:execute_refund) and INV-002 (session:call_sequence)


def test_missing_required_fields_fails():
    invalid_data = {
        "spec_version": "0.3",
        # missing metadata!
        "tools": [],
    }
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(invalid_data)
    assert "validation failed" in str(exc.value).lower()


def test_duplicate_invariant_id_fails():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    data["invariants"].append(
        {
            "id": "INV-001",  # duplicate!
            "target": "tool:execute_refund",
            "description": "Another rule with same ID",
            "rule": "true",
        }
    )
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(data)
    assert "Duplicate invariant ID" in str(exc.value)


def test_undefined_tool_in_invariant_fails():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    data["invariants"].append(
        {
            "id": "INV-003",
            "target": "tool:non_existent_tool",
            "description": "Rule for phantom tool",
            "rule": "true",
        }
    )
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(data)
    assert "references undefined tool 'non_existent_tool'" in str(exc.value)


def test_undefined_tool_in_scenario_fails():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    data["scenarios"][0]["expected_flow"].append({"tool_call": "unknown_tool_xyz"})
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(data)
    assert "expects tool 'unknown_tool_xyz' which is not defined" in str(exc.value)


def test_load_from_file(tmp_path):
    contract_file = tmp_path / "test.contract.yaml"
    contract_file.write_text(VALID_CONTRACT_YAML, encoding="utf-8")

    ast = load_contract(contract_file)
    assert ast.metadata.name == "billing_resolution_agent"


def test_invalid_cel_syntax_fails():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    data["invariants"].append(
        {
            "id": "INV-SYNTAX-ERR",
            "target": "tool:execute_refund",
            "description": "Malformed syntax",
            "rule": "args.amount_cents === 25000",  # Invalid CEL syntax
        }
    )
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(data)
    assert "contains invalid CEL expression" in str(exc.value)


def test_undefined_parameter_reference_fails():
    data = yaml.safe_load(VALID_CONTRACT_YAML)
    data["invariants"].append(
        {
            "id": "INV-UNKNOWN-PARAM",
            "target": "tool:execute_refund",
            "description": "References unknown parameter",
            "rule": "args.unregistered_param == 'xyz'",
        }
    )
    with pytest.raises(ContractValidationError) as exc:
        ContractParser.from_dict(data)
    assert "references undefined parameter 'args.unregistered_param'" in str(exc.value)
