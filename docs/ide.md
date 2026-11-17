# Cursor IDE with Microsoft Foundry

**Verdict: a partial switch.** The IDE is the only Cursor surface with a way to
make a Foundry deployment the **chat model**. It works through your own API
key, covers chat and Agent models only, speaks OpenAI format only, and sends
every request through Cursor's servers. Claude on Foundry needs a translating
gateway, and the **Free plan locks the model picker**, so a paid plan is
needed. If you want Cursor's agent to keep running on Cursor and only *call*
Foundry, use [the MCP fallback](#fallback-foundry-models-as-mcp-tools).

What I could and could not confirm, as of 17 November 2026:

| Part | Status |
| --- | --- |
| The settings exist (Azure OpenAI slot, OpenAI Base URL override, custom models) | **Confirmed** in Cursor IDE 3.30.14 (screenshots below) |
| Foundry accepts the requests such a slot sends | **Verified** with a resource key: 12 of 12 probes behaved as expected |
| Cursor itself sends a request to your endpoint | **Not observed.** On the Free plan the chat model picker is locked ("More models are only available on paid plans"), so Cursor sent nothing |
| Claude on Foundry through a LiteLLM gateway | The gateway **passed locally** (text, tools, streaming). It was **not** tested through Cursor |
| Foundry models as MCP tools | **Verified end to end** in the IDE |

> **Tested with:** Cursor IDE 3.30.14 on Windows 11, Free plan,
> 17 November 2026.

## The routes

| Route | Foundry models | What you do | Status |
| --- | --- | --- | --- |
| [1. Azure OpenAI slot](#route-1-the-azure-openai-slot) | OpenAI format | Fill three fields in **Models > API Keys > Azure OpenAI** | Foundry side verified; Cursor side unobserved |
| [2. OpenAI key with a base URL override](#route-2-openai-key-with-override-base-url) | OpenAI format | Point **Override OpenAI Base URL** at Foundry and add a custom model | Documented by Microsoft for another gateway [M9]; Foundry side verified; Cursor side unobserved |
| [3. Claude through a gateway](#route-3-claude-through-a-gateway) | Claude | Run LiteLLM in front of the Claude deployment and use route 2 | Gateway verified locally; Cursor side unobserved |
| [Fallback: MCP tools](#fallback-foundry-models-as-mcp-tools) | OpenAI and Claude | Cursor's model calls Foundry as a tool | **Verified**; not a switch |

## Before you start

- A **paid Cursor plan**. Own-key models are chat models and appear in the
  model picker after you save the keys [C11]; on Free the picker is locked.
- The [Foundry setup](setup.md) steps 1 to 3, and an **API key** for the
  resource, because the IDE can't use Entra ID. See
  [API-key access](setup.md#optional-api-key-access-for-the-ide-full-switch).
- Read [all the disadvantages](#all-the-disadvantages) first. In particular,
  Cursor's servers send the requests, so your Foundry endpoint must be public.

## Route 1: the Azure OpenAI slot

Open **Cursor Settings > Models**, expand **API Keys**, and scroll to
**Azure OpenAI**:

![Azure OpenAI section of Cursor Settings with the Use Azure OpenAI toggle and Base URL, Deployment Name and API Key fields, above the AWS Bedrock section](assets/ide-byok-azure-slot.png)

| Field | What to enter for Foundry |
| --- | --- |
| **Use Azure OpenAI** | On |
| **Base URL** | `<resource>.openai.azure.com`, the format the placeholder shows. Cursor staff say `*.cognitiveservices.azure.com` endpoints work too [F8] |
| **Deployment Name** | Your OpenAI deployment, for example `cursor-poc-gpt-6-luna` |
| **API Key** | A key of the Foundry resource (portal: **Keys and Endpoint**) |

After you save, the model should appear in the picker [C11]. Choose it in a
new chat.

**What is confirmed.** On 10 November 2026 Cursor staff said Foundry OpenAI
deployments should work through this slot, that there is no dedicated Foundry
integration, and that there is no timeline for one [F8]. Cursor's own list of
providers includes "Azure OpenAI: models deployed in your Azure OpenAI
Service instance" [C11].

**What may break.** Users report unstable Agent behavior with Azure
deployments. In February 2026 a staff member said the tools schema is wrong
for file operations and that the Responses API is not supported on Azure
[F28]. See [the pitfalls](#pitfalls-when-you-turn-on-an-api-key).
**Test your model in the Agent before relying on it.**

## Route 2: OpenAI key with Override Base URL

Under **API Keys**, the **OpenAI API Key** section has an
**Override OpenAI Base URL** toggle. The **Anthropic API Key** section below it
has no base URL option:

![OpenAI API Key section with the Override OpenAI Base URL toggle, above the Anthropic API Key section that applies to all models beginning with claude-](assets/ide-byok-openai-anthropic.png)

Microsoft documents this pattern for Cursor with a different gateway,
Databricks AI Gateway: set **Override OpenAI Base URL**, put the gateway key in
the OpenAI key field, and **Add Custom Model** [M9]. For Foundry the values
would be:

| Setting | Value |
| --- | --- |
| **Override OpenAI Base URL** | `https://<resource>.openai.azure.com/openai/v1` |
| **OpenAI API Key** | The Foundry resource key |
| **Custom model** | The deployment name, for example `cursor-poc-gpt-6-luna` |

I tried the Cursor side on the Free plan, pointing the override at the
[capture proxy](#verify-what-cursor-sends) with a throwaway secret. The
settings accepted the base URL and the custom model, but the model picker was
locked, so Cursor sent no request. I turned the override off afterwards. The
custom model `cursor-poc-gpt-6-luna` stays in the settings, disabled, because
Free doesn't allow removing it.

**The override is global.** It applies to every OpenAI-family model while it
is on, including Cursor-managed ones, which staff confirmed in August 2026
[F27]. See [what stays on Cursor](#what-stays-on-cursor).

## Route 3: Claude through a gateway

Cursor routes every model whose name starts with `claude-` to its Anthropic
key slot, and that slot has no base URL [C11]. Foundry also returns 404 for
Claude on Chat Completions (see
[the probe](#what-the-route-probe-shows)). So Cursor can't talk to Foundry
Claude directly. A gateway can translate: it exposes a Chat Completions
endpoint to Cursor and calls the native Anthropic route on Foundry.

I tested LiteLLM 1.108.4 on `127.0.0.1` in front of the Claude Haiku 5.5
deployment. It handled text with both token-limit spellings, a tool call, the
tool-result round trip, and streaming with usage; a wrong gateway key was
rejected ([`litellm-gateway.json`](../evidence-snapshot/litellm-gateway.json),
[`probe_litellm_gateway.py`](../scripts/probe_litellm_gateway.py)).

1. Install LiteLLM in its own environment: `pip install "litellm[proxy]"`.
2. Copy [`config/litellm.config.example.yaml`](../config/litellm.config.example.yaml),
   and replace `<resource>` and the deployment name. **The alias must not start
   with `claude`**; the example uses `foundry-haiku`.
3. Set `AZURE_AI_API_KEY` (the Foundry key, which stays on the gateway) and
   `LITELLM_MASTER_KEY` (a long random value starting with `sk-`, which you
   give to Cursor).
4. Start it: `litellm --config config/litellm.config.example.yaml --host 0.0.0.0 --port 4000`.
5. Put it behind **public HTTPS**. Cursor sends requests from its own servers,
   so `localhost` won't work [L2].
6. In Cursor, use route 2 with **Override OpenAI Base URL** set to
   `https://<gateway-host>/v1`, the master key as the OpenAI key, and a custom
   model named `foundry-haiku`.

Cursor then holds a revocable gateway key and never your Foundry key. That is
an advantage over routes 1 and 2, but I did not verify it through Cursor.
You now run and secure a public service, and the override disables native
Claude while it is on [F26].

## What the route probe shows

These probes call Foundry directly, so they describe what Foundry accepts. They
do not show what Cursor sends.

`scripts/probe_openai_routes.py` used Entra authentication
([`openai-api-routes.json`](../evidence-snapshot/openai-api-routes.json)):

| Route | Result |
| --- | --- |
| Current `/openai/v1/chat/completions` | 200 |
| Current `/openai/v1/chat/completions` with `reasoning_effort` | 200 |
| Current `/openai/v1/chat/completions` with a Responses-style `reasoning` object | **400** `unknown_parameter`: "Unknown parameter: 'reasoning'." |
| Legacy `/openai/deployments/<name>/chat/completions?api-version=...` | 200 |
| Current `/openai/v1/responses` | 200 |

That 400 is the error users report for GPT-6 Astra in the Azure slot. Staff
explained that for some models Cursor sends a reasoning setting that only the
Responses API accepts to Chat Completions [F9].

`scripts/probe_fullswitch_routes.py` repeated the calls with a **resource API
key**, the way a Cursor key slot would
([`fullswitch-key-routes.json`](../evidence-snapshot/fullswitch-key-routes.json)):

| Case | Result |
| --- | --- |
| Luna chat, key as `Authorization: Bearer` | 200 |
| Luna chat, key as `api-key` header | 200 |
| Luna chat with a wrong key | 401 |
| Luna chat with the legacy `max_tokens` | **400**: use `max_completion_tokens` |
| Luna chat with tools, no `reasoning_effort` | **400**: "Function tools with reasoning_effort are not supported ... use /v1/responses or set reasoning_effort to 'none'" |
| Luna chat with tools, `reasoning_effort: "low"` | **400**, same message |
| Luna chat with tools, `reasoning_effort: "none"` | 200, returns a `read_file` tool call |
| The same, streaming | 200, finishes with `tool_calls` |
| Claude on `/openai/v1/chat/completions` | **404** `api_not_supported` |
| Claude on `/openai/v1/responses` | 200 |
| Claude on `/anthropic/v1/messages`, `x-api-key` or Bearer | 200 |

Two results matter for the Agent. Luna refuses tools on Chat Completions unless
`reasoning_effort` is `none`, and Claude has no Chat Completions route at all.
I don't know what Cursor sends for either; that needs a paid plan to observe.

## What stays on Cursor

Even with every route set up:

- **Tab completion** always uses Cursor's models [F22], [C11].
- **Auto, Composer and Cursor's own models** stay on Cursor. Keys apply to
  chat models only [C11].
- **The CLI and Cloud Agents** don't use the IDE's keys [O1]. See
  [CLI](cli.md#why-there-is-no-switch) and [Cloud](cloud.md#why-there-is-no-switch).
- **Prompt building** happens on Cursor's backend, which receives your key
  with each request. The documentation says the key is not stored [C11].

## All the disadvantages

This is the complete list of costs I found, with the source for each.

**Privacy and security**

- **Every request goes through Cursor's servers.** The key is sent "with every
  request" for final prompt building [C11]. It is a switch of the *endpoint*,
  not of who handles your code.
- **Zero Data Retention no longer applies** with your own key; the provider's
  data handling does [C11], [C16].
- **Key only.** The slots take an API key. They don't offer Entra ID or
  managed identity.
- **The endpoint must be publicly reachable.** Cursor calls it from the
  internet, so there is no private endpoint or VNet route [L2].

**Coverage**

- **Chat and Agent models only.** Tab, Auto, Composer and Cursor models stay
  on Cursor; the CLI and Cloud Agents don't use keys [C11], [O1].
- **OpenAI format only.** Claude on Foundry returns 404 on Chat Completions
  (probe above), and the Anthropic slot has no base URL [C11].
- **Claude needs a gateway** with a non-`claude` alias, which you run and
  secure. The override must be off for native Claude [F26].
- **Cursor's own docs scope the OpenAI slot** to "standard, non-reasoning chat
  models" [C11]. Luna is a reasoning model.

**Reliability**

- **Luna's tool calls need `reasoning_effort: "none"`** on Chat Completions and
  the Agent uses tools (probe above). Cursor sometimes sends a Responses-style
  `reasoning` object that Chat Completions rejects with a 400 [F9].
- **Azure BYOK is reported unstable in the Agent.** Reports include a wrong
  tool schema for file operations and no Responses API on Azure [F28], and
  `response.failed` errors on GPT-5.4 and GPT-5.6 [F10].
- **Toggles have side effects.** An empty Azure field breaks every model [F12],
  Azure wins over Bedrock [F13], and Grok 4.6 fails behind the override [F15].

**Configuration**

- **One global override and key per provider.** There is no per-model base URL
  and no per-model parameters such as reasoning effort or context length [F20],
  [F29]. Cursor-managed OpenAI-family models, including its built-in
  `gpt-5.6-luna`, are routed through the override while it is on [F27].
- **No dedicated Foundry integration, no timeline** [F8].
- **No Microsoft Learn guide for Cursor on Foundry.** Learn documents the same
  override pattern only for Databricks [M9].

**Cost**

- **A paid plan.** Some plans exclude own keys [F22].
- **Teams and Enterprise pay Cursor's token rate** on top of Azure, $0.25 per
  million tokens at the time of writing [C11], [C17]. Individual plans don't
  draw their included usage, and the provider bills you [C11].

## Pitfalls when you turn on an API key

Each row comes from Cursor staff replies on the forum.

| What happens | Why | Sources |
| --- | --- | --- |
| Models other than Auto, Composer and Cursor's Grok start failing | When any personal key toggle is on, those other models go through your key configuration | [F11] |
| Every model fails with `resource_exhausted` | **Use Azure OpenAI** was on with empty fields | [F12] |
| Cursor's Grok 4.6 fails behind a Cloudflare block | Grok 4.6 runs only on Cursor's infrastructure; turn off personal keys and the override | [F15], [F16] |
| Claude or GPT models fail with a `tool_use` error | Remove the OpenAI base URL override or Azure key while using Anthropic models | [F17] |
| AWS Bedrock models fail with "Unknown parameter: 'system'" or invalid names | With both on, Azure settings win over Bedrock and Azure rejects the Claude-format request | [F13], [F14] |
| Anthropic BYOK is unusable while the override is on | The override is global | [F26] |
| Tab completion doesn't use your model | Your own keys apply to chat models only | [F22], [C11] |

## Verify what Cursor sends

Cursor's servers call your base URL, so don't paste a real Foundry key into a
test. [`scripts/capture_proxy.py`](../scripts/capture_proxy.py) lets you see
the request with a **throwaway secret** instead:

1. Run it on `127.0.0.1`. It prints a shared secret.
2. Expose that port with a temporary public tunnel, for example a Microsoft
   dev tunnel, and delete the tunnel afterwards.
3. In Cursor, use route 2 with the tunnel URL as the base URL and the shared
   secret as the OpenAI key.
4. The proxy checks the secret, swaps in your Entra token, forwards the body
   unchanged to Foundry and records only the request shape (keys, tool names,
   `reasoning` fields) in `evidence/proxy-capture.jsonl`. `--save-bodies` also
   keeps full bodies, which may contain your code.

Because the body is forwarded unchanged, whatever status you see is what
Foundry would return directly. I built and unit-tested this proxy, and set up
the tunnel, but the Free-plan lock meant Cursor never called it. On a paid plan
this is the quickest way to learn what Cursor sends for Luna.

## Fallback: Foundry models as MCP tools

If you can't or don't want to route Cursor's model through your key, keep
Cursor's own model as the agent and let it call Foundry deployments as tools.
This is **not** a switch: the agent still runs on Cursor and Cursor sees every
tool argument and result. It works on the Free plan.

The IDE reads the same `.cursor/mcp.json` file as the [CLI](cli.md).
`Setup.ps1` wrote one with absolute paths to the `demo` folder.

1. **Open the folder.** Use **File > Open Folder** and choose `demo` in your
   clone. To use the tools in your own project, copy `demo/.cursor/mcp.json`
   to `<your-project>/.cursor/mcp.json`, or to `~/.cursor/mcp.json` for every
   project.
2. **Turn the server on.** Open **Cursor Settings** (gear icon, top right),
   then select **Customize** in the settings sidebar. In the **Customize** tab,
   filter by **MCPs**. `foundry-models` appears with a badge showing the
   project folder (`demo`).
   **Project MCP servers start turned off.** Turn it on. After a few seconds
   the status dot turns green and the entry shows **2 tools enabled**.
3. **Ask the Agent.** Start a new Agent chat and name the tools:

   ```text
   Call foundry_openai and foundry_claude, each with the prompt "In one sentence, what is a Python list comprehension?". For each tool, report its text, deployment and response_id.
   ```

   In the recorded run the Agent first searched the tool schemas
   ("Explored 1 search, 2 tools") and then called both tools. No approval
   prompt appeared. Depending on your auto-run settings, Cursor may ask you to
   approve each call.

![Cursor IDE Customize tab with foundry-models connected and 2 tools enabled, next to the Agent's answer with both Foundry response IDs](assets/ide-mcp-result.png)

### Prove it with a fresh challenge

`verify_ide.py` checks that the IDE really reached Azure. It works in two
phases because the IDE has no command-line mode:

```powershell
$py = if ($IsWindows) { './.venv/Scripts/python.exe' } else { './.venv/bin/python' }
& $py scripts/verify_ide.py prepare
```

`prepare` saves a random arithmetic challenge with one-time markers to
`evidence/ide-challenge.json` and prints a prompt. Paste that prompt into a
new Agent chat in the `demo` folder. When the Agent finishes, copy the chat
into `evidence/ide-transcript.txt`, then run:

```powershell
& $py scripts/verify_ide.py check evidence/ide-transcript.txt
```

`check` passes only if the transcript contains both correct answers and the
response IDs of new audit records whose answers hash to the expected text. It
writes `evidence/ide-mcp-e2e.json` and exits with a non-zero code on failure.

Recorded run ([`ide-mcp-e2e.json`](../evidence-snapshot/ide-mcp-e2e.json),
[`ide-transcript.txt`](../evidence-snapshot/ide-transcript.txt)):

| Tool | Expected and returned | Response ID | Azure request ID | Tokens in / out |
| --- | --- | --- | --- | --- |
| `foundry_openai` (GPT-6 Luna) | `NONCE_1d6d72c082f1c5ba:1625` | `resp_0005469135d59969016afba15331588193a4abfce9cfd018c0` | `cff94086-7086-4bd8-84c6-73fe5beed153` | 40 / 22 |
| `foundry_claude` (Claude Haiku 5.5) | `NONCE_3ea9b72b73b4577c:1058` | `msg_011Ch7ZcVhwms1HNAQKsBk9e` | `req_011Ch7ZcUwYqzm3QvWPTp9Hr` | 53 / 22 |

The Agent itself ran on Grok 4.7 through Cursor, the only model the Free plan
offered. Only the two tool calls were processed and billed by Foundry. Text you
send to a tool goes to both Foundry and Cursor; the Azure credential stays on
your machine.

## Troubleshooting

Problems with Azure, roles or deployments are covered in
[Foundry setup troubleshooting](setup.md#8-troubleshooting).

| Symptom | Cause and fix |
| --- | --- |
| The model picker says "More models are only available on paid plans" | Own-key models need a paid plan. The MCP fallback works on Free. |
| `foundry-models` is missing in **Customize** | Open the folder that contains `.cursor/mcp.json` (`demo`), or copy the file to `~/.cursor/mcp.json`. |
| The server is listed but has no tools | It is turned off; project servers start off. Turn it on and wait for the green dot. |
| Red status or "The system cannot find the path specified" | Run `./scripts/Setup.ps1` again to rewrite absolute paths, then check with `smoke_test.py --transport mcp`. |
| The Agent answers without calling the tools | Name `foundry_openai` or `foundry_claude` in the prompt. |
| Every model fails after you set a key | See [pitfalls](#pitfalls-when-you-turn-on-an-api-key). Turn off **Use Azure OpenAI** and **Override OpenAI Base URL**, and clear empty fields. |
| `Unknown parameter: 'reasoning'` with the Azure slot | Known issue for some models [F9]. Try a model that Cursor sends through the Responses API, or use the MCP fallback. |
| A 400 about "Function tools with reasoning_effort" | Luna on Chat Completions rejects tools unless `reasoning_effort` is `none`. Cursor has no per-model setting for it [F29]. Capture the request to see what it sends, or use the MCP fallback for Luna. |
| 401 from Foundry | The key is wrong, rotated, or from a different resource. Compare against **Keys and Endpoint**. |

## Clean up

1. **Cursor Settings > Models > API Keys:** turn off any key toggles you
   turned on, and clear their fields. Disable custom models you added; Free
   plans can't delete them.
2. **Customize > MCPs > foundry-models:** turn it off. The test IDE was left
   with it on after the recorded run.
3. Stop the gateway or tunnel, and delete the tunnel.
4. If a key was ever pasted into Cursor, rotate it in the portal.
5. [Delete the deployments](setup.md#9-clean-up) you no longer need.

---

Source keys such as [F8] and [C11] refer to [Sources](../SOURCES.md).
