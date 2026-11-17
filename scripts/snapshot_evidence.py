"""Copy local evidence into evidence-snapshot/ with account-identifying values replaced.

The raw evidence/ directory stays local (gitignored). The snapshot keeps response IDs,
hashes, usage and model behavior, but replaces the subscription, resource group,
Foundry resource/project names, the local home path and unrelated deployment names.
"""

import getpass
import json
import re
import shutil
from pathlib import Path

from foundry_client import EXAMPLE_CONFIG_PATH, ROOT, load_config

SOURCE = ROOT / "evidence"
TARGET = ROOT / "evidence-snapshot"
FILES = [
    "environment.json",
    "cursor-cli-help.txt",
    "cursor-routing-initial.json",
    "cursor-routing.json",
    "deployment.json",
    "deployment-created.json",
    "deployment-inventory.json",
    "openai-direct-smoke.json",
    "openai-mcp-smoke.json",
    "claude-direct-smoke.json",
    "claude-mcp-smoke.json",
    "openai-responses-features.json",
    "claude-responses-features.json",
    "claude-anthropic-features.json",
    "claude-api-formats.json",
    "cursor-mcp-e2e.json",
    "ide-transcript.txt",
    "ide-mcp-e2e.json",
    "openai-api-routes.json",
    "fullswitch-key-routes.json",
    "cli-fullswitch.json",
    "litellm-gateway.json",
    "litellm-gateway-docker.json",
    "premium-round.json",
    "key-route-probe.json",
    "claude-proxy-probe.json",
    "ide-realkey-round.json",
    "ide-realkey-cursor-log-summary.json",
    "ide-realkey-diag-rows.json",
    "usage-check-selftest.json",
    "development-study.json",
    "development-pilot.json",
    "development-followup.json",
    "guide-prompt-output.txt",
    "foundry-audit.jsonl",
    "unit-tests.txt",
]
GUID = r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}"
AZURE_HOST = re.compile(r"\b([a-z0-9][a-z0-9-]*)\.(openai\.azure\.com|services\.ai\.azure\.com|cognitiveservices\.azure\.com)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def build_redactor(real, example):
    pairs = {real[key]: example[key] for key in ("subscription_id", "resource_group", "account_name", "project_name")}
    home = str(Path.home())
    pairs[home] = "~"
    pairs[home.replace("\\", "\\\\")] = "~"
    pairs[home.replace("\\", "/")] = "~"
    user = getpass.getuser()
    if len(user) >= 4:
        pairs[user] = "user"
    literal = re.compile("|".join(re.escape(key) for key in sorted(pairs, key=len, reverse=True)))

    def redact(text):
        text = literal.sub(lambda match: pairs[match.group(0)], text)
        text = re.sub(r"(/subscriptions/)" + GUID, r"\g<1>" + example["subscription_id"], text, flags=re.IGNORECASE)
        text = AZURE_HOST.sub(
            lambda m: m.group(0) if m.group(1) == example["account_name"] else f"other-foundry-resource.{m.group(2)}",
            text,
        )
        return EMAIL.sub("user@example.invalid", text)

    return redact


def trim_deployments(name, text, keep):
    if name == "deployment-inventory.json":
        data = [entry for entry in json.loads(text) if entry.get("deployment") in keep]
        return json.dumps(data, indent=2) + "\n"
    if name in ("deployment.json", "deployment-created.json"):
        data = json.loads(text)
        before = data.get("existing_deployments_before") or []
        data["existing_deployments_before"] = [item for item in before if item in keep]
        data["other_deployments_omitted"] = len([item for item in before if item not in keep])
        return json.dumps(data, indent=2) + "\n"
    return text


def main():
    real = load_config()
    example = load_config(EXAMPLE_CONFIG_PATH)
    redact = build_redactor(real, example)
    keep = {real["deployment_name"], real["claude_deployment_name"]}
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir()
    written = []
    for name in FILES:
        source = SOURCE / name
        if not source.is_file():
            print(f"skip (missing): {name}")
            continue
        text = trim_deployments(name, source.read_text(encoding="utf-8-sig"), keep)
        (TARGET / name).write_text(redact(text), encoding="utf-8", newline="\n")
        written.append(name)
    forbidden = [real["subscription_id"], real["account_name"], real["resource_group"], str(Path.home())]
    for name in written:
        content = (TARGET / name).read_text(encoding="utf-8")
        leaked = [value for value in forbidden if value in content]
        if leaked:
            raise RuntimeError(f"Redaction failed for {name}.")
    print(f"Wrote {len(written)} redacted files to {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
