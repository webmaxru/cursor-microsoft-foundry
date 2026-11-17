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
| [`ide-mcp-e2e.json`](../evidence-snapshot/ide-mcp-e2e.json) | **IDE proof.** In the Cursor IDE 3.30.14 Agent panel (Grok 4.7, on the Free plan before the Premium round), the Agent called both tools with a fresh challenge from `verify_ide.py prepare`. `verify_ide.py check` matched the displayed results and response IDs with new audit records. Luna response `resp_0005469135d59969016afba15331588193a4abfce9cfd018c0`; Claude Haiku response `msg_011Ch7ZcVhwms1HNAQKsBk9e`. |
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
| [`cursor-routing.json`](../evidence-snapshot/cursor-routing.json) | The first routing probe. With `--endpoint` pointed at a local listener and an **invalid** API key, Cursor CLI sent only its own authentication call (`/auth/exchange_user_api_key`), so it never got past sign-in. With fake `OPENAI_BASE_URL`, `AZURE_OPENAI_ENDPOINT`, `ANTHROPIC_BASE_URL` and matching key variables set, the `auto` run succeeded and sent nothing to the local listener. [`cli-fullswitch.json`](../evidence-snapshot/cli-fullswitch.json) repeats the endpoint test with a real login. |
| [`cursor-routing-initial.json`](../evidence-snapshot/cursor-routing-initial.json) | Earlier attempt of the same probe with an explicit paid model, refused with "Model unavailable on Free". Kept because it records the plan limitation. |
| [`cursor-cli-help.txt`](../evidence-snapshot/cursor-cli-help.txt) | `agent --help` from the tested version, `2026.11.13-eacade1`. |
| [`environment.json`](../evidence-snapshot/environment.json) | Tool versions, the absence of a Cursor API key and why no Cloud Agent run was attempted. |

## Full-switch tests

