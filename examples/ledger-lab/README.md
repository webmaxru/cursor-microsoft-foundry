# Ledger Lab: development-study artifacts

This is the synthetic greenfield project used in the
[MCP development study](../../docs/development.md).

The two directories contain the final application, tests and README produced
by the two workflows. Neither application calls an AI service at runtime:
Foundry was used as a development tool, not embedded in the resulting app.
Both use only the Python standard library.

**These are unchanged research artifacts, with known gaps.** The Foundry-assisted
version accepts an unclosed CSV quote, trims dates more permissively and rejects
leading-zero amounts. Its generated subprocess test assumes UTF-8. See the
[post-study observations](../../docs/development.md#passing-the-planned-tests-was-not-production-readiness);
passing the original acceptance suite is not production approval.

- `cursor-only`: Cursor's pinned Grok 4.7 Medium writes and tests the project itself.
- `foundry-heavy`: The same Cursor model delegates bounded implementation to Foundry
  GPT-6 Luna and test design/review to Foundry Claude Haiku 5.5, then applies
  code and runs tests locally. It uses the explicit shell-invoked MCP client;
  native tool dispatch failed in the separate setup pilots.

Run either application's CLI from the repository root:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python examples\ledger-lab\foundry-heavy\ledger.py examples\ledger-lab\sample.csv --month 2026-02 --refunds
python -m unittest discover -s examples\ledger-lab\foundry-heavy -v
python scripts\development_acceptance.py examples\ledger-lab\foundry-heavy --stage 3
```

Expected CLI output (JSON spacing may differ):

```json
{"food": "12.30", "travel": "3.00"}
```

Replace `foundry-heavy` with `cursor-only` to run the comparison artifact.
The independent acceptance suite is maintained outside both generated
applications; the agents did not write that suite.

These are small experimental artifacts, not production financial software.
The study is not a security audit or an assurance of arbitrary-size decimal
precision, performance, data persistence or accounting correctness.
