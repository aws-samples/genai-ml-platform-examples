"""Shared pieces for the load generators: a streaming OpenAI-compatible client that
measures time to first token, plus percentile and output helpers."""

import csv
import json
import math
import os
import time

import httpx


async def stream_chat(client, base_url, model, messages, max_tokens, extra_body=None):
    """Send one streaming chat completion and time it.

    Time to first token (TTFT) is measured to the first streamed delta that carries
    any text, reasoning included: GLM-5.3 always reasons, and its reasoning tokens
    are what the user sees first.
    """
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        **(extra_body or {}),
    }
    out = {"ttft_s": None, "e2e_s": None, "prompt_tokens": None, "completion_tokens": None,
           "cached_tokens": None, "status": None, "error": None, "text": ""}
    start = time.perf_counter()
    parts = []
    try:
        async with client.stream("POST", f"{base_url.rstrip('/')}/v1/chat/completions",
                                 json=body) as resp:
            out["status"] = resp.status_code
            if resp.status_code != 200:
                out["error"] = (await resp.aread()).decode(errors="replace")[:300]
                return out
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
                    if piece:
                        if out["ttft_s"] is None:
                            out["ttft_s"] = time.perf_counter() - start
                        parts.append(delta.get("content") or "")
                usage = chunk.get("usage")
                if usage:
                    out["prompt_tokens"] = usage.get("prompt_tokens")
                    out["completion_tokens"] = usage.get("completion_tokens")
                    details = usage.get("prompt_tokens_details") or {}
                    out["cached_tokens"] = details.get("cached_tokens")
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        out["error"] = repr(e)[:300]
    out["e2e_s"] = time.perf_counter() - start
    out["text"] = "".join(parts)
    return out


def make_client(concurrency, timeout_s=1800):
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency * 2)
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_s, connect=30), limits=limits)


def pct(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] if lo == hi else vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def stats(values):
    vals = [v for v in values if v is not None]
    return {"n": len(vals), "p50": pct(vals, 50), "p90": pct(vals, 90), "p95": pct(vals, 95),
            "p99": pct(vals, 99), "mean": sum(vals) / len(vals) if vals else None}


def write_results(out_dir, name, rows, summary):
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(out_dir, f"{name}-{stamp}.csv")
    json_path = os.path.join(out_dir, f"{name}-{stamp}-summary.json")
    if rows:
        keys = [k for k in rows[0] if k != "text"]
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    with open(json_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {csv_path}\nwrote {json_path}")
