# Cursor IDE with Microsoft Foundry

**Verdict: for OpenAI deployments, a supported switch that I could not finish
here; for Claude, none.** The only native IDE route to a Foundry model is the
**Azure OpenAI slot pointed straight at your Foundry resource**. Cursor staff
and users report it working in the Agent, including with a Luna model
[F31], [F8]. On a Premium plan I confirmed that turning the slot on sends a
GPT model to your endpoint instead of Cursor's plan gate. I did not run it with
a real Foundry key. It covers chat and the Agent, not Tab, and only OpenAI
deployments.

The gateway route that LiteLLM documents, an OpenAI key with **Override OpenAI
Base URL**, was refused by Cursor before any request left: zero requests
reached the gateway. Claude on Foundry has no IDE route, so use the
[MCP fallback](#fallback-foundry-models-as-mcp-tools).

| Part | Status on 17 November 2026 |
| --- | --- |
| [Azure OpenAI slot to Foundry](#main-option-the-azure-openai-slot), OpenAI deployment | **Main option.** Reported working by staff and users [F31], [F8]. Here the plan gate was bypassed, and a dummy key then failed as expected. **Not run with a real key**; [check it with yours](#check-it-with-your-own-key) |
| [OpenAI key with Override Base URL to a LiteLLM gateway](#gateway-route-refused-by-cursor) | **Refused by Cursor.** The custom models are listed. Selecting one gives "This model does not support custom API keys"; sending gives "Invalid API key. Unauthorized User API key". **0 requests** reached the gateway |
| Azure OpenAI slot to a gateway or other non-Azure host | **0 requests** in two tests. LiteLLM documents this working on Cursor 3.17.21 [L2]; it didn't on 3.30.14 |
| Claude Haiku 5.5 on Foundry | **No route.** The Anthropic slot has no base URL [C11], and the gateway alias was refused like the GPT one |
| The LiteLLM gateway itself, both models, called directly | **Verified**: 15 of 15 Cursor-shaped cases on Docker 1.109.1 and on pip 1.108.4 |
| [Foundry models as MCP tools](#fallback-foundry-models-as-mcp-tools) | **Verified** end to end. Not a switch |

> **Tested with:** Cursor IDE 3.30.14 on Windows 11, individual Premium plan,
> 17 November 2026 ([`premium-round.json`](../evidence-snapshot/premium-round.json)).
> An earlier round on the Free plan stopped at the model picker: "More models
> are only available on paid plans".

## The routes

| Route | Foundry models | What you do | Status |
| --- | --- | --- | --- |
| [Main: Azure OpenAI slot](#main-option-the-azure-openai-slot) | OpenAI deployments | Fill three fields in **Models > API Keys > Azure OpenAI** | Reported working; plan gate passed here; real key not run |
| [Gateway: Override OpenAI Base URL](#gateway-route-refused-by-cursor) | GPT and Claude through LiteLLM | Run a public gateway, set the override, add custom models | Refused by Cursor 3.30.14 |
| [Fallback: MCP tools](#fallback-foundry-models-as-mcp-tools) | GPT and Claude | Cursor's model calls Foundry as a tool | **Verified**; not a switch |

## Before you start

- **A paid Cursor plan.** On Free the picker is locked. On individual plans
  your provider bills own-key requests and they don't use your included usage
  [C11]. On Team and Enterprise plans with pooled usage, own-key requests count
  toward usage limits, and a "Request higher limits" block appears before
  anything reaches Azure [F36].
- The [Foundry setup](setup.md) steps 1 to 3, and an **API key** for the
  resource, because the IDE can't use Entra ID. See
  [API-key access](setup.md#optional-api-key-access-for-the-ide-full-switch).
- **An OpenAI deployment.** Claude deployments don't work in this slot.
- Read [all the disadvantages](#all-the-disadvantages) first. In particular,
  Cursor's servers send the requests and receive your key with each one [C11].

## Main option: the Azure OpenAI slot

Open **Cursor Settings > Models**, expand **API Keys**, and scroll to
**Azure OpenAI**:

![Azure OpenAI section of Cursor Settings with the Use Azure OpenAI toggle and Base URL, Deployment Name and API Key fields, above the AWS Bedrock section](assets/ide-byok-azure-slot.png)

| Field | What to enter for Foundry |
| --- | --- |
| **Base URL** | `https://<resource>.openai.azure.com` and **nothing more**. Cursor staff, July 2026: "no /openai/v1 or anything else on the end, Cursor appends the rest", and point it at the `*.openai.azure.com` resource, not the Foundry project endpoint (`*.services.ai.azure.com`), "which we don't currently support" [F31]. Staff later said `*.cognitiveservices.azure.com` endpoints work too [F8] |
| **Deployment Name** | The exact name of your deployment, for example `cursor-poc-gpt-6-luna`. A wrong name can show the same error as a usage-limit block [F36] |
| **API Key** | A key of the Foundry resource (portal: **Keys and Endpoint**). Use **key 2** for a trial, so you can regenerate it afterwards without breaking anything that uses key 1 |
| **Use Azure OpenAI** | On, after the three fields are filled. An empty field with the toggle on breaks every model [F12] |

Turning the toggle on opens this dialog. Confirm it:

> Are you sure you want to enable your own Azure OpenAI API key? Several of
> Cursor's features require custom models (Tab, Apply from Chat, Agent), which
> cannot be billed to an API key.

Despite the wording, users report the Agent working on this slot [F31]. Then
pick the model:

1. **Add Custom Model** named exactly like your deployment, enable it, and
   select it in a new Agent chat. Users got the slot working this way when the
   built-in names didn't [F32]. LiteLLM reports that on this slot the
   **Deployment Name** decides which model answers, and the picked name is
   only a label [L2].
2. If the picker refuses the custom model, choose a built-in **GPT** model.
   With any key on, every model except Auto, Composer and Cursor's Grok goes
   through your keys [F11]. In this round GPT-5.2 stopped hitting the plan
   gate as soon as the slot was on ([below](#what-i-saw-with-a-dummy-key)).
3. Don't use **Auto**, Composer or Cursor's Grok to test. Auto never uses your
   keys [F13], and the other two refuse them with "This model does not support
   custom API keys" [F31], [F15].

### What I saw with a dummy key

To test this without saving a real key in Cursor, I filled the slot with a
dummy key and sent one Agent prompt with GPT-5.2 each time. Two of the four
tests pointed at a stub behind a temporary public tunnel, which logs every
request it receives.

| Test | Base URL | Result |
| --- | --- | --- |
| Control, slot off | n/a | "GPT-5.2 is not included in your weekly usage. Buy credits or switch to a Grok model to continue." |
| 1 | Bare tunnel host | "Rate limited by model provider, retrying..." and then "Network Error - We're having trouble connecting to the model provider". The stub logged **0 requests** |
| 2 | `<resource>.openai.azure.com`, no scheme | The same network error |
| 3 | `https://<tunnel host>` | The same network error. The stub logged **0 requests** |
| 4 | `https://<resource>.openai.azure.com` | The same network error |

What this shows:

- **The plan gate stopped applying.** With the slot off, Cursor refused
  GPT-5.2 on the plan's usage. With it on, Cursor tried the model provider
  instead, and failed on the dummy key.
- **Non-Azure hosts received nothing**, so you can't put a gateway behind this
  slot on 3.30.14, and I could not see the request shape it sends.
- **Tests 2 and 4 are inconclusive.** Azure Monitor doesn't record requests
  rejected with 401, so I can't tell whether Cursor reached Foundry with the
  dummy key.

### Check it with your own key

This is the one step the evidence still lacks. It puts your Foundry key into
Cursor, so it is your decision, and it is cheap to undo.

1. Fill the slot as above with **key 2**, turn it on, and confirm the dialog.
2. Start a new Agent chat in a test folder, choose the model, and send a small
   task such as "Read README.md and summarize it in one sentence."
3. Within ten minutes, in the repository with the [Foundry setup](setup.md):

   ```powershell
   $py = if ($IsWindows) { './.venv/Scripts/python.exe' } else { './.venv/bin/python' }
   & $py scripts/check_foundry_usage.py --minutes 10
   ```

   The script reads the `ModelRequests` metric of your deployment from Azure
   Monitor with your `az login`. Rows with status `200` mean Foundry served
   Cursor's requests. Metrics can lag a few minutes, and rejected keys (401)
   are never recorded.
4. **Regenerate key 2** in the portal when you finish, unless you keep using
   the slot.

### What has broken before

Every row is a dated forum report with a staff reply. Most were fixed, but the
pattern shows that Cursor updates have broken this slot for weeks at a time.

| When | What users saw | Cause and status | Sources |
| --- | --- | --- | --- |
| August 2025 | GPT-5 on Azure: internal server error; with the slot on, only Auto worked | Closed without a fix | [F33] |
| January to July 2026 | `model is required` with a deployment that works from curl | A Cursor bug with a hard-coded API version; a nightly build and a custom model named after the deployment helped; fixed in July | [F32] |
| May 2026 | A 502 from Cursor's backend | The reporter's base URL was misspelled | [F34] |
| June to July 2026 | Own-key requests dropped the model field: `400 invalid_input: model is required` | Requests were built without the model and rejected before reaching Azure; fixed 8 July | [F37] |
| July 2026 | GPT-5.x on Azure stopped working again, while curl worked | Fixes merged 22 July | [F35] |
| July 2026 | `response.failed` on GPT-5.4 and GPT-5.6 | Model-specific | [F10] |
| August 2026 | Manual `/summarize` failed with GPT-5.6 Luna on Azure; the autonomous Agent worked | Reported | [F31] |
| October 2026 | `Unknown parameter: 'reasoning'` with GPT-6 Astra | Some models go to Chat Completions with a Responses-only setting; known issue | [F9] |

Images you attach also bypass the custom URL and go to Cursor's provider
[F32].

## Gateway route: refused by Cursor

This is the setup LiteLLM documents for Cursor, with the gateway's public URL
as the OpenAI base URL [L2]. Microsoft documents the same override pattern for
Databricks AI Gateway [M9]. I ran it with one LiteLLM gateway serving both
Foundry models:

| Alias | Foundry model | How LiteLLM calls it |
| --- | --- | --- |
| `foundry-luna` | GPT-6 Luna | Always through the current Responses API, because Luna refuses tools on Chat Completions unless reasoning is off |
| `foundry-haiku` | Claude Haiku 5.5 | Through the Anthropic Messages route, dropping OpenAI-only parameters |

The aliases avoid `gpt-` and `claude-`. Cursor sends `claude-*` names to its
Anthropic slot, and it rejects custom names that match its own models [L2].

### Set up the gateway

Either install works. Both passed the same 15 cases.

**Docker (LiteLLM 1.109.1).** LiteLLM's Docker quickstart stores models in its
database (`STORE_MODEL_IN_DB=True`) and ignores a config file's `model_list`.
With the gateway running and `LITELLM_MASTER_KEY` set in your shell, register
both aliases. The script reads the Foundry key with `az` in memory and LiteLLM
stores it encrypted:

```powershell
& $py scripts/litellm_gateway.py register --url http://127.0.0.1:4000
```

**pip (LiteLLM 1.108.4).** Install LiteLLM in its own environment, not the
repository's `.venv`, then start it with the rendered config:

```powershell
py -3.12 -m venv .litellm
./.litellm/Scripts/python.exe -m pip install "litellm[proxy]"
$env:LITELLM_MASTER_KEY = "sk-<long random value>"
./.litellm/Scripts/python.exe scripts/litellm_gateway.py serve --litellm ./.litellm/Scripts/litellm.exe
```

`render` prints the same config without starting anything; it matches
[`config/litellm.config.example.yaml`](../config/litellm.config.example.yaml).
On Python 3.11 an older LiteLLM failed with a certificate-store error in my
environment; Python 3.12 worked.

Two settings make Luna work. The `openai/responses/` prefix sends every
request, Chat Completions included, to the Responses API, where Luna accepts
tools with reasoning on. And because a Foundry deployment name isn't in
LiteLLM's model map, `model_info` with `base_model: gpt-6-luna` and
`supports_reasoning: true` stops LiteLLM from refusing Cursor's `tool_choice`
and reasoning settings with `UnsupportedParamsError`.

Then check the gateway on the routes Cursor uses, before involving Cursor:

```powershell
$env:LITELLM_API_KEY = "<a LiteLLM virtual key>"
& $py scripts/probe_litellm_gateway.py --base-url http://127.0.0.1:4000 --out litellm-gateway-docker.json
```

It runs 15 cases: the model list, and for each alias plain text, a tool call,
a tool round trip, a streamed Responses-shaped tool call and its round trip,
and the Azure-slot route with an `api-key` header. It also checks that a
`-thinking-high` suffix resolves to the alias and that a wrong key is
rejected. Results:
[`litellm-gateway-docker.json`](../evidence-snapshot/litellm-gateway-docker.json)
and [`litellm-gateway.json`](../evidence-snapshot/litellm-gateway.json).

### Point Cursor at it

1. Give the gateway a **public HTTPS** address. Cursor's servers make the
   calls, so `localhost` and private addresses don't work [L2]. I used a
   temporary dev tunnel in front of the
   [capture proxy](#verify-what-cursor-sends), which forwarded to LiteLLM.
2. In LiteLLM, create a **virtual key** limited to the two aliases, with a
   budget and an expiry. Never give Cursor the master key.
3. In Cursor, **Models > API Keys > OpenAI API Key**: paste the virtual key,
   turn on **Override OpenAI Base URL** and set it to
   `https://<public host>/cursor`.
4. Turn on **Use OpenAI API Key** and confirm the dialog: "Are you sure you
   want to enable your own OpenAI API key? Several of Cursor's features require
   custom models (Tab, Apply from Chat, Agent), which cannot be billed to an
   API key."
5. **Add Custom Model** `foundry-luna` and `foundry-haiku`, and enable both.

![OpenAI API Key section with the Override OpenAI Base URL toggle, above the Anthropic API Key section that applies to all models beginning with claude-](assets/ide-byok-openai-anthropic.png)

### What happened

| Attempt | Result | Requests at the gateway |
| --- | --- | --- |
| Saving the key, the override and the custom models | Accepted | 0 |
| Model picker in the IDE and the Agents Window | `foundry-luna` and `foundry-haiku` are listed | n/a |
| `/model foundry-luna` in a new Agent chat | "Bad Request - This model does not support custom API keys." | 0 |
| Sending a prompt with `foundry-luna` or `foundry-haiku` | "Invalid API key. Unauthorized User API key" | 0 |
| A built-in name, GPT-5.2, mapped to Luna by a gateway alias | "Invalid API key. Unauthorized User API key" | 0 |

The capture log for the whole round holds only my own checks
([`premium-round.json`](../evidence-snapshot/premium-round.json)). LiteLLM's
own guide says "Cursor gates custom API keys by mode and model on its side, so
coverage follows what Cursor enables" [L2]. On 3.30.14 with a Premium plan,
the gate was closed for the Agent.

**Watch for a tempting false positive.** LiteLLM documents that Cursor calls
the gateway with `User-Agent: Cursor/1.0` [L2]. Two of my own reachability
checks through the tunnel used that header too, and later they looked like
requests from Cursor in the log. Don't fake that header in tests. If you
already did, tell the requests apart by their headers: my client sent no
`Accept-Encoding`, and both checks came before any key was saved in Cursor.

## Claude on Foundry: no IDE route

- Cursor sends every `claude-*` model to its **Anthropic API Key** slot, which
  has no base URL [C11], and users have asked for one since May 2026 [F3].
- Foundry serves Claude on the Anthropic Messages route and the Responses API,
  but returns **404** on Chat Completions
  ([the probe](#what-the-route-probe-shows)).
- The gateway alias `foundry-haiku` was refused like `foundry-luna`.

Use the [MCP fallback](#fallback-foundry-models-as-mcp-tools) for Claude.
Untested: whether the Azure slot, which uses the Responses API for some GPT
models [F9], would work with a Claude deployment name.

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
`reasoning_effort` is `none`, and Claude has no Chat Completions route. That is
why the gateway sends Luna through the Responses API and Claude through the
Anthropic route.

## What stays on Cursor

Even when the Azure slot works:

- **Tab completion** always uses Cursor's models [F22], [C11].
- **Auto, Composer and Cursor's own models** stay on Cursor; Composer and
  Cursor's Grok refuse to run while a key is on [F31], [F11].
- **Apply from Chat** is listed among the features that "cannot be billed to an
  API key" in the enable dialog.
- **Image attachments** go to Cursor's provider [F32].
- **The CLI and Cloud Agents** don't use the IDE's keys [O1], [F23], [F25]. See
  [CLI](cli.md#why-there-is-no-switch) and [Cloud](cloud.md#why-there-is-no-switch).
- **Prompt building** happens on Cursor's backend, which receives your key
  with each request. The documentation says the key is not stored [C11].

## All the disadvantages

This is the complete list of costs I found for the Azure slot, with the source
for each.

**Privacy and security**

- **Every request goes through Cursor's servers.** The key is sent "with every
  request" for final prompt building [C11]. It switches the *model endpoint*,
  not who handles your code.
- **Zero Data Retention no longer applies** with your own key; the provider's
  data handling does [C11], [C16].
- **Key only.** The slot takes an API key. It doesn't offer Entra ID or
  managed identity, so a long-lived resource key sits in Cursor.
- **The endpoint must be publicly reachable**, because Cursor calls it from the
  internet. There is no private endpoint or VNet route [L2].

**Coverage**

- **Chat and the Agent only.** Tab, Apply, Auto, Composer and Cursor's models
  stay on Cursor; the CLI and Cloud Agents don't use keys
  ([above](#what-stays-on-cursor)).
- **OpenAI deployments only.** Claude on Foundry has no IDE route
  ([above](#claude-on-foundry-no-ide-route)).
- **One deployment at a time.** There is one Azure slot, and on it the
  Deployment Name decides the model [L2]. There is no per-model base URL or
  per-model parameters such as reasoning effort [F20], [F29].
- **No gateway in between** on 3.30.14: non-Azure hosts received no requests,
  so you can't add logging, budgets or failover at your own gateway.

**Reliability**

- **A history of regressions.** Cursor updates broke Azure own-key requests
  several times in 2026, for weeks each time
  ([table](#what-has-broken-before)).
- **Model-specific failures** such as the `reasoning` parameter error [F9] and
  `response.failed` [F10].
- **Toggles have side effects.** An empty Azure field breaks every model [F12],
  Azure settings win over Bedrock [F13], and Cursor-only models fail while a
  key is on [F11], [F15].

**Cost and plan**

- **A paid plan.** Some plans exclude own keys [F22].
- **Pooled Team and Enterprise plans** count own-key requests toward usage
  limits [F36], and pay Cursor's token rate on top of Azure, $0.25 per million
  tokens at the time of writing [C11], [C17]. On individual plans the provider
  bills you and your included usage isn't used [C11].

**Support**

- **No dedicated Foundry integration, and no timeline** for one [F8].
- **No Microsoft Learn guide for Cursor on Foundry.** Learn documents the
  override pattern only for Databricks [M9].

## Pitfalls when you turn on an API key

Each row comes from Cursor staff replies on the forum.

| What happens | Why | Sources |
| --- | --- | --- |
| Composer or Cursor's Grok fails with "This model does not support custom API keys" | With a key or the override on, the credentials are attached to every request, and those models run only on Cursor. Auto still works | [F31], [F15] |
| Every model fails with `resource_exhausted` | **Use Azure OpenAI** was on with empty fields | [F12] |
| The Azure slot fails although curl works | Base URL with a path such as `/openai/v1`, a project endpoint (`*.services.ai.azure.com`), or a wrong deployment name | [F31], [F36] |
| "Request higher limits" with your own key | A pooled plan's usage limit; checked before Azure | [F36] |
| Claude or GPT models fail with a `tool_use` error | Remove the OpenAI base URL override or Azure key while using Anthropic models | [F17] |
| AWS Bedrock models fail with "Unknown parameter: 'system'" or invalid names | With both on, Azure settings win over Bedrock and Azure rejects the Claude-format request | [F13], [F14] |
| Anthropic own-key models are unusable while the override is on | The override is global | [F26] |
| Tab completion doesn't use your model | Your own keys apply to chat models only | [F22], [C11] |

## Verify what Cursor sends

Cursor's servers call your base URL, so don't paste a real Foundry key into a
test. [`scripts/capture_proxy.py`](../scripts/capture_proxy.py) records the
shape of each request (keys, tool names, `reasoning` fields, auth style) in a
local log. It has three modes:

| Mode | What it does | Use it for |
| --- | --- | --- |
| Default | Checks a throwaway shared secret, swaps in your Entra token and forwards the body unchanged to Foundry | Seeing what Foundry returns for Cursor's exact request |
| `--forward-to http://127.0.0.1:4000` | Passes the request to a local gateway, but only on model routes such as `/cursor/`, `/openai/deployments/` and `/v1/responses`; everything else gets 404 | Fronting LiteLLM without exposing its admin API |
| `--stub` | Forwards nothing and answers model routes with a canned "pong" | Testing a slot with a dummy key, so the secret unlocks no model |

1. Run it on `127.0.0.1`. It prints the shared secret unless you pass
   `--secret`.
2. Expose that port with a temporary public tunnel, such as a Microsoft dev
   tunnel, and delete the tunnel afterwards.
3. In Cursor, use the tunnel URL as the base URL and the shared secret as the
   key.
4. Read `evidence/proxy-capture.jsonl`. `--save-bodies` also keeps full
   bodies, which contain your code; delete them after use.

In the Premium round this proxy recorded **no request from Cursor** on any
route. Its logs are the evidence for the zero counts above.

**Never paste a key into a chat box.** During this round an automated
clipboard paste put a gateway virtual key into a Cursor chat. The key was
budget-limited and was revoked at once. Type keys only into settings fields,
and use keys you can revoke.

## Fallback: Foundry models as MCP tools

For code generation, regression tests and multi-turn work, see
[Does the MCP fallback work for real development?](development.md).
That comparison used a shell-invoked MCP client with the same bridge after
native CLI dispatch failed. It was not repeated through the IDE UI and does
not establish IDE development reliability or token savings.

Keep Cursor's own model as the agent and let it call Foundry deployments as
tools. This is **not** a switch: the agent still runs on Cursor and Cursor
sees every tool argument and result. It works with both GPT and Claude
deployments, uses Entra ID instead of keys, and works on any plan.

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

That run was on the Free plan, where the Agent itself ran on Grok 4.7 through
Cursor. Only the two tool calls were processed and billed by Foundry. Text you
send to a tool goes to both Foundry and Cursor; the Azure credential stays on
your machine.

## Troubleshooting

Problems with Azure, roles or deployments are covered in
[Foundry setup troubleshooting](setup.md#8-troubleshooting).

| Symptom | Cause and fix |
| --- | --- |
| "More models are only available on paid plans" | Own-key models need a paid plan. The MCP fallback works on Free. |
| "Network Error - We're having trouble connecting to the model provider" with the Azure slot | Check the Base URL is exactly `https://<resource>.openai.azure.com`, the deployment name is exact, and the key is from the same resource [F31]. Non-Azure hosts get no requests on 3.30.14. |
| "This model does not support custom API keys" | The model runs only on Cursor, or Cursor doesn't allow your custom model on this route. Turn the key off to use Cursor's models [F31]. |
| "Invalid API key. Unauthorized User API key" with the override | Cursor refused the custom model before calling your base URL. The gateway route isn't usable for the Agent on 3.30.14; use the Azure slot or MCP. |
| "Request higher limits" with your own key | Pooled plan limit, or a wrong deployment name [F36]. |
| `model is required` or `400 invalid_input` | A Cursor bug fixed in July 2026; update Cursor [F35], [F37]. |
| `Unknown parameter: 'reasoning'` with the Azure slot | Known issue for some models [F9]. Try another GPT deployment, or use the MCP fallback. |
| Every model fails after you set a key | See [pitfalls](#pitfalls-when-you-turn-on-an-api-key). Turn off **Use Azure OpenAI** and **Override OpenAI Base URL**, and clear empty fields. |
| `foundry-models` is missing in **Customize** | Open the folder that contains `.cursor/mcp.json` (`demo`), or copy the file to `~/.cursor/mcp.json`. |
| The server is listed but has no tools | It is turned off; project servers start off. Turn it on and wait for the green dot. |
| Red status or "The system cannot find the path specified" | Run `./scripts/Setup.ps1` again to rewrite absolute paths, then check with `smoke_test.py --transport mcp`. |
| The Agent answers without calling the tools | Name `foundry_openai` or `foundry_claude` in the prompt. |
| `check_foundry_usage.py` shows no rows | Wait a few minutes; metrics lag. A 401 (wrong key) is never recorded. |

## Clean up

1. **Cursor Settings > Models > API Keys:** turn off the key toggles you turned
   on, clear their fields, and remove or disable custom models you added.
2. **Delete test chats** that might contain a pasted key.
3. **Customize > MCPs > foundry-models:** turn it off if you don't use it.
4. Stop the gateway, the capture proxy and the tunnel, and delete the tunnel.
   Revoke LiteLLM virtual keys you gave to Cursor.
5. **Regenerate** any Foundry key that was saved in Cursor.
6. [Delete the deployments](setup.md#9-clean-up) you no longer need.

---

Source keys such as [F31] and [C11] refer to [Sources](../SOURCES.md).
