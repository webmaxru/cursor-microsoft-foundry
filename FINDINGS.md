# Investigation: Cursor inference through Microsoft Foundry

## Executive conclusion

**Cursor has no full switch to Microsoft Foundry like Claude Code's.** Claude
Code sets `CLAUDE_CODE_USE_FOUNDRY=1` and calls Foundry directly from your
machine [A3]. Cursor sends model calls from its own servers, and its three
surfaces differ in how much of that you can redirect:

**Development-study update:** the earlier native MCP arithmetic proof did not
reproduce in new CLI coding sessions: tool listing worked, but runtime dispatch
could not find the server. The [separate practical study](docs/development.md)
reports that failure, excludes an agent's direct-SDK substitution, and evaluates
an explicitly labeled shell-invoked MCP client. Connectivity evidence alone
is not a claim of dependable development integration.

The completed shell-MCP comparison used eight successful Foundry responses
(13,147 input / 8,011 output tokens). Cursor still reported 336,776 input and
70,238 output tokens, versus 345,859 / 46,079 in the control. Elapsed time rose
from 13.0 to 24.9 minutes. Both workflows passed the planned three-stage
acceptance checks; additional probes found malformed-CSV acceptance,
contract drift and a Windows encoding dependency in the delegated artifact.
The [study](docs/development.md) publishes the unchanged files, limits and
separate usage counters rather than claiming production readiness or savings.

| Surface | Full switch to Foundry? | Fallback: Foundry models as MCP tools | Details |
| --- | --- | --- | --- |
| **Cursor IDE** | **Yes, for chat and the Agent.** Your own key in the Azure OpenAI slot, a paid plan; requests pass through Cursor's servers. **Verified with the real key on Premium**: `gpt-4.1` on a Foundry resource and on a classic Azure OpenAI resource answered with text and tool calls, every request `200` in Azure. GPT-6 Luna directly: `400` (tools need the Responses API). Claude has no direct route. A translating proxy built here, behind a public tunnel, ran the Agent on Claude Haiku 5.5 and GPT-6 Luna from the Azure slot and the OpenAI override, 14 requests from Cursor. Tab, Auto and Composer stay on Cursor; matches staff and users [F31, F8]. | **Verified** with both models in IDE 3.30.14 | [IDE](docs/ide.md) |
| **Cursor CLI** | **No.** `--endpoint` is Cursor's own service, `--model` accepts only Cursor's catalog, and provider environment variables are ignored. On Premium a custom model was refused: "Cannot use this model". | Earlier arithmetic proof verified; new native-dispatch sessions failed. See the [development study](docs/development.md) | [CLI](docs/cli.md) |
| **Cloud Agents** | **No, by design.** Cursor staff say own keys are attached by the IDE client, which headless runs don't have. On Premium a custom model gave "Model Not Available". | Possible through a remote HTTP MCP service: blueprint, not run | [Cloud](docs/cloud.md) |

**No Cursor request reached the LiteLLM gateway from the CLI or Cloud Agents
during the Premium round**, although the same gateway passed 15 of 15
Cursor-shaped cases for both models when called directly. **In the real-key
round the IDE reached Foundry directly and through the translating proxy.**

