"""Local stdio MCP tool; this does not change Cursor's orchestrator model."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from foundry_client import infer
from claude_client import infer_claude

mcp = FastMCP(
    "foundry-models",
    instructions=(
        "This server delegates bounded text tasks to an OpenAI model or a Claude model deployed in "
        "Microsoft Foundry. It does not replace the Cursor model. Use synthetic, non-sensitive prompts only. "
        "Return the deployment, model, response_id and text as evidence."
    ),
)


@mcp.tool()
def foundry_openai(
    prompt: Annotated[str, Field(min_length=1, max_length=8000)],
    max_output_tokens: Annotated[int, Field(ge=128, le=2048, strict=True)] = 512,
) -> dict:
    """Run a text task on the configured OpenAI model deployment in Microsoft Foundry.

    Uses the OpenAI Responses API on the Foundry v1 endpoint. The Azure credential
    stays in this local process. Text and response metadata return to Cursor and
    therefore may leave the machine. Never pass secrets.
    No files, shell commands, custom endpoints, or model overrides are accepted.
    """
    return infer(prompt, max_output_tokens)


@mcp.tool()
def foundry_claude(
    prompt: Annotated[str, Field(min_length=1, max_length=8000)],
    max_output_tokens: Annotated[int, Field(ge=128, le=2048, strict=True)] = 512,
) -> dict:
    """Run a text task on the configured Claude deployment in Microsoft Foundry.

    Uses the native Anthropic Messages API, not an OpenAI URL. The Azure
    credential stays local; the returned text and metadata are visible to Cursor.
    Never pass secrets. This does not replace Cursor's orchestrator model.
    """
    return infer_claude(prompt, max_output_tokens)


if __name__ == "__main__":
    mcp.run(transport="stdio")
