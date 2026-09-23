"""Deterministic code generator translating ContractAST into Protocols and synthetic Mocks."""

from __future__ import annotations

from typing import Any

from contract_agent.core.ast import ContractAST


def _json_type_to_python(schema_type: str | None) -> str:
    """Maps JSON schema types to Python type annotations."""
    mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list[Any]",
        "object": "dict[str, Any]",
        "null": "None",
    }
    return mapping.get(schema_type or "object", "Any")


def _format_parameters(parameters_schema: dict[str, Any]) -> str:
    """Formats JSON Schema properties into Python typed function parameters."""
    props: dict[str, Any] = parameters_schema.get("properties", {})
    required: list[str] = parameters_schema.get("required", [])

    if not props:
        return "self"

    params: list[str] = ["self"]
    # Required parameters first
    for name in required:
        if name in props:
            ptype = _json_type_to_python(props[name].get("type"))
            params.append(f"{name}: {ptype}")

    # Optional parameters with default None
    for name, spec in props.items():
        if name not in required:
            ptype = _json_type_to_python(spec.get("type"))
            params.append(f"{name}: {ptype} | None = None")

    return ", ".join(params)


def _format_return_type(returns_schema: dict[str, Any]) -> str:
    """Formats return type from JSON Schema."""
    rtype = returns_schema.get("type")
    if not rtype:
        return "dict[str, Any]"
    return _json_type_to_python(rtype)


def generate_interface_code(ast: ContractAST) -> str:
    """Generates typed Python Protocol definitions for dist/interface.py."""
    lines: list[str] = [
        '"""Auto-generated tool protocols derived from contract specification."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Protocol, runtime_checkable",
        "",
        "",
        "@runtime_checkable",
        "class AgentToolsProtocol(Protocol):",
        f'    """Tool interface protocol for {ast.metadata.name}."""',
        "",
    ]

    if not ast.tools:
        lines.append("    pass\n")
    else:
        for tool in ast.tools:
            params = _format_parameters(tool.parameters)
            rtype = _format_return_type(tool.returns)
            lines.append(f"    def {tool.name}({params}) -> {rtype}:")
            lines.append(f'        """{tool.description}"""')
            lines.append("        ...")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_mocks_code(ast: ContractAST) -> str:
    """Generates synthetic test mock implementation in dist/mocks.py."""
    lines: list[str] = [
        '"""Synthetic test double implementing AgentToolsProtocol for local evaluation."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "try:",
        "    from interface import AgentToolsProtocol",
        "except ImportError:",
        "    from dist.interface import AgentToolsProtocol  # type: ignore[no-redef]",
        "",
        "",
        "class MockAgentTools(AgentToolsProtocol):",
        f'    """Synthetic mock double for {ast.metadata.name} tools."""',
        "",
        "    def __init__(self, default_returns: dict[str, Any] | None = None) -> None:",
        "        self.calls: list[dict[str, Any]] = []",
        "        self.default_returns: dict[str, Any] = default_returns or {}",
        "        self.call_counts: dict[str, int] = {}",
        "",
    ]

    if not ast.tools:
        lines.append("    pass\n")
    else:
        for tool in ast.tools:
            params = _format_parameters(tool.parameters)
            rtype = _format_return_type(tool.returns)
            props: dict[str, Any] = tool.parameters.get("properties", {})
            param_names = list(props.keys())

            args_dict_entries = ", ".join(f'"{p}": {p}' for p in param_names)
            args_repr = f"{{{args_dict_entries}}}" if param_names else "{}"

            lines.append(f"    def {tool.name}({params}) -> {rtype}:")
            lines.append(f"        call_info = {{'tool': '{tool.name}', 'args': {args_repr}}}")
            lines.append("        self.calls.append(call_info)")
            lines.append(f"        self.call_counts['{tool.name}'] = self.call_counts.get('{tool.name}', 0) + 1")
            lines.append(f"        if '{tool.name}' in self.default_returns:")
            lines.append(f"            return self.default_returns['{tool.name}']")
            
            # Default placeholder return
            if rtype == "dict[str, Any]":
                default_val = "{'status': 'mocked_ok'}"
            elif rtype == "list[Any]":
                default_val = "[]"
            elif rtype == "int":
                default_val = "0"
            elif rtype == "float":
                default_val = "0.0"
            elif rtype == "bool":
                default_val = "True"
            else:
                default_val = "'mock_result'"
            lines.append(f"        return {default_val}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
