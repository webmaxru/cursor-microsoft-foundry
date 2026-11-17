# Cursor + Microsoft Foundry

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

Publish an independent, reproducible investigation of using Microsoft Foundry
inference from Cursor CLI, Cursor IDE, and Cursor Cloud Agents. Readers can
understand the limits, select a supported path, configure it, and inspect
the recorded evidence.

## Users

Inferred from the research brief: developers and technical evaluators who use
Cursor and want OpenAI or Anthropic models deployed in Microsoft Foundry.
They need practical instructions and verifiable results, not promotional claims.

## Capabilities and Constraints

- Keep CLI, IDE, and Cloud as distinct, prominent sections.
- Shared pages cover setup, findings, scripts, evidence, and sources.
- The local MCP bridge calls Foundry OpenAI and Claude models as tools. It
  does not replace Cursor's own agent model.
- CLI and IDE MCP paths have recorded end-to-end evidence. The IDE's own-key
  path was inspected but not tested with a key. Cloud is an unexecuted blueprint.
- Preserve those confidence distinctions, source citations, and all evidence.
- Publish static HTML on GitHub Pages, generated from Markdown with Python.
- Keep old guide links and anchors working. Do not require JavaScript to read
  the guides or navigate the website.
- Publish no Azure credentials or private account identifiers.
- Use "current" and "legacy" for API shapes, with date context in notes.

## Brand Commitments

The name is Cursor + Microsoft Foundry. This is independent research, not an
official Cursor or Microsoft website. The requested redesign must look polished
and avoid generic AI-generated design conventions.

## Evidence on Hand

`FINDINGS.md`, `SOURCES.md`, and `docs/` contain the investigation and guides.
`evidence-snapshot/` contains redacted live-run records. `docs/assets/` contains
three real Cursor IDE screenshots. `scripts/` and `tests/` supply reproducible
checks. Do not invent additional results, product capabilities, or endorsements.

## Product Principles

- Distinguish inference as a tool from inference as the primary agent model.
- Show what was measured and what remains unverified.
- Keep instructions reproducible and evidence reachable.
- Preserve technical detail without making the entry page a transcript.
