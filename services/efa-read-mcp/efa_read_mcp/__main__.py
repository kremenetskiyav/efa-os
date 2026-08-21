"""Run EFA Read MCP over Streamable HTTP."""

from .config import Settings
from .server import mcp


def main() -> None:
    settings = Settings.from_environment()
    mcp.run(
        transport="streamable-http",
        host=settings.http_host,
        port=settings.http_port,
        streamable_http_path=settings.http_path,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
