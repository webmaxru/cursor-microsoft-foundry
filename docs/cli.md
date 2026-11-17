# Cursor CLI with Microsoft Foundry

**Verdict: no full switch.** The Cursor CLI has no setting that sends its own
model calls to Foundry, so nothing here resembles Claude Code's Foundry mode
[A3]. `--endpoint` points at Cursor's own service, `--model` accepts only
Cursor's catalog, and provider environment variables are ignored. The fallback
is to keep Cursor's model and let the CLI agent call Foundry deployments as
**MCP tools**. That was **verified end to end in the earlier arithmetic
proof**, but the agent still runs on Cursor. New development sessions could
not discover the native tools; the [development study](development.md)
separates that failure from a shell-invoked MCP-client workaround.

| You want to... | Status |
| --- | --- |
| Make a Foundry deployment the CLI's main model | **Not possible** ([evidence](#why-there-is-no-switch)) |
| Point `--endpoint` at Foundry | Doesn't work: it is Cursor's own protobuf service |
| Use your own provider key, the way the IDE does | Not supported by the CLI [F25]; still refused on Premium |
| Put a gateway such as LiteLLM in front of Foundry and pick it in the CLI | **Refused**: "Cannot use this model", 0 requests at the gateway |
| Let the CLI agent call Foundry OpenAI and Claude models as tools | Earlier arithmetic proof verified; native dispatch failed in the new development sessions. See [the practical study](development.md) before relying on it |

> **Tested with:** Cursor CLI `2026.11.13-eacade1` on Windows 11, first on a
> Free account and again on an individual **Premium** plan (17 November 2026).
> The full-switch results didn't change. The MCP fallback needs [Foundry setup](setup.md)
> steps 1 to 7.

## Why there is no switch

I tested each place a switch could live.

### `--endpoint` is Cursor's service, not an inference base URL

`agent --help` lists `--endpoint` / `CURSOR_API_ENDPOINT`, defaulting to
`https://api2.cursor.sh`. To see what that endpoint is used for,
`scripts/probe_cli_fullswitch.py` starts a loopback listener, signs in with
the real account, and points `--endpoint` at the listener. It records only
method, path, header names and content type
([`cli-fullswitch.json`](../evidence-snapshot/cli-fullswitch.json)).

The CLI made these calls, all `POST` with `application/proto` bodies, and
then exited with `Error: [unimplemented]`:

```text
/aiserver.v1.DashboardService/GetMe
/aiserver.v1.ServerConfigService/GetServerConfig
/aiserver.v1.DashboardService/GetTeamAdminSettingsOrEmptyIfNotInTeam
/aiserver.v1.DashboardService/GetTeamReposOrEmptyIfNotInTeam
/aiserver.v1.DashboardService/ListMarketplaces
```

These are Connect calls to Cursor's `aiserver.v1` services. None is an OpenAI
Chat Completions, Responses or Anthropic Messages request, and Azure can't
answer them. The listener answered nothing, so the CLI never got as far as an
inference call. That is a limit of this test, but the endpoint's role is clear
from the first requests. Each request carries an `authorization` header, so
`--endpoint` sends your **Cursor credential** to whatever you point it at.

With a deliberately invalid synthetic key the first request is instead
`POST /auth/exchange_user_api_key` with a JSON body
([`cursor-routing.json`](../evidence-snapshot/cursor-routing.json)), Cursor's
key exchange. The probe doesn't document Cursor's private protocol.

### `--model` accepts only Cursor's catalog

`agent --model cursor-poc-gpt-6-luna` was refused before any request:

```text
Cannot use this model: cursor-poc-gpt-6-luna. Available models: auto, gpt-5.3-codex-low, ...
```

The names are Cursor's own catalog entries, not your deployments. On Premium,
`agent models` lists about 300 Cursor-hosted models and no custom or own-key
ones. A custom model added in the IDE and served by a working LiteLLM gateway
was refused the same way, and the gateway logged no request
([`premium-round.json`](../evidence-snapshot/premium-round.json)):

```text
Cannot use this model: foundry-luna. Available models: ...
```

### No provider flags, and environment variables are ignored

- **Commands.** The installed CLI offers `persist`, `login`, `logout`, `mcp`,
  `plugin`, `worker`, `status`, `models`, `team`, `bedrock`, `about`, `update`,
  `create-chat`, `generate-rule`, `agent`, `ls`, `resume` and `help`.
  `bedrock` is the only cloud-provider command.
- **Authentication.** Only `agent login` or `CURSOR_API_KEY`, which is a
  Cursor key [C3]. There is no provider key option.
- **Configuration.** The documented schema has no provider block; project
  `cli.json` controls permissions, not providers [C1, C2].
- **Environment variables.** An authenticated `auto` run set `OPENAI_BASE_URL`,
  `OPENAI_API_BASE`, `AZURE_OPENAI_ENDPOINT` and `ANTHROPIC_BASE_URL` to a
  listener, with dummy provider keys. Cursor answered normally and the
  listener saw **zero requests**
  ([`cursor-routing.json`](../evidence-snapshot/cursor-routing.json)).

