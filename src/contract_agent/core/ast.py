"""Pydantic V2 models for ContractAgent Abstract Syntax Tree (AST)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Metadata(BaseModel):
    name: str = Field(..., description="Unique machine-readable name of the agent")
    version: str = Field(default="0.1.0", description="Semver version string")
    description: str | None = Field(None, description="Human readable description")

    model_config = ConfigDict(extra="forbid")


class SystemConfig(BaseModel):
    role: str = Field(..., description="System persona and domain role")
    guidelines: list[str] = Field(
        default_factory=list, description="Operational guidelines"
    )

    model_config = ConfigDict(extra="forbid")


class Invariant(BaseModel):
    id: str = Field(
        ..., description="Unique identifier for the invariant (e.g. INV-001)"
    )
    target: str = Field(
        ...,
        description="Target scope for enforcement (e.g. tool:execute_refund or session:call_sequence)",
    )
    description: str = Field(..., description="Human-readable policy rationale")
    rule: str = Field(
        ..., description="Google Common Expression Language (CEL) boolean rule"
    )
    on_violation: Literal[
        "raise_invariant_violation", "block_tool_call", "require_escalation"
    ] = Field(
        default="raise_invariant_violation",
        description="Action to take when invariant evaluates to False",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Invariant id cannot be empty")
        return v.strip()

    @field_validator("rule")
    @classmethod
    def validate_rule(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Invariant CEL rule cannot be empty")
        return v.strip()


class ToolContract(BaseModel):
    name: str = Field(..., description="Function name of the tool")
    description: str = Field(..., description="Documentation for the tool")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema object for inputs"
    )
    returns: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema object for return payload"
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict, description="Optional static tool constraints"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"Tool name '{v}' must be a valid Python identifier")
        return v


class ScenarioExpectation(BaseModel):
    tool_call: str | None = Field(
        None, description="Expected tool invoked at this step"
    )
    with_args: dict[str, Any] | None = Field(
        None, description="Expected tool arguments"
    )
    never_call: str | None = Field(
        None, description="Tool that MUST NOT be called at this step"
    )
    response_contains: list[str] | None = Field(
        None, description="Keywords or phrases expected in final agent response"
    )

    model_config = ConfigDict(extra="forbid")


class Scenario(BaseModel):
    id: str = Field(..., description="Unique scenario ID (e.g. SCEN-001)")
    title: str = Field(..., description="Descriptive scenario title")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Mock state fixture for the scenario"
    )
    user_input: str = Field(
        ..., description="Natural language prompt sent to the agent"
    )
    expected_flow: list[ScenarioExpectation] = Field(
        default_factory=list, description="Sequence of expected actions and assertions"
    )

    model_config = ConfigDict(extra="forbid")


class ContractAST(BaseModel):
    spec_version: str = Field(
        default="0.3", description="ContractAgent specification schema version"
    )
    metadata: Metadata
    system: SystemConfig | None = None
    invariants: list[Invariant] = Field(default_factory=list)
    tools: list[ToolContract] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def get_tool(self, name: str) -> ToolContract | None:
        """Look up a tool contract by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_invariants_for_tool(self, tool_name: str) -> list[Invariant]:
        """Return all invariants scoped to a specific tool."""
        tool_target = f"tool:{tool_name}"
        matching: list[Invariant] = []

        for inv in self.invariants:
            if inv.target == tool_target or inv.target == "*":
                matching.append(inv)
            elif inv.target == "session:call_sequence":
                # Check if this rule is a sequence check gating this specific tool
                # E.g. called_before('fetch_invoice', 'execute_refund') gates execute_refund
                quoted_target1 = f"'{tool_name}'"
                quoted_target2 = f'"{tool_name}"'
                if "called_before" in inv.rule:
                    # In called_before(prior, target), target is the second argument
                    if quoted_target1 in inv.rule or quoted_target2 in inv.rule:
                        parts = inv.rule.split("called_before", 1)[1]
                        # If tool_name is the second argument in called_before, it gates this tool
                        if (
                            f", {quoted_target1}" in parts
                            or f",{quoted_target1}" in parts
                            or f", {quoted_target2}" in parts
                            or f",{quoted_target2}" in parts
                        ):
                            matching.append(inv)
                else:
                    # Generic session rule mentioning tool
                    if quoted_target1 in inv.rule or quoted_target2 in inv.rule:
                        matching.append(inv)

        return matching
