# Sources and confidence

Accessed during 17 November 2026 local time. This file records source URLs and
our summaries rather than republishing third-party pages. Documentation and
forum content can change after the observation date.

## Official Cursor documentation

| Key | Source | Relevance |
| --- | --- | --- |
| C1 | [CLI configuration](https://cursor.com/docs/cli/reference/configuration) | Global vs project config, published schema, network proxy settings; no documented Azure model-provider block |
| C2 | [CLI parameters](https://cursor.com/docs/cli/reference/parameters) | Model/auth/MCP/worker flags; compare with saved installed `--help` |
| C3 | [CLI authentication](https://cursor.com/docs/cli/reference/authentication) | Browser login vs Cursor API keys; provider keys are not Cursor credentials |
| C4 | [CLI MCP](https://cursor.com/docs/cli/mcp) and [MCP configuration](https://cursor.com/docs/mcp) | Shared CLI/editor MCP configuration, tools, stdio and HTTP transports, approval model |
| C5 | [Cloud Agents overview](https://cursor.com/docs/cloud-agent) | Curated models, runtimes, billing and supported plans |
| C6 | [Current Cloud Agents API](https://cursor.com/docs/cloud-agent/api/endpoints) and [OpenAPI](https://cursor.com/docs-static/cloud-agents-openapi.yaml) | Agent/run request shape, model catalog IDs, inline MCP configuration, environment variables |
| C7 | [Cloud Agent capabilities](https://cursor.com/docs/cloud-agent/capabilities) | HTTP vs stdio MCP, credential visibility, no SSE in the capabilities guidance |
| C8 | [Self-Hosted Machines](https://cursor.com/docs/cloud-agent/self-hosted) | Explicit distinction: Cursor owns inference/planning; worker executes tools |
| C9 | [AWS Bedrock](https://cursor.com/docs/customizing/aws-bedrock) | Provider-specific integration exists; cannot extrapolate it to Azure |
| C10 | [Cloud Agent OIDC identity](https://cursor.com/docs/cloud-agent/identity) | Issuer, token socket, audience/subject controls and five-minute token lifetime |
| C11 | [Bring your own API key](https://cursor.com/help/models-and-usage/api-keys) | IDE providers (including an Azure OpenAI slot: "Models deployed in your Azure OpenAI Service instance"), chat models only, requests and keys through Cursor's backend, zero data retention not applying, and billing differences by plan |
| C12 | [Legacy Cloud Agents API](https://cursor.com/docs/cloud-agent/api/v0) | Older body/model shape and explicit lack of MCP in that surface |
| C13 | [Cloud Agent Secrets & Network](https://cursor.com/docs/cloud-agent/security-network) | Secrets, egress, VM and conversation retention, OIDC guidance |
| C14 | [CLI permissions](https://cursor.com/docs/cli/reference/permissions) | Exact `Mcp(server:tool)`, `Shell`, `Read`, `Write` and `WebFetch` allow/deny syntax |
| C15 | [Cursor CLI product page](https://cursor.com/cli) | Product scope and links to automation/headless documentation; not proof of BYOK support |
| C16 | [Network configuration](https://cursor.com/docs/enterprise/network-configuration) | Zero data retention doesn't apply when requests use your own API keys |
| C17 | [Models and pricing](https://cursor.com/docs/models-and-pricing) | The $0.25 per million tokens Cursor Token Rate that applies to own-key use on Teams and Enterprise |
| C18 | [CLI output formats](https://cursor.com/docs/cli/reference/output-format) | NDJSON tool start/completion events, terminal results and session IDs. The tested CLI also emitted usage counters; the documented example does not define their cache-accounting semantics |
| C19 | [Cursor rules](https://cursor.com/docs/rules) | Persistent project instructions in `.cursor/rules/*.mdc` or `AGENTS.md`; referenced file contents are not automatically inlined. Rules guide the Cursor host, not a separate Foundry call |
| C20 | [Reporting a bug](https://cursor.com/help/troubleshooting/reporting-bugs) | How to copy a Request ID from a conversation's "..." menu and send it through the forum or email; Request IDs are lookup keys for Cursor's backend, and connectivity issues can often be debugged with Privacy Mode on |

## Requested forum threads and related community evidence

| Key | Source | Date / confidence and qualification |
| --- | --- | --- |
| F1 | [Support for Azure AI Foundry, staff reply #10](https://forum.cursor.com/t/support-for-azure-ai-foundry/162862/10) and [full thread](https://forum.cursor.com/t/support-for-azure-ai-foundry/162862) | June 2026 staff answer: IDE Azure OpenAI-format limitations, and a statement that requests go directly to your provider, which the current docs contradict [C11]; not a current CLI configuration guide |
| F2 | [Allow use of Claude models through Azure Foundry](https://forum.cursor.com/t/allow-use-of-claude-models-through-azure-foundry/145774) | December 2025 feature request; does not establish delivered functionality |
| F3 | [Request to override Anthropic Base URL](https://forum.cursor.com/t/request-to-override-anthropic-base-url/161445) | May 2026 request; staff confirms traffic through Cursor; later users still request override |
| F4 | [Enable Azure OpenAI settings in cursor-agent CLI](https://forum.cursor.com/t/enable-azure-openai-settings-when-using-cursor-agent-cli/151891) | February 2026 user report specific to CLI; behavior substantially consistent with the new probes |
| F5 | [Cursor CLI custom endpoint and API key support](https://forum.cursor.com/t/cursor-cli-custom-endpoint-and-api-key-support/129424) | Request spanning August 2025-August 2026; no demonstrated generic inference override |
| F6 | [Azure Anthropic Proxy for Cursor](https://forum.cursor.com/t/azure-anthropic-proxy-for-cursor-claude-opus-4-5/147042) | Community workaround plus staff acknowledgement; author later says it was mainly used with Ctrl+K, not Agent |
| F7 | [Enterprise BYOK + AI Gateway model-routing report](https://forum.cursor.com/t/enterprise-byok-ai-gateway-built-ins-ignore-override-base-url-need-anthropic-override/175824) | October 2026 community report, not a guarantee or instruction to use model-ID collisions |
| F8 | [Fable 5.2 BYOK errors, news on Azure Foundry](https://forum.cursor.com/t/fable-5-2-byok-errors-news-on-azure-foundry/177890) | November 2026 staff reply: Foundry OpenAI deployments, including `*.cognitiveservices.azure.com` endpoints, should work through the IDE Azure OpenAI key; no dedicated Foundry integration or timeline |
| F9 | [Azure OpenAI GPT-6 Astra: unknown parameter `reasoning`](https://forum.cursor.com/t/azure-openai-gpt-6-astra-unknown-parameter-reasoning/175820) | October 2026 staff reply: some models go to Chat Completions with a Responses-only reasoning setting; GPT-5.6 uses Responses; known issue |
| F10 | [Azure OpenAI BYOK Agent fails with `response.failed` on GPT-5.4 and GPT-5.6](https://forum.cursor.com/t/bug-azure-openai-byok-agent-fails-with-response-failed-error-null-on-gpt-5-4-and-gpt-5-6/166822) | July 2026 bug report; model-specific Azure slot failures |
| F11 | [Rate limited by model provider](https://forum.cursor.com/t/rate-limited-by-model-provider/172594) | September 2026 staff reply: any key toggle routes all models except Auto, Composer and Cursor's Grok through your keys; an empty Azure entry breaks them |
| F12 | [All models fail with `resource_exhausted` on new conversations](https://forum.cursor.com/t/bug-all-models-fail-with-resource-exhausted-on-new-conversations-pro-plan/175267) | October 2026: caused by **Use Azure OpenAI** on with empty fields |
| F13 | [AWS Bedrock model name not valid for explicit IDs](https://forum.cursor.com/t/aws-bedrock-model-name-is-not-valid-for-all-explicit-bedrock-ids-auto-works/177396) | November 2026 staff reply: Azure settings take precedence over Bedrock; Auto never uses your keys |
| F14 | [AWS Bedrock unknown parameter](https://forum.cursor.com/t/aws-bedrock-unknown-parameter/175840) | October 2026: Azure rejected a Claude-format request with "Unknown parameter: 'system'" while both were on |
| F15 | [Grok 4.6 blocked by Cloudflare](https://forum.cursor.com/t/cursor-grok-4-6-fails-on-every-prompt-with-cloudflare-sorry-you-have-been-blocked-on-x-ai/170286) and [Grok 4.6 not working](https://forum.cursor.com/t/cursor-grok-4-6-not-working/170287) | September 2026 staff replies: Grok 4.6 runs only on Cursor's infrastructure; turn off keys and the override |
| F16 | [Persistent network error; only Auto and Composer work](https://forum.cursor.com/t/persistent-network-error-cloudflare-block-only-auto-composer-work-pro/172443) | September 2026 report with the same key-related cause |
| F17 | [Can't use Opus and GPT models](https://forum.cursor.com/t/cant-use-opus-and-gpt-models/164728) | July 2026 staff reply: remove the OpenAI override or Azure key while using Anthropic models |
| F18 | [Custom OpenAI override and Cursor models can't both stay enabled](https://forum.cursor.com/t/custom-openai-override-and-cursor-models-cannot-both-stay-enabled/172795) | September 2026: the override applies to every non-Claude, non-Gemini model, including Composer and Grok |
| F19 | [Can't use any models if OpenAI base URL is overridden](https://forum.cursor.com/t/cannot-use-any-models-if-openai-base-url-overridden/140266) | October 2025 report |
| F20 | [Custom base URLs for each custom model](https://forum.cursor.com/t/custom-base-urls-for-each-custom-model/147219) | December 2025 feature request; not delivered |
| F21 | [How to use a custom OpenAI-compatible API in Cursor](https://forum.cursor.com/t/how-to-use-a-custom-openai-compatible-api-in-cursor-setup-limits-and-tips/171497) | September 2026 community guide, not official documentation |
| F22 | [Adding new models](https://forum.cursor.com/t/adding-new-models/176811) | October 2026 staff reply: supported key providers are OpenAI, Anthropic, Google, Azure OpenAI and Bedrock; keys apply to chat only, Tab uses Cursor; some plans exclude own keys |
| F23 | [Why is BYOK not available on cloud agents](https://forum.cursor.com/t/why-is-byok-not-available-on-cloud-agents/167358) | Created August 2026; staff reply 5 August 2026: keys are attached by the IDE client on each request, headless runs have no client, and cloud runs include VM compute |
| F24 | [Support for BYOK in Cloud Agents](https://forum.cursor.com/t/support-for-byok-in-cloud-agents/161348) | May to November 2026, 9 posts: continued requests; no delivered feature |
| F25 | [Can I use provider API keys with Cursor cli agent?](https://forum.cursor.com/t/can-i-use-provider-api-keys-with-cursor-cli-agent/149158) | January to November 2026, 8 posts; staff reply in November 2026: the CLI doesn't support provider API keys |
| F26 | [Anthropic BYOK still unusable while Override OpenAI Base URL is set](https://forum.cursor.com/t/anthropic-byok-still-unusable-while-override-openai-base-url-is-set-one-global-toggle-breaks-claude-byok-windows-3-27-22/177380) | November 2026 user report: the one global override breaks Claude BYOK |
| F27 | [Cursor-managed models are routed through Override OpenAI Base URL](https://forum.cursor.com/t/cursor-managed-models-are-routed-through-override-openai-base-url/169088) | August to October 2026; staff confirmed in August that managed models are routed through the override |
| F28 | [Azure AI API models still unreliable in Cursor](https://forum.cursor.com/t/azure-ai-api-models-still-unreliable-in-cursor-please-prioritize-a-native-fix/150606) | February to March 2026: user reports plus staff pointing at tool-schema problems for file operations and missing Responses API support on Azure |
| F29 | [When will Cursor fully support BYOK?](https://forum.cursor.com/t/when-will-cursor-fully-support-byok/164375) | June 2026, 8 posts: no per-model base URL or parameters; "no concrete timeline" |
| F30 | [Override OpenAI Base URL not working](https://forum.cursor.com/t/override-openai-base-url-not-working/168323) and [The custom override of the OpenAI base URL is unusable](https://forum.cursor.com/t/the-custom-override-of-the-openai-base-url-is-unusable/152675) | August 2026 and February 2026 user reports only; not reproduced here |
| F31 | [Using Azure OpenAI API Key](https://forum.cursor.com/t/using-azure-openai-api-key/162214) | June to August 2026, 13 posts. Staff, 29 July: the Base URL must be only `https://<resource>.openai.azure.com`, "Cursor appends the rest", with the real deployment name, and a Foundry project endpoint (`*.services.ai.azure.com`) is not supported; the user confirmed it worked. Staff, 30 July: with an OpenAI key or the override on, credentials go with every request, so Cursor-only models fail and Auto works. A user ran GPT-5.6 Luna through the Azure slot autonomously in August |
| F32 | [Not able to use azure api key](https://forum.cursor.com/t/not-able-to-use-azure-api-key/149185) | January to July 2026, 33 posts. `model is required` traced to Cursor; a custom model named after the deployment worked for some; staff recommended a community proxy [G3] in April; image attachments bypass the custom URL; fixed in July |
| F33 | [Azure GPT-5 API Key Not Working, Internal Server Error](https://forum.cursor.com/t/azure-gpt-5-api-key-not-working-internal-server-error/128572) | August to September 2025, 42 posts. With the Azure slot on only Auto worked; closed without a fix |
| F34 | [BYOK with Azure OpenAI no longer works since 12 hours](https://forum.cursor.com/t/byok-with-azure-openai-no-longer-works-since-12-hours/161692) | May to June 2026. "Network Error" with the Azure slot. Staff first called it a 502 on Cursor's side that fails "before they ever get sent to Azure"; the user then found a misspelled Base URL and asked for a clearer error message. The same message covered both explanations |
| F35 | [Azure OpenAI model with key stopped working, works from curl](https://forum.cursor.com/t/azure-open-ai-model-with-key-stop-working-works-from-curl/165482) | July 2026. `400 invalid_input: model is required` on 3.11.19; staff: requests were built without the model and rejected before Azure; fixes merged 22 July |
| F36 | [Azure OpenAI with GPT-5.6 Terra fails with "Request higher limits"](https://forum.cursor.com/t/azure-openai-with-gpt-5-6-terra-fails-with-request-higher-limits-in-cursor-3-15-6/168107) | August 2026 staff reply: on pooled Team and Enterprise plans own-key requests count toward usage limits and the block happens before Azure; a wrong deployment name can show the same error |
| F37 | [Azure OpenAI BYOK in Cursor Agent fails with "model is required"](https://forum.cursor.com/t/azure-openai-byok-in-cursor-agent-fails-with-model-is-required-even-though-the-same-azure-deployment-works-with-curl/162417) | June to July 2026. The model field was dropped; staff: own-key requests go to the provider and Cursor credits don't affect them; fixed 8 July |

The public proxy endpoint in F6 was not invoked. No Azure credentials were
shared with a community proxy. The author's code was not incorporated.

### Other public discussion

| Key | Source | Relevance |
| --- | --- | --- |
| H1 | [Hacker News comment, May 2025](https://news.ycombinator.com/item?id=43907187) | In a Gemini 2.5 Pro thread: run Cursor through a LiteLLM proxy for per-project keys, budgets and traces; mentions LLemonStack [G11] |
| H2 | [Hacker News comment, August 2025](https://news.ycombinator.com/item?id=44830915) | On the Cursor CLI launch: even with your own key, requests are routed through Cursor's servers |
| Q1 | [Why doesn't my Azure OpenAI model show up in Cursor?](https://stackoverflow.com/questions/79544040/why-doesnt-my-azure-openai-model-show-up-in-cursor) | March 2025 question; the answer says the Deployment Name must match the Azure deployment exactly. Old model list; the naming advice still matches F31 |

## Microsoft / Anthropic primary sources

| Key | Source | Relevance |
| --- | --- | --- |
| M1 | [Foundry model endpoints](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/endpoints) | Account `/openai/v1/` routing, deployment aliases, Entra scope, SDK usage |
| M2 | [Deploy and use Claude models in Foundry](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-claude) | Native `/anthropic/v1/messages`, AnthropicFoundry client, Entra auth and header/API differences |
| M3 | [Foundry SDKs and endpoints](https://learn.microsoft.com/azure/foundry/how-to/develop/sdk-overview) | Distinguishes project, OpenAI and Anthropic surfaces; general Claude wording is narrower than the live Responses result here |
| M4 | [Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses) and [reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning) | Responses requests, tool continuation, streaming, reasoning and incomplete-result handling |
| M5 | [Foundry model deployment types](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types) | DataZoneStandard vs GlobalStandard, pay-per-token vs reserved capacity, residency limitations |
| M6 | [Foundry model deployment quickstart](https://learn.microsoft.com/azure/foundry/tutorials/quickstart-create-foundry-resources#deploy-a-model) | Azure CLI model-deployment command shape |
| M7 | [Partner models: Anthropic](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-from-partners#anthropic) | Haiku-specific capability/parameter differences; do not copy all Sonnet examples blindly |
| M8 | [Configure keyless authentication with Microsoft Entra ID](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/configure-entra-id) | `Cognitive Services User` role for inference on all Foundry models; Owner/Contributor alone do not grant inference; role propagation delay |
| M9 | [Databricks AI Gateway with Cursor](https://learn.microsoft.com/en-us/azure/databricks/ai-gateway/coding-agent-cursor) | Updated 11 November 2026. Microsoft's own pattern for pointing the Cursor IDE at a gateway: Models > API Keys, Override OpenAI Base URL, the gateway token as the OpenAI key, and **+ Add Custom Model**. It isn't a Foundry guide; there is none |
| A1 | [Anthropic OpenAI SDK compatibility](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) | Compatibility for the Claude API is not proof that every Foundry endpoint exposes the same routes |
| A2 | [Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming) | Native stream events, text streaming and tool/usage semantics |
| A3 | [Claude Code on Microsoft Foundry](https://code.claude.com/docs/en/microsoft-foundry) | The full switch used for comparison: `CLAUDE_CODE_USE_FOUNDRY=1`, `ANTHROPIC_FOUNDRY_RESOURCE` or `ANTHROPIC_FOUNDRY_BASE_URL`, an API key, Entra ID or a token for authentication, and pinned model variables. Read as documentation; Claude Code was not run |
| O1 | [OpenAI models in Cursor](https://help.openai.com/en/articles/20001506-using-openai-models-in-cursor) | Directional desktop BYOK/gateway guidance explicitly excludes CLI and Cloud; defers to Cursor for evolving behavior |

## Maintained implementation references and secondary research

| Key | Source | How it was used |
| --- | --- | --- |
| S1 | [Official MCP Python SDK, supported v1 line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x) | FastMCP server and stdio client; installed versions are pinned in the lockfile |
| S2 | [MCP tools specification](https://modelcontextprotocol.io/specification/latest/server/tools) | Model-controlled tools return results to the host model. Calling a tool is not replacement of that model or automatic sharing of its conversation |
| L1 | [LiteLLM Azure Anthropic provider](https://docs.litellm.ai/docs/providers/azure/azure_anthropic) | Maintained translator for Foundry Claude. Versions 1.108.4 (pip) and 1.109.1 (Docker) passed the 15 gateway probes here; Cursor never called them |
| L2 | [LiteLLM: use with Cursor](https://docs.litellm.ai/docs/tutorials/cursor_integration) | Base URL `<proxy>/cursor`, reachable from the internet because Cursor calls it from its servers with `User-Agent: Cursor/1.0`; Agent mode since LiteLLM 1.97.0; "Cursor gates custom API keys by mode and model on its side". Documents an Azure-slot fallback verified on Cursor 3.17.21, which did not reach a gateway on 3.30.14 here. Its CLI relay (1.112) only relays Cursor's own sessions and is not a model route |
| G1 | [sherkevin/cursor-agent-byok](https://github.com/sherkevin/cursor-agent-byok) | Claims to run the Cursor Agent CLI with your own OpenAI- or Anthropic-compatible key. Source read, not run: it impersonates Cursor's API host with a local certificate and forwards to `127.0.0.1:18090`, which nothing in the repository serves, and the provider URL and key you enter are never passed on. 3 stars, MIT |
| G2 | [leookun/cursor-byok](https://github.com/leookun/cursor-byok) | Local replacement for Cursor's backend, intercepting the IDE's traffic with a local certificate authority. About 3,200 stars, MIT, archived October 2026; Tab completion defaults to the author's service. Read, not run |
| G3 | [gabrii/Cursor-Azure-GPT-5](https://github.com/gabrii/Cursor-Azure-GPT-5) | Flask gateway that turns the IDE override's requests into Azure Responses API calls; needs a paid plan and a public endpoint. Recommended by Cursor staff in April 2026 [F32]. 75 stars, MIT, last push July 2026. Read, not run |
| G4 | [rosch100/AI-Model-proxy](https://github.com/rosch100/AI-Model-proxy) | Archived copy of G3 with newer model mappings, including Luna |
| G5 | [xFurti/cursor-custom-provider](https://github.com/xFurti/cursor-custom-provider) | Model-name rewriting gateway with an automatic HTTPS tunnel for the IDE override. 19 stars, MIT |
| G6 | [0xSero/factory-cursor-bridge](https://github.com/0xSero/factory-cursor-bridge) | IDE override gateway translating between OpenAI and Anthropic formats. 85 stars, no license |
| G7 | [bcat95/Cursor-Azure-Claude](https://github.com/bcat95/Cursor-Azure-Claude) | OpenAI-to-Anthropic gateway for Azure-hosted Claude; the author used it mainly with Ctrl+K [F6]. 11 stars, no license |
| G8 | [Alorse/llm-proxy](https://github.com/Alorse/llm-proxy) | Aliases any OpenAI-compatible model under a name Cursor accepts. 24 stars, MIT, last push July 2025 |
| G9 | [hainuoli/cursor-byok](https://github.com/hainuoli/cursor-byok) | Backend replacement like G2, active (v1.1.0, 14 November 2026). 55 stars, MIT. Not run |
| G10 | [Yimikami/cursor-byok](https://github.com/Yimikami/cursor-byok) | Desktop app that turns the IDE into an own-key client "without Pro account". 57 stars, AGPL-3.0. Not run |
| G11 | [LLemonStack](https://github.com/LLemonStack/llemonstack) | Local stack that packages LiteLLM with Langfuse tracing [H1]. 146 stars, AGPL-3.0 |
| X1 | [OpenCode providers](https://opencode.ai/docs/providers) | Documents `azure` provider modes for chat and responses. Configuration docs only; not tested |
| X2 | [Codex advanced configuration](https://developers.openai.com/codex/config-advanced) | Documents an Azure provider and per-provider tuning. Configuration docs only; not tested |
| B1 | [Cursor BYOK guide, BYOKList](https://byoklist.com/guides/cursor-byok) | Secondary cross-check on IDE setup/privacy; not treated as authoritative CLI or Cloud evidence |

## Interpreting apparent contradictions

- Search summaries sometimes confuse the **Cursor service endpoint** with a
  model-provider base URL. The installed help and local HTTP probes are the
  evidence for the CLI distinction.
- A June 2026 staff reply says requests go directly to your provider [F1];
  the current Cursor documentation says your key and requests pass through
  Cursor's servers [C11, C16]. The documentation is treated as authoritative.
- Staff cite `*.cognitiveservices.azure.com` endpoints for Foundry [F8], while
  another staff reply and the slot's placeholder use `*.openai.azure.com`
  [F31]. Both host names exist on a Foundry resource. With the resource's
  real key, both forms gave the same "Network Error" through Cursor and
  Foundry recorded no successful request. Direct calls with the same key
  succeeded on both hosts for the GPT deployments.
- LiteLLM documents the Azure slot reaching a LiteLLM gateway on Cursor
  3.17.21 [L2]. On 3.30.14 two non-Azure hosts in the slot received no
  requests. Cursor may have restricted the slot since, or it may differ by
  plan; this was not resolved.
- Third-party proxy documentation can list `/chat/completions` because the
  proxy implements it. That does not make it an Azure-native endpoint.
- Generic statements that Claude requires a separate Anthropic API are useful
  integration guidance, but did not predict the successful Responses calls
  against this specific Haiku deployment. Both observations are documented.
- A model appearing in Cursor's catalog, or sharing its name with an Azure
  deployment, does not identify which account pays for inference.
- Protocol and feature support can be deployed incrementally. The saved
  evidence establishes behavior of the tested versions/account, not a
  universal service contract.

## Coverage limits

- Community evidence comes mostly from the Cursor forum, read through its
  public JSON API, plus two Hacker News comments [H1, H2] and one Stack
  Overflow question [Q1]. Reddit and X could not be read without signing in
  and are not covered.
- Claude Code was compared through its documentation [A3] and not run.
  OpenCode and Codex were read through their configuration documentation
  [X1, X2]. Cline, Roo Code, Continue and GitHub Copilot were not checked.
- The community bridges [G1 to G11] were read, not run. Backend replacements
  [G2, G9, G10] install a local certificate authority and impersonate Cursor's
  servers; running them is a security decision, so read Cursor's terms and
  the code first.
- The Premium round used one individual plan. Team and Enterprise plans, and
  other Cursor versions, may behave differently.
- The later [development study](docs/development.md) could not reproduce native
  CLI MCP dispatch in new Auto or pinned-model sessions, despite successful
  local tool listing. Its measured workaround uses a shell-invoked MCP client.
  Earlier arithmetic evidence is historical, not a guarantee of current
  native-tool availability. The discovery failure's root cause is unresolved.
