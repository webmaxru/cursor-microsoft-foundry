"""Show recent model requests for one Foundry deployment from Azure Monitor.

Use it to prove that a client really reached your deployment, for example after you
send one prompt from Cursor with the Azure OpenAI key slot enabled. Cursor's error
banners do not say whether a request left Cursor's servers; these metrics do.

Reads metrics through `az monitor metrics list` with your signed-in Azure CLI. It
needs Monitoring Reader on the resource and never reads or prints keys.

Metrics usually appear 1-3 minutes after a request. Azure Monitor does not count
requests that fail key authentication (401), so a wrong key shows nothing here.
"""

import argparse
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from foundry_client import load_config


def resource_id(config):
    return (f"/subscriptions/{config['subscription_id']}/resourceGroups/{config['resource_group']}"
            f"/providers/Microsoft.CognitiveServices/accounts/{config['account_name']}")


def query(config, deployment, metric, minutes):
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)
    command = [
        "az", "monitor", "metrics", "list", "--resource", resource_id(config),
        "--metrics", metric, "--aggregation", "Total", "--interval", "PT1M",
        "--start-time", start.isoformat(), "--end-time", end.isoformat(),
        "--filter", (f"ModelDeploymentName eq '{deployment}' and StatusCode eq '*'"
                   " and OperationName eq '*' and StreamType eq '*'"),
        "-o", "json"]
    result = subprocess.run(command, capture_output=True, text=True, shell=os.name == "nt", timeout=180)
    if result.returncode:
        raise SystemExit(f"az monitor metrics list failed: {result.stderr.strip()[:500]}")
    return json.loads(result.stdout)


def summarize(payload):
    rows, totals = [], defaultdict(int)
    for metric in payload.get("value", []):
        for series in metric.get("timeseries", []):
            labels = {item["name"]["value"]: item["value"] for item in series.get("metadatavalues", [])}
            for point in series.get("data", []):
                count = int(point.get("total") or 0)
                if count:
                    status = labels.get("statuscode", "?")
                    rows.append({"minute": point["timeStamp"], "status": status,
                                 "operation": labels.get("operationname", "?"),
                                 "stream": labels.get("streamtype", "?"), "requests": count})
                    totals[status] += count
    rows.sort(key=lambda row: row["minute"])
    return rows, dict(totals)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="Path to foundry.json (default: config/foundry.json).")
    parser.add_argument("--deployment", help="Deployment name (default: deployment_name from the config).")
    parser.add_argument("--minutes", type=int, default=30, help="Look-back window in minutes (default 30).")
    parser.add_argument("--metric", default="ModelRequests", choices=["ModelRequests", "AzureOpenAIRequests"])
    parser.add_argument("--out", help="Optional path for a JSON copy of the result.")
    args = parser.parse_args()
    if not 1 <= args.minutes <= 1440:
        parser.error("--minutes must be between 1 and 1440.")

    config = load_config(args.config) if args.config else load_config()
    deployment = args.deployment or config["deployment_name"]
    rows, totals = summarize(query(config, deployment, args.metric, args.minutes))

    print(f"{args.metric} for deployment '{deployment}', last {args.minutes} min (UTC):")
    for row in rows:
        print(f"  {row['minute']}  status {row['status']:>4}  {row['operation']:<28} {row['stream']:<14} {row['requests']}")
    if not rows:
        print("  none recorded (allow 1-3 minutes for metrics to arrive)")
    print("Totals by status:", json.dumps(totals) if totals else "{}")

    if args.out:
        record = {"checked_at": datetime.now(timezone.utc).isoformat(), "metric": args.metric,
                  "deployment": deployment, "minutes": args.minutes, "rows": rows, "totals": totals}
        Path(args.out).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
