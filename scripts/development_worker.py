"""Shell-invoked MCP client: save a bounded proposal, never execute it."""

import argparse
import asyncio
import json
from pathlib import Path

from smoke_test import via_mcp


def proposal_paths(workspace, prompt, output_name):
    workspace = workspace.resolve()
    requests = (workspace / ".foundry" / "requests").resolve()
    proposals = (workspace / ".foundry" / "proposals").resolve()
    source = prompt.resolve()
    if not requests.is_relative_to(workspace) or not proposals.is_relative_to(workspace):
        raise ValueError(".foundry directories must remain inside this workspace.")
    if not source.is_relative_to(requests) or not source.is_file():
        raise ValueError("--prompt must be a file inside this workspace's .foundry/requests/.")
    if Path(output_name).name != output_name or output_name in ("", ".", ".."):
        raise ValueError("--out must be a file name, not a path.")
    target = proposals / output_name
    if target.exists() or target.is_symlink():
        raise FileExistsError("Proposal already exists; choose a fresh --out name.")
    return source, target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("openai", "claude"), required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--out", required=True, help="New file name under .foundry/proposals/")
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    args = parser.parse_args()
    source, target = proposal_paths(Path.cwd(), args.prompt, args.out)
    prompt = source.read_text(encoding="utf-8")
    if not prompt.strip() or len(prompt) > 8000 or not 128 <= args.max_output_tokens <= 2048:
        parser.error("Use a nonempty prompt of at most 8000 characters and 128-2048 output tokens.")
    result = asyncio.run(via_mcp(prompt, args.model, args.max_output_tokens))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(result["text"])
    metadata = {k: v for k, v in result.items() if k != "text"}
    metadata.update(transport="MCP stdio via shell client", proposal=str(target.relative_to(Path.cwd())))
    with (Path.cwd() / ".foundry" / "calls.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(metadata) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