| File | What it shows |
| --- | --- |
| [`fullswitch-key-routes.json`](../evidence-snapshot/fullswitch-key-routes.json) | Twelve checks of a resource API key against the Foundry routes an IDE key slot would use, all as expected. Luna on Chat Completions: **200** with a Bearer header and with the `api-key` header, **401** with a wrong key, **400** for legacy `max_tokens`, **400** for tools without `reasoning_effort: "none"`, **200** with it, and **200** for streaming. Claude: **404 `api_not_supported`** on Chat Completions, **200** on Responses and on Anthropic Messages. This shows what Foundry accepts. It doesn't show what Cursor sends. |
| [`key-route-probe.json`](../evidence-snapshot/key-route-probe.json) | One request per route to both deployments with a resource API key and the `api-key` header, from [`probe_key_routes.py`](../scripts/probe_key_routes.py). GPT: **200** on legacy Chat Completions with `max_completion_tokens`, on current Chat Completions and on Responses; **400** with `max_tokens`. Claude: **404 `api_not_supported`** on legacy and current Chat Completions, **200** on Responses and on Anthropic Messages with `x-api-key`, **401** on Messages with `api-key`. This is the basis for the [proxy answer](ide.md#can-a-proxy-bring-claude-to-the-ide). It shows what Foundry accepts, not what Cursor sends. |
| [`cli-fullswitch.json`](../evidence-snapshot/cli-fullswitch.json) | With a real Cursor login, `--endpoint` made the CLI call only Cursor's own `/aiserver.v1.*` services (`GetMe`, `GetServerConfig` and others, all `application/proto`), with an `authorization` header, and exit with `[unimplemented]`. `--model` rejected a name outside Cursor's catalog. `agent --help` lists `bedrock` as the only provider command. Only header names were recorded. |
| [`litellm-gateway.json`](../evidence-snapshot/litellm-gateway.json) | LiteLLM 1.108.4 (pip), started by [`litellm_gateway.py`](../scripts/litellm_gateway.py)'s config with the `foundry-luna` and `foundry-haiku` aliases, passed **15 of 15** Cursor-shaped cases: the model list; for each alias text, a tool call and a tool-result round trip on the `/cursor` route with Chat Completions and Responses-shaped bodies, and the Azure slot's deployment route with an `api-key` header; a `-thinking-high` suffix; and a refused wrong key. This shows the gateway works. I haven't re-run it in Cursor since the [correction](ide.md#correction-what-went-wrong-in-the-first-tests); the same position behind the OpenAI override was proven with the translating proxy (`ide-proxy-cursor-requests.json` below). |
| [`litellm-gateway-docker.json`](../evidence-snapshot/litellm-gateway-docker.json) | The same 15 cases, all as expected, against LiteLLM's Docker quickstart (1.109.1) with the aliases added by `litellm_gateway.py register`. |

## Premium round

| File | What it shows |
| --- | --- |
| [`premium-round.json`](../evidence-snapshot/premium-round.json) | **Every surface on an individual Premium plan** (Cursor IDE 3.30.14, CLI 2026.11.13-eacade1), with the gateway or a stub behind a temporary public tunnel. **The CLI and Cloud results stand:** the CLI said "Cannot use this model: foundry-luna" and its only provider command, `bedrock`, is for AWS; Cloud said "Model Not Available". **The IDE cases are withdrawn.** The UI automation that filled the IDE's settings changed the screen without saving them, so the override, gateway and dummy-key cases ran with settings Cursor never stored (see the [correction](ide.md#correction-what-went-wrong-in-the-first-tests)). Their messages are kept for the record. Also records my own reachability checks, which aren't Cursor requests. |
| [`usage-check-selftest.json`](../evidence-snapshot/usage-check-selftest.json) | A self-test of [`check_foundry_usage.py`](../scripts/check_foundry_usage.py): one direct request to the Luna deployment appeared in Azure Monitor as one `200` in `ModelRequests`. The real-key round below used the same script. |

## Real-key round and the Claude proxy

| File | What it shows |
| --- | --- |
| [`ide-realkey-round.json`](../evidence-snapshot/ide-realkey-round.json) | **The IDE with a real key on Premium**, test by test, each marked `valid` or not. **The Azure OpenAI slot works** with settings Cursor saved: on a classic Azure OpenAI resource, Agent turns answered with 200s (K, L with a file-tool call, N), a missing deployment gave "Provider Error" (M2), and a 10K TPM deployment gave 429s shown as "User Provided API Key Rate Limit Exceeded" (I, J). On the Foundry resource, `gpt-4.1` answered with text and a file-tool call (R1, R2), and GPT-6 Luna got Foundry's 400 for tools with reasoning (R3). An empty saved Base URL reproduces the earlier "Network Error" exactly (O). Through the translating proxy behind a tunnel, the Azure slot reached Claude (P) and Luna (Q), and the OpenAI override reached both (S1 to S3). S4 records the override's side effects: Cursor's own GPT models go to the proxy, Composer is blocked, Claude stays on Cursor. **Tests A to H, F and F2 are marked `valid: false`**: the UI automation changed the screen without saving the settings. The `automation_defect` entry explains how test M1 found that and test O confirmed it. Also records the error signatures, the enable dialogs, the controls and the related forum threads. |
| [`ide-classic-slot-usage.json`](../evidence-snapshot/ide-classic-slot-usage.json) | Azure Monitor `ModelRequests` per minute, deployment and status on the classic resource during tests I to N, each row attributed to a test or to my direct controls: the two 429s of I and J, the 200s of K, L and N, and M1's request landing on the old deployment. |
| [`ide-foundry-direct-usage.json`](../evidence-snapshot/ide-foundry-direct-usage.json) | `ModelRequests` on the Foundry `gpt-4.1` deployment during R1 and R2: three streamed 200s on `chatcompletions_create`. |
| [`ide-foundry-luna-usage.json`](../evidence-snapshot/ide-foundry-luna-usage.json) | `ModelRequests` on the Luna deployment during R3: one streamed 400 on `chatcompletions_create`. |
| [`ide-proxy-cursor-requests.json`](../evidence-snapshot/ide-proxy-cursor-requests.json) | The proxy's log of the 14 requests Cursor sent it in tests P, Q and S, all with `User-Agent: Cursor/1.0`: path, `api-version`, header style, body keys (including `thinking`, `output_config` and `fallbacks`), tool count, upstream API, status and token usage. Request ids, hosts and the tunnel address are dropped. Also lists the S4 models that never reached the proxy. |
| [`ide-proxy-claude-usage.json`](../evidence-snapshot/ide-proxy-claude-usage.json), [`ide-proxy-luna-usage.json`](../evidence-snapshot/ide-proxy-luna-usage.json) | `ModelRequests` during P and Q: Claude 200s on `POST /anthropic/v1/messages`; Luna 200s on `create-response`, next to the 400s and Chat Completions 200s from my direct checks before Responses mode was added. |
| [`ide-override-claude-usage.json`](../evidence-snapshot/ide-override-claude-usage.json), [`ide-override-luna-usage.json`](../evidence-snapshot/ide-override-luna-usage.json) | `ModelRequests` during S: three Claude 200s on Messages and two Luna 200s on `create-response`. |
| [`ide-realkey-diag-rows.json`](../evidence-snapshot/ide-realkey-diag-rows.json) | Every row in a temporary diagnostic log on the Foundry resource during the withdrawn tests A to H: category, operation, status, duration and time only. All are my direct control requests. Kept for the record. |
| [`ide-realkey-cursor-log-summary.json`](../evidence-snapshot/ide-realkey-cursor-log-summary.json) | Cursor's own agent log for each turn, reduced by [`summarize_cursor_agent_log.py`](../scripts/summarize_cursor_agent_log.py) to model, routing, backend error codes, retry decisions and final error, without request or conversation ids. Own-key turns are `byok-connect-routed`. An unusable Base URL ends in `resource_exhausted` after three retries (A to H and O), a missing deployment in `not_found`, a rate limit in `invalid_argument`. |
| [`claude-proxy-probe.json`](../evidence-snapshot/claude-proxy-probe.json) | [`probe_claude_proxy.py`](../scripts/probe_claude_proxy.py) against [`foundry_claude_proxy.py`](../scripts/foundry_claude_proxy.py): **13 of 13** cases. In Messages mode: text, streaming with usage, a parallel two-tool round trip (plain and streamed), the Azure slot's route, GPT passthrough, the model list and a refused wrong secret. In Responses mode: the first five again. The proxy log held no prompt text. Cursor's own use of the proxy is in `ide-proxy-cursor-requests.json` above. |

## Deployments and tests

The [development study](development.md) distinguishes new native-dispatch
failures from the earlier arithmetic proofs.
[`development-study.json`](../evidence-snapshot/development-study.json) contains
the completed three-stage comparison: eight successful shell-MCP calls, separate
Cursor/Foundry counters, acceptance outcomes and artifact hashes.
[`development-pilot.json`](../evidence-snapshot/development-pilot.json) records
excluded setup attempts and three native-discovery diagnostics without
publishing session IDs, local paths or complete conversations.
[`development-followup.json`](../evidence-snapshot/development-followup.json)
records additional validation and encoding gaps found after the timed study;
the generated files were not silently repaired.

| File | What it shows |
| --- | --- |
| [`deployment-created.json`](../evidence-snapshot/deployment-created.json) | The Luna deployment created by `Deploy-OpenAIModel.ps1`: DataZoneStandard, capacity 10, 10 requests and 10,000 tokens per minute. |
| [`deployment.json`](../evidence-snapshot/deployment.json) | A later run of the same script found the matching deployment and changed nothing. |
| [`deployment-inventory.json`](../evidence-snapshot/deployment-inventory.json) | Both deployments used: Luna (OpenAI format) and the existing Claude Haiku 5.5 deployment (Anthropic format, version 2, GlobalStandard). |
| [`unit-tests.txt`](../evidence-snapshot/unit-tests.txt) | All 25 offline tests passed, including the key-route probe guard, Claude tool and streaming translation in the proxy, Responses mode for OpenAI reasoning deployments, the Cursor log summarizer, transport verification, interrupted-run accounting and proposal-path guards for the development study. |
