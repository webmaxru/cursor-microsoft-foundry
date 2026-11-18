# Data boundaries and enterprise governance

**Foundry inference is not an Azure-only data boundary.** The IDE can use
your Foundry deployment as its main model, but Cursor still builds the prompt
on its servers. MCP adds a Foundry call without removing Cursor's model.
A translating proxy adds another place that can read the request. Approve
the whole path, not just the model endpoint. [C11, C8]

**Policy review: 18 November 2026.** This page combines current first-party
documentation with the [recorded PoC](evidence.md) and its source code.
The runs used an individual Premium account, not an Enterprise contract.
Residency enrollment, contractual deletion, private networking, CMEK and
enterprise policy enforcement were **not tested**. This is technical
due-diligence guidance, not a legal opinion or a compliance certification.

## What this means for an enterprise

| Requirement | Assessment for the mixed routes on this site |
| --- | --- |
| Keep all code and prompts inside Azure | **Not met.** Cursor processes context before the IDE's Foundry call; in MCP flows, Cursor's model also sees delegated prompts and returned results. An Azure-hosted worker does not change this. [C11, C8] |
| Keep all processing and storage in the EU/EEA | **Not established.** Cursor currently offers US-only residency enrollment, with EU/EEA support in development. An EU Foundry deployment does not cover the Cursor or gateway legs. [P1, M5] |
| Keep all processing in the US | **Not automatically met by BYOK.** Cursor's Enterprise US-only program explicitly excludes BYOK, custom gateways, and user-configured MCP services from its guarantee. Each excluded service needs separate assurance. [P1] |
| Never use code to train models | **Can be addressed by policy and contract**, separately for Cursor, Azure OpenAI and Anthropic. It does not imply no storage, no safety review or no international transfer. [P2, P10, P19] |
| Delete every copy immediately after a turn | **Not demonstrated.** Cloud Agent histories, snapshots, stateful APIs, local files, backups and safety exceptions have different lifecycles. [C13, M4, P11, P14] |
| Use the working proxy as a production service | **Not as supplied.** It is a test adapter, not an enterprise identity, DLP, retention or availability layer. The development tunnel is explicitly not for production. [P16] |

For ordinary internal development, the outcome can be an approved
multi-provider service with documented controls. For a strict locality,
single-processor or immediate-deletion requirement, do not approve this PoC
on the strength of a successful Foundry request.

## Follow the data, not the credential

| Route | Who receives content | What the credential separation does |
| --- | --- | --- |
| IDE Azure OpenAI slot | Device -> Cursor backend -> Azure OpenAI deployment; answers return through Cursor | Cursor receives the resource key with every request. Cursor says it is encrypted in transit and not persisted on its servers after the request. This is not device-to-Azure inference. [C11] |
| IDE through the translating proxy | Device -> Cursor backend -> tunnel or gateway -> proxy -> Foundry; the response follows the return path | Cursor receives a proxy secret rather than the Foundry key. The proxy still reads prompts, code context, tool definitions and results. The Azure credential stays with the proxy. |
| IDE or CLI with local MCP | Cursor's agent/model -> tool arguments -> local MCP bridge -> Foundry -> tool result -> Cursor's agent/model | The supplied bridge obtains an Entra token locally; it does not return the token to Cursor. That protects credentials, **not the confidentiality of tool content from Cursor**. |
| Shell-MCP development workaround | Same provider split, plus local request files, proposal files and shell output | The [development worker](../scripts/development_worker.py) saves Foundry output locally; Cursor reads it to continue engineering. Saving to a file is not a data barrier. |
| Cursor-hosted Cloud Agent with HTTP MCP | Repository and run context in Cursor's cloud; Cursor-managed inference plus an external MCP service and Foundry | HTTP MCP can keep the Azure credential out of the agent VM. Cursor still receives the tool results. This is an architectural option, not a Cloud-MCP result verified here. [C7, C13] |
| Self-hosted Cloud Agent worker | Checkout and execution on your worker; selected file content, terminal output, diffs, screenshots and MCP results sent to Cursor | Moves execution, not inference or planning. Artifacts can also upload to Cursor-managed storage. [C8] |

