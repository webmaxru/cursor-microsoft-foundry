# Can Cursor fully switch to Microsoft Foundry?

**Short answer: not the way Claude Code can.** Claude Code has a Foundry mode:
set `CLAUDE_CODE_USE_FOUNDRY=1`, name your resource, and the agent's own model
calls go straight to your Foundry deployments, signed in with Entra ID or a
key [A3]. Cursor has no equivalent on any surface. The Cursor IDE has the
closest thing: key slots that send **chat-model** requests to an OpenAI-format
endpoint, through Cursor's servers. The CLI and Cloud Agents have nothing.

| Surface | Full switch to Foundry? | The route | What was verified here |
| --- | --- | --- | --- |
| [Cursor IDE](ide.md) | **Partial.** Chat and Agent models only, OpenAI format only, paid plan | **Azure OpenAI** key slot, or OpenAI key with **Override OpenAI Base URL** | Settings screens captured. Foundry accepts the requests such a slot sends (12 of 12 probes with a resource key). **Cursor's own request was not observed**: the Free plan locks the model picker |
| [Cursor CLI](cli.md) | **No** | None. `--endpoint` is Cursor's own service; `--model` accepts only Cursor's catalog | Tested on the installed CLI |
| [Cursor Cloud Agents](cloud.md) | **No, by design** | None. The API has a model ID and MCP servers, nothing for a provider | Staff statement and the API schema; not run (paid plan) |

