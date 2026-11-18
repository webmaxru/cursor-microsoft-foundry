# Does the MCP fallback work for real development?

An arithmetic tool call proves connectivity. It does not show whether an agent
can build software, preserve requirements across changes, or save Cursor usage.
This study uses a greenfield application and compares two actual Cursor CLI
workflows: Cursor-only and deliberately Foundry-heavy.

**Verdict: useful bounded assistance, not a practical full switch.** The
Foundry-assisted workflow completed all three development stages, including
a fresh-session handoff and a real bug-fix cycle. But it required an explicit
MCP-client workaround, took **24.9 versus 13.0 minutes**, and used **52.4% more
Cursor output tokens**. Post-study checks also found validation and Windows
encoding gaps. It is more than an arithmetic demo; it is not evidence that
Foundry can replace Cursor's inference or make this workflow cheaper.

The workflow also writes requests and generated proposals to disk and returns
their content to Cursor. See [Data boundaries and governance](governance.md)
before using it with confidential code or regulated data.

## Important: native MCP versus the tested workaround

**Native Cursor tool dispatch failed in the new development sessions.**
`agent mcp list-tools foundry-models` connected and listed both tools, but
actual Auto and pinned Grok sessions could not find the server. One native
call returned `MCP server does not exist: foundry-models`. This was not an
Azure authentication error. The earlier arithmetic proof remains a historical
success; it was not reproduced in these new native-dispatch sessions.

An initial coding attempt substituted direct Python API clients and eventually
passed its first-stage acceptance tests. **That attempt is excluded from the
MCP comparison.** Its transcript also showed shell-quoting failures and model
contract mistakes. It would be misleading to call those costs native MCP
performance, or its completed code proof that native MCP worked.

The final Foundry-heavy arm uses a **shell-invoked MCP client**:

```text
Cursor model -> local Python client -> MCP stdio -> existing Foundry tool
             <- proposal path + usage metadata <- saved model response
```

[`development_worker.py`](../scripts/development_worker.py) calls the actual
MCP protocol, saves a proposed code/review file, and returns metadata to Cursor.
It does not call the SDK directly, execute generated code or replace Cursor's
model. Cursor reads and reviews the proposal, applies it, and runs tests.
Both tools were checked through this helper before the development comparison.

This is an additional adapter with an extra shell permission, **not a repair
of native MCP discovery**. If your native tools work, you do not need it.
If they do not, report the failure rather than silently counting direct SDK
calls as MCP calls.

### Failed attempts are part of the result

| Attempt | Observed outcome | How it is counted |
| --- | --- | --- |
| Nested project without its own Git root | The CLI could not find the configured server | Setup failure, not model inference |
| Native dispatch: nested Auto, repository-root Auto, pinned Grok | All three reported the server unavailable; no successful native MCP call | Separate diagnostic usage, not the coding comparison |
| Auto coding pilot after native dispatch failed | Cursor substituted direct SDK calls; 17 successful Foundry responses and a passing first-stage application | Excluded: it did not use the requested transport |
| Shell-MCP helper self-test | Both Foundry models returned the requested marker through actual MCP stdio | Transport gate, not evidence of coding quality |

The excluded SDK-assisted stage took **847.9 seconds**, with **89,715 Cursor
input tokens and 20,130 output tokens**. It was interrupted during the next
stage, so those figures are not its total cost. The [pilot evidence](../evidence-snapshot/development-pilot.json)
keeps the completed counters and diagnostic failures separate from the final
comparison. This is why a successful application alone is insufficient proof
that a requested inference route worked.

## What we built

**Ledger Lab** is an offline Python application that reads a CSV expense ledger
and emits category totals as JSON. It uses exact decimal arithmetic, validates
calendar dates and money syntax, handles quoted CSV fields, and reports errors
without partial output. There are no third-party dependencies.

Both runs received the same requirements and independent acceptance tests:

