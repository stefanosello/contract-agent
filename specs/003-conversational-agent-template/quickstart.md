# Quickstart & Validation Guide: Conversational Agent Template

**Feature**: `003-conversational-agent-template`  
**Date**: 2026-09-24  
**Status**: Ready for Validation  

---

## 1. Prerequisites

- Python 3.11+
- Virtual environment active with dependencies installed (`uv sync`)
- Benchmark contracts available in `tests/fixtures/benchmarks/`

---

## 2. Validation Scenario 1: Multi-Turn Conversational Interaction

Validate that a compiled conversational agent can engage in multi-turn dialogues, maintaining history and state across messages.

### Python Verification
```python
from dist.agent import BillingDisputeAgent, AgentState
from dist.mocks import MockAgentTools
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.guards import GuardInterceptor
from contract_agent.core.parser import ContractParser
from pathlib import Path

contract = ContractParser.from_file(Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"))
tools = MockAgentTools()
context = WorkflowContext()
interceptor = GuardInterceptor(contract=contract, context=context)

agent = BillingDisputeAgent(tools=tools, interceptor=interceptor)

# Turn 1
reply1 = agent.chat("Hi, I have a question about my invoice.")
assert len(reply1) > 0
assert agent.state == AgentState.AWAITING_INPUT
assert len(agent.session.messages) == 2  # user + assistant

# Turn 2 (referencing previous turn)
reply2 = agent.chat("Can you check invoice INV-101?")
assert "INV-101" in reply2 or "fetch_invoice" in tools.call_counts
assert agent.state == AgentState.AWAITING_INPUT
assert len(agent.session.messages) == 4
```

---

## 3. Validation Scenario 2: Stream-First Event Consumption

Validate that `stream()` emits typed events incrementally during interaction.

### Python Verification
```python
import asyncio

async def test_streaming():
    events = []
    async for event in agent.stream("Please fetch invoice INV-101"):
        events.append(event)
    
    event_types = [e.type for e in events]
    assert "token" in event_types or "tool_call_start" in event_types
    assert "turn_complete" in event_types

asyncio.run(test_streaming())
```

---

## 4. Validation Scenario 3: Invariant Escalation & Hybrid Approval

Validate that when an invariant requires escalation (e.g. refund > $100), the agent pauses with status `AWAITING_APPROVAL`, provides a token, and resumes upon approval.

### Python Verification
```python
# Request refund exceeding $100 limit (INV-001)
result = agent.step("Please refund $150 on invoice INV-101")

assert result.requires_approval is True
assert agent.state == AgentState.AWAITING_APPROVAL
assert result.approval_token is not None

# Resume execution via approve()
approval_result = agent.approve(result.approval_token)
assert approval_result.requires_approval is False
assert agent.state in (AgentState.AWAITING_INPUT, AgentState.COMPLETED)
assert tools.call_counts.get("execute_refund", 0) == 1
```

---

## 5. Validation Scenario 4: Conversational Test Suite Generation

Validate that the compiler generates multi-turn dialogue test suites in `dist/test_contract.py` that pass 100% under pytest.

### Command
```bash
uv run contract-agent compile tests/fixtures/benchmarks/01_billing_dispute.contract.yaml \
  --output-dir dist \
  --headless-ci

uv run pytest dist/test_contract.py -v
```

### Expected Outcome
- `dist/agent.py` contains conversational ReAct FSM agent with `stream`, `step`, `chat`, and `approve`.
- `dist/test_contract.py` executes multi-turn conversational tests verifying invariant enforcement and state transitions.
- Pytest exits code 0 with 100% passed tests.
