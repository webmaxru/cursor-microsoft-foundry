# Cursor Cloud Agents with Microsoft Foundry

**Verdict:** Cloud Agents have **no setting that runs their model on your
Foundry deployments**. They can reach Foundry the same way the CLI and IDE do,
by calling tools on an MCP server. The difference is that the server must be a
**remote, authenticated HTTP service**, because the agent runs in a
Cursor-hosted VM that can't reach a server on your laptop.

This page is a **blueprint. It has not been run.** The test account was on
Cursor's Free plan, which doesn't include Cloud Agents, and no Cursor API key
was available [C3, C5].

| Question | Answer | Status |
| --- | --- | --- |
| Can a Cloud Agent's own model run on Foundry? | No documented setting | Documented by Cursor |
| Can a Cloud Agent call Foundry models as tools? | Yes, through an HTTP MCP server you host | Blueprint; not run |
| Does the local `foundry-models` stdio server work there? | No. Cloud VMs can't reach `localhost` on your machine | By design |
| Do self-hosted workers move inference to Azure? | No. Cursor keeps the agent loop and model calls | Documented by Cursor [C8] |

## What the current Cloud Agents API offers

Cloud Agents run in isolated remote environments with a curated set of models.
The Cloud Agents API creates and manages agents; it is not an OpenAI-style
inference API. A current create request takes [C5, C6]:

- a **model** ID from Cursor's model catalog, with optional parameters
- an execution environment, optionally with a repository
- inline **MCP server** definitions, over HTTP or stdio

There is no field for an Azure endpoint, a Foundry deployment or a provider
credential.

Two details matter when you build on this:

- **Use HTTP or stdio MCP.** The API reference lists an `sse` value, but the
  capabilities guide excludes SSE [C6, C7]. The legacy API has no MCP support
  at all. Don't copy its `source` and string `model` request shape into a new
  integration [C12].
- **`envVars` doesn't change the model provider.** It sets environment
  variables for the agent's shell and tools. The current API is in public beta,
  and its documentation warns that `envVars` can be silently ignored on
  accounts where it hasn't rolled out. Putting `AZURE_OPENAI_ENDPOINT` there
  doesn't route inference to Azure [C6].

## Architecture that would work

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

1. **A Cursor plan with Cloud Agents**, plus a Cursor API key for the API.
   Free and Plus plans don't include Cloud Agents [C5].
2. **A network-reachable MCP service** with the two tools and real
   authentication. The local bridge in this repository is stdio-only and has
   no HTTP authentication.
3. **Least-privilege Azure access** for that service. Give its managed
   identity the **Cognitive Services User** role on the Foundry resource only
   [M8].
4. **A real run with a fresh challenge**, checked against the service's Azure
   request logs, as [`verify_cursor.py`](cli.md#4-run-the-full-end-to-end-check)
   does for the CLI.

None of this was created for the investigation. There was no plan upgrade, no
Cursor API key, no public service, no Entra application and no role
assignment.

## OIDC: useful, but not automatic Azure access

Cloud Agents can request short-lived OIDC tokens through a local socket in the
VM. The issuer is `https://api.cursor.com`, tokens last five minutes, and the
receiving side must check the audience and subject [C10].

With an Entra **federated identity credential** that trusts those tokens, an
agent could get an Azure token without a stored secret. A Cursor OIDC token is
not itself a Foundry token, so you still have to set up the trust and the
token exchange. This was researched, not configured.

## Self-hosted workers

A self-hosted worker runs tools, file edits, terminal commands and MCP servers
on your machine, for example an Azure VM. Cursor still runs the agent loop,
planning and model calls [C8]. A worker on Azure can host the stdio bridge
next to your Foundry resource, but the main model still runs on Cursor, and
file contents and tool results still go to Cursor.

## Privacy

- Cloud Agent conversations and environment snapshots have their own
  retention and secret-handling rules [C13].
- A **stdio** MCP server inside the cloud VM exposes its configuration and
  environment to that VM. Cursor recommends **HTTP** MCP when server
  credentials should stay out of the agent's VM [C7].
- With either transport, Cursor sees the prompts you send to the tools and the
  answers they return. Foundry processes only the tool calls.

See [Findings: privacy, credentials, billing and residency](../FINDINGS.md#5-privacy-credentials-billing-and-residency)
for details that apply to every surface.

---

Source keys such as [C5] and [M8] refer to [Sources](../SOURCES.md).
