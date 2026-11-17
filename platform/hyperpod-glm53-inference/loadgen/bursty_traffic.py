#!/usr/bin/env python3
"""Experiment 2: tail latency under bursty traffic, with no added GPU capacity.

Open-loop load: requests arrive as a Poisson process whose rate jumps from a base
rate to a burst rate for a fixed period at regular intervals. Requests are sent on
schedule whether or not earlier ones have finished, as real clients do. A mix of
short and long prompts makes some replicas busier than others, which is where
GPU-aware endpoint selection should beat round robin.

Run the same command against each arm and compare p95 and p99 latency during bursts:
  python bursty_traffic.py --base-url http://<endpoint-service>:8000 --arm roundrobin
  python bursty_traffic.py --base-url http://<gateway-address> --arm gateway
"""

import argparse
import asyncio
import json
import random
import time

from common import make_client, stats, stream_chat, write_results

WORDS = ("cluster quota tensor kernel latency gradient shard replica routing cache "
         "prefix decode prefill token batch queue scheduler memory bandwidth node").split()


def unique_document(rng, tokens):
    # Random words, so requests don't share a prefix and prefix caching can't flatter either arm.
    return " ".join(rng.choice(WORDS) for _ in range(int(tokens * 0.75)))


def rate_at(t, args):
    in_burst = (t % args.burst_every) < args.burst_length and t >= args.burst_every / 2
    return (args.burst_rps if in_burst else args.base_rps), ("burst" if in_burst else "base")


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--arm", required=True, help="label for this run, e.g. roundrobin or gateway")
    ap.add_argument("--model", default="glm-5.3")
    ap.add_argument("--duration", type=float, default=600, help="seconds of load")
    ap.add_argument("--base-rps", type=float, default=1.0)
    ap.add_argument("--burst-rps", type=float, default=6.0)
    ap.add_argument("--burst-every", type=float, default=120, help="seconds between burst starts")
    ap.add_argument("--burst-length", type=float, default=30, help="seconds each burst lasts")
    ap.add_argument("--long-fraction", type=float, default=0.3, help="share of requests with long prompts")
    ap.add_argument("--short-tokens", type=int, default=500)
    ap.add_argument("--long-tokens", type=int, default=16000)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--max-inflight", type=int, default=512)
    ap.add_argument("--extra-body", type=json.loads, default=None)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows, tasks = [], []
    sem = asyncio.Semaphore(args.max_inflight)

    async def one(i, sent_at, phase, kind, client):
        async with sem:
            tokens = args.long_tokens if kind == "long" else args.short_tokens
            msgs = [{"role": "user", "content":
                     "Summarize this text in two sentences:\n" + unique_document(rng, tokens)}]
            r = await stream_chat(client, args.base_url, args.model, msgs, args.max_tokens, args.extra_body)
            rows.append({"arm": args.arm, "id": i, "sent_at_s": round(sent_at, 3), "phase": phase,
                         "prompt_kind": kind, **{k: v for k, v in r.items() if k != "text"}})

    start = time.perf_counter()
    async with make_client(args.max_inflight, timeout_s=900) as client:
        t, i = 0.0, 0
        while t < args.duration:
            rate, phase = rate_at(t, args)
            t += rng.expovariate(rate)
            delay = start + t - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            kind = "long" if rng.random() < args.long_fraction else "short"
            tasks.append(asyncio.create_task(one(i, t, phase, kind, client)))
            i += 1
            if i % 50 == 0:
                print(f"t={t:6.1f}s sent={i} phase={phase}", flush=True)
        await asyncio.gather(*tasks)

    ok = [r for r in rows if r["status"] == 200 and r["ttft_s"] is not None]
    summary = {
        "experiment": "bursty_traffic", "arm": args.arm, "base_url": args.base_url,
        "config": {k: getattr(args, k) for k in ("duration", "base_rps", "burst_rps", "burst_every",
                                                 "burst_length", "long_fraction", "short_tokens",
                                                 "long_tokens", "max_tokens")},
        "requests": len(rows), "errors": len(rows) - len(ok),
        "by_phase": {
            phase: {"requests": sum(1 for r in rows if r["phase"] == phase),
                    "ttft_s": stats([r["ttft_s"] for r in ok if r["phase"] == phase]),
                    "e2e_s": stats([r["e2e_s"] for r in ok if r["phase"] == phase])}
            for phase in ("base", "burst")},
        "overall": {"ttft_s": stats([r["ttft_s"] for r in ok]), "e2e_s": stats([r["e2e_s"] for r in ok])},
    }
    write_results(args.out, f"bursty-{args.arm}", rows, summary)


if __name__ == "__main__":
    asyncio.run(main())