1. Build the application, its own unit tests and usage documentation.
2. Resume the same Cursor conversation. Add a month filter while retaining
   validation of records outside the selected month.
3. Start a **fresh Cursor conversation** with the files left by the previous
   stages. Add optional refunds without losing the month filter, validation
   rules or money precision.

The evaluator wrote the requirements and acceptance suite before either run;
Cursor wrote each application's code and its own tests. The evaluator did not
repair the implementations by hand. The runner permits one repair turn after
an independent acceptance failure and preserves it in the accounting.
Stage 1 has five active acceptance tests, stage 2 seven, and stage 3 nine;
the remaining tests are explicitly skipped before their feature is requested.
Several tests contain multiple invalid-input cases.

The Foundry-heavy instructions delegated implementation to **GPT-6 Luna** and
test design/review to **Claude Haiku 5.5**, through the shell-invoked MCP client
and existing bridge.
Cursor retained file editing, test execution and integration. This is a
deliberately aggressive delegation strategy, not an optimal-cost claim.
**"Foundry-heavy" names the delegation policy, not a measured majority of
tokens.** Foundry proposed production code and review/test cases; Cursor still
wrote the executable tests, maintained the README and handled integration.

Each final-run workspace is its own Git repository. An initial setup pilot
exposed an important CLI detail: inside a larger repository, a nested working
directory's MCP configuration was not discovered. Initializing a separate
repository made configuration discovery work, but did not resolve native runtime dispatch.
The initial Cursor-only pilot is not the comparison control; both final arms
use the corrected layout and pin the same `grok-4.7-medium` model.

## Results and token consumption

Both arms passed the **prewritten** acceptance suite at every stage, without
an evaluator-requested repair turn. Internal debugging is included in the
timings and usage. The final source, agent-written tests and README are
published in [Ledger Lab](../examples/ledger-lab/).

| Stage | Acceptance checks | Cursor-only time | Foundry-assisted time | Successful Foundry calls |
| --- | --- | --- | --- | --- |
| Initial application | 5 passed | 311.0 s | 605.6 s | 2 |
| Month filter, same conversation | 7 passed | 132.7 s | 418.6 s | 3 |
| Refunds, fresh conversation | 9 passed | 334.8 s | 466.8 s | 3 |
| Total | All planned checks passed | 778.5 s | 1,491.0 s | 8 |

The telemetry confirms that stage 2 reused the preceding session and stage 3
did not, in both arms. These are elapsed Cursor-run times, including tools and
local execution, not isolated model latency.

### Cursor consumption did not move wholesale to Foundry

| Cursor counter | Cursor-only | Foundry-assisted |
| --- | --- | --- |
| Input tokens | 345,859 | 336,776 |
| Output tokens | 46,079 | 70,238 |
| Cache-read tokens | 1,036,032 | 3,773,056 |
| Cache-write tokens | 0 | 0 |
| Reasoning tokens | 31,285 | 43,881 |

Input was **2.6% lower**, but output was **52.4% higher**, cache-read traffic
was **3.64 times as large**, and the workflow took **1.92 times as long**.
Keep those counters separate: do not add reasoning to output or cache reads
to input and call the result an invoice. This single pair does not establish
cost savings; the host still did substantial planning, reading, test-writing,
debugging and integration.

### Foundry consumption was additional

| Foundry model | Successful calls | Input tokens | Output tokens |
| --- | --- | --- | --- |
| GPT-6 Luna | 4 | 5,875 | 4,169 |
| Claude Haiku 5.5 | 4 | 7,272 | 3,842 |
| Total | 8 | 13,147 | 8,011 |

There was also **one truncated Claude review** whose usage was not captured
as a successful bridge response. These Foundry figures are therefore a
successful-call lower bound, not all billed consumption. Setup probes and
excluded pilots are outside this table.