The [14 captured IDE proxy requests](../evidence-snapshot/ide-proxy-cursor-requests.json)
establish that Cursor's backend reached the proxy. They do **not** locate
Cursor's prompt-building servers or every downstream processor, or prove
deletion after the requests.

**Content is more than the message you type.** Include selected files,
conversation history, rules, tool schemas, terminal output, paths, screenshots
and generated code in the data classification. The IDE tests saw roughly
14,000 to 24,500 input tokens on first turns. A downstream DLP check cannot
undo the disclosure that already happened when the client sent context to
Cursor.

Other features need separate review: Tab, Auto, built-in models,
subagents, safety classifiers, web search, integrations and artifact sharing.
Selecting a Foundry model does not prove that every auxiliary model call
uses Foundry. Cursor's model-management documentation, for example, describes
a separate model-backed Auto-review classifier. [C11, P6]

## Geographic boundaries

### Cursor is a separate processing boundary

Cursor's current Enterprise program offers **US-only** inference, content
processing and storage, including backups, for supported features and models.
It is enabled per team through the account team; it is not a benefit inferred
from an individual Premium subscription. Unsupported models are blocked and
Auto is constrained to eligible models. EU/EEA and APAC support are described
as in development, not as generally available commitments. [P1]

The exclusions matter more than the headline for this project: **BYOK is not
covered**; custom endpoints carry the gateway/model's geography; MCP and other
external integrations have their own regions. Authentication, external shared
links and some trigger paths also have exclusions. Enrolling a team in US-only
residency therefore does not certify its Foundry override or MCP workflow. [P1]

Outside a documented enrollment or negotiated agreement, this review does not
establish a single processing country for Cursor. Do not infer it from your
office location, a DNS name, an egress IP or your Azure resource region.

### Azure OpenAI: resource region is not inference region

For **Models sold by Azure**, including Azure OpenAI, distinguish inference
from storage. Microsoft's documentation says at-rest customer data remains in
the designated Azure geography, while processing follows the deployment type.
Geography is not necessarily a single region or datacenter. [M5, P10]

Microsoft hosts these models in Azure, rather than calling OpenAI's own
API. It says customer prompts and completions are not available to OpenAI
and are not used to train generative foundation models without permission
or instruction. Apply that statement to **Models sold by Azure**, not
automatically to every Marketplace model sold through Foundry. [P10]

| Deployment type | Processing boundary in current documentation | What it does not establish |
| --- | --- | --- |
| `GlobalStandard`, `GlobalProvisionedManaged`, `GlobalBatch` | Global processing where the model is available | An EU resource name or location does not make inference EU-only |
| `DataZoneStandard`, `DataZoneProvisionedManaged`, `DataZoneBatch` | The Microsoft-defined data zone; current deployment guidance lists US, EU and APAC, subject to model availability | Not a specific country, region or datacenter; not every model supports every zone |
| `Standard`, `ProvisionedManaged` | Customer-specified Azure geography; processing may move between regions within that geography for operational reasons | Not necessarily the resource's individual Azure region |
| `DeveloperTier` | Global; evaluation tier without a data-residency guarantee | Not a substitute for a geography-constrained production tier |

**An important documentation mismatch:** the current deployment-types page
defines the EU zone using the Azure EU Data Boundary and says it can include
EFTA locations such as Norway and Switzerland. The Models-sold-by-Azure
privacy page still describes EU DataZone processing in EU member nations.
Do not silently treat these as identical. For an EU-member-states-only,
EEA-only or country-only requirement, obtain the applicable model/zone
definition in writing before deployment. An "EU" SKU label alone is not
sufficient evidence. [M5, P10]

The PoC recorded Luna as `DataZoneStandard`, with the resource in Sweden
Central. That is not proof of Sweden-only inference. The
[inventory](../evidence-snapshot/deployment-inventory.json) is a historical
snapshot, not a current compliance inventory or a record of each request's
physical processing location.

### Claude: check hosting as well as SKU

