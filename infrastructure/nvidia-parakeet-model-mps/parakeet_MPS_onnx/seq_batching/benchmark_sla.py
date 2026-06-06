#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
SLA benchmark — measures single-GPU capacity against production targets:
  - Concurrency: 100
  - Latency: mean < 650ms, p99 < 1000ms
  - Throughput: 150 RPS (9000 RPM)

Current production: 16 GPUs × 1 replica each.
Goal: find the minimum GPUs needed by packing multiple replicas per GPU.

Usage:
    python benchmark_sla.py --wav test.wav
    python benchmark_sla.py --wav test.wav --duration-sec 60
"""

import argparse
import asyncio
import io
import math
import statistics
import time
import wave

import aiohttp


# --- SLA targets ---
TARGET_CONCURRENCY = 100
TARGET_RPS = 150
TARGET_RPM = TARGET_RPS * 60
TARGET_MEAN_MS = 650          # mean / p50 < 600-650ms
TARGET_P99_MS = 1000          # p99 < 1 second
CURRENT_GPUS = 16


def make_wav_bytes(sample_rate: int, duration_sec: float) -> bytes:
    n_samples = max(1, int(sample_rate * duration_sec))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(pct / 100 * (len(s) - 1)))))]


async def send_request(session: aiohttp.ClientSession, url: str, wav_bytes: bytes) -> tuple[float, int, str | None]:
    data = aiohttp.FormData()
    data.add_field("audio_file", wav_bytes, filename="audio.wav", content_type="audio/wav")
    data.add_field("timestamps", "false")
    t0 = time.perf_counter()
    try:
        async with session.post(url, data=data) as resp:
            await resp.read()
            return time.perf_counter() - t0, resp.status, None
    except Exception as e:
        return time.perf_counter() - t0, 0, str(e)


async def sustained_load(url: str, wav_bytes: bytes, concurrency: int, duration_sec: float) -> list[tuple[float, int]]:
    """Keep `concurrency` requests in-flight for `duration_sec`."""
    results: list[tuple[float, int]] = []
    deadline = time.perf_counter() + duration_sec
    sem = asyncio.Semaphore(concurrency)

    async def worker(session: aiohttp.ClientSession):
        while time.perf_counter() < deadline:
            async with sem:
                lat, status, _ = await send_request(session, url, wav_bytes)
                results.append((lat, status))

    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [asyncio.create_task(worker(session)) for _ in range(concurrency * 2)]
        await asyncio.gather(*tasks)

    return results


async def run_phase(url: str, wav_bytes: bytes, concurrency: int, duration_sec: float, label: str) -> dict | None:
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"  Concurrency: {concurrency}, Duration: {duration_sec}s")
    print(f"{'─'*60}")

    results = await sustained_load(url, wav_bytes, concurrency, duration_sec)
    latencies = [lat for lat, status in results if status == 200]
    failed = sum(1 for _, status in results if status != 200)

    if not latencies:
        print("  ❌ All requests failed!")
        return None

    rps = len(latencies) / duration_sec
    stats = {
        "concurrency": concurrency,
        "ok": len(latencies),
        "failed": failed,
        "rps": rps,
        "rpm": rps * 60,
        "mean_ms": statistics.fmean(latencies) * 1000,
        "p50_ms": percentile(latencies, 50) * 1000,
        "p95_ms": percentile(latencies, 95) * 1000,
        "p99_ms": percentile(latencies, 99) * 1000,
        "max_ms": max(latencies) * 1000,
        "min_ms": min(latencies) * 1000,
    }

    mean_ok = "✅" if stats["mean_ms"] <= TARGET_MEAN_MS else "❌"
    p99_ok = "✅" if stats["p99_ms"] <= TARGET_P99_MS else "❌"
    print(f"  Requests:   {stats['ok']} ok / {stats['failed']} failed")
    print(f"  Throughput: {stats['rps']:.1f} RPS  ({stats['rpm']:.0f} RPM)")
    print(f"  Mean:       {stats['mean_ms']:>8.1f} ms  {mean_ok} (target: {TARGET_MEAN_MS}ms)")
    print(f"  p50:        {stats['p50_ms']:>8.1f} ms")
    print(f"  p95:        {stats['p95_ms']:>8.1f} ms")
    print(f"  p99:        {stats['p99_ms']:>8.1f} ms  {p99_ok} (target: {TARGET_P99_MS}ms)")
    print(f"  Max:        {stats['max_ms']:>8.1f} ms")
    return stats


async def main_async(args):
    if args.wav:
        with open(args.wav, "rb") as f:
            wav_bytes = f.read()
        print(f"Audio: {args.wav}")
    else:
        wav_bytes = make_wav_bytes(args.sample_rate, args.audio_duration)
        print(f"Synthetic: {args.audio_duration}s silence @ {args.sample_rate}Hz")

    url = f"{args.base_url}/transcribe/file"
    print(f"Target: {url}")
    print(f"SLA: concurrency={TARGET_CONCURRENCY}, mean<{TARGET_MEAN_MS}ms, p99<{TARGET_P99_MS}ms, {TARGET_RPM} RPM ({TARGET_RPS:.1f} RPS)")
    print(f"Current production: {CURRENT_GPUS} GPUs × 1 replica each")

    # Warmup
    print("\nWarming up...", flush=True)
    async with aiohttp.ClientSession() as session:
        for _ in range(args.warmup):
            await send_request(session, url, wav_bytes)
    print("Warmup done.")

    d = args.duration_sec

    # Phase 1: Sweep concurrency levels to find the sweet spot
    concurrency_levels = [1, 4, 8, 12, 16, 18, 20, 22, 24, 28, 32, 64, 100]
    sweep_results: list[dict] = []

    for c in concurrency_levels:
        s = await run_phase(url, wav_bytes, concurrency=c, duration_sec=d, label=f"Sweep concurrency={c}")
        if s:
            sweep_results.append(s)

    # Analysis
    print(f"\n{'='*60}")
    print(f"  SINGLE-GPU CAPACITY REPORT")
    print(f"{'='*60}")

    print(f"\n  ── Concurrency Sweep Summary ──")
    print(f"  {'Conc':>6}  {'RPS':>8}  {'RPM':>8}  {'p50ms':>8}  {'mean':>8}  {'p99ms':>8}  SLA")
    for s in sweep_results:
        ok = "✅" if s["mean_ms"] <= TARGET_MEAN_MS and s["p99_ms"] <= TARGET_P99_MS else "❌"
        print(f"  {s['concurrency']:>6}  {s['rps']:>8.1f}  {s['rpm']:>8.0f}  {s['p50_ms']:>8.1f}  {s['mean_ms']:>8.1f}  {s['p99_ms']:>8.1f}  {ok}")

    print(f"\n  ── GPU Estimates ──")

    # Find max concurrency where mean < 650ms AND p99 < 1000ms
    passing = [s for s in sweep_results if s["mean_ms"] <= TARGET_MEAN_MS and s["p99_ms"] <= TARGET_P99_MS]
    best = max(passing, key=lambda s: s["concurrency"]) if passing else None

    # Find peak throughput regardless of latency
    peak = max(sweep_results, key=lambda s: s["rps"]) if sweep_results else None

    if best:
        max_conc_per_gpu = best["concurrency"]
        rps_per_gpu = best["rps"]
        rpm_per_gpu = best["rpm"]

        gpus_for_concurrency = math.ceil(TARGET_CONCURRENCY / max_conc_per_gpu)
        gpus_for_throughput = math.ceil(TARGET_RPS / rps_per_gpu)
        gpus_needed = max(gpus_for_concurrency, gpus_for_throughput)

        print(f"  Max concurrency/GPU at mean<{TARGET_MEAN_MS}ms & p99<{TARGET_P99_MS}ms:  {max_conc_per_gpu}")
        print(f"  Throughput at that level:            {rps_per_gpu:.1f} RPS ({rpm_per_gpu:.0f} RPM)")
        print(f"  Mean latency:                        {best['mean_ms']:.1f} ms")
        print(f"  p99 latency:                         {best['p99_ms']:.1f} ms")
        print()
        print(f"  GPUs needed for concurrency ({TARGET_CONCURRENCY}):   {gpus_for_concurrency}")
        print(f"  GPUs needed for throughput ({TARGET_RPS} RPS):  {gpus_for_throughput}")
        print(f"  ──────────────────────────────────────")
        print(f"  GPUs recommended:                    {gpus_needed}")
        print(f"  Current GPUs:                        {CURRENT_GPUS}")
        print(f"  Savings:                             {max(0, CURRENT_GPUS - gpus_needed)} GPUs ({max(0, (CURRENT_GPUS - gpus_needed)) / CURRENT_GPUS * 100:.0f}%)")
    else:
        print(f"  ❌ Could not meet mean<{TARGET_MEAN_MS}ms & p99<{TARGET_P99_MS}ms at any concurrency level")
        if peak:
            best_latency = min(sweep_results, key=lambda s: s["mean_ms"])
            print(f"  Best mean was {best_latency['mean_ms']:.0f}ms (p99={best_latency['p99_ms']:.0f}ms) at concurrency={best_latency['concurrency']}")
            print(f"  Peak throughput: {peak['rps']:.1f} RPS at concurrency={peak['concurrency']}")
            print()
            gpus_for_throughput = math.ceil(TARGET_RPS / peak["rps"])
            lowest_mean = min(sweep_results, key=lambda s: s["mean_ms"])
            gpus_for_latency = math.ceil(TARGET_CONCURRENCY / lowest_mean["concurrency"])
            gpus_needed = max(gpus_for_throughput, gpus_for_latency)
            print(f"  Estimated GPUs (throughput only):     {gpus_for_throughput}")
            print(f"  Estimated GPUs (latency-bound):       {gpus_for_latency}")
            print(f"  Conservative estimate:                {gpus_needed}")
            print(f"  Current GPUs:                         {CURRENT_GPUS}")
            print(f"  Potential savings:                    {max(0, CURRENT_GPUS - gpus_needed)} GPUs")

    print(f"\n{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="SLA benchmark — single-GPU capacity for multi-GPU planning")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--wav", default=None)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--audio-duration", type=float, default=15.0)
    parser.add_argument("--duration-sec", type=float, default=30, help="Duration per test phase (sec)")
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