All eight successful responses were verified through the **shell-invoked MCP
client**; there were **zero successful native Cursor MCP calls** in this
comparison. Counts come from CLI/provider telemetry, not model self-reports.
The [machine-readable study](../evidence-snapshot/development-study.json)
includes each phase, separate counters, transport counts, session-reuse flags,
shell outcomes and artifact hashes.

### Passing the planned tests was not production readiness

After freezing the measured artifacts, additional offline probes found gaps
that the original acceptance suite missed:

| Follow-up probe | Cursor-only artifact | Foundry-assisted artifact |
| --- | --- | --- |
| Unclosed quote around an amount | Rejects malformed CSV | Incorrectly accepts it as `1.00` |
| Date with trailing whitespace | Rejects it | Trims and accepts it, weakening the exact-format contract |
| Amount `00.50` | Accepts it | Rejects it; the delegated prompt added a leading-zero restriction absent from the original brief |
| Generated tests with UTF-8 stdio | 20 pass | 41 pass |
| Generated tests with CP1252 stdio | 20 pass | One fails because a subprocess test assumes UTF-8 |

The extra amount restriction and date trimming appeared in Cursor's delegated
contract; the workers then followed that narrower/different contract. This is
a concrete example of context being changed at the handoff, not proof that
MCP itself changes data. The malformed-CSV gap also survived model review.

The [follow-up evidence](../evidence-snapshot/development-followup.json)
contains exact inputs and observed results. Reproduce it without inference:

```powershell
python scripts\probe_development_artifacts.py --out evidence\my-followup.json
```

The probe reports known behavior; it is **not a passing-quality gate**.
The generated files are preserved unchanged to keep the comparison auditable,
not offered as production financial software. Use the parent
[artifact instructions](../examples/ledger-lab/README.md), which explicitly
select UTF-8 for running the generated tests on Windows.

## Does it break the engineering context?

**There are two context boundaries, not one shared conversation.**

Cursor owns the repository view, user conversation, file tools and test output.
The Foundry tools receive only the `prompt` argument Cursor constructs. In this
bridge, each OpenAI call has a new Responses input with `store: false`, and each
Claude call contains a single user message. No previous-response ID, chat
history, repository search or filesystem tool is forwarded.

| Information | Cursor has it | Foundry receives it |
| --- | --- | --- |
| Conversation and project rules | In the host's available context | Only if copied into that call's prompt |
| Current source code | Can read it with file tools | Only the selected text sent by Cursor |
| A failing test | Can execute and inspect it | Only the failure and relevant code sent back |
| Earlier Foundry answer | Can retain it in the conversation or files | Not automatically present in the next call |
| New-session handoff | Must reconstruct from files and documentation | Must be given a fresh, self-contained task |

This is the tool model defined by MCP: the host selects a tool and receives
its result. It is not a protocol for replacing the host's model. [S2]
Cursor rules make host instructions persistent, but a referenced file is not
automatically included in a prompt, let alone sent to Foundry. [C19]

The practical risk is **lossy delegation**: an omitted invariant, stale source
snippet or summarized test failure can make the worker solve a different
problem. A long host conversation does not fix that. Keep the authoritative
contract in files, include exact interfaces in each delegation, and use
executable regression tests as the final check.

**The fresh-session handoff worked for the planned features, but not by sharing
memory with Foundry.** Cursor reread the saved code, tests and README, then
included the current implementation and invariants in new worker requests.
The retained month-filter behavior passed the independent stage-3 checks.

There was a real debugging cycle: Luna's first refund implementation negated
an already-negative Decimal, turning refunds into charges. Haiku's review
said "Defects: none", yet the generated tests exposed five failures. Cursor
diagnosed the double negation, sent the exact failing examples and a focused
correction request back to Luna, applied its response and reran the tests.
Thus Foundry supplied code, but Cursor still supplied essential diagnosis
and engineering context.