**Claude in Foundry is not governed as Azure OpenAI simply because it has an
Azure URL or appears on an Azure bill.** Microsoft identifies Anthropic as
the seller and operator, and an independent processor of Claude prompts and
outputs, for both hosting options. Microsoft provides the Foundry, Azure and
billing services under its applicable terms; Anthropic's terms govern the
Claude service. [P12, P19]

| Claude hosting option | Where content is processed | Remaining boundaries |
| --- | --- | --- |
| **Hosted on Azure** | Request ingress, API services and inference on Azure; Microsoft says prompts and outputs do not leave Azure | Anthropic still operates the service. Anthropic says retained content stays on Azure, but operational data without prompts/completions, including identifiers, safety scores and billing/usage data, is stored on Anthropic systems outside Azure. Available geography choices are Global or US Data Zone for supported models. [P12, P13] |
| **Hosted on Anthropic infrastructure** | Anthropic infrastructure; may be outside Azure and outside the selected Azure geography | Current Anthropic Foundry guidance lists Global Standard, not a selectable EU or US Data Zone for this option. [P12, P13] |

The recorded Haiku deployment was `GlobalStandard`; a native response
reported `inference_geo: global`. Neither that label, model version `2`, nor
the successful proxy requests establishes which hosting option was selected.
The evidence did not capture that selection. Do not label this Claude PoC
EU-only, Sweden-only or verified Azure-hosted. Check the deployment's hosting
version and accepted Marketplace terms. [P13]

An API translation from Chat Completions to Messages or Responses changes
protocol, **not** the model's operator, hosting choice or data-processing
terms.

## Retention is different at every layer

**No training, zero retention, encryption and residency are four different
claims.** Privacy Mode is worth enforcing, but Cursor explicitly says its ZDR
policy does not apply to own-key requests. Keep Privacy Mode on for Cursor's
handling and other features; review Foundry's terms separately. This exception
does not, by itself, mean Cursor trains on BYOK content. [C11, P2, P3]

| Layer or feature | What can persist, and for how long | Enterprise action |
| --- | --- | --- |
| Cursor with Privacy Mode | No training by Cursor; eligible managed providers operate under ZDR arrangements, with abuse/legal exceptions and designated non-ZDR models. These agreements do not transfer to BYOK. [P1, P2, C11] | Enforce the mode and restrict retention-requiring models; document each exception |
| Cursor file cache and client data | Cursor documents temporary encrypted server-side file caching, with client-generated decryption keys held only for the request. The cited page does not specify a cache TTL. Local histories, logs and backups are separate. [P2] | Obtain the cache expiry/deletion terms needed by your policy; manage local disks and backups |
| Search/indexing | Current Instant Grep guidance says the index stays on the machine, without uploading code/paths to build it or storing codebase embeddings for search. Opened matches may still enter model requests. [P9] | Check the deployed version and enabled features; do not assume older indexing descriptions or local search mean local inference |
| Cloud Agent conversations | Prompts, responses, tool calls and artifacts kept **indefinitely by default**. The Delete Agent API deletes the transcript and artifacts. [C13] | Set a deletion workflow; review early-access Enterprise retention, currently Indefinite or 90 days |
| Cloud Agent environment snapshots | Encrypted disk snapshots expire after **30 days of inactivity**; each start/resume renews the window. They cannot be deleted on demand through Delete Agent. [C13] | Treat repository copies, build caches and any disk-resident secrets as retained until expiry; rotate credentials independently |
| Azure OpenAI Responses state | Stored responses retained **30 days by default**; deletion by response ID is supported. `store: false` supports stateless requests. Background mode requires storage. [M4] | Disable unneeded state and avoid background mode when incompatible with policy; include Files, vector stores or other stateful features if added |
| Azure abuse monitoring | Automated review does not store prompts/completions in the abuse-monitoring system; selected content can be stored for human review. Modified monitoring is conditional and changing. [P10, P11] | Verify applicable monitoring and human-access terms; do not infer them from `store: false` or a disabled diagnostic setting |
| Claude content and safety records | Anthropic terms, selected features, model-specific rules and safety/legal exceptions apply. No contractual retention setting for the PoC subscription was verified. [P12 to P15] | Get a Foundry-specific retention statement for the exact hosting option and model; see below |
| Proxy, LiteLLM, tunnel and observability | Request metadata, errors, traces, optional body captures, databases and stdout may persist independently of model APIs | Define TTLs, access controls and deletion for every sink, including backups and external tracing |
| MCP development files | Request text, generated proposals and transcript copies can outlive the session; local audit metadata has no automatic expiry in this repo | Apply a workspace retention policy; do not publish raw project evidence |

