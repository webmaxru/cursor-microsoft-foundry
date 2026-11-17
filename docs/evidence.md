# Evidence from the live runs

Every file below was produced by the scripts in this repository during the
November 2026 runs. The raw results stay on the test machine. These published
copies come from [`scripts/snapshot_evidence.py`](../scripts/snapshot_evidence.py),
which replaces account-identifying values with placeholders:

| Real value | Replaced with |
| --- | --- |
| Subscription ID | `00000000-0000-0000-0000-000000000000` |
| Resource group | `rg-my-foundry` |
| Foundry resource | `my-foundry-resource` |
| Foundry project | `my-foundry-project` |
| Local home folder | `~` |
| Other deployments in the account | Omitted (only the count is kept) |

Response IDs, request IDs, hashes, token usage, HTTP status codes, timestamps
and model output are unchanged. The files are local records, not
Azure-signed attestations.

## Cursor CLI end to end

| File | What it shows |
| --- | --- |
| [`cursor-mcp-e2e.json`](../evidence-snapshot/cursor-mcp-e2e.json) | **Main proof.** Cursor CLI (`auto` model) called both tools with fresh random tasks. Cursor's answer contains both correct results and both Azure response IDs, and they match new audit records, including request and response SHA-256 hashes. Luna used 40 input and 22 output tokens; Claude Haiku used 53 and 22. |
| [`guide-prompt-output.txt`](../evidence-snapshot/guide-prompt-output.txt) | Verbatim output of the example prompt in [step 3 of the CLI guide](cli.md#3-ask-cursor-to-use-your-foundry-models). Both response IDs appear in the audit log. |
| [`foundry-audit.jsonl`](../evidence-snapshot/foundry-audit.jsonl) | One line per successful Foundry call: time, route, deployment, response ID, Azure request ID, hashes and usage. No prompt, answer or credential. |

## Cursor IDE end to end

| File | What it shows |
| --- | --- |
| [`ide-mcp-e2e.json`](../evidence-snapshot/ide-mcp-e2e.json) | **IDE proof.** In the Cursor IDE 3.30.14 Agent panel (Grok 4.7, Free plan), the Agent called both tools with a fresh challenge from `verify_ide.py prepare`. `verify_ide.py check` matched the displayed results and response IDs with new audit records. Luna response `resp_0005469135d59969016afba15331588193a4abfce9cfd018c0`; Claude Haiku response `msg_011Ch7ZcVhwms1HNAQKsBk9e`. |
| [`ide-transcript.txt`](../evidence-snapshot/ide-transcript.txt) | The Agent's chat copied from the IDE, which the check read. |

## Foundry calls without Cursor

| File | What it shows |
| --- | --- |
| [`openai-direct-smoke.json`](../evidence-snapshot/openai-direct-smoke.json) | GPT-6 Luna answered a random arithmetic task correctly through the OpenAI Responses API with Entra ID. |
| [`claude-direct-smoke.json`](../evidence-snapshot/claude-direct-smoke.json) | Claude Haiku 5.5 did the same through the Anthropic Messages API. |
| [`openai-mcp-smoke.json`](../evidence-snapshot/openai-mcp-smoke.json) | Same check for Luna, through the MCP server and the official MCP client. |
| [`claude-mcp-smoke.json`](../evidence-snapshot/claude-mcp-smoke.json) | Same check for Claude, through the MCP server. |

## API format behavior

| File | What it shows |
| --- | --- |
| [`claude-api-formats.json`](../evidence-snapshot/claude-api-formats.json) | The Claude deployment returned **200** on the OpenAI Responses route and **404 `api_not_supported`** on both Chat Completions routes (`/openai/v1/chat/completions` and `/anthropic/v1/chat/completions`). |
| [`openai-api-routes.json`](../evidence-snapshot/openai-api-routes.json) | The request shapes the IDE key slots can send, against the Luna deployment with Entra ID. Current `/openai/v1/chat/completions`, the same with `reasoning_effort`, legacy `/openai/deployments/{name}/chat/completions` and current `/openai/v1/responses` returned **200**. Chat Completions with a Responses-style `reasoning` object returned **400 `unknown_parameter`**. |
| [`openai-responses-features.json`](../evidence-snapshot/openai-responses-features.json) | Luna on the Responses API: streaming and a full function-tool round trip passed. |
| [`claude-responses-features.json`](../evidence-snapshot/claude-responses-features.json) | Claude on the Responses API: streaming and a function-tool round trip passed. |
| [`claude-anthropic-features.json`](../evidence-snapshot/claude-anthropic-features.json) | Claude on the native Messages API: streaming and a tool-use round trip passed. |

## Cursor routing experiments

| File | What it shows |
| --- | --- |
| [`cursor-routing.json`](../evidence-snapshot/cursor-routing.json) | With `--endpoint` pointed at a local listener, Cursor CLI sent only its own authentication call (`/auth/exchange_user_api_key`), so the flag targets Cursor's service, not a model API. With fake `OPENAI_BASE_URL`, `AZURE_OPENAI_ENDPOINT`, `ANTHROPIC_BASE_URL` and matching key variables set, the `auto` run succeeded and sent nothing to the local listener. |
| [`cursor-routing-initial.json`](../evidence-snapshot/cursor-routing-initial.json) | Earlier attempt of the same probe with an explicit paid model, refused with "Model unavailable on Free". Kept because it records the plan limitation. |
| [`cursor-cli-help.txt`](../evidence-snapshot/cursor-cli-help.txt) | `agent --help` from the tested version, `2026.11.13-eacade1`. |
| [`environment.json`](../evidence-snapshot/environment.json) | Tool versions, the absence of a Cursor API key and why no Cloud Agent run was attempted. |

## Deployments and tests

| File | What it shows |
| --- | --- |
| [`deployment-created.json`](../evidence-snapshot/deployment-created.json) | The Luna deployment created by `Deploy-OpenAIModel.ps1`: DataZoneStandard, capacity 10, 10 requests and 10,000 tokens per minute. |
| [`deployment.json`](../evidence-snapshot/deployment.json) | A later run of the same script found the matching deployment and changed nothing. |
| [`deployment-inventory.json`](../evidence-snapshot/deployment-inventory.json) | Both deployments used: Luna (OpenAI format) and the existing Claude Haiku 5.5 deployment (Anthropic format, version 2, GlobalStandard). |
| [`unit-tests.txt`](../evidence-snapshot/unit-tests.txt) | All eight unit tests passed. |
