# Cursor Cloud Agents with Microsoft Foundry

**Verdict: no full switch, and Cursor says that is by design.** Cloud Agents
have no setting that runs their model on your Foundry deployments, so there is
nothing like Claude Code's Foundry mode here [A3]. The fallback is the same as
for the CLI: the agent keeps its Cursor model and calls Foundry as tools over
MCP. The difference is that the MCP server must be a **remote, authenticated
HTTP service**, because the agent runs in a Cursor-hosted VM that can't reach a
server on your laptop.

The switch was tested on an individual **Premium** plan (17 November 2026,
Cursor IDE 3.30.14). In the Agents Window's Cloud environment, a custom model
`foundry-luna`, served by a working LiteLLM gateway in front of Foundry, was
refused before any request reached the gateway
([`premium-round.json`](../evidence-snapshot/premium-round.json)):

```text
Model Not Available - The AI model you selected isn't available...
```

The MCP fallback below is a **blueprint. It has not been run**: it needs a
public, authenticated MCP service and a Cursor API key, and neither was
created [C3].

| Question | Answer | Status |
| --- | --- | --- |
| Can a Cloud Agent's own model run on Foundry? | No. No API field or setting exists | Documented by Cursor and confirmed by staff [F23]; a custom model gave "Model Not Available" on Premium |
| Can you bring your own provider key to Cloud Agents? | No | Staff say it is by design [F23]; users keep asking [F24]; OpenAI's guidance agrees [O1] |
| Can a Cloud Agent call Foundry models as tools? | Yes, through an HTTP MCP server you host | Blueprint; not run |
| Does the local `foundry-models` stdio server work there? | No. Cloud VMs can't reach `localhost` on your machine | By design |
| Do self-hosted workers move inference to Azure? | No. Cursor keeps the agent loop and model calls | Documented by Cursor [C8] |

## Why there is no switch

- **The API has no field for it.** A current create-agent request takes a
  model ID from Cursor's catalog, an environment, optional repositories and
  inline MCP servers [C5, C6]. There is no provider, endpoint, deployment or
  key field. The Cloud Agents API is not an OpenAI-style inference API.
- **Staff say it is by design.** A Cursor staff member explained in August
  2026 why there is no BYOK for Cloud Agents. Own keys are attached by the IDE
  client on each request, and a headless cloud run has no such client. Cloud
  runs also include VM compute, which Cursor provides. The same reasoning
  covers the CLI [F23]. Users keep asking for it, most recently in
  November 2026 [F24].
- **Self-hosted workers don't change it.** A worker runs tools, file edits,
  terminal commands and MCP servers on your machine, but Cursor still runs the
  agent loop, planning and model calls [C8].
- **OpenAI's own guidance excludes it.** Its steps for using OpenAI models in
  Cursor leave out Cloud Agents and the CLI [O1].
- **`envVars` doesn't change the provider.** It sets environment variables for
  the agent's shell and tools. Putting `AZURE_OPENAI_ENDPOINT` there doesn't
  route inference to Azure. The current API is in public beta, and its
  documentation warns that `envVars` can be silently ignored on accounts where
  it hasn't rolled out [C6].

The same gap exists on the [CLI](cli.md#why-there-is-no-switch). Only the
[IDE](ide.md) has an own-key route, and it needs a paid plan.

## Fallback: Foundry models as MCP tools

A Cloud Agent can reach Foundry the way the CLI and IDE do, by calling tools on
an MCP server. This does not change the agent's model: Cursor still runs it.

Two details matter when you build on the API:

- **Use HTTP or stdio MCP.** The API reference lists an `sse` value, but the
  capabilities guide excludes SSE [C6, C7]. The legacy API has no MCP support
  at all. Don't copy its `source` and string `model` request shape into a new
  integration [C12].
- **Cursor's VM can't reach your laptop.** The local `foundry-models` stdio
  bridge runs on your machine, so a Cloud Agent needs a network-reachable
  service instead.

### Architecture that would work

```mermaid
flowchart LR
    C[Cursor Cloud Agent<br/>model runs on Cursor] -->|HTTPS MCP call + bearer token| G[Your MCP service<br/>in Azure]
    G -->|Managed identity| O[Foundry OpenAI deployment]
    G -->|Managed identity| A[Foundry Claude deployment]
```

The service would expose the same two tools as the local bridge,
`foundry_openai` and `foundry_claude`, and call Foundry with a managed
identity. Then no Azure secret enters the Cursor VM.

### Request blueprint

[`config/cloud-agent.request.example.json`](../config/cloud-agent.request.example.json)
shows the current create-agent request with an HTTP MCP server:

```json
{
  "name": "Foundry inference tool experiment",
  "prompt": {
    "text": "Use only synthetic data. Call the foundry-models MCP tools foundry_openai and foundry_claude, asking each to add 17 and 25. Report each response_id, deployment, model, and answer. Do not claim that the Cloud Agent's own model runs on Foundry."
  },
  "autoCreatePR": false,
  "mcpServers": [
    {
      "name": "foundry-models",
      "type": "http",
      "url": "https://foundry-mcp.example.invalid/mcp",
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_YOUR_MCP_SERVICE_TOKEN_NOT_AN_AZURE_KEY"
      }
    }
  ]
}
```

- The `.invalid` host and the token placeholder are intentional. **This file
  is not a working service.**
- It leaves out `repos`, which is the documented shape for an agent without a
  repository.
- It leaves out `model`, so Cursor uses its default model. That is a Cursor
  model, not a Foundry deployment.
- Its structure was checked against the current create-agent schema. No
  request was sent.

### What is still missing

1. **A Cursor API key** for the API, on a plan that includes Cloud Agents.
   Free and Plus plans don't [C5].
2. **A network-reachable MCP service** with the two tools and real
   authentication. The local bridge in this repository is stdio-only and has
   no HTTP authentication.
3. **Least-privilege Azure access** for that service. Give its managed
   identity the **Cognitive Services User** role on the Foundry resource only
   [M8].
4. **A real run with a fresh challenge**, checked against the service's Azure
   request logs, as [`verify_cursor.py`](cli.md#4-run-the-full-end-to-end-check)
   does for the CLI.

None of this was created for the investigation. There was no Cursor API key,
no public MCP service, no Entra application and no role assignment.

## OIDC: useful, but not automatic Azure access

Cloud Agents can request short-lived OIDC tokens through a local socket in the
VM. The issuer is `https://api.cursor.com`, tokens last five minutes, and the
receiving side must check the audience and subject [C10].

With an Entra **federated identity credential** that trusts those tokens, an
agent could get an Azure token without a stored secret. A Cursor OIDC token is
not itself a Foundry token, so you still have to set up the trust and the
token exchange. This was researched, not configured.

## Self-hosted workers

A self-hosted worker can host the stdio bridge next to your Foundry resource,
for example on an Azure VM. The main model still runs on Cursor, and file
contents and tool results still go to Cursor [C8].

## Privacy

- Cloud Agent conversations and environment snapshots have their own
  retention and secret-handling rules [C13].
- A **stdio** MCP server inside the cloud VM exposes its configuration and
  environment to that VM. Cursor recommends **HTTP** MCP when server
  credentials should stay out of the agent's VM [C7].
- With either transport, Cursor sees the prompts you send to the tools and the
  answers they return. Foundry processes only the tool calls.

See [Data boundaries and governance](governance.md#retention-is-different-at-every-layer)
for the separate conversation and snapshot retention periods, geographic
limits and enterprise controls. Self-hosting execution does not self-host
Cursor's agent loop.

---

Source keys such as [C5] and [M8] refer to [Sources](../SOURCES.md).
