#!/usr/bin/env python3
"""Experiment 1: multi-turn coding sessions that resend a large repository context.

Each session simulates a coding agent working on one repository. Every turn sends
the same repository context (the shared prefix), the conversation so far, and a
new question. With prefix-aware routing and the managed tiered KV cache, turns
after the first should reuse the cached repository prefix instead of recomputing
it; with round robin, a turn often lands on a replica that has never seen it.

Run the same command against each arm and compare the summaries:
  python multiturn_coding.py --base-url http://<endpoint-service>:8000 --arm roundrobin
  python multiturn_coding.py --base-url http://<router-service>:8000 --arm prefixaware

Reported per arm: TTFT for turn 1 (cold) and turns 2+ (where reuse should help),
throughput, and cost per million tokens from the node count and hourly price.
"""

import argparse
import asyncio
import json
import os
import random
import time

from common import make_client, stats, stream_chat, write_results

QUESTIONS = [
    "Summarize the architecture of this repository and its main modules.",
    "Find a function that could raise an unhandled exception and explain how to fix it.",
    "Write a unit test for the most complex function in the repository.",
    "Suggest a refactor that reduces duplication between two modules. Show the diff.",
    "Explain how data flows from the entry point to persistent storage.",
    "Add input validation to the public API functions and show the changes.",
    "Identify a performance bottleneck and propose an optimization.",
    "Document the configuration options this code reads, with defaults.",
]

SOURCE_EXT = (".py", ".go", ".java", ".ts", ".js", ".rs", ".c", ".h", ".cpp", ".md", ".yaml")


def repo_context_from_dir(repo_dir, chars, rng):
    files = []
    for root, _, names in os.walk(repo_dir):
        if "/." in root:
            continue
        files += [os.path.join(root, n) for n in names if n.endswith(SOURCE_EXT)]
    rng.shuffle(files)
    out, size = [], 0
    for path in files:
        try:
            text = open(path, errors="replace").read()
        except OSError:
            continue
        block = f"\n### File: {os.path.relpath(path, repo_dir)}\n{text}\n"
        out.append(block)
        size += len(block)
        if size >= chars:
            break
    return "".join(out)[:chars]


def synthetic_repo_context(session, chars, rng):
    """Deterministic, session-specific code, so sessions do not share a prefix."""
    out, i = [], 0
    while sum(len(b) for b in out) < chars:
        name = f"svc{session}_{i}"
        a, b = rng.randint(2, 99), rng.randint(2, 99)
        out.append(
            f"\n### File: pkg_{session}/{name}.py\n"
            f"def {name}(items, limit={a}):\n"
            f"    \"\"\"Filter and score items for module {name}.\"\"\"\n"
            f"    result = []\n"
            f"    for idx, item in enumerate(items):\n"
            f"        if idx >= limit:\n"
            f"            break\n"
            f"        score = (item.get('weight', 0) * {b}) % {a + b}\n"
            f"        if score > {a}:\n"
            f"            result.append((item['id'], score))\n"
            f"    return sorted(result, key=lambda r: -r[1])\n")
        i += 1
    return "".join(out)[:chars]


async def run_session(sid, args, client, sem, rows, rng_seed):
    rng = random.Random(rng_seed + sid)
    chars = args.context_tokens * 4  # about 4 characters per token for code
    context = (repo_context_from_dir(args.repo_dir, chars, rng) if args.repo_dir
               else synthetic_repo_context(sid, chars, rng))
    system = ("You are a senior software engineer helping with the repository below. "
              "Answer concisely.\n\n# Repository\n" + context)
    history = [{"role": "system", "content": system}]
    async with sem:
        for turn in range(1, args.turns + 1):
            question = QUESTIONS[(sid + turn) % len(QUESTIONS)]
            history.append({"role": "user", "content": question})
            r = await stream_chat(client, args.base_url, args.model, history,
                                  args.max_tokens, args.extra_body)
            history.append({"role": "assistant", "content": r["text"] or "(no answer)"})
            rows.append({"arm": args.arm, "session": sid, "turn": turn,
                         **{k: v for k, v in r.items() if k != "text"}})
            print(f"session {sid:3} turn {turn} ttft={r['ttft_s'] and round(r['ttft_s'], 3)}s "
                  f"prompt={r['prompt_tokens']} cached={r['cached_tokens']} "
                  f"status={r['status']}{' ' + r['error'] if r['error'] else ''}", flush=True)
            if args.think_time:
                await asyncio.sleep(args.think_time)


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--arm", required=True, help="label for this run, e.g. roundrobin or prefixaware")
    ap.add_argument("--model", default="glm-5.3")
    ap.add_argument("--sessions", type=int, default=24)
    ap.add_argument("--turns", type=int, default=6)
    ap.add_argument("--concurrency", type=int, default=8, help="sessions in flight at once")
    ap.add_argument("--context-tokens", type=int, default=32000)
    ap.add_argument("--repo-dir", help="use real source files from this directory as the context")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--think-time", type=float, default=0.0, help="seconds between turns")
    ap.add_argument("--extra-body", type=json.loads, default=None,
                    help='JSON merged into each request, e.g. \'{"temperature": 0}\'')
    ap.add_argument("--node-count", type=int, default=3, help="GPU nodes serving this arm")
    ap.add_argument("--node-hourly-usd", type=float, required=True,
                    help="effective price of one GPU node per hour (training plan or on-demand)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    rows, sem = [], asyncio.Semaphore(args.concurrency)
    start = time.time()
    async with make_client(args.concurrency) as client:
        await asyncio.gather(*(run_session(s, args, client, sem, rows, args.seed)
                               for s in range(args.sessions)))
    wall = time.time() - start

    ok = [r for r in rows if r["status"] == 200 and r["ttft_s"] is not None]
    prompt = sum(r["prompt_tokens"] or 0 for r in ok)
    completion = sum(r["completion_tokens"] or 0 for r in ok)
    cached = sum(r["cached_tokens"] or 0 for r in ok)
    gpu_cost = args.node_count * args.node_hourly_usd * wall / 3600
    summary = {
        "experiment": "multiturn_coding", "arm": args.arm, "base_url": args.base_url,
        "sessions": args.sessions, "turns": args.turns, "concurrency": args.concurrency,
        "context_tokens": args.context_tokens, "requests": len(rows), "errors": len(rows) - len(ok),
        "wall_s": round(wall, 1),
        "ttft_s_turn1": stats([r["ttft_s"] for r in ok if r["turn"] == 1]),
        "ttft_s_turn2plus": stats([r["ttft_s"] for r in ok if r["turn"] > 1]),
        "ttft_s_by_turn": {t: stats([r["ttft_s"] for r in ok if r["turn"] == t])["p50"]
                           for t in range(1, args.turns + 1)},
        "e2e_s": stats([r["e2e_s"] for r in ok]),
        "tokens": {"prompt": prompt, "completion": completion, "cached_reported": cached},
        "throughput_tokens_per_s": round((prompt + completion) / wall, 1) if wall else None,
        "cost": {
            "node_count": args.node_count, "node_hourly_usd": args.node_hourly_usd,
            "gpu_cost_usd": round(gpu_cost, 2),
            "usd_per_million_total_tokens": round(gpu_cost / (prompt + completion) * 1e6, 3) if prompt + completion else None,
            "usd_per_million_output_tokens": round(gpu_cost / completion * 1e6, 3) if completion else None,
        },
    }
    write_results(args.out, f"multiturn-{args.arm}", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