> **Correction, 17 November 2026.** Earlier versions said the IDE's Azure
> slot failed with a real key and that the IDE refused a gateway behind the
> OpenAI override. Those tests were filled in by UI automation that changed
> the screen but never saved Cursor's settings. With saved settings both
> routes work ([correction](docs/ide.md#correction-what-went-wrong-in-the-first-tests)).

The cross-surface comparison, community evidence and the research gaps are on
[Full switch](docs/fullswitch.md). Four separate questions sit behind the table:

1. **Can the model be called through Foundry?** Yes: both a GPT-6 Luna
   deployment and a Claude Haiku 5.5 deployment were invoked successfully with
   Microsoft Entra authentication, and with a resource API key.
2. **Can a client speak the model's API?** Yes, but the API route and
   model-specific parameters matter. Haiku accepts native Anthropic Messages.
   The same deployment also accepted OpenAI Responses, streaming, and function
   tools in live tests; it did not accept Chat Completions. Luna accepts both
   Chat Completions and Responses, but rejects a Responses-style `reasoning`
   object on Chat Completions, which matches a known Cursor IDE error, and
   rejects function tools on Chat Completions unless `reasoning_effort` is
   `none`.
3. **Will Cursor use that endpoint as its main inference provider?** Only in
   the IDE, through the Azure OpenAI slot or the OpenAI base-URL override,
   and both worked with a real key. Directly, the Azure slot suits
   non-reasoning OpenAI deployments; Luna and Claude need a translating proxy.
   The CLI and Cloud Agents have no setting and refused custom models. API
   compatibility alone does not create a routing setting that Cursor doesn't
   expose.
4. **If a switch exists, what does it cost you?** Privacy (traffic goes
   through Cursor's servers and zero data retention doesn't apply), coverage
   (chat and Agent only, one global override), reliability and a paid plan.
   The [IDE page](docs/ide.md#all-the-disadvantages) lists all of them.

Where no switch exists (the CLI and Cloud Agents), the working solution in
this repository is **Cursor orchestration with Foundry inference delegated to
two MCP tools**, verified in both the CLI and the IDE. It is a fallback, not a
claim that all Cursor inference, billing, or data processing has moved into
Azure.

Source keys such as [C1] and [M1] refer to [SOURCES.md](SOURCES.md).

## 1. Scope and evidence quality

All experiments used one Foundry resource (Sweden Central) and one Foundry
project resolved through Azure Resource Manager, plus, for the IDE's
real-key round, a classic Azure OpenAI resource in the same resource group:

`https://<resource>.services.ai.azure.com/api/projects/<project>`

Published evidence is in [`evidence-snapshot/`](evidence-snapshot/). It is
generated by `scripts/snapshot_evidence.py`, which replaces the subscription
ID, resource group, Foundry resource and project names, local paths and
unrelated deployment names with placeholders such as `my-foundry-resource`.
Response IDs, hashes, token usage, HTTP statuses and model behavior are kept.
All model creation and inference used the selected project's parent account;
no other Azure resource was modified.

The installed Cursor CLI (2026.11.13-eacade1) and Cursor IDE (3.30.14) were
inspected and executed, not inferred from documentation, first on the Free
plan and again on an individual Premium plan. IDE settings were inspected
through the UI and captured as screenshots. The Premium round used dummy keys
and LiteLLM gateway keys that were revoked afterwards. For the real-key round
the key owner typed or pasted the resource keys into Cursor, and from test M2
on every value was read back from Cursor's saved settings, not the screen. A
temporary diagnostic-log sink was deleted afterwards. All model creation and
inference used the selected project's parent account or the classic resource
created for the IDE round. Azure control-plane metadata, HTTP results, SDK response IDs,
token usage, and fresh arithmetic challenges were captured locally. Sources
are distinguished as official documentation, staff forum responses, community
reports, or observed behavior. A forum feature request is not a release note.

This is a functional integration PoC, not a penetration test, compliance
certification, throughput benchmark, or full production agent evaluation.
No confidential repository was supplied to Cursor; only the synthetic `demo`
workspace was used.

## 2. Results by surface

Each surface has its own page with setup steps and full detail. This section
summarizes the evidence.

### Cursor CLI

- **The MCP bridge works.** `verify_cursor.py` asked the installed CLI to call
  both tools with fresh random challenges and passed only after matching the
  answers, request and response hashes, and Azure response IDs against new
  local audit records
  ([`cursor-mcp-e2e.json`](evidence-snapshot/cursor-mcp-e2e.json)).
- **`--endpoint` is not an inference base URL.** With an invalid key, the
  CLI's first request to a loopback listener was `POST
  /auth/exchange_user_api_key`, a Cursor authentication exchange
  ([`cursor-routing.json`](evidence-snapshot/cursor-routing.json)). With a real
  login it called Cursor's own protobuf services (`/aiserver.v1.DashboardService/GetMe`,
  `ServerConfigService/GetServerConfig` and three more), sent an
  `authorization` header with the Cursor token, and ended with
  `[unimplemented]`. It never reached an inference call
  ([`cli-fullswitch.json`](evidence-snapshot/cli-fullswitch.json)).
- **`--model` accepts only Cursor's catalog.** A name outside it is refused
  ("Cannot use this model ... Available models: auto, ...").
- **Provider environment variables are ignored.** With `OPENAI_BASE_URL`,
  `OPENAI_API_BASE`, `AZURE_OPENAI_ENDPOINT` and `ANTHROPIC_BASE_URL` pointed
  at the listener, an Auto run answered and the listener saw zero requests.
- **Bedrock commands exist; Azure ones don't.** The CLI has `bedrock`
  subcommands, so "no provider keys of any kind" would be too broad. Bedrock
  is not evidence of Azure support. Staff said in November 2026 that the CLI
  doesn't support provider API keys. [C1, C2, C3, C9, F4, F5, F25, O1]
- **Premium changes nothing.** `agent models` lists about 300 Cursor-hosted
  models and no custom ones. A custom model served by a working LiteLLM
  gateway was refused ("Cannot use this model: foundry-luna") and the gateway
  logged no request. `bedrock` takes AWS credentials only, and `agent worker`
  moves tool execution, not inference [C8]
  ([`premium-round.json`](evidence-snapshot/premium-round.json)).
- **A community CLI bridge exists, with incomplete plumbing.** Its source
  impersonates Cursor's API host with a local certificate and forwards to a
  local port nothing in the repository serves; the provider URL and key are
  never passed on. Read, not run [G1].

Details: [Cursor CLI](docs/cli.md).

### Cursor IDE

- **The same MCP bridge works.** The IDE reads the same `.cursor/mcp.json`.
  The project server started turned off and had to be turned on in
  **Customize > MCPs**. `verify_ide.py` checked a pasted Agent transcript
  against new audit records the same way the CLI check does
  ([`ide-mcp-e2e.json`](evidence-snapshot/ide-mcp-e2e.json)). The Agent
  model was Grok 4.7; the run was on the Free plan, where it was the only
  model allowed.
- **The IDE has provider key slots.** Cursor Settings > Models > API Keys
  offers OpenAI (with an **Override OpenAI Base URL** toggle), Anthropic
  (no base URL), **Azure OpenAI** (base URL, deployment name and key) and
  AWS Bedrock. Cursor staff say Foundry OpenAI deployments work through the
  Azure slot and that there is no dedicated Foundry integration [F8, C11].
  Microsoft's own Databricks guide uses the OpenAI key plus override pattern
  with a custom model [M9].
- **Foundry accepts what those slots would send, with caveats.** With a
  resource API key, Luna answered Chat Completions with Bearer and `api-key`
  headers, but rejected legacy `max_tokens`, and rejected function tools
  unless `reasoning_effort` was `none`. Claude returned 404 on Chat
  Completions. Twelve of twelve checks matched expectations
  ([`fullswitch-key-routes.json`](evidence-snapshot/fullswitch-key-routes.json)).
- **Free plan: blocked at the picker.** The chat model picker was locked
  ("More models are only available on paid plans"), so nothing could be sent.
- **Premium: the plan gate still applies to built-in models.** A built-in
  model outside the plan's weekly usage is refused ("not included in your
  weekly usage") whatever keys are set.
- **Real key, Azure slot: it works.** The key owner typed or pasted the keys;
  from test M2 on, every value was read back from Cursor's saved settings
  before the test. On a classic Azure OpenAI resource with a `gpt-4.1`
  deployment, the Agent answered and used its Read tool, and Azure Monitor
  recorded `200` for every request (`chatcompletions_create`, streaming). On
  the Foundry resource, a `gpt-4.1` deployment did the same: text, then a
  "Read README.md L1-11" card, three `200`s. A deployment at 10K tokens per
  minute failed with "User Provided API Key Rate Limit Exceeded" and a logged
  `429`; Cursor's first-turn prompts are about 14,000 to 25,000 tokens. GPT-6
  Luna gave Foundry's own `400`: "Function tools with reasoning_effort are not
  supported ... use /v1/responses or set reasoning_effort to 'none'". The
  model picked in the Agent doesn't route; the saved deployment does
  ([`ide-realkey-round.json`](evidence-snapshot/ide-realkey-round.json),
  [`ide-classic-slot-usage.json`](evidence-snapshot/ide-classic-slot-usage.json),
  [`ide-foundry-direct-usage.json`](evidence-snapshot/ide-foundry-direct-usage.json)).
- **Correction: the first real-key tests were invalid.** Tests A to H (the
  Azure slot, "Network Error" after about 19 seconds, nothing at Foundry) and
  F and F2 (the OpenAI override, "Invalid API key. Unauthorized User API
  key") were filled in by computer-use automation that changed the settings
  screen without saving Cursor's settings. Test M1 exposed it: a deployment
  name changed the same way still produced a `200` on the old deployment.
  Test O, with the Base URL emptied by hand and saved, reproduced the A to H
  signature exactly. The Premium round's IDE override, gateway and dummy-key
  cases used the same automation and are withdrawn as well. Withdrawn: "the
  slot failed with a real key", "non-Azure hosts receive nothing" and "Cursor
  refuses the OpenAI override or a gateway behind it"
  ([correction](docs/ide.md#correction-what-went-wrong-in-the-first-tests)).
- **Cursor's errors have signatures.** An unusable Base URL gives "Network
  Error" after about 20 seconds and `resource_exhausted` four times in
  Cursor's log; a missing deployment gives "Provider Error ... finding the
  resource" (`not_found`); a low rate limit gives "User Provided API Key Rate
  Limit Exceeded"; a Foundry `400` is shown with Foundry's JSON. A forum user
  saw "Network Error" for a misspelled Base URL [F34]
  ([`ide-realkey-cursor-log-summary.json`](evidence-snapshot/ide-realkey-cursor-log-summary.json)).
- **Turning on a key has side effects.** Staff replies describe the key
  toggles and the OpenAI override as affecting most non-Cursor models, and
  empty Azure fields breaking every model. Users report that managed
  OpenAI-family models are routed through the override and that the Anthropic
  key stops working while the override is set [F11, F12, F17, F18, F26, F27].
  Observed with the override on: a built-in GPT model went to the override
  and got `404`, Composer gave "This model does not support custom API keys",
  and Claude Opus stayed on Cursor.
- **Foundry Claude can't be the IDE chat model directly.** The Anthropic slot
  has no base URL and the Azure slot speaks Chat Completions [F1, F2, F3].
  Foundry returns 404 to Claude on both Chat Completions routes
  ([`key-route-probe.json`](evidence-snapshot/key-route-probe.json)). Cursor
  also rejects a custom model named `claude-haiku-5-5` ("already available as
  Claude Haiku 5.5"), so a proxy must serve an alias.
- **A translating proxy brings Claude and Luna to the IDE.**
  [`scripts/foundry_claude_proxy.py`](scripts/foundry_claude_proxy.py) turns
  Chat Completions into Claude's Messages API, or into the Responses API for
  Claude or OpenAI deployments (`--openai-api responses`), and back, including
  streaming, usage and tool round trips. It accepts the Azure slot's route and
  `api-key` header and the override's Bearer token, and calls Foundry with a
  key or Entra ID. It passed 13 of 13 cases called directly
  ([`claude-proxy-probe.json`](evidence-snapshot/claude-proxy-probe.json)).
  Behind a public tunnel, Cursor's backend sent it 14 requests: through the
  Azure slot the Agent ran on Claude Haiku 5.5 (3 requests) and GPT-6 Luna
  (4), and through the OpenAI override with custom models `foundry-haiku` and
  `foundry-luna` (5); each was answered `200` by Foundry. The two other
  requests were built-in model names the proxy doesn't serve, answered `404`
  ([`ide-proxy-cursor-requests.json`](evidence-snapshot/ide-proxy-cursor-requests.json)).
  See
  [Can a proxy bring Claude to the IDE?](docs/ide.md#can-a-proxy-bring-claude-to-the-ide).
- **A LiteLLM gateway wasn't re-run in Cursor.** It passes 15 of 15
  Cursor-shaped cases directly, and LiteLLM documents it on Cursor 3.17.21
  [L2]; the translating proxy shows the override reaching a public gateway
  ([`litellm-gateway-docker.json`](evidence-snapshot/litellm-gateway-docker.json)).

Details: [Cursor IDE](docs/ide.md).

### Cursor Cloud Agents

- **No provider setting, by design.** The current Cloud Agents API takes a
  model ID from Cursor's catalog and inline MCP servers. It has no Azure
  endpoint, deployment or credential field, and `envVars` only reaches the
  agent's shell and tools. A Cursor staff reply in August 2026 says keys are
  attached by the IDE client on each request, headless runs have no client,
  and cloud runs include VM compute [C5, C6, F23, F24].
- **MCP tools could reach Foundry** through a remote, authenticated HTTP MCP
  service. The local stdio bridge isn't reachable from a Cursor-hosted VM.
  [`config/cloud-agent.request.example.json`](config/cloud-agent.request.example.json)
  is a request-shape blueprint only [C7].
- **Custom models refused.** On Premium, a Cloud chat in the Agents Window
  with the custom model `foundry-luna` answered "Model Not Available - The AI
  model you selected isn't available...", and the gateway logged 0 requests
  ([`premium-round.json`](evidence-snapshot/premium-round.json)).
- **MCP blueprint not run.** It needs a Cursor API key and a public,
  authenticated MCP service; neither was created [C3]. OIDC federation [C10]
  and self-hosted workers [C8] were researched; neither moves the main model
  to Foundry.

Details: [Cursor Cloud Agents](docs/cloud.md).

## 3. API format results

### Do not conflate three APIs

| API | Request shape | Tool shape | Text/stream shape |
| --- | --- | --- | --- |
| OpenAI Responses | `input`, `max_output_tokens`, nested `reasoning` | `function_call` and `function_call_output` | `output` items; `response.output_text.delta` events |
| OpenAI Chat Completions | `messages`, `max_tokens` or `max_completion_tokens` | `tool_calls` and role `tool` | `choices[].message`; chat-completion chunks |
| Anthropic Messages | `messages`, required `max_tokens`, top-level `system`, `thinking` | `tool_use` and `tool_result` content blocks | `content` blocks; message/content-block events |

Changing the hostname is not enough when the client speaks the wrong API.
System messages, reasoning controls, tool-call IDs, tool results, stop reasons,
stream events, and token accounting all have format-specific semantics.

### Results against the tested Haiku deployment

| Destination | Result |
| --- | --- |
| `https://<resource>.services.ai.azure.com/anthropic/v1/messages` | **Works** with Entra auth; basic text, streaming and tool round trip verified |
| `https://<resource>.openai.azure.com/openai/v1/responses` | **Works in this account/deployment**; text, streaming and tool round trip verified |
| `https://<resource>.openai.azure.com/openai/v1/chat/completions` | **404**, `api_not_supported` |
| `https://<resource>.services.ai.azure.com/anthropic/v1/chat/completions` | **404**, `api_not_supported` |

Evidence: [`claude-api-formats.json`](evidence-snapshot/claude-api-formats.json),
[`claude-responses-features.json`](evidence-snapshot/claude-responses-features.json),
[`claude-anthropic-features.json`](evidence-snapshot/claude-anthropic-features.json),
and the direct/MCP smoke files in [`evidence-snapshot/`](evidence-snapshot/).

**This is an important correction to a blanket "Claude cannot use an OpenAI
API" conclusion.** The current SDK overview still directs Claude users to the
separate Anthropic endpoint, while the actual Responses endpoint accepted
this deployment. Treat this as verified behavior of this account/model, not a
guarantee for every Foundry region, tenant, model, or API. The native Anthropic
route is the documented route and remains the main Haiku MCP implementation.
[M2, M3]

### Results against the tested Luna deployment

Cursor doesn't document which Azure route its IDE Azure OpenAI slot calls, so
`probe_openai_routes.py` called the Luna deployment on each candidate with
Entra authentication:

| Route | Result |
| --- | --- |
| Current `/openai/v1/chat/completions` | **200**; response `model` is `gpt-6-luna-2026-09-22` |
| Current `/openai/v1/chat/completions` with `reasoning_effort` | **200** |
| Current `/openai/v1/chat/completions` with a Responses-style `reasoning` object | **400** `unknown_parameter`: "Unknown parameter: 'reasoning'." |
| Legacy `/openai/deployments/<name>/chat/completions?api-version=2025-04-01-preview` | **200** |
| Current `/openai/v1/responses` | **200** |

Evidence: [`openai-api-routes.json`](evidence-snapshot/openai-api-routes.json).

The 400 is the same error users report when the IDE's Azure slot sends some
models to Chat Completions with a Responses-only reasoning setting. Cursor
staff call it a known issue [F9]. Luna itself accepts both API formats; the
failure comes from mixing them in one request.

### Results with a resource API key

The IDE's key slots authenticate with a resource key, not Entra ID, so
`probe_fullswitch_routes.py` repeated the request shapes with a key:

| Request | Result |
| --- | --- |
| Luna Chat Completions, `Authorization: Bearer <key>` | **200** |
| Luna Chat Completions, `api-key: <key>` | **200** |
| Luna Chat Completions, wrong key | **401** |
| Luna Chat Completions with legacy `max_tokens` | **400**: "Use 'max_completion_tokens' instead" |
| Luna Chat Completions with tools, no `reasoning_effort` | **400**: tools with `reasoning_effort` aren't supported on Chat Completions; use Responses or set `reasoning_effort` to `none` |
| Luna Chat Completions with tools, `reasoning_effort: "none"` | **200**, `tool_calls` returned |
| Luna Chat Completions streaming with tools | **200**, finish reason `tool_calls` |
| Claude `/openai/v1/chat/completions` | **404** `api_not_supported` |
| Claude `/openai/v1/responses` | **200** |
| Claude `/anthropic/v1/messages` | **200** with `x-api-key` or Bearer (needs `anthropic-version: 2023-06-01`) |

Evidence: [`fullswitch-key-routes.json`](evidence-snapshot/fullswitch-key-routes.json).
This shows what Foundry accepts. What Cursor sends from the IDE for a given
model is **unobserved**, so whether an Agent request carries
`reasoning_effort: "none"` is not known.

`probe_key_routes.py` then sent the same small request with the key to both
deployments on the routes the Azure slot can use
([`key-route-probe.json`](evidence-snapshot/key-route-probe.json)):

| Route and header | GPT (Luna) | Claude Haiku 5.5 |
| --- | --- | --- |
| Legacy `/openai/deployments/<name>/chat/completions`, `api-key` | **400** with `max_tokens`; 200 with `max_completion_tokens` | **404** `api_not_supported` with either |
| Current `/openai/v1/chat/completions` | 200 | **404** `api_not_supported` |
| Current `/openai/v1/responses` | 200 | 200 |
| `/anthropic/v1/messages`, `x-api-key` | n/a | 200 |
| `/anthropic/v1/messages`, `api-key` | n/a | **401** |

So a Claude deployment name in the Azure slot can only work if Cursor sends
the Responses API, which is unobserved. A proxy must also translate the
`api-key` header to `x-api-key` for the Messages route.

### Reasoning settings are not interchangeable

The Responses API rejected `reasoning: {"effort":"none"}` for Haiku with HTTP
400, listing `low`, `medium`, `high`, `xhigh`, and `max`. The feature test uses
`low` for Haiku and `none` for Luna.

Native Haiku accepted `thinking: {"type":"disabled"}` for these text/tool tests.
The PoC does not send sampling parameters copied from another Claude model.
These controls must remain provider- and API-specific even when both calls
use the OpenAI SDK.

### Solutions built: the MCP bridge, LiteLLM and a translating proxy

For Cursor, the MCP bridge performs the operation at the **tool boundary**:
Cursor sends a small JSON tool argument; the bridge calls the appropriate
native SDK and returns a common text/metadata result. Cursor never needs to
speak Anthropic Messages itself.

For a client that supports OpenAI Responses, the same Foundry OpenAI base URL
can reach both tested deployments. `verify_model_features.py` demonstrates
that route with real streaming and complete tool-call continuation, not just
a one-message "hello".

If a client speaks only Chat Completions, as the Azure slot's route does
[L2], use a maintained translator such as LiteLLM's `azure_ai/` Anthropic
provider, or a separately tested gateway. LiteLLM documents
translation, streaming and tool handling; its advertised `/chat/completions`
endpoint is the **proxy's** interface, not proof that Azure's native Anthropic
endpoint supports it. `scripts/litellm_gateway.py` runs LiteLLM with two
aliases, `foundry-luna` (always through the Responses API, which avoids
Luna's tool restriction on Chat Completions) and `foundry-haiku` (through the
Anthropic route). With LiteLLM 1.108.4 (pip) and 1.109.1 (Docker),
`probe_litellm_gateway.py` passed 15 of 15 cases: text, tool calls and
tool-result round trips on the `/cursor` route with Chat Completions and
Responses-shaped bodies, the Azure deployment route, streaming, a model-name
suffix and a wrong key
([`litellm-gateway.json`](evidence-snapshot/litellm-gateway.json),
[`litellm-gateway-docker.json`](evidence-snapshot/litellm-gateway-docker.json)).
**I haven't re-run it in Cursor since the correction**; the earlier run used
UI automation that never saved Cursor's settings. [L1, L2]

The real-key round added a small, dependency-free translator,
[`scripts/foundry_claude_proxy.py`](scripts/foundry_claude_proxy.py). It
accepts Chat Completions on the `/v1/chat/completions` route and on the Azure
slot's `/openai/deployments/<name>/chat/completions` route, with
`Authorization: Bearer` or `api-key`, and translates to Claude's Messages API
(default) or the Responses API (`--claude-api responses`, or
`--openai-api responses` for OpenAI deployments such as GPT-6 Luna). It maps
system and developer messages, tool definitions, `tool_choice`, tool calls
and tool results, images, stop sequences, streaming deltas, finish reasons and
usage, and drops Claude-only fields Cursor adds (`thinking`, `output_config`,
`fallbacks`). Upstream it uses `x-api-key`, `api-key` or Entra ID.
`probe_claude_proxy.py` passed 13 of 13 cases, including a parallel two-tool
round trip, streaming with usage, both API modes and a wrong-secret rejection
([`claude-proxy-probe.json`](evidence-snapshot/claude-proxy-probe.json)).
**Cursor 3.30.14 used it** behind a public tunnel: 14 requests from Cursor's
backend, through the Azure slot and through the OpenAI override, ran the
Agent on Claude Haiku 5.5 and GPT-6 Luna with tool calls
([`ide-proxy-cursor-requests.json`](evidence-snapshot/ide-proxy-cursor-requests.json)).

The translation is therefore proven for Cursor's IDE, including for Claude.
The proxy needs a public address, because Cursor's servers make the call, and
it sees every prompt. No translator can manufacture an Azure-provider override
in Cursor CLI or Cloud Agents.

## 4. How the forum threads fit together

| Source/time | What it establishes | What it does not establish |
| --- | --- | --- |
| Claude-via-Foundry feature request, December 2025 [F2] | Users wanted native Azure-hosted Claude support | Delivered support or a timeline |
| Community Azure/Claude proxy guide, December 2025 [F6] | An IDE OpenAI-to-Anthropic translation approach was demonstrated | CLI support or reliable Agent-mode compatibility |
| Same proxy author's March 2026 follow-up [F6] | Author mainly used Ctrl+K and had not used the proxy with an agent | A validated autonomous-agent solution |
| Anthropic base-URL request, May 2026 [F3] | No equivalent Anthropic override was available to the requester; staff confirms overridden OpenAI traffic traverses Cursor | An Azure-native CLI switch |
| Foundry support reply, June 2026 [F1] | IDE Azure slot supports Azure OpenAI-format use; Claude's different format was a limitation then | Universal impossibility of all later Foundry Responses compatibility |
| Enterprise gateway report, October 2026 [F7] | Community reports model-ID collisions/built-in routing can bypass expected gateway selection | A stable or officially supported model-alias hack |
| OpenAI override threads, October 2025 to September 2026 [F18, F19, F20, F21] | The IDE's OpenAI base URL override is global: it also captures Cursor's own models, and there is no per-model base URL | A safe way to combine the override with Cursor's models |
| Key side-effect threads, July to November 2026 [F11, F12, F13, F14, F15, F16, F17] | Staff: any key toggle routes most non-Cursor models through your keys; empty Azure fields break every model; Azure settings win over Bedrock; Grok 4.6 runs only on Cursor | That these interactions are stable across releases |
| Azure slot model errors, July and October 2026 [F9, F10] | Staff: some models reach Chat Completions with a Responses-only reasoning setting, a known issue; users report `response.failed` errors for GPT-5.4 and GPT-5.6 | Which models are affected in a given release |
| Model and plan answer, October 2026 [F22] | Own keys are for chat models only; Tab always uses Cursor; some plans can't use own keys | Plan details beyond that reply |
| Foundry BYOK staff reply, November 2026 [F8] | Foundry OpenAI deployments, including `*.cognitiveservices.azure.com` endpoints, should work through the IDE Azure OpenAI slot; no dedicated Foundry integration and no timeline | Claude support, or CLI and Cloud Agents support |
| Cloud Agents BYOK threads, May to November 2026 [F23, F24] | Staff (August 2026): own keys are attached by the IDE client on each request, headless cloud runs have no client, and cloud runs include VM compute, so keys aren't available there "by design"; users keep asking | A timeline or any Foundry-specific plan |
| CLI provider-key thread, January to November 2026 [F25] | Staff (November 2026): the CLI doesn't support provider API keys | A planned feature |
| Override and key conflicts, February to November 2026 [F26, F27, F30] | Users report that the Anthropic key stops working while the OpenAI override is set, that Cursor-managed OpenAI-family models are rerouted through the override, and that the override is unusable for some setups | That every user is affected; these are user reports, with staff confirmation only where [F27] says so |
| Azure model reliability, February to March 2026 [F28] | Users reported Azure AI API models as unreliable in the Agent; staff pointed at tool-schema problems for file operations and missing Responses API support on Azure | The state of that behavior in the tested IDE |
| "When will Cursor fully support BYOK?", June 2026 [F29] | No per-model base URL or parameters; "no concrete timeline" | A roadmap |
| Azure slot how-to, June to August 2026 [F31] | Staff: Base URL only `https://<resource>.openai.azure.com`, "Cursor appends the rest", real deployment name, project endpoints (`*.services.ai.azure.com`) not supported; the user confirmed it and later ran GPT-5.6 Luna in the Agent. Staff: with an OpenAI key or override on, Cursor-only models fail and Auto works | That it keeps working across releases |
| Azure slot breakages, August 2025 to July 2026 [F32, F33, F35, F37] | `model is required` from January to July 2026, traced to Cursor and fixed in July; GPT-5 errors in 2025 closed without a fix; staff recommended a community gateway [G3] in April 2026; images bypass the custom URL | That current releases are stable |
| Configuration and plan errors, May and August 2026 [F34, F36] | A misspelled base URL gave a 502; on pooled Team and Enterprise plans own-key requests count toward usage limits, and a wrong deployment name can show the same block | Individual-plan behavior |
| Hacker News and Stack Overflow, 2025 [H1, H2, Q1] | A LiteLLM proxy in front of Cursor for keys and budgets; own-key requests still go through Cursor; the Deployment Name must match exactly | Anything about current releases |
| Community bridges, 2025 to 2026 [G1 to G11] | Gateways for the IDE override (G3 to G8, LiteLLM) and backend replacements that intercept Cursor's traffic with a local certificate authority (G2, G9, G10). The CLI bridge's published source doesn't pass on the provider URL or key [G1] | That any of them is safe, supported or works on current Cursor; none was run here |
| These live experiments, November 2026 | Both models work through local MCP in the CLI and IDE; Haiku Responses works; Haiku Chat Completions fails; Luna rejects a `reasoning` object on Chat Completions and tools without `reasoning_effort: "none"`; the CLI's `--endpoint` and `--model` can't route to Foundry; a LiteLLM gateway serves both models with 15 of 15 Cursor-shaped cases | |
| Premium round, 17 November 2026 | The CLI and Cloud Agents refused custom models and sent no request to a working gateway; Claude has no Chat Completions route on Foundry, with 404 on both routes. Its IDE cases were withdrawn: the automation never saved Cursor's settings | Anything about the IDE's override or Azure slot |
| Real-key round, 17 November 2026 | With saved settings and the resource's real key, the Azure slot ran the Agent with tool calls on `gpt-4.1` on a Foundry resource and a classic Azure OpenAI resource, every request `200` in Azure; GPT-6 Luna directly gave a `400`; a translating proxy behind a tunnel served Claude Haiku 5.5 and Luna to Cursor through the Azure slot and the OpenAI override, 14 requests; the first tests (A to H, F, F2) were invalid because the automation never saved the settings | That it keeps working across releases [F32, F35, F37], or reasoning models other than Luna directly |

Do not send Azure credentials to the public Railway endpoint in the community
post. Its URL is a research reference, not a trusted service for this account.
No request or credential from this PoC was sent there.

### Interpreting apparent contradictions

- **"Directly to your provider" or "through Cursor's servers"?** A June 2026
  staff reply [F1] described requests as going directly to your provider. The
  official docs say your key and requests travel through Cursor's backend
  [C11], and the Override Base URL must be reachable from the internet [L2].
  The docs are authoritative here.
- **`*.cognitiveservices.azure.com` or `*.openai.azure.com`?** The November
  staff reply [F8] cites the first endpoint form; the July staff reply [F31]
  and the slot's placeholder use the second. Both belong to the same Foundry
  resource. The valid real-key tests used `https://<resource>.openai.azure.com`
  and worked; the other form wasn't re-tested after the correction.
- **Does the Azure slot reach a gateway?** LiteLLM documents a gateway behind
  the Azure slot on Cursor 3.17.21 [L2]. On 3.30.14 with Premium, the slot
  reached the translating proxy behind a public tunnel.
- **"Supported" or "known issue"?** Staff say Foundry OpenAI deployments work
  through the Azure slot [F8], and that some models hit a Chat Completions
  `reasoning` error [F9]. Both can be true: support is per model.

## 5. Privacy, credentials, billing, and residency

| Concern | Actual behavior / limitation |
| --- | --- |
| Azure credentials | The MCP bridge obtains Entra tokens locally and sends them only to the configured Azure service. For the IDE key route, a resource API key (all deployments on the resource) goes to Cursor's servers on every request. The key was read from Azure only in memory for probes and never entered into Cursor, printed or written. |
| Cursor's visibility | Cursor sees the user prompt, MCP arguments, returned text and metadata; using Foundry for a tool does not create an Azure-only data boundary. |
| **IDE BYOK privacy** | Official docs say your key and requests pass through Cursor's backend, that zero data retention does **not** apply when you use your own keys, and that the key isn't persisted. This is an IDE consideration, not what the local MCP server does. [C11, C16] |
| Main-model cost | Cursor inference remains a separate usage lane. MCP does not transfer all Cursor tokens to Azure commitments. With your own key on an individual plan, the provider bills you and included usage isn't drawn; on Teams or Enterprise, Cursor's token rate of $0.25 per million tokens applies on top. [C11, C17] |
| Foundry cost | The newly created Luna SKU is pay-per-token, not provisioned throughput. Capacity limits throughput, not total spend. No account-specific dollar invoice was queried. |
| Luna residency | DataZoneStandard in Sweden Central uses the Microsoft-defined EU data zone, not a guarantee of inference exclusively in Sweden. [M5] |
| Haiku residency | Existing deployment is GlobalStandard; native response usage reported `inference_geo: global`. Do not claim EU-only processing. |
| Response storage | OpenAI Responses requests use `store: false`. That flag is not a blanket promise about provider logging, safety processing, or Cursor retention. |
| Audit contents | Successful-call metadata, hashes and usage are recorded; no prompt, answer or credential is written to the audit stream. Synthetic test artifacts intentionally include their test text. |
| Error behavior | No model fallback or silent retry; incomplete/empty responses are failures. SDK error bodies are not echoed through the core inference tools. |
| Local permissions | In the CLI, only named inference tools are allowlisted; no `--force` or blanket MCP approval is used. In the IDE, the project server had to be turned on by hand, and the recorded run then called both tools without an approval prompt. Neither replaces a production sandbox. |

Cloud Agent conversations and environment snapshots have their own retention
and secret-handling rules. A stdio server inside the cloud VM exposes its
configuration/environment to that VM. Official documentation recommends
HTTP MCP for separating server credentials from the agent VM. [C7, C13]

## 6. Verification and limits

| Check | Evidence (in `evidence-snapshot/`) | Outcome |
| --- | --- | --- |
| Luna creation and repeat deployment command | `deployment-created.json`, `deployment.json` | Created once; repeat did not modify the model |
| Haiku reuse and other deployments preserved | `deployment-inventory.json` | Haiku and the account's pre-existing deployments remain present (other names omitted from the public snapshot) |
| Direct Luna and native Haiku calls | `openai-direct-smoke.json`, `claude-direct-smoke.json` | Passed |
| SDK MCP client to both models | `openai-mcp-smoke.json`, `claude-mcp-smoke.json` | Passed |
| Actual installed Cursor CLI to both models | `cursor-mcp-e2e.json` | Passed with hashes/IDs correlated |
| Cursor IDE Agent to both models | `ide-mcp-e2e.json`, `ide-transcript.txt` | Passed with hashes/IDs correlated (IDE 3.30.14, Grok 4.7 Agent) |
| Luna on candidate OpenAI routes | `openai-api-routes.json` | Chat Completions (current and legacy) and Responses 200; `reasoning` object on Chat Completions 400 |
| Luna Responses streaming + tool continuation | `openai-responses-features.json` | Passed |
| Haiku Responses streaming + tool continuation | `claude-responses-features.json` | Passed |
| Haiku native streaming + tool continuation | `claude-anthropic-features.json` | Passed |
| Haiku endpoint compatibility | `claude-api-formats.json` | Responses 200; both Chat Completions routes 404 |
| CLI endpoint/auth distinction and environment overrides | `cursor-routing.json` | Observed Cursor auth exchange with an invalid key; Auto did not use provider overrides |
| CLI `--endpoint` with a real login, `--model` and provider commands | `cli-fullswitch.json` | Only Cursor's `aiserver.v1` services were called; non-catalog model refused; `bedrock` is the only provider command |
| Resource API key on the routes an IDE slot would use | `fullswitch-key-routes.json` | 12 of 12 checks as expected (see section 3) |
| Both deployments on the Azure slot's routes with a key | `key-route-probe.json` | GPT 200 on Chat Completions and Responses; Claude **404** on both Chat Completions routes, 200 on Responses and Messages (`x-api-key`), 401 with `api-key` |
| Both models through a LiteLLM gateway | `litellm-gateway.json`, `litellm-gateway-docker.json` | 15 of 15 cases on pip 1.108.4 and Docker 1.109.1 |
| Cursor's use of the gateway, CLI and Cloud, Premium | `premium-round.json` | **0 requests** from Cursor; CLI "Cannot use this model"; Cloud "Model Not Available". The IDE cases are withdrawn: the automation never saved Cursor's settings |
| IDE Azure OpenAI slot, Premium, dummy key | `premium-round.json` | Withdrawn for the same reason |
| IDE Azure OpenAI slot, Premium, real keys | `ide-realkey-round.json`, `ide-classic-slot-usage.json`, `ide-foundry-direct-usage.json`, `ide-foundry-luna-usage.json`, `ide-realkey-cursor-log-summary.json` | **Works**: `gpt-4.1` on a classic Azure OpenAI resource and on a Foundry resource answered with text and tool calls, every request `200`; 10K tokens per minute gave a `429`; GPT-6 Luna gave a `400` on tools; a missing deployment gave "Provider Error"; an empty Base URL gave "Network Error", the signature of the withdrawn tests A to H |
| Translating Claude proxy, direct | `claude-proxy-probe.json` | 13 of 13 cases: text, streaming with usage, a parallel tool round trip, Messages and Responses modes, the Azure route, GPT passthrough and a wrong-secret rejection |
| Cursor's use of the translating proxy | `ide-proxy-cursor-requests.json`, `ide-proxy-claude-usage.json`, `ide-proxy-luna-usage.json`, `ide-override-claude-usage.json`, `ide-override-luna-usage.json` | **14 requests** from Cursor's backend: the Azure slot to Claude Haiku 5.5 (3) and GPT-6 Luna (4), the OpenAI override to `foundry-haiku` and `foundry-luna` (5), all `200` from Foundry; 2 built-in model names answered `404` |
| Azure Monitor usage check | `usage-check-selftest.json` | A direct request showed up as one `200` |
| Input, destination, missing-config, error, audit, MCP rejection, transcript-correlation, capture-proxy, probe, translating-proxy, Cursor-log and development-study guards | `unit-tests.txt` | 25 tests passed, including the key-route probe guard, Claude tool and streaming translation, Responses mode for OpenAI reasoning deployments, direct-SDK substitution rejection and interrupted-run accounting |
| Live Cloud Agent with MCP | Plan and API-key requirements | Not run; no Cursor API key or public MCP service was created |
| IDE Azure OpenAI, OpenAI and Anthropic key slots | Screenshots in `docs/assets/` | Fields captured |
| Public community proxy | Research only | Not invoked |

Streaming tests verify text deltas and final completion. Tool tests verify one
function call, exact arguments, a correctly correlated result, and a final
answer. They do not establish support for all parallel tools, multimodal
inputs, long-context behavior, thinking signatures, server tools, or every
structured-output option.

An initial tool-round-trip check asked for a marker without an exact formatting
contract; valid model wording failed its strict assertion. The final tests
explicitly request `marker:<integer>` with no spaces or Markdown and check the
real continuation against that contract. This corrected the test, not the
provider's protocol.

## 7. Recommendations

**Choose by how much of Cursor you need to move to Foundry:**

1. **If you want Cursor's chat model to run on your Foundry OpenAI
   deployment, use the IDE's Azure OpenAI slot.** It is the only switch:
   chat and Agent, a paid plan. Set the Base URL to
   `https://<resource>.openai.azure.com` and nothing else, the deployment
   name exactly, and **key 2** of the resource [F31, F8, Q1]. Give the
   deployment at least 100K tokens per minute; 10K failed on the first
   request. A non-reasoning deployment such as `gpt-4.1` works directly; GPT-6
   Luna needs the proxy in Responses mode, and some models hit the
   `reasoning` parameter error [F9]. Never leave **Use Azure OpenAI** on with
   empty fields [F12]. Requests pass through Cursor's servers, zero data
   retention doesn't apply, and the key goes to Cursor with every request
   [C11, C16]. Close and reopen Cursor Settings to check the values were
   saved, confirm a test prompt with `scripts/check_foundry_usage.py`, and
   regenerate key 2 when you stop. **Verified with a real key on Premium**;
   Cursor updates have broken it before [F32, F35, F37], so re-check after
   updates. If it fails, match the message in
   [What Cursor's errors mean](docs/ide.md#what-cursors-errors-mean) and send
   Cursor the Request ID [C20].
2. **For Claude or GPT-6 Luna in the IDE, run the translating proxy.** It
   worked from the Azure slot and from the OpenAI override, but it needs a
   public address, sees every prompt and adds an always-on process you
   operate. Protect it with a secret and stop the tunnel when you're done.
   LiteLLM does the same translation and passes 15 of 15 direct cases, but
   wasn't re-run in Cursor here [L2]. Avoid community backend replacements
   for work code: they impersonate Cursor and see everything you send
   [G2, G9, G10].
3. **For the CLI and Cloud Agents there is no switch.** Use the MCP fallback:
   the provided local bridge in the CLI or IDE, and an authenticated HTTP MCP
   service for Cloud Agents. The CLI and IDE paths are verified end to end.
   In the IDE, turn the server on in **Customize > MCPs** and off again when
   you're done. Cloud Agents: host the two tools as an HTTP MCP service that
   calls Foundry with a managed identity, then verify a real run with a fresh
   challenge. This path is a blueprint, not run.

**For a Responses-capable custom application:** the unified Foundry Responses
route worked for both models; retain deployment-specific reasoning controls
and run the compatibility tests in each target environment.

**For durable native Claude integration:** prefer the documented Anthropic
Messages SDK route. The MCP wrapper already implements it.

**If the hard requirement is that all agent inference be billed and processed
through your own Foundry account with Cursor, this experiment does not
satisfy it.** The IDE route covers only chat and Agent models, still passes
through Cursor's backend and doesn't apply to Tab, the CLI or Cloud Agents.
For a real full switch, use an agent runtime with explicit Foundry support,
such as Claude Code with `CLAUDE_CODE_USE_FOUNDRY=1` [A3], or other agents with
documented Azure providers [X1, X2], or obtain a supported Cursor enterprise
integration with verifiable routing guarantees.

---

API naming note: this report uses "current" and "legacy" for API shapes. At the
time of the investigation, the current Cloud Agents API used `/v1` durable
agents plus runs; the legacy API used `/v0`. Sources and experiments were
checked on 17 November 2026 local time; UTC evidence timestamps can show
16 November. Findings are specific to those observed versions and resources.
