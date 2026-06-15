#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""Latency benchmark for the seq_batching gateway."""

import argparse
import concurrent.futures
import io
import json
import statistics
import struct
import time
import wave
from http.client import HTTPConnection
from typing import Optional


def make_wav_bytes(sample_rate: int, duration_sec: float) -> bytes:
    """Generate a silent WAV file (16-bit PCM, mono) in memory."""
    n_samples = max(1, int(sample_rate * duration_sec))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def read_wav_chunks(wav_path: str, chunk_sec: float) -> list[bytes]:
    """Read a WAV file and split into chunk-sized WAV byte buffers."""
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        sw = wf.getsampwidth()
        nch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    frame_bytes = sw * nch
    chunk_frames = int(sr * chunk_sec)
    chunk_size = chunk_frames * frame_bytes
    chunks = []
    for offset in range(0, len(raw), chunk_size):
        pcm = raw[offset : offset + chunk_size]
        if not pcm:
            break
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(nch)
            wf.setsampwidth(sw)
            wf.setframerate(sr)
            wf.writeframes(pcm)
        chunks.append(buf.getvalue())
    return chunks


BOUNDARY = "----BenchBoundary"


def build_multipart(fields: dict[str, str], file_bytes: Optional[bytes] = None) -> bytes:
    """Pre-build multipart body."""
    parts = []
    for k, v in fields.items():
        parts.append(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    if file_bytes is not None:
        parts.append(
            f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"audio_file\"; filename=\"c.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n".encode() + file_bytes + b"\r\n"
        )
    parts.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(parts)


def run_recording(
    host: str,
    port: int,
    recording_id: str,
    wav_chunks: list[bytes],
    segmentation_mode: str,
) -> list[float]:
    """Send chunks over a single persistent connection, return per-chunk latencies."""
    conn = HTTPConnection(host, port)
    headers = {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}
    latencies = []
    try:
        for wav_bytes in wav_chunks:
            body = build_multipart(
                {"action": "chunk", "recording_id": recording_id, "segmentation_mode": segmentation_mode},
                file_bytes=wav_bytes,
            )
            t0 = time.perf_counter()
            conn.request("POST", "/diarize", body=body, headers=headers)
            resp = conn.getresponse()
            resp.read()
            latencies.append(time.perf_counter() - t0)

        # End the sequence
        body = build_multipart({"action": "end", "recording_id": recording_id, "segmentation_mode": segmentation_mode})
        conn.request("POST", "/diarize", body=body, headers=headers)
        conn.getresponse().read()
    finally:
        conn.close()
    return latencies


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(pct / 100 * (len(s) - 1)))))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark seq_batching chunk latency")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--wav", default=None, help="Path to a real WAV file (overrides synthetic audio)")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk-duration", type=float, default=15)
    parser.add_argument("--max-duration", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2, help="Warmup requests to discard")
    parser.add_argument("--rounds", type=int, default=5, help="Number of benchmark rounds (results averaged)")
    parser.add_argument("--segmentation-mode", default="argmax")
    args = parser.parse_args()

    # Parse host/port from base-url
    url = args.base_url.replace("http://", "")
    host, port = url.split(":") if ":" in url else (url, 8002)
    port = int(port)

    # Build chunks
    if args.wav:
        wav_chunks = read_wav_chunks(args.wav, args.chunk_duration)
        print(f"Audio: {args.wav} -> {len(wav_chunks)} chunks x {args.chunk_duration}s")
    else:
        args.max_duration = min(args.max_duration, 60.0)
        remaining = args.max_duration
        wav_chunks = []
        while remaining > 0:
            d = min(args.chunk_duration, remaining)
            wav_chunks.append(make_wav_bytes(args.sample_rate, d))
            remaining -= d
        print(f"Synthetic: {len(wav_chunks)} chunks covering {args.max_duration:.1f}s "
              f"(chunk={args.chunk_duration}s, sr={args.sample_rate})")

    print(f"Concurrency: {args.concurrency}, warmup: {args.warmup}")

    # Warmup
    if args.warmup > 0:
        print("Warming up...", flush=True)
        for i in range(args.warmup):
            run_recording(host, port, f"warmup-{i}", wav_chunks[:1], args.segmentation_mode)

    # Benchmark
    round_means = []
    round_p50s = []
    round_p95s = []
    round_p99s = []
    round_maxs = []

    for r in range(args.rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(run_recording, host, port, f"bench-r{r}-{i}", wav_chunks, args.segmentation_mode)
                for i in range(args.concurrency)
            ]
            all_latencies = []
            for f in futures:
                all_latencies.extend(f.result())

        m = statistics.fmean(all_latencies) * 1000
        p50 = percentile(all_latencies, 50) * 1000
        p95 = percentile(all_latencies, 95) * 1000
        p99 = percentile(all_latencies, 99) * 1000
        mx = max(all_latencies) * 1000
        round_means.append(m)
        round_p50s.append(p50)
        round_p95s.append(p95)
        round_p99s.append(p99)
        round_maxs.append(mx)
        print(f"  Round {r+1}/{args.rounds}: mean={m:.2f}ms  p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms  max={mx:.2f}ms")

    print(f"\n{'='*60}")
    print(f"  AVERAGE over {args.rounds} rounds:")
    print(f"    mean_ms={statistics.fmean(round_means):.2f}")
    print(f"    p50_ms={statistics.fmean(round_p50s):.2f}")
    print(f"    p95_ms={statistics.fmean(round_p95s):.2f}")
    print(f"    p99_ms={statistics.fmean(round_p99s):.2f}")
    print(f"    max_ms={statistics.fmean(round_maxs):.2f}")
    print(f"    stdev_mean_ms={statistics.stdev(round_means):.2f}" if len(round_means) > 1 else "")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