### Azure safety retention is not the Responses retention period

Microsoft separates real-time filtering, automated abuse review and human
review. Human reviewers have restricted, approved access; the privacy page
places the human-review store in the resource geography and says reviewers
for EEA deployments are located in the EEA. That does not establish the
inference location of a Global deployment. [P10, P11]

The current pages reviewed here do **not** give a universal numeric expiry
for human-review content. Do not copy the Responses API's 30-day default into
an abuse-monitoring policy. Obtain the applicable retention and access terms.

There is also a time-sensitive change: existing Modified Abuse Monitoring
approvals continue for models made available before **1 November 2026**.
For models made available on or after that date, Microsoft says the option
will become unavailable on a future date to be announced, with at least
30 days' notice per affected model. It has **not** said all approvals ended
on 1 November. Where applicable, `ContentLogging: false` is documented
evidence that abuse-monitoring storage is off; it is not an all-services ZDR
certificate, and no such approval was verified for this PoC. [P10, P11]

### Do not assign Claude a blanket zero-day or 30-day policy

Anthropic's API retention guide explicitly includes Foundry, describes ZDR
arrangements and feature-specific eligibility, and says conversation content
is not retained by default apart from Covered Models. Its separate
commercial retention article describes deletion of standard API inputs and
outputs within 30 days, subject to agreements and exceptions. These public
statements are not enough to determine the effective retention setting of
this Foundry subscription. Record the applicable contract, model, hosting
option and enabled features rather than choosing the more favorable wording.
[P14, P15]

The commercial article also describes flagged inputs/outputs retained for
up to **two years**, safety classification scores for up to **seven years**,
and feedback-related data for **five years**, with legal exceptions.
Covered Models have separate mandatory retention rules. These are policy
exceptions to review, not evidence that the PoC's Haiku prompts were flagged
or retained for those periods. A Haiku experiment does not approve the next
Claude model someone selects. [P14, P15]

### What the supplied code actually does

The [OpenAI MCP client](../scripts/foundry_client.py) sends `store: false`.
The translating proxy's
[`chat_to_responses`](../scripts/foundry_claude_proxy.py) does the same for
translated Chat Completions requests, including Luna's Responses mode.
**It does not enforce this for every request:** its native Responses
passthrough preserves the caller's storage settings. The
[LiteLLM configuration generator](../scripts/litellm_gateway.py) likewise
does not declare an explicit `store: false` policy. Do not market either
as a universally non-retaining gateway.

The core MCP audit omits answer text and stores hashes, IDs, timing and usage.
The proxy records request shape, usage and errors; provider error messages can
contain sensitive detail, so "no full prompt logging" is not a comprehensive
redaction guarantee. The [capture proxy](../scripts/capture_proxy.py) has an
explicit `--save-bodies` option. The development worker intentionally writes
prompts/proposals on disk. None of these local stores implements automatic
retention expiry. Hashes and request IDs should still be access-controlled;
they are not proof that a record is anonymous.

## Enterprise controls that matter

These are recommended controls, not settings enabled by this research.