Where no switch exists, the fallback is to keep Cursor's own model and let it
call Foundry deployments as **MCP tools**. That works on all three surfaces
(verified on the CLI and IDE, blueprint for Cloud) but it is **not** a switch:
Cursor's model still runs on Cursor. Read [what MCP does and doesn't do](#what-the-mcp-fallback-does-and-doesnt-do).

> **As of 17 November 2026.** Tested with Cursor CLI `2026.11.13-eacade1` and
> Cursor IDE `3.30.14` on the Free plan. Check the [sources](../SOURCES.md)
> before relying on any of it; Cursor changes these settings often.

## Claude Code and Cursor, side by side

| | Claude Code with Foundry [A3] | Cursor |
| --- | --- | --- |
| Switch | One environment variable, `CLAUDE_CODE_USE_FOUNDRY=1` | A set of IDE key slots; nothing in the CLI or Cloud Agents |
| Where the agent's model calls go | Directly from your machine to the Foundry resource | From Cursor's servers: the IDE sends your key to Cursor with every request and Cursor builds the prompt [C11] |
| Sign-in | Resource API key, Entra ID (the default Azure credential chain, so `az login` works) or a bearer token | A resource API key only. No Entra ID |
| Claude on Foundry as the main model | Yes: you pin model names to your deployments with `ANTHROPIC_DEFAULT_*_MODEL` | No. Cursor's Anthropic key slot has no base URL, and Foundry rejects Claude on Chat Completions. A translating gateway is needed |
| OpenAI models on Foundry as the main model | Not applicable | IDE only, through the Azure OpenAI slot |
| What moves to Foundry | The agent's model calls | Only the IDE's chat models. Tab, Auto, Composer, the CLI and Cloud Agents stay on Cursor |

The comparison explains why the question has a different answer in each
product. Claude Code calls Foundry from your machine. Cursor sends model
requests from its own servers, so a custom endpoint has to be reachable by
Cursor and speak a format Cursor chooses.

## What the community says

I read the forum threads linked from the sources, through their public JSON
view, and checked the dates. The picture is consistent:

- **Cloud Agents:** users have asked for BYOK since May 2026 [F24]. A Cursor
  staff reply in August 2026 explained why there is none: keys are attached by
  the IDE client on each request, a headless cloud run has no such client, and
  cloud runs include VM compute. The same reasoning covers the CLI [F23].
- **CLI:** in November 2026 staff said the CLI does not support provider keys
  [F25]. Users report that IDE Azure settings and provider environment
  variables don't affect it [F4].
- **IDE, Foundry:** staff said in November 2026 that Foundry OpenAI deployments
  should work through the Azure OpenAI slot, with no dedicated Foundry
  integration and no timeline [F8].
- **IDE, reliability:** a February 2026 thread says Azure models are unreliable
  in the Agent, and staff pointed at tool-schema problems for file operations
  and missing Responses API support on Azure [F28]. A July 2026 thread reports
  `response.failed` errors on GPT-5.4 and GPT-5.6 [F10], and an October 2026
  one the `reasoning` error shown on the [IDE page](ide.md#what-the-route-probe-shows) [F9].
- **IDE, the global override:** one Override URL and one key serve every
  OpenAI-family model. Staff confirmed in August 2026 that Cursor-managed
  models are routed through it too [F27]. A November 2026 report says Claude
  BYOK stays unusable while the override is on [F26]. Others report the
  override failing outright [F30].
- **Per-model base URLs:** users asked for them; staff gave no concrete
  timeline [F20, F29].
- **Claude on Foundry:** requested since December 2025 [F2, F3]. A community
  proxy exists, but its author used it mainly with Ctrl+K, not the Agent [F6].

### What I could not find

- No primary posts from Reddit, Hacker News, X or Stack Overflow were opened.
  The evidence is the Cursor forum plus documentation, not a survey of all
  public opinion.
- Only Claude Code was checked against its documentation. OpenCode and Codex
  have Azure provider settings in their documentation [X1, X2]; I did not run
  them. Cline, Roo, Continue and Copilot's bring-your-own-key options were not
  checked.
- Staff replies sometimes disagree. In June 2026 a staff member wrote that
  requests go directly to your provider [F1]; the current documentation says
  they pass through Cursor's servers [C11]. I follow the documentation. Staff
  also cite `*.cognitiveservices.azure.com` endpoints [F8], while the slot's
  own placeholder shows `*.openai.azure.com`.

## Why the CLI and Cloud Agents have no switch

- **CLI:** I pointed `--endpoint` at a local listener. With real sign-in the
  CLI called `aiserver.v1` Connect services (`DashboardService/GetMe` and
  others) with `application/proto` bodies and ended with `[unimplemented]`; it
  never sent an OpenAI or Anthropic request. `--model cursor-poc-gpt-6-luna`
  was refused with a list of Cursor's own models. The only provider command is
  `bedrock` ([`cli-fullswitch.json`](../evidence-snapshot/cli-fullswitch.json)).
  Details on the [CLI page](cli.md#why-there-is-no-switch).
- **Cloud Agents:** the create-agent API takes a Cursor model ID,
  environment, repositories and MCP servers. It has no provider, endpoint or
  key field. Self-hosted workers only move where tools run [C6, C8]. Details on
  the [Cloud page](cloud.md#why-there-is-no-switch).

## The IDE switch and its costs

The IDE route is real but narrow, and it has many trade-offs. The
[IDE page](ide.md#all-the-disadvantages) lists all of them. In short:

- Requests still go through Cursor's servers, with your key, so Foundry must be
  reachable from the public internet. Private endpoints and Entra ID don't fit.
- OpenAI format only. Claude needs a translating gateway such as LiteLLM, and
  the model alias must not start with `claude`.
- Tab, Auto, Composer, the CLI and Cloud Agents stay on Cursor.
- One global override, no per-model settings, and several staff-confirmed side
  effects when toggles are on.
- A paid plan, and the Teams token rate applies on top.

## Other routes to a full switch

None of these is a Cursor setting, and none was tested through Cursor.

- **A gateway you run.** Cursor's override can point at a LiteLLM proxy [L2]
  or a Databricks AI Gateway, which Microsoft documents for Cursor with the
  same Override OpenAI Base URL and custom-model steps [M9]. For Foundry Claude
  I ran LiteLLM 1.108.4 locally and it passed text, tool calls, a tool-result
  round trip and streaming ([`litellm-gateway.json`](../evidence-snapshot/litellm-gateway.json)).
  The gateway also means Cursor holds a revocable gateway key and not the
  Foundry resource key. I did not verify that benefit through Cursor.
- **Unofficial CLI bridges.** The community project [G1] claims to run the
  Cursor agent CLI against OpenAI- or Anthropic-compatible endpoints. It has
  3 stars, and I did not evaluate how it works, so I can't say it is safe or
  supported. An older project [G2] is archived. A third [G3] targets Azure
  GPT-5 in the IDE.
- **Another agent.** If every token must go to Foundry, use a tool built for
  it, such as Claude Code [A3]. OpenCode and Codex document Azure providers
  [X1, X2].

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

Use it when a surface has no switch, or next to the IDE switch when you want
Claude on Foundry without a gateway.

---

Source keys such as [A3] and [F23] refer to [Sources](../SOURCES.md).
