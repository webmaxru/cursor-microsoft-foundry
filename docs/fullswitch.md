# Can Cursor fully switch to Microsoft Foundry?

**Short answer: not the way Claude Code can.** Claude Code has a Foundry mode:
set `CLAUDE_CODE_USE_FOUNDRY=1`, name your resource, and the agent's own model
calls go straight to your Foundry deployments, signed in with Entra ID or a
key [A3]. Cursor has no equivalent. The closest thing is one key slot in the
**IDE** that sends **OpenAI** deployments' requests to your Foundry resource,
through Cursor's servers. The CLI and Cloud Agents have nothing.

I tested every surface again on a **Premium** plan with a local LiteLLM
gateway in front of both Foundry models. **Cursor sent no request to the
gateway on any surface.** A later round used the resource's **real key** in the
IDE's Azure slot and a purpose-built Claude proxy. **Foundry and the proxy
recorded no request from Cursor either.**

| Surface | Full switch to Foundry? | The route | What was verified here |
| --- | --- | --- | --- |
| [Cursor IDE](ide.md) | **OpenAI deployments only, through the Azure OpenAI slot, on paper.** Chat and Agent; not Tab, Auto or Composer | **Models > API Keys > Azure OpenAI** with `https://<resource>.openai.azure.com` | Reported working by staff and users [F31], [F8]. Here, with the resource's real key on Premium, **it failed in 4 of 4 tests**: "Network Error" after about 19 seconds, and **0 requests** in Foundry's metrics and request logs, while the same key returned 200 directly ([real-key round](ide.md#what-happened-with-a-real-key)). The OpenAI key with Override Base URL to a gateway was **refused**, with 0 requests at the gateway |
| [Cursor CLI](cli.md) | **No** | None. `--model` accepts only Cursor's catalog; the only provider command is AWS Bedrock | "Cannot use this model: foundry-luna" on Premium; 0 gateway requests |
| [Cursor Cloud Agents](cloud.md) | **No, by design** | None. The API takes a Cursor model ID and MCP servers, nothing for a provider | "Model Not Available" for the custom model on Premium; 0 gateway requests |
| Claude on Foundry, any surface | **No** | Cursor's Anthropic slot has no base URL, and Foundry has no Chat Completions route for Claude | The LiteLLM alias was refused like the GPT one; a [translating proxy](ide.md#can-a-proxy-bring-claude-to-the-ide) passed 13 of 13 direct cases and got 0 requests from the Azure slot or the override |

Where no switch exists, the fallback is to keep Cursor's own model and let it
call Foundry deployments as **MCP tools**. That works on all three surfaces
(verified on the CLI and IDE, blueprint for Cloud) but it is **not** a switch:
Cursor's model still runs on Cursor. Read [what MCP does and doesn't do](#what-the-mcp-fallback-does-and-doesnt-do).

> **As of 17 November 2026.** Tested with Cursor CLI `2026.11.13-eacade1` and
> Cursor IDE `3.30.14` on an individual **Premium** plan, with LiteLLM 1.109.1
> (Docker) and 1.108.4 (pip). An earlier round on the Free plan stopped at the
> model picker. Check the [sources](../SOURCES.md) before relying on any of
> it; Cursor changes these settings often.

## Claude Code and Cursor, side by side

| | Claude Code with Foundry [A3] | Cursor |
| --- | --- | --- |
| Switch | One environment variable, `CLAUDE_CODE_USE_FOUNDRY=1` | One IDE key slot for Azure OpenAI; nothing in the CLI or Cloud Agents |
| Where the agent's model calls go | Directly from your machine to the Foundry resource | From Cursor's servers: the IDE sends your key to Cursor with every request and Cursor builds the prompt [C11] |
| Sign-in | Resource API key, Entra ID (the default Azure credential chain, so `az login` works) or a bearer token | A resource API key only. No Entra ID |
| Claude on Foundry as the main model | Yes: you pin model names to your deployments with `ANTHROPIC_DEFAULT_*_MODEL` | No. The Anthropic slot has no base URL; a LiteLLM alias was refused and a translating proxy got no request |
| OpenAI models on Foundry as the main model | Not applicable | IDE only, one deployment at a time, through the Azure OpenAI slot; failed here with a real key |
| A gateway in between | Not needed | Documented by LiteLLM [L2], but refused by Cursor 3.30.14 on Premium |
| What moves to Foundry | The agent's model calls | At most the IDE's chat and Agent requests for GPT models. Tab, Auto, Composer, the CLI and Cloud Agents stay on Cursor |

The comparison explains why the question has a different answer in each
product. Claude Code calls Foundry from your machine. Cursor sends model
requests from its own servers and decides, per model and mode, whether your
key may be used at all. LiteLLM's own Cursor guide puts it this way: "Cursor
gates custom API keys by mode and model on its side, so coverage follows what
Cursor enables" [L2].

## What the community says

I read the forum threads linked from the sources through their public JSON
view, checked the dates, and searched Hacker News and Stack Overflow. The
picture is consistent:

- **The Azure slot works, when it works.** Staff in July 2026: the Base URL is
  only `https://<resource>.openai.azure.com`, "Cursor appends the rest", and a
  Foundry project endpoint (`*.services.ai.azure.com`) is not supported. The
  user confirmed it worked, and later ran GPT-5.6 Luna in the Agent [F31].
  Staff in November 2026: Foundry OpenAI deployments should work, with no
  dedicated Foundry integration and no timeline [F8]. It didn't work in this
  study's [real-key round](ide.md#what-happened-with-a-real-key).
- **It breaks often.** Cursor-side bugs stopped Azure own-key requests for
  weeks at a time: `model is required` from January to July 2026 [F32], [F35],
  [F37], and GPT-5 errors in 2025 that closed without a fix [F33]. Other
  failures were configuration: a misspelled URL [F34], a wrong deployment
  name [F36], or an empty Azure field that breaks every model [F12].
- **Model-specific failures** keep appearing: `response.failed` on GPT-5.4 and
  GPT-5.6 [F10], and `Unknown parameter: 'reasoning'` on GPT-6 Astra, which
  matches the 400 on the [IDE page](ide.md#what-the-route-probe-shows) [F9].
- **Cursor-only models refuse your key.** With any key on, Composer and
  Cursor's Grok fail with "This model does not support custom API keys", and
  Auto keeps working because it never uses your key [F31], [F11], [F13].
- **Plans matter.** On pooled Team and Enterprise plans, own-key requests
  count toward usage limits, and a "Request higher limits" block appears
  before Azure [F36].
- **The override is global.** One OpenAI base URL serves every OpenAI-family
  model, Cursor-managed ones included [F27], and Claude own-key models stay
  unusable while it is on [F26]. Per-model base URLs have "no concrete
  timeline" [F20], [F29].
- **Cloud Agents and CLI:** no provider keys. Staff explained that keys are
  attached by the IDE client on each request, and headless runs have no such
  client [F23], [F25]. Users have asked since May 2026 [F24].
- **Claude on Foundry:** requested since December 2025 [F2], [F3]. A
  community proxy exists, but its author used it mainly with Ctrl+K, not the
  Agent [F6].
- **Outside the forum:** a 2025 Hacker News comment suggests running Cursor
  through LiteLLM for per-project keys and budgets [H1]; another notes that
  own-key requests still go through Cursor's servers [H2]. A Stack Overflow
  answer gives the same advice as staff: the Deployment Name must match
  exactly [Q1].

### What the community built

Two kinds of project exist. Neither was run here.

**Gateways for the IDE's override.** These sit where I put LiteLLM: Cursor's
servers call them, and they call your provider.

| Project | What it does | Status |
| --- | --- | --- |
| LiteLLM [L2] | General gateway with a documented Cursor route | Tested directly here (15 of 15); Cursor refused to use it on 3.30.14 |
| gabrii/Cursor-Azure-GPT-5 [G3] | Turns override requests into Azure Responses API calls | 75 stars, MIT. Recommended by Cursor staff in April 2026 [F32] |
| rosch100/AI-Model-proxy [G4] | Copy of G3 with newer models, including Luna | Archived |
| xFurti/cursor-custom-provider [G5] | Model-name rewriting plus an automatic HTTPS tunnel | 19 stars, MIT |
| 0xSero/factory-cursor-bridge [G6] | Translates between OpenAI and Anthropic formats | 85 stars, no license |
| bcat95/Cursor-Azure-Claude [G7] | OpenAI to Anthropic for Azure-hosted Claude | 11 stars; used mainly with Ctrl+K [F6] |
| Alorse/llm-proxy [G8] | Aliases a model under a name Cursor accepts | 24 stars; last push July 2025 |

All of them depend on the same Cursor gate that refused LiteLLM here. If
Cursor doesn't call your base URL, no gateway helps.

**Backend replacements.** These install a local certificate authority,
intercept Cursor's own traffic and answer it locally, so Cursor never talks to
its servers. They can route every request, including the CLI's, but they
impersonate Cursor, can break with any update, and see everything you send.

| Project | Notes |
| --- | --- |
| leookun/cursor-byok [G2] | About 3,200 stars; archived October 2026; Tab completion defaults to the author's service |
| hainuoli/cursor-byok [G9] | Active successor, v1.1.0 on 14 November 2026 |
| Yimikami/cursor-byok [G10] | Desktop app, "without Pro account" |
| sherkevin/cursor-agent-byok [G1] | Claims to support the CLI. Its published source forwards to a local port that nothing in the repository serves, and never passes on the provider URL or key you enter |

I don't recommend the backend replacements for work code. Read
[Coverage limits](../SOURCES.md#coverage-limits) for what this survey doesn't
cover.

### What I could not find

- Reddit and X could not be read without signing in, so they are not
  covered.
- Only Claude Code was checked against its documentation. OpenCode and Codex
  have Azure provider settings in their documentation [X1], [X2]; I did not
  run them. Cline, Roo, Continue and Copilot's bring-your-own-key options were
  not checked.
- Staff replies sometimes disagree. In June 2026 a staff member wrote that
  requests go directly to your provider [F1]; the current documentation says
  they pass through Cursor's servers [C11]. I follow the documentation.
- LiteLLM documents the Azure slot reaching a gateway on Cursor 3.17.21 [L2].
  On 3.30.14 it didn't. I can't tell whether Cursor changed it or the plan
  matters.

## Why the CLI and Cloud Agents have no switch

- **CLI:** on Premium, `agent models` lists about 300 Cursor models and no
  custom ones, and `agent -p --model foundry-luna` answers "Cannot use this
  model". `--endpoint` is Cursor's own service: pointed at a local listener,
  the CLI called `aiserver.v1` Connect services with `application/proto`
  bodies and never sent an OpenAI or Anthropic request. The only provider
  command is `bedrock`, for AWS ([`cli-fullswitch.json`](../evidence-snapshot/cli-fullswitch.json),
  [`premium-round.json`](../evidence-snapshot/premium-round.json)). Details on
  the [CLI page](cli.md#why-there-is-no-switch).
- **Cloud Agents:** the create-agent API takes a Cursor model ID,
  environment, repositories and MCP servers. It has no provider, endpoint or
  key field. A cloud chat with the custom model `foundry-luna` gave "Model
  Not Available". Self-hosted workers only move where tools run [C6], [C8].
  Details on the [Cloud page](cloud.md#why-there-is-no-switch).

## The IDE switch and its costs

The IDE route is documented but narrow, and it failed here with a real key.
The [IDE page](ide.md#all-the-disadvantages) lists every disadvantage. In short:

- **It may not work at all.** With the resource's real key on Premium,
  Cursor's backend gave "Network Error" in four tests and Foundry logged no
  request. Others report it working, and it has broken after past updates.
- Requests still go through Cursor's servers, with your key, so Foundry must be
  reachable from the public internet. Private endpoints and Entra ID don't fit.
- OpenAI deployments only, one at a time. No Claude.
- Tab, Auto, Composer, Apply, image attachments, the CLI and Cloud Agents stay
  on Cursor.
- No gateway or proxy in between on 3.30.14, so no logging, budgets or
  failover of your own.
- Repeated breakages after Cursor updates, and several staff-confirmed side
  effects when toggles are on.
- A paid plan; on pooled plans Cursor's token rate and usage limits apply too.

## Other routes to a full switch

- **A gateway you run.** LiteLLM [L2] and Databricks AI Gateway [M9] document
  Cursor's override for this. My LiteLLM gateway passed all 15 Cursor-shaped
  cases against both Foundry models
  ([`litellm-gateway-docker.json`](../evidence-snapshot/litellm-gateway-docker.json)),
  and a purpose-built [Claude proxy](ide.md#can-a-proxy-bring-claude-to-the-ide)
  passed 13 of 13, but Cursor 3.30.14 sent neither anything. Re-test after
  Cursor updates; the [IDE page](ide.md#gateway-route-refused-by-cursor) has
  the setup and the probe.
- **A backend replacement.** See [above](#what-the-community-built). Not
  recommended.
- **Another agent.** If every token must go to Foundry, use a tool built for
  it, such as Claude Code [A3]. OpenCode and Codex document Azure providers
  [X1], [X2].

## What the MCP fallback does and doesn't do

The local `foundry-models` MCP server gives Cursor's agent two tools,
`foundry_openai` and `foundry_claude`. The agent decides when to call them.

- **Doesn't do:** change the model that runs Cursor. You still need Cursor
  models, still pay Cursor for them, and Cursor sees every tool argument and
  result.
- **Does:** let a Foundry deployment do work you delegate, billed to your Azure
  subscription, with the Azure credential staying on your machine. Verified on
  the [CLI](cli.md#fallback-foundry-models-as-mcp-tools) and the
  [IDE](ide.md#fallback-foundry-models-as-mcp-tools).

Use it when a surface has no switch, for Claude on Foundry, or next to the
Azure slot when you want both.

For practical limits rather than another connectivity proof, see
[MCP for real development](development.md): a greenfield project, follow-up
changes, a new-session handoff, and separate Cursor/Foundry usage.
The measured shell-client workaround completed the planned features but
increased Cursor output usage and elapsed time; native CLI discovery failed.

---

Source keys such as [A3] and [F23] refer to [Sources](../SOURCES.md).
