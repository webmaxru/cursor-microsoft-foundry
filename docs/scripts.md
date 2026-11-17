# Scripts and configuration reference

All scripts read `config/foundry.json` and use your Azure CLI login. The
everyday scripts and the bridge never use an API key. The few research scripts
marked **(key)** read the Foundry resource key from `FOUNDRY_API_KEY` or from
`az` in memory, and never print or write it. Scripts marked **Live** call
Foundry models and are billed per token. They use very small prompts, so a
full run costs a few hundred tokens.

Run Python scripts with the virtual environment's interpreter, created by
`Setup.ps1`:

```powershell
$py = if ($IsWindows) { './.venv/Scripts/python.exe' } else { './.venv/bin/python' }
& $py scripts/smoke_test.py --transport direct --model openai
```

## Everyday scripts

| Script | What it does | Calls Azure | Writes |
| --- | --- | --- | --- |
| [`scripts/Setup.ps1`](../scripts/Setup.ps1) | Creates `.venv`, installs the pinned packages from `requirements.lock.txt` and writes `demo/.cursor/mcp.json` with absolute paths. `-UpdateLock` reinstalls from `requirements.txt` and refreshes the lock file. | No | `.venv/`, `demo/.cursor/mcp.json` |
| [`scripts/Deploy-OpenAIModel.ps1`](../scripts/Deploy-OpenAIModel.ps1) | Checks that the configured project endpoint and `base_url` match Azure, that the model, version and SKU are available, and that quota is sufficient. Then it creates the OpenAI deployment. Does nothing if a matching deployment exists; stops if one with the same name differs. | Control plane | `evidence/deployment.json`, `evidence/deployment-created.json` |
| [`scripts/Run-Poc.ps1`](../scripts/Run-Poc.ps1) | Runs the four smoke tests, approves the `foundry-models` MCP server in `demo`, lists its tools and runs `verify_cursor.py`. Stops at the first failure. | **Live** | Smoke-test and E2E evidence |
| [`scripts/smoke_test.py`](../scripts/smoke_test.py) | `--transport direct\|mcp --model openai\|claude`. Sends a random arithmetic task with a one-time marker and checks the exact answer. `mcp` starts the MCP server and calls it with the official MCP client. | **Live** | `evidence/<model>-<transport>-smoke.json` |
| [`scripts/verify_cursor.py`](../scripts/verify_cursor.py) | Runs the real Cursor CLI in `demo` and asks it to call both tools with fresh random tasks. Passes only if Cursor's answer and the new audit records agree on results, request and response hashes, and response IDs. | **Live** (and uses Cursor) | `evidence/cursor-mcp-e2e.json` |
| [`scripts/verify_ide.py`](../scripts/verify_ide.py) | The same proof for the Cursor IDE, in two phases. `prepare` saves a fresh challenge and prints the prompt to paste into the Agent. `check <transcript>` correlates the copied chat with the new audit records. See the [IDE guide](ide.md#prove-it-with-a-fresh-challenge). | **Live** (through the IDE) | `evidence/ide-challenge.json`, `evidence/ide-mcp-e2e.json` |

## The bridge

| File | Role |
| --- | --- |
| [`scripts/foundry_mcp.py`](../scripts/foundry_mcp.py) | The stdio MCP server Cursor starts. Exposes `foundry_openai` and `foundry_claude`. Each takes `prompt` (1 to 8,000 characters) and `max_output_tokens` (128 to 2,048, default 512) and returns the text, deployment, model, response ID and token usage. |
| [`scripts/foundry_client.py`](../scripts/foundry_client.py) | Loads and validates the config, calls the OpenAI deployment through the Responses API (`/openai/v1/`) with `store: false`, and appends metadata to `evidence/foundry-audit.jsonl`. |
| [`scripts/claude_client.py`](../scripts/claude_client.py) | Calls the Claude deployment through the native Anthropic Messages API (`/anthropic`) using the official `AnthropicFoundry` client. |

Both clients use `AzureCliCredential` with the token scope
`https://ai.azure.com/.default`. Neither retries silently or falls back to
another model. The audit log records metadata, hashes and token usage, never
the prompt, the answer or a credential.

## Research and evidence scripts

These scripts reproduce specific findings. You don't need them to use the
bridge.

| Script | What it checks | Calls Azure | Writes |
| --- | --- | --- | --- |
| [`scripts/verify_model_features.py`](../scripts/verify_model_features.py) | `--api responses --model openai\|claude` or `--api anthropic --model claude`. Checks streaming and a full function-tool round trip on that API. | **Live** | `evidence/<model>-<api>-features.json` |
| [`scripts/probe_claude_formats.py`](../scripts/probe_claude_formats.py) | Sends one request to the Claude deployment through the Responses API and both Chat Completions routes and records the HTTP status of each. | **Live** | `evidence/claude-api-formats.json` |
| [`scripts/probe_openai_routes.py`](../scripts/probe_openai_routes.py) | Sends the request shapes that Cursor's IDE key slots can produce to the OpenAI deployment: current and legacy Chat Completions, Chat Completions with `reasoning_effort` and with a Responses-style `reasoning` object, and Responses. Uses Entra ID, never an API key. | **Live** | `evidence/openai-api-routes.json` |
| [`scripts/probe_cursor_routing.py`](../scripts/probe_cursor_routing.py) | Black-box test of Cursor CLI: points `--endpoint` at a local listener that discards request bodies, then runs Cursor with fake OpenAI and Azure provider variables to see whether they change routing. | No (uses Cursor) | `evidence/cursor-routing.json` |
| [`scripts/probe_fullswitch_routes.py`](../scripts/probe_fullswitch_routes.py) | Sends the request shapes an IDE key slot would use to your deployments with a **resource API key**: Bearer and `api-key` headers, a wrong key, legacy and current token limits, tools with and without `reasoning_effort`, streaming, and Claude on Chat Completions, Responses and Messages. Prints 12 pass or fail checks. The key is read from `FOUNDRY_API_KEY` or `az` in memory and never printed or written. Needs key access on the resource ([setup](setup.md#optional-api-key-access-for-the-ide-full-switch)). | **Live** (key) | `evidence/fullswitch-key-routes.json` |
| [`scripts/probe_cli_fullswitch.py`](../scripts/probe_cli_fullswitch.py) | Checks whether the Cursor CLI can use another provider: `--endpoint` at a local listener that records method, path and header names only, `--model` with a name outside Cursor's catalog, and a search of `agent --help` for provider commands. Sends no Foundry credential. Your Cursor login token does reach the local listener, which discards it. | No (uses Cursor) | `evidence/cli-fullswitch.json` |
| [`scripts/litellm_gateway.py`](../scripts/litellm_gateway.py) | Runs a [LiteLLM](https://docs.litellm.ai/) gateway with two aliases: `foundry-luna` (the OpenAI deployment, always through the Responses API) and `foundry-haiku` (the Claude deployment, through the Anthropic route). `render` prints the config, which holds no secret. `serve --litellm <path> [--host] [--port]` runs a pip-installed LiteLLM on 127.0.0.1:4000. `register --url <gateway>` adds the aliases to a running gateway that keeps models in its database, such as LiteLLM's Docker quickstart. Needs `LITELLM_MASTER_KEY` (starting with `sk-`, at least 24 characters). See [Gateway route](ide.md#gateway-route-refused-by-cursor). | No (the gateway does, when called) | Nothing |
| [`scripts/probe_litellm_gateway.py`](../scripts/probe_litellm_gateway.py) | Sends 15 Cursor-shaped cases through a LiteLLM gateway: the model list, then for each alias plain text, a tool call and a tool-result round trip on LiteLLM's `/cursor` route with both Chat Completions and Responses-shaped bodies (streamed), and the Azure slot's deployment route with an `api-key` header; then a `-thinking-high` model-name suffix and a wrong gateway key. Without `--base-url` it starts its own LiteLLM (`--litellm <path>`) with a throwaway key; with `--base-url` it tests a running gateway, using `LITELLM_API_KEY` or `LITELLM_MASTER_KEY`. `--version` records the LiteLLM version, `--out` names the evidence file. LiteLLM isn't a dependency of this repository. | **Live** (key) | `evidence/litellm-gateway.json` or the `--out` name |
| [`scripts/capture_proxy.py`](../scripts/capture_proxy.py) | A request-capture proxy for testing what Cursor sends to a custom base URL. It checks a throwaway shared secret and records the request shape, never the prompt text, so you never paste a real Foundry key into Cursor. Three modes: by default it swaps in your Entra token and forwards the body unchanged to Foundry; `--forward-to <gateway>` fronts a local gateway such as LiteLLM and exposes only model routes; `--stub` answers model routes with a canned reply and contacts nothing. Bind it to localhost behind a tunnel you delete afterwards. Its logs can hold the secret and, with `--save-bodies`, request bodies: don't publish them. See [Verify what Cursor sends](ide.md#verify-what-cursor-sends). | **Live** (default and `--forward-to`) | `evidence/proxy-capture.jsonl` or `--log` |
| [`scripts/check_foundry_usage.py`](../scripts/check_foundry_usage.py) | Reads Azure Monitor request metrics for one deployment, per minute, status code and API, to prove a client really reached it. `--minutes` (default 30), `--deployment`, `--metric ModelRequests\|AzureOpenAIRequests`, `--out`. Needs Monitoring Reader on the resource. Metrics appear after 1 to 3 minutes, and failed key authentication (401) is not counted. See [Check it with your own key](ide.md#check-it-with-your-own-key). | Control plane (metrics) | `--out` file, if given |
| [`scripts/snapshot_evidence.py`](../scripts/snapshot_evidence.py) | Copies `evidence/` to `evidence-snapshot/`, replacing the subscription, resource group, resource and project names, local paths and unrelated deployment names with the values from `config/foundry.example.json`. Fails if a private value remains. | No | `evidence-snapshot/` |
| [`scripts/cursor_runtime.py`](../scripts/cursor_runtime.py) | Helper that starts Cursor CLI from Python. On Windows it runs the installed version's Node entry point directly; elsewhere it runs `agent`. | No | Nothing |

Run live scripts one at a time. The example deployment has a small rate
limit.

## Tests

```powershell
& $py -m unittest discover -s tests -v
```

[`tests/test_clients.py`](../tests/test_clients.py) has thirteen offline tests.
They check input limits, rejection of non-Azure destinations and credentials
in URLs, the missing-config message, that incomplete or empty responses fail,
that audit records hold no prompt or answer, that provider errors are redacted
and not retried, that invalid MCP arguments never reach Azure, and that a
Cursor transcript counts as proof only when it shows response IDs whose audit
records match the expected answers for both deployments. The other five check
that the capture proxy records request shape but not prompt text, that it
summarizes errors and stream usage, that a wrong shared secret is rejected
before any Azure token is requested, that `--stub` mode answers locally
without an Azure token or any forwarding, and that the CLI probe reads
provider commands only from the help text's commands section. The tests don't call
Azure or Cursor.

## Configuration files

| File | Purpose |
| --- | --- |
| [`config/foundry.example.json`](../config/foundry.example.json) | Template. Copy it to `config/foundry.json` (gitignored) and fill in your values. The [setup guide](setup.md#2-get-the-code-and-create-your-configuration) explains each key. |
| `demo/.cursor/mcp.json` | Written by `Setup.ps1` (gitignored, because it holds absolute local paths). The Cursor CLI and IDE both read it. [`mcp.example.json`](../demo/.cursor/mcp.example.json) shows the shape. |
| [`demo/.cursor/cli.json`](../demo/.cursor/cli.json) | Cursor CLI permissions for the demo: allows only the two Foundry tools and denies shell, file and web tools. |
| [`config/cloud-agent.request.example.json`](../config/cloud-agent.request.example.json) | Shape of a Cursor Cloud Agents API request that adds a remote HTTP MCP server. **Blueprint only**; the host name and token are placeholders. |
| [`config/litellm.config.example.yaml`](../config/litellm.config.example.yaml) | Example LiteLLM config with the `foundry-luna` and `foundry-haiku` aliases, the same as `litellm_gateway.py render` prints. Passed 15 of 15 cases with LiteLLM 1.108.4 (pip) and 1.109.1 (Docker). **Cursor 3.30.14 sent it no request** on a Premium plan. The resource name is a placeholder; keys come from environment variables. |
| [`requirements.txt`](../requirements.txt), [`requirements.lock.txt`](../requirements.lock.txt) | Direct dependencies and the exact tested versions. |

The `evidence/` folder holds raw local results and is gitignored. The
published, redacted copy is [`evidence-snapshot/`](evidence.md).
