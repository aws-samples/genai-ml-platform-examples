#!/usr/bin/env python3
"""Experiment 3: time for a new GLM-5.3 replica to start serving during scale-out.

Raises spec.replicas on an InferenceEndpointConfig by one, finds the new GPU pod,
and records when it was created, scheduled, initialized (image pulled and weights
loaded or prefetched), became Ready, and answered its first request directly on
its pod IP. Run it against exp3-cache-off and exp3-cache-on and compare.

  python scaleout_timer.py --endpoint glm53-cold --namespace glm53 --label cache-off
  python scaleout_timer.py --endpoint glm53-warm --namespace glm53 --label cache-on

Run inside the cluster (the toolbox pod), so the pod IP is reachable. Needs kubectl
with permission to patch inferenceendpointconfigs and read pods in the namespace,
which k8s/namespace.yaml grants to the loadgen service account.
"""

import argparse
import datetime as dt
import json
import subprocess
import time

import httpx

from common import write_results


def kubectl_json(*args):
    out = subprocess.run(["kubectl", *args, "-o", "json"], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def gpu_pods(ns):
    pods = kubectl_json("get", "pods", "-n", ns)["items"]
    return {p["metadata"]["name"]: p for p in pods
            if any("nvidia.com/gpu" in (c.get("resources", {}).get("requests") or {})
                   for c in p["spec"]["containers"])}


def ts(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() if value else None


def condition_time(pod, ctype):
    for c in pod.get("status", {}).get("conditions", []):
        if c["type"] == ctype and c["status"] == "True":
            return ts(c.get("lastTransitionTime"))
    return None


def first_response(ip, port, model, timeout):
    body = {"model": model, "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": 1}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.post(f"http://{ip}:{port}/v1/chat/completions", json=body, timeout=60)
            if r.status_code == 200:
                return time.time()
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", required=True, help="InferenceEndpointConfig name")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--label", required=True, help="label for this run, e.g. cache-on")
    ap.add_argument("--model", default="glm-5.3")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--timeout", type=float, default=7200, help="seconds to wait for the new replica")
    ap.add_argument("--restore", action="store_true", help="scale back to the original count afterwards")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    iec = kubectl_json("get", "inferenceendpointconfig", args.endpoint, "-n", args.namespace)
    before = iec["spec"].get("replicas", 1)
    existing = set(gpu_pods(args.namespace))
    print(f"{args.endpoint}: {before} replica(s), {len(existing)} GPU pod(s); scaling to {before + 1}")

    t_patch = time.time()
    subprocess.run(["kubectl", "patch", "inferenceendpointconfig", args.endpoint, "-n", args.namespace,
                    "--type", "merge", "-p", json.dumps({"spec": {"replicas": before + 1}})], check=True)

    new, deadline = None, t_patch + args.timeout
    while time.time() < deadline:
        pods = gpu_pods(args.namespace)
        added = [p for n, p in pods.items() if n not in existing]
        if added:
            new = added[0]
            if condition_time(new, "Ready"):
                break
        time.sleep(3)
    if not new or not condition_time(new, "Ready"):
        raise SystemExit("new replica did not become Ready within the timeout")

    name, ip = new["metadata"]["name"], new["status"]["podIP"]
    print(f"new pod {name} Ready at {ip}; probing")
    t_serving = first_response(ip, args.port, args.model, timeout=600)

    marks = {
        "created": ts(new["metadata"]["creationTimestamp"]),
        "scheduled": condition_time(new, "PodScheduled"),
        "initialized": condition_time(new, "Initialized"),
        "ready": condition_time(new, "Ready"),
        "first_response": t_serving,
    }
    rel = {k: (round(v - t_patch, 1) if v else None) for k, v in marks.items()}
    summary = {
        "experiment": "scaleout", "label": args.label, "endpoint": args.endpoint,
        "replicas_before": before, "pod": name, "node": new["spec"].get("nodeName"),
        "seconds_after_patch": rel,
        "phases_s": {
            "schedule": rel["scheduled"],
            "init_containers (image pull, weights prefetch)": (round(marks["initialized"] - marks["scheduled"], 1)
                                                               if marks["initialized"] and marks["scheduled"] else None),
            "container_start_to_ready (model load)": (round(marks["ready"] - marks["initialized"], 1)
                                                      if marks["ready"] and marks["initialized"] else None),
        },
        "time_to_serve_s": rel["first_response"],
    }
    write_results(args.out, f"scaleout-{args.label}", [], summary)

    if args.restore:
        subprocess.run(["kubectl", "patch", "inferenceendpointconfig", args.endpoint, "-n", args.namespace,
                        "--type", "merge", "-p", json.dumps({"spec": {"replicas": before}})], check=True)
        print(f"restored {args.endpoint} to {before} replica(s)")


if __name__ == "__main__":
    main()