### What staff and users say

- In November 2026 a Cursor staff member answered a "provider API keys with
  the CLI" thread: the CLI doesn't support them [F25].
- A February 2026 thread reports that IDE Azure settings and provider
  environment variables don't affect the CLI [F4]. A long-running request for
  a custom CLI endpoint remains open [F5].
- OpenAI's guidance for using its models in Cursor excludes the CLI and Cloud
  Agents from its own-key steps [O1].
- Cursor staff explain the Cloud side by saying own keys are attached by the
  IDE client on each request, and that the same applies to the CLI [F23].

### Bedrock is not Azure

The CLI ships `bedrock` commands (`configure`, `enable`, `status`, `test`,
`clear`, `disable`), so "the CLI has no bring-your-own model of any kind"
would be too broad. They take AWS credentials and a region, and list Bedrock
models only; `agent bedrock status` on Premium showed it off, in access-key
mode. Bedrock was not configured here, and it is not evidence of Azure or
Foundry support [C9].

### `agent worker` doesn't move inference

`agent worker` turns your machine into a self-hosted worker for Cloud Agents.
Tool calls and file edits run on your machine; planning and model calls stay
with Cursor [C8]. It is not a model route.

### LiteLLM's CLI relay is not a model route

LiteLLM 1.112 documents a relay for the Cursor CLI. It passes Cursor's own
sessions through LiteLLM for logging; the models are still Cursor's [L2]. It
doesn't let the CLI call Foundry.

### An unofficial bridge exists, but its plumbing is incomplete

