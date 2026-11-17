"""Render or run a LiteLLM gateway that serves Foundry GPT and Claude deployments to Cursor.

Cursor's OpenAI base URL override and Azure OpenAI slot are documented to send OpenAI-shaped
requests from Cursor's servers; Cursor IDE 3.30.14 on a Premium plan sent none to this gateway in
testing. Foundry answers GPT deployments on the OpenAI v1 routes and Claude deployments on the
Anthropic Messages route, so one LiteLLM gateway gives a client a single endpoint for both:

  foundry-luna   Foundry GPT deployment, always called through the Responses API
  foundry-haiku  Foundry Claude deployment, called through the Anthropic Messages route

The aliases deliberately avoid the `gpt-` and `claude-` prefixes. Cursor routes `claude-*` names to
its Anthropic key slot, and names that collide with Cursor's built-in models are rejected.

  python scripts/litellm_gateway.py render            print the config (no secrets in it)
  python scripts/litellm_gateway.py serve --litellm <path>
  python scripts/litellm_gateway.py register --url http://127.0.0.1:4000

`serve` reads the Foundry resource key from FOUNDRY_API_KEY or from `az` in memory and hands it to
LiteLLM through its environment. The gateway key comes from LITELLM_MASTER_KEY, which you set. The
gateway listens on 127.0.0.1; put an HTTPS tunnel or reverse proxy in front of it for Cursor.

`register` is for a gateway that keeps models in its database, such as LiteLLM's Docker quickstart
(STORE_MODEL_IN_DB=True). It adds or replaces the two aliases through the admin API with
LITELLM_MASTER_KEY, and LiteLLM stores the Foundry key encrypted with its salt key.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from foundry_client import load_config

LUNA_ALIAS = "foundry-luna"
HAIKU_ALIAS = "foundry-haiku"
ALIASES = (LUNA_ALIAS, HAIKU_ALIAS)


def model_entries(config):
    """(alias, litellm_params, model_info) for both Foundry deployments; secrets are environment references only.

    Foundry deployment names are your own, so LiteLLM cannot find them in its model map. Without
    hints it treats the deployment as a model with no known features and refuses Cursor's
    `tool_choice` and `reasoning.effort`. base_model points it at the real model's capability row,
    and the Responses route, which checks the deployment's own row, needs supports_reasoning too.
    """
    return [
        (LUNA_ALIAS, {
            # The responses/ prefix sends every request, including Chat Completions bodies, to the
            # Responses API. Foundry GPT models refuse function tools on Chat Completions unless
            # reasoning is switched off, and Cursor's agent sends tools with reasoning on.
            "model": f"openai/responses/{config['deployment_name']}",
            "api_base": config["base_url"].rstrip("/"),
            "api_key": "os.environ/AZURE_AI_API_KEY",
        }, {"base_model": config["model_name"], "supports_reasoning": True}),
        (HAIKU_ALIAS, {
            "model": f"azure_ai/{config['claude_deployment_name']}",
            "api_base": config["anthropic_base_url"].rstrip("/"),
            "api_key": "os.environ/AZURE_AI_API_KEY",
            # Cursor sends OpenAI-only parameters; drop the ones a Claude deployment does not accept.
            "drop_params": True,
        }, {"base_model": f"azure_ai/{config.get('claude_model_name', config['claude_deployment_name'])}"}),
    ]


def yaml_value(value):
    return str(value).lower() if isinstance(value, bool) else value


def render_config(config):
    lines = ["model_list:"]
    for alias, params, info in model_entries(config):
        lines += [f"  - model_name: {alias}", "    litellm_params:"]
        lines += [f"      {key}: {yaml_value(value)}" for key, value in params.items()]
        lines += ["    model_info:"] + [f"      {key}: {yaml_value(value)}" for key, value in info.items()]
    lines += [
        "general_settings:",
        "  master_key: os.environ/LITELLM_MASTER_KEY",
    ]
    return "\n".join(lines) + "\n"


def master_key():
    master = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if not master.startswith("sk-") or len(master) < 24:
        raise SystemExit("Set LITELLM_MASTER_KEY to the gateway's master key (a long value that starts with sk-).")
    return master


def serve(args):
    from probe_fullswitch_routes import resource_key

    master_key()
    if not args.litellm:
        raise SystemExit('LiteLLM not found. Install "litellm[proxy]" in its own environment and pass --litellm.')
    config = load_config()
    env = dict(os.environ, AZURE_AI_API_KEY=resource_key(config),
               LITELLM_LOCAL_MODEL_COST_MAP="True", PYTHONUTF8="1")
    workdir = tempfile.mkdtemp(prefix="litellm-gateway-")
    try:
        settings = Path(workdir) / "litellm.config.yaml"
        settings.write_text(render_config(config), encoding="utf-8")
        print(f"LiteLLM gateway on http://{args.host}:{args.port} serving {', '.join(ALIASES)}", flush=True)
        return subprocess.call([args.litellm, "--config", str(settings), "--host", args.host,
                                "--port", str(args.port)], env=env)
    except KeyboardInterrupt:
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def register(args):
    import httpx

    from probe_fullswitch_routes import resource_key

    base = args.url.rstrip("/")
    headers = {"Authorization": f"Bearer {master_key()}"}
    config = load_config()
    foundry_key = resource_key(config)
    response = httpx.get(base + "/v2/model/info", headers=headers, timeout=30)
    existing = response.json().get("data", []) if response.status_code == 200 else []
    for alias, params, info in model_entries(config):
        for item in existing:
            model_id = (item.get("model_info") or {}).get("id")
            if item.get("model_name") == alias and model_id:
                deleted = httpx.post(base + "/model/delete", headers=headers, json={"id": model_id}, timeout=30)
                print(f"replaced {alias}" if deleted.status_code == 200 else f"could not replace {alias}: {deleted.status_code}")
        body = {"model_name": alias, "litellm_params": {**params, "api_key": foundry_key}, "model_info": info}
        created = httpx.post(base + "/model/new", headers=headers, json=body, timeout=60)
        if created.status_code != 200:
            raise SystemExit(f"Adding {alias} failed with HTTP {created.status_code}.")
        print(f"added {alias} -> {params['model']}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render", help="Print the LiteLLM config for config/foundry.json")
    run = sub.add_parser("serve", help="Run LiteLLM with the rendered config")
    run.add_argument("--litellm", default=os.environ.get("LITELLM_BIN") or shutil.which("litellm"))
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=4000)
    add = sub.add_parser("register", help="Add both aliases to a running LiteLLM that stores models in its database")
    add.add_argument("--url", default="http://127.0.0.1:4000")
    args = parser.parse_args()
    if args.command == "render":
        sys.stdout.write(render_config(load_config()))
        return 0
    if args.command == "register":
        return register(args)
    return serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