| Owner | Control to put in place | Important limitation |
| --- | --- | --- |
| Cursor administrator | Enforce Privacy Mode; use SSO/SCIM and managed-device Allowed Team IDs to prevent personal-account use | A personal Premium subscription is not an Enterprise policy boundary or the same contractual arrangement. [P1, P3] |
| Cursor administrator | Restrict models and personal BYOK; approve new models and retention exceptions deliberately | Model access combines team and group permissions by **union**: an allowing group can widen access. BYOK policy is team-level. [P6] |
| Cursor administrator | Allowlist MCP server commands/URLs and tools; restrict local-server network access | An allowlisted server can still be dangerous. The shell-MCP workaround also needs shell controls; an MCP allowlist alone is not its enforcement boundary. [P6, C14] |
| Repository owner | Keep secrets and production datasets out of the workspace; use synthetic fixtures and least-privilege repositories | `.cursorignore` does not stop terminal or MCP access. Do not rely on it as DLP. [P8] |
| Cloud administrator | Lock Cloud Agent egress, restrict repositories, use protected Git scopes and scoped secrets | Internet access is on by default. Some service/SCM destinations remain available in allowlist-only mode. Dashboard network locks do not govern self-hosted workers. [C13, P6] |
| Azure/gateway owner | Use workload identity and least-privilege inference access; separate resources and environments; rotate secrets | The native IDE slot takes a resource key. This repo's keyless code uses a developer's Azure CLI login, not a production managed-identity implementation. |
| Azure/gateway owner | Enforce permitted deployment SKUs, zones, model versions and Claude hosting options; review fallback routes | Endpoint aliases and an Azure resource-location policy alone do not constrain every inference geography. [M5, P13] |
| Security operations | Correlate Cursor admin changes, gateway requests and Azure usage without routinely recording content | Cursor audit logs cover administrative activity, **not** prompts, responses or generated code. Hooks/tracing add their own sensitive records. [P7] |
| Data/platform owner | Set retention and deletion for transcripts, application files, logs, backups and support exports | Azure metrics proving a `200` do not prove upstream or downstream deletion |

For a shared gateway, use per-client, revocable inference credentials rather
than distributing a gateway administrator/master key. Keep the Azure
credential server-side. Restrict model aliases, request size, concurrency,
spend and egress; refuse unapproved models instead of silently falling back
to another provider. A gateway on its own cannot police unrelated Cursor
features or MCP endpoints.

Treat tool results and repository instructions as untrusted input. Keep
approval and sandbox controls for writes, shell execution and outbound access.
Foundry content filters are not a substitute for these controls, nor are they
a general-purpose secret scanner.

## Network and encryption limits of the proxy

The tested route used an internet-reachable **development tunnel** in front
of a localhost proxy. The tunnel allowed anonymous connection, while the
proxy still required its own shared secret. "Anonymous tunnel" does not mean
unauthenticated model inference, but it does expose the proxy to internet
traffic.

Microsoft says Dev Tunnels is for development/testing, not production, and
its web-forwarding service terminates TLS at ingress. It is not an opaque
end-to-end-encrypted pipe that prevents the relay from processing content.
The tunnel's location is also independent of the model's deployment zone.
[P16, P17]

A production candidate would replace it with an approved gateway reachable
from Cursor's backend, with server authentication, scoped client credentials,
redacted logs and a private upstream path to Foundry where supported:

```text
Managed device -> Cursor backend -> governed gateway -> Foundry private endpoint
                      |                  |
                Cursor controls    Your identity, logging,
                                   network and retention controls
```

This is a **design recommendation, not a deployed result**. Cursor's backend
does not inherit your laptop's VPN or private DNS. A private endpoint at
Foundry can protect the gateway-to-Foundry leg; it cannot remove the prior
Cursor processing. Foundry network isolation requires the appropriate
network path, DNS and access settings. Do not disable required enterprise
controls simply to make the PoC connect. [C11, P18]

Cursor separately documents private connectivity for certain enterprise
Cloud Agent/source-control scenarios. Do not assume it also provides a
private BYOK inference path; that combination was not verified. Local MCP
can call a private Foundry endpoint from a networked machine, but returned
content still goes to Cursor. [C16, C8]

TLS and encryption at rest protect transport and storage; they do not stop
authorized service processing. Cursor's CMEK offering describes protection
for stored Cloud Agent data, not a means to hide live prompts from Cursor.
Azure CMK coverage is also feature-specific and does not encrypt Cursor's
copy with your Azure key. [P1, P10]

## Contracts, regulated data and procurement