The resumed month-filter stage illustrates the extra coordination: one Claude
review hit this bridge's output cap and was rejected, so Cursor split it into
separate review and test-design requests. The failed response's token usage is
not in the successful-call totals. Some review prose also labeled correctly
handled cases as defects before retracting the claim. Model agreement is not
a substitute for running tests.

The first delegated stage also included four rejected shell commands and one
failed Python import in a scratch probe. Those costs belong to the observed
host workflow and its permission rules, not to the MCP protocol alone. The
comparison deliberately includes that integration overhead rather than
counting only the fast, successful Foundry requests.
The control also encountered six rejected shell commands in its final stage;
neither arm was a frictionless idealized run.

## How to use it on a development task

Start with the [Foundry setup](setup.md), then merge the generated MCP server
entry into `.cursor/mcp.json` at the **Git root of the project** you actually
want Cursor to edit. Preserve any other server entries. The CLI and IDE share
the MCP configuration. [C4] In this installed CLI, `--workspace` pointing
inside an existing repository did not make its nested MCP config the project
config. Check `agent mcp list-tools foundry-models` from your project before
spending tokens on a development run. **Listing is necessary, not sufficient:**
also ask Cursor to make one real tool call before starting a large task.

**Do not copy the demo's `cli.json` unchanged.** It intentionally denies file
reads, writes and shell execution for the arithmetic proof. Development needs
those capabilities. Allow only the intended project files, test commands and
the two Foundry tools; keep normal approval controls. The experiment runner
creates its own permissions for a disposable synthetic project. Shell access
to Python is powerful and is not an operating-system sandbox. [C14]

Optionally copy
[`config/foundry-development.mdc`](../config/foundry-development.mdc)
to `.cursor/rules/foundry-development.mdc`. It is guidance, not enforcement
of a spending limit or proof that a model actually used Foundry. This rule
targets native dispatch; use it only after the actual-call check passes.

Use a task prompt like this:

```text
Use Foundry-assisted development for this change.
Read the current implementation and tests. Send foundry_openai the exact
interface, relevant code and acceptance criteria for one bounded change.
Ask foundry_claude to review that change and propose regression tests.
Apply the proposed code yourself, run the real test suite, and send any
failure back with the current code. Do not claim a tool ran tests.
Keep existing behavior and record any durable decisions in the project docs.
Report which work used Foundry and which work remained on Cursor.
```

For each delegation, include:

```text
Goal: add month filtering to summarize_csv.
Contract: validate every row before filtering; reject invalid excluded rows.
Interface: summarize_csv(text: str, month: str | None = None) -> dict[str, str].
Current code: <the relevant function, copied from the current file>.
Acceptance: Jan 1 + Feb 2 filtered to February returns 2.00.
Invalid January NaN still raises ValueError when filtering to February.
Return: one complete replacement function and any required imports.
```

For the tested shell-client alternative, have Cursor save that request under
`.foundry/requests/` in its project and run the helper with the repository's
configured virtual environment:

```powershell
& "<checkout>\.venv\Scripts\python.exe" "<checkout>\scripts\development_worker.py" --model openai --prompt .foundry\requests\month-filter.txt --out month-filter.py --max-output-tokens 1800
```

The result is `.foundry/proposals/month-filter.py`. Choose a fresh output name
each time: the helper refuses overwrites and paths outside its proposal
directory. It returns the model response verbatim, so inspect it before applying
it. Use `--model claude` and a `.txt` proposal for review/test design.
The helper's output is not an executable approval, and its path checks do not
sandbox Cursor's separate shell tool. Never turn off approvals wholesale.

The tools accept **8,000 characters of input and at most 2,048 output tokens**
(512 by default). These are this repository's safety limits, not the models'
context windows or an MCP limitation. Set `max_output_tokens` deliberately,
usually up to 1,800 for a small code response. Split larger work into functions
or modules. Incomplete responses fail rather than being returned as usable code.

Never send secrets or unapproved private code. The bridge keeps Azure
credentials local, but Cursor sees the tool request and answer, and Foundry
receives the selected code. This is not an Azure-only data boundary.

