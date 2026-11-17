"""Exercise real Foundry inference directly and through an MCP stdio client."""

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from foundry_client import ROOT, infer, load_config
from claude_client import infer_claude


TOOLS = {"openai": "foundry_openai", "claude": "foundry_claude"}


def challenge():
    left = secrets.randbelow(900) + 100
    right = secrets.randbelow(900) + 100
    nonce = secrets.token_hex(8)
    prompt = f"Compute {left} + {right}. Reply with exactly NONCE_{nonce}: followed by the sum. No spaces."
    return prompt, f"NONCE_{nonce}:{left + right}"


async def via_mcp(prompt, model, max_output_tokens=256):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("foundry_mcp.py"))],
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == set(TOOLS.values()), "Unexpected MCP tools."
            response = await session.call_tool(TOOLS[model], {"prompt": prompt, "max_output_tokens": max_output_tokens})
            if response.isError:
                raise RuntimeError(f"MCP call failed: {response.content}")
            if response.structuredContent is not None:
                return response.structuredContent
            return json.loads(response.content[0].text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["direct", "mcp"], required=True)
    parser.add_argument("--model", choices=sorted(TOOLS), default="openai")
    args = parser.parse_args()
    prompt, expected = challenge()
    generate = infer if args.model == "openai" else infer_claude
    result = generate(prompt, 256) if args.transport == "direct" else asyncio.run(via_mcp(prompt, args.model))
    if result["text"].strip() != expected:
        raise RuntimeError(f"Challenge failed: expected {expected!r}, received {result['text']!r}")
    config = load_config()
    name = config["model_name" if args.model == "openai" else "claude_model_name"]
    deployment = config["deployment_name" if args.model == "openai" else "claude_deployment_name"]
    if not result["response_id"] or not (
        result["model"] == deployment or result["model"] == name or result["model"].startswith(name + "-")
    ):
        raise RuntimeError("Missing or unexpected model identity in the real response.")
    evidence = {"test": args.transport, "model": args.model, "passed": True, "prompt": prompt, "expected": expected, "result": result}
    path = ROOT / "evidence" / f"{args.model}-{args.transport}-smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