**Treat this as a multi-party service.** Review the Cursor agreement/DPA,
Microsoft DPA and relevant Azure terms, Anthropic Marketplace terms/DPA for
Claude, and contracts for any hosted gateway, tunnel, telemetry or MCP service.
Azure billing does not collapse those responsibilities into a single
Microsoft processor. [P4, P10, P12, P19]

For personal data, have privacy counsel establish the parties' roles,
lawful basis, data categories, retention schedule and transfer mechanism.
The Cursor and Anthropic DPAs provide transfer-related provisions; SCCs or
an adequacy mechanism address lawful transfers, **not** a promise of
EU-local processing. A DPIA/transfer assessment, where applicable, should
cover tool outputs and employee telemetry as well as source code. [P4, P19]

Two details deserve an explicit procurement check:

- Cursor's public DPA Annex 1 says customers must not provide sensitive or
  special-category personal data under that agreement. Do not assume a paid
  plan permits patient records or other regulated production data. [P4]
- Anthropic describes Foundry as eligible for HIPAA-ready use with an
  Anthropic BAA **and** HIPAA configuration on the Azure subscription. That
  does not cover the Cursor leg, connected services or every feature. No BAA
  or HIPAA configuration was reviewed or enabled here. [P14]

Cursor reports SOC 2 Type II and other certifications, with reports available
through its Trust Center. Verify scope, dates and exclusions against your
use case; a certification is not blanket approval of this mixed workflow.
The subprocessor portal returned a JavaScript application rather than a
readable register in this review, so no complete current subprocessor/country
inventory is claimed. Obtain that register and subscribe to change notices.
[P5]

For operational governance, assign an owner for model/version changes,
gateway patching, incident response and key revocation. Keep provider usage
and budgets separate: moving model inference to Foundry does not remove all
Cursor costs or create a hard spend cap. Do not use prompt logs as your
default cost-accounting mechanism. [C11]

## Approval checklist and evidence gaps

Before allowing confidential repositories, record the following in your own
controlled approval system, not in this public repository:

1. **Data scope and owners:** approved repositories and data classes; excluded
   secrets, personal data and production dumps; owners for Cursor, Azure,
   Anthropic, gateway/MCP and logs.
2. **Exact routes:** client/version, key toggles, model aliases, tool hosts and
   auxiliary features. Check saved settings and verify destinations using
   synthetic prompts. Include negative tests for blocked models and hosts.
3. **Geography evidence:** applicable Cursor enrollment and exclusions, Azure
   SKU/zone, Claude hosting version, gateway location, support access and
   backup locations. Resolve the EU definition mismatch for your requirement.
4. **Contract evidence:** applicable DPAs/Marketplace terms, subprocessors,
   transfer mechanism, permitted data categories and any required BAA.
5. **Retention evidence:** defaults and overrides per store, safety exceptions,
   `store` behavior on every API path, and a deletion test with its known
   limits. Do not claim immediate deletion for Cloud Agent snapshots.
6. **Access and egress:** test team/group model policy, MCP and shell controls,
   identity offboarding, credential rotation and self-hosted worker firewalls.
7. **Operations:** minimal audit records, monitoring access, incident contacts,
   quotas/budgets, change approval and a safe rollback that does not switch
   to an unapproved provider.

**Still unverified for this PoC:** exact Cursor processing locations; Claude's
selected hosting option and effective contractual retention; Modified Abuse
Monitoring approval; enterprise residency/CMEK/policy settings; provider
deletion and backup behavior; and a production private gateway. These are
approval gaps, not evidence of a breach.

Three source differences are deliberately left visible: the Azure EU-zone
definitions, Anthropic's general versus arrangement-specific retention
wording, and Cursor's high-level "deleted after completion" Cloud Agent
description versus the feature-specific indefinite-conversation/rolling-
snapshot policy. Use the detailed retention policy for planning and obtain
written confirmation where a contract depends on the distinction.
[M5, P10, P14, P15, P1, C13]

For connection instructions, return to [IDE](ide.md), [CLI](cli.md),
[Cloud Agents](cloud.md) or [Foundry setup](setup.md). The
[development study](development.md) measures engineering trade-offs; it does
not establish enterprise compliance. All numbered source references are
interactive superscripts on the website; see [Sources](../SOURCES.md).
