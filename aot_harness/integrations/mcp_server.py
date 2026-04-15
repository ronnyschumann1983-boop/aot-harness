"""
aot_harness/integrations/mcp_server.py
MCP (Model Context Protocol) Server — makes the Harness usable in Claude Code.
Install MCP SDK: pip install mcp
"""
from __future__ import annotations

MCP_TOOL_SCHEMA = {
    "name": "aot_harness_run",
    "description": (
        "Run a complex goal through the AoT Harness. "
        "Decomposes the goal into atoms, solves them in parallel, "
        "and returns a verified result."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "The complex task or question to solve"
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID for persistent memory"
            }
        },
        "required": ["goal"]
    }
}


def create_mcp_server(orchestrator_factory):
    """
    Returns an MCP server instance with the harness tool registered.
    orchestrator_factory: callable() -> Orchestrator
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types
    except ImportError:
        raise ImportError("Run: pip install mcp")

    server = Server("aot-harness")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(**MCP_TOOL_SCHEMA)]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "aot_harness_run":
            raise ValueError(f"Unknown tool: {name}")
        orch   = orchestrator_factory(arguments.get("session_id", "mcp"))
        result = orch.run(arguments["goal"])
        return [types.TextContent(type="text", text=result["result"])]

    return server, stdio_server