A community project says it runs the Cursor agent CLI against OpenAI- or
Anthropic-compatible APIs [G1]. I read its source but did not run it. It
installs a local certificate, answers in place of Cursor's API host and
forwards requests to a port on your machine that nothing in the repository
serves. The provider URL and key you enter are saved but never passed on. Other
projects replace Cursor's backend the same way for the IDE [G2], [G9], [G10];
they impersonate Cursor and see everything you send. The
[full-switch page](fullswitch.md#what-the-community-built) compares them.

> Do not use a command such as `cursor chat --endpoint <azure-url>
> --deployment <name>` copied from an unverified summary. It is not part of
> the installed CLI.

## Fallback: Foundry models as MCP tools

Since there is no switch, keep Cursor's model as the agent and let it call your
Foundry deployments as tools. The agent still runs on Cursor, and Cursor sees
every tool argument and result. Only the Azure credential stays on your
machine. The steps need a free Cursor account and `--model auto`.

### 1. Install and sign in

```bash
# macOS, Linux, WSL
curl https://cursor.com/install -fsS | bash
```

```powershell
# Windows PowerShell
irm 'https://cursor.com/install?win32=true' | iex
```

```powershell
agent --version
agent login
```

### 2. Connect the MCP server

Cursor reads `.cursor/mcp.json` from the folder it runs in.
[`Setup.ps1`](setup.md#6-install-the-bridge) wrote one to `demo`. Approve only
this server, then check that Cursor can load its tools:

```powershell
cd demo
agent mcp enable foundry-models
agent mcp list
agent mcp list-tools foundry-models
```

```text
foundry-models: ready
Tools for foundry-models (2):
- foundry_claude (prompt, max_output_tokens)
- foundry_openai (prompt, max_output_tokens)
```

The demo's `.cursor/cli.json` allows only these two tools and denies shell,
file and web tools:

```json
{
  "permissions": {
    "allow": ["Mcp(foundry-models:foundry_openai)", "Mcp(foundry-models:foundry_claude)"],
    "deny": ["Shell(*)", "Read(**)", "Write(**)", "WebFetch(*)"]
  }
}
```

### 3. Ask Cursor to use your Foundry models

From the `demo` folder:

```powershell
agent --mode ask --model auto --print --trust "Call foundry_openai and foundry_claude, each with the prompt 'In one sentence, what is a Python list comprehension?'. For each tool, report its text, deployment and response_id. Do not read files or run shell commands."
```

Real output (exit code 0, about 30 seconds):

```text
**foundry_openai**
- **text:** A Python list comprehension is a concise way to create a list by transforming or filtering items from an iterable in a single expression.
- **deployment:** `cursor-poc-gpt-6-luna`
- **response_id:** `resp_0c6f4d57c8f858d0016afb99a9766c81958a84539c773a7180`

**foundry_claude**
- **text:** A Python list comprehension is a concise syntax for creating a new list by applying an expression to each item in an iterable, optionally filtering items with a condition, as in `[x * 2 for x in range(5) if x % 2 == 0]`.
- **deployment:** `claude-haiku-5-5`
- **response_id:** `msg_011Ch7X7ugJReAnRB6NoRKdT`
```

Both response IDs match records that the MCP server wrote to its local audit
log (`evidence/foundry-audit.jsonl`) when Azure responded, so they come from
real Azure calls, not from model-generated text. The published copies are
[`guide-prompt-output.txt`](../evidence-snapshot/guide-prompt-output.txt) and
[`foundry-audit.jsonl`](../evidence-snapshot/foundry-audit.jsonl). Your text
and IDs will differ. The `resp_` prefix comes from the OpenAI Responses API
and the `msg_` prefix from the Anthropic Messages API.

### 4. Run the full end-to-end check

From the repository root:

```powershell
cd ..
./scripts/Run-Poc.ps1
```

This runs all four smoke tests, approves and lists the MCP server, and then
runs `scripts/verify_cursor.py`. That script asks Cursor to call both tools
with fresh random tasks. It passes only if Cursor's answer contains the
correct results **and** the request hashes, response hashes and response IDs
match new audit records. The recorded run is in
[`cursor-mcp-e2e.json`](../evidence-snapshot/cursor-mcp-e2e.json).

### 5. Use it in your own project

For a complete coding workflow rather than the arithmetic proof, see
[MCP for real development](development.md), including the generated application,
token comparison and context-handoff test.

1. Merge the `foundry-models` entry from `demo/.cursor/mcp.json` into
   `<your-project>/.cursor/mcp.json` **at the Git repository root**, preserving
   other servers. Alternatively, merge it into `~/.cursor/mcp.json` to make
   the tools available in every project. In the development study, the
   installed CLI ignored a nested working directory's config until that
   workspace became an independent Git repository. Verify discovery with
   `agent mcp list-tools foundry-models`, then one actual agent tool call before
   running a task. Listing succeeded even when native dispatch failed here.
2. Allow the two tools in `<your-project>/.cursor/cli.json`:

   ```json
   {
     "permissions": {
       "allow": ["Mcp(foundry-models:foundry_openai)", "Mcp(foundry-models:foundry_claude)"]
     }
   }
   ```

   The demo's `deny` rules exist to isolate the experiment. In a real project,
   set shell and file permissions to suit your own workflow.
3. Approve the server from that project folder:

   ```powershell
   agent mcp enable foundry-models
   ```

4. Ask for the tool by name, for example: *"Ask foundry_claude to review the
   function below for edge cases"*.

Each tool call accepts up to 8,000 characters and 128 to 2,048 output tokens.
Text you send to a tool goes to **both** Foundry and Cursor, because Cursor's
agent writes the tool arguments and reads the results.

## How the proof works

```mermaid
flowchart LR
    U[Synthetic prompt] --> C[Cursor CLI, Cursor-routed auto]
    C -->|MCP tool call| M[Local Python stdio MCP server]
    M -->|Entra token stays local| L[Foundry OpenAI Responses, Luna]
    M -->|Entra token stays local| H[Foundry Anthropic Messages, Haiku]
    L -->|Answer and metadata| M
    H -->|Answer and metadata| M
    M -->|Tool result visible to Cursor| C
```

The official MCP Python SDK handles protocol framing and tool schemas. The
model clients use the official OpenAI and Anthropic SDKs, with
`AzureCliCredential` tokens for `https://ai.azure.com/.default`. The caller
can't supply an endpoint, credential, shell command or file path. [C4, M1, M2]

`verify_cursor.py` passes only when all of these hold:

- Cursor finishes successfully with both correct answers.
- New audit records exist from the local model client.
- Request-body and response-text SHA-256 hashes match exactly.
- Cursor's answer contains the matching Azure response IDs.
- Both configured deployments answered.

That is stronger than asking an agent which model it used, but it is local
test evidence, not Azure billing attestation. In the recorded run the
delegated calls used **62 Luna tokens (40 in, 22 out) and 75 Haiku tokens
(53 in, 22 out)**. Cursor's own orchestration tokens are reported separately
in [`cursor-mcp-e2e.json`](../evidence-snapshot/cursor-mcp-e2e.json).

## Troubleshooting

Problems with Azure, roles or deployments are covered in
[Foundry setup troubleshooting](setup.md#8-troubleshooting).

| Symptom | Cause and fix |
| --- | --- |
| `Model unavailable on Free` | Use `--model auto`, or a paid plan. Explicit Composer 2.5 was refused on the Free plan. |
| `Cannot use this model: <deployment name>` | `--model` takes Cursor catalog names only. Your deployment is reachable through the tools, not as a model. |
| `Error: [unimplemented]` after setting `--endpoint` | The endpoint isn't a Cursor service. Remove `--endpoint`. |
| `agent mcp list-tools` can't find `foundry-models` | Run it from the folder that contains `.cursor/mcp.json`. Passing only `--workspace` from the parent folder did not work on Windows. |
| Cursor asks for approval again | Changing `mcp.json` resets approval. Run `agent mcp enable foundry-models` again; don't approve all servers at once. |
| "The system cannot find the path specified" | `${workspaceFolder}` with parent-relative paths failed on Windows. Run `./scripts/Setup.ps1` again to write absolute paths. |
| Luna's `model` field shows the deployment name | Expected. The scripts compare against Azure deployment metadata instead. |

## Disconnect

```powershell
cd demo
agent mcp disable foundry-models
```

Then [delete the deployments](setup.md#9-clean-up) you no longer need.

---

Source keys such as [C1] and [F4] refer to [Sources](../SOURCES.md).
