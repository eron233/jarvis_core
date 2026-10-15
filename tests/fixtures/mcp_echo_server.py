"""Servidor MCP real minimo usado somente no teste de interoperabilidade."""

from mcp.server import MCPServer

mcp = MCPServer("jarvis-mcp-integration-test")


@mcp.tool()
def echo(text: str) -> dict[str, str]:
    """Retorna exatamente o texto recebido."""
    return {"echo": text}


@mcp.resource("echo://hello")
def hello_resource() -> str:
    """Resource fixo de teste."""
    return "hello-from-real-mcp-resource"


@mcp.prompt()
def greet(name: str = "Jarvis") -> str:
    """Prompt simples de teste."""
    return f"Cumprimente {name} em português brasileiro."


if __name__ == "__main__":
    mcp.run(transport="stdio")