## Reproduce the comparison

The existing configured deployments and Azure CLI login are sufficient; no
LiteLLM, public tunnel or provider key in Cursor is needed. A logged-in Cursor
CLI with available usage is required. These runs consume **both** services'
quota, unlike a local unit test.

From this repository root, after setup:

```powershell
.\.venv\Scripts\python.exe scripts\run_development_study.py --arm cursor-only --model grok-4.7-medium --out evidence\my-baseline
.\.venv\Scripts\python.exe scripts\run_development_study.py --arm foundry-heavy --model grok-4.7-medium --transport shell-mcp --out evidence\my-foundry
.\.venv\Scripts\python.exe scripts\summarize_development_study.py evidence\my-baseline evidence\my-foundry --out evidence\my-study.json
```

Use new output directories; the runner refuses to overwrite an existing
experiment. The commands pin the model used in this comparison. If it is
unavailable on your plan, select the same supported explicit model in both
runs. Omitting `--model` uses Auto, which weakens the comparison.
The runner defaults to `--transport native` for a native-dispatch experiment;
the explicit `shell-mcp` flag is what selects the measured workaround.
Do not run other Foundry probes concurrently.

The runner records Cursor's NDJSON stream and terminal usage, resumes the
conversation for stage 2, and deliberately omits resume for stage 3. [C18]
Successful Foundry responses are correlated to the local audit by the response
IDs actually returned to Cursor, and the runner also checks that those IDs
came through the selected MCP transport. A direct SDK response cannot pass
that check. The public summary retains hashes and usage,
not session IDs, Azure request IDs, local paths or complete conversations.
Raw transcripts stay under the ignored `evidence/` directory; do not publish
them without review.

## Measurement limits

- **One paired case, one small project.** This does not predict large-repository
  refactors, UI development, dependency upgrades, long context or a team's
  monthly bill.
- **Acceptance was incomplete.** Additional probes found defects and contract
  drift after both arms passed the planned tests. The original suite was not
  retroactively changed to make the comparison look better.
- **Pinned model, still not a randomized benchmark.** The final runs request
  the same model. Setup pilots used Auto and are excluded. The final runs are
  sequential; caches and service load can differ.
- **Report counters separately.** Cursor's `inputTokens`, `outputTokens`,
  `cacheReadTokens`, `cacheWriteTokens` and `reasoningTokens` are preserved as
  emitted. Do not add reasoning to output or assume cache accounting is the
  same as either Foundry SDK. Different models also use different tokenizers.
- **Successful Foundry calls only.** An incomplete or failed provider response
  can consume tokens without producing a successful bridge audit record.
  Missing telemetry is unknown, not zero.
- **Not an invoice.** Cursor's plan pools, cache rates, model routing and
  Foundry deployment pricing differ. No prepaid balance or Azure invoice was
  reconciled. A token count is not a dollar-saving estimate. [C17]
- **CLI development measured; IDE portability inferred.** The IDE has already
  called the same MCP tools, but this three-stage coding comparison was not
  repeated through its UI. Cloud MCP remains an unexecuted blueprint.

## When to choose this approach

Use it to bring a particular Foundry deployment into an existing Cursor
workflow for a **bounded implementation, review, test design or explanation**.
The repository and tests remain the shared source of truth; Cursor is the
integrator.

Do not choose it to eliminate Cursor inference, bypass exhausted Cursor
usage, keep all code inside Azure, or guarantee that most tokens are billed
to Foundry. Even a Foundry-generated implementation must be requested, read,
applied and tested by Cursor, and often becomes part of Cursor's later context.

For production work, start with selective delegation rather than asking
Foundry to redo every step. Measure a representative task from your own stack,
including corrections and a fresh-session handoff. If the requirement is
that the **agent's entire inference loop** runs on Foundry, use an agent with
a native Foundry provider instead. [A3]
