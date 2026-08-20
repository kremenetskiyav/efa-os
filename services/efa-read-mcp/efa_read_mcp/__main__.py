"""Run EFA Read MCP over stdio."""

from .server import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
