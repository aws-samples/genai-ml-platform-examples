#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Benchmark diarization latency against SA requirements:
  - Target latency: < 4-5s per chunk
  - Target throughput: 10 RPS (1-2% of 150 RPS transcription traffic)
  - Uses real audio file split into chunks
"""

import argparse
import concurrent.futures
import io
import json
import statistics
import struct
import time
import urllib.parse
import urllib.request
import wave
from pathlib import Path


def read_wav_chunks(wav_path: str, chunk_sec: float) -> list[bytes]:
    """Read a 16kHz mono WAV and split into chunk_sec-sized WAV byte chunks."""
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        sw = wf.getsampwidth()
        nch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())

    frame_bytes = sw * nch
    chunk_frames = int(sr * chunk_sec)
    chunk_bytes = chunk_frames * frame_bytes
    chunks = []
    for offset in range(0, len(raw), chunk_bytes):
        pcm = raw[offset : offset + chunk_bytes]
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


def post_multipart(url: str, fields: dict, file_bytes: bytes | None = None) -> tuple[float, dict]:
    boundary = "----BenchBoundary"
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    if file_bytes:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio_file\"; filename=\"c.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
            + file_bytes + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    t0 = time.perf_counter()
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {url}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected
        result = json.loads(resp.read())
    return time.perf_counter() - t0, result


def run_session(base_url: str, session_id: str, wav_chunks: list[bytes]) -> list[dict]:
    """Run one full recording session, return per-chunk stats."""
    results = []
    for i, chunk in enumerate(wav_chunks):
        latency, resp = post_multipart(
            f"{base_url}/diarize",
            {"action": "chunk", "recording_id": session_id},
            file_bytes=chunk,
        )
        results.append({"session": session_id, "chunk": i, "latency": latency, "segments": len(resp.get("segments", []))})
    # End
    latency, resp = post_multipart(f"{base_url}/diarize", {"action": "end", "recording_id": session_id})
    results.append({"session": session_id, "chunk": "end", "latency": latency, "segments": len(resp.get("segments", []))})
    return results


def percentile(vals: list[float], p: float) -> float:
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return s[idx]


def main():
    parser = argparse.ArgumentParser(description="Diarization latency benchmark (SA requirements)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--wav", required=True, help="Path to 16kHz mono WAV file")
    parser.add_argument("--chunk-sec", type=float, default=15.0, help="Chunk duration in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent recording sessions (target: 10 RPS)")
    parser.add_argument("--rounds", type=int, default=3, help="Number of rounds to repeat all sessions")
    args = parser.parse_args()

    wav_chunks = read_wav_chunks(args.wav, args.chunk_sec)
    print(f"Audio: {args.wav}")
    print(f"Chunks: {len(wav_chunks)} x {args.chunk_sec}s")
    print(f"Concurrency: {args.concurrency} sessions")
    print(f"Rounds: {args.rounds}")
    print(f"Target: <4-5s latency, 10 RPS\n")

    all_results = []
    wall_start = time.perf_counter()
    for r in range(args.rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(run_session, args.base_url, f"bench-r{r}-s{i}", wav_chunks)
                for i in range(args.concurrency)
            ]
            for f in futures:
                all_results.extend(f.result())
    wall_time = time.perf_counter() - wall_start

    chunk_latencies = [r["latency"] for r in all_results if r["chunk"] != "end"]
    end_latencies = [r["latency"] for r in all_results if r["chunk"] == "end"]
    all_latencies = [r["latency"] for r in all_results]

    total_requests = len(all_results)
    actual_rps = total_requests / wall_time

    print("=" * 55)
    print(f"{'RESULTS':^55}")
    print("=" * 55)
    print(f"  Total requests:    {total_requests}")
    print(f"  Wall time:         {wall_time:.2f}s")
    print(f"  Throughput:        {actual_rps:.1f} RPS")
    print()
    print(f"  CHUNK latencies ({len(chunk_latencies)} requests):")
    print(f"    Mean:   {statistics.fmean(chunk_latencies)*1000:>8.1f} ms")
    print(f"    p50:    {percentile(chunk_latencies, 50)*1000:>8.1f} ms")
    print(f"    p95:    {percentile(chunk_latencies, 95)*1000:>8.1f} ms")
    print(f"    p99:    {percentile(chunk_latencies, 99)*1000:>8.1f} ms")
    print(f"    Max:    {max(chunk_latencies)*1000:>8.1f} ms")
    print()
    print(f"  END latencies ({len(end_latencies)} requests):")
    print(f"    Mean:   {statistics.fmean(end_latencies)*1000:>8.1f} ms")
    print(f"    Max:    {max(end_latencies)*1000:>8.1f} ms")
    print()

    target = 5.0
    over = [l for l in chunk_latencies if l > target]
    print(f"  Chunks > {target}s:    {len(over)}/{len(chunk_latencies)} ({100*len(over)/len(chunk_latencies):.1f}%)")
    print(f"  Target RPS met:    {'YES' if actual_rps >= 10 else 'NO'} ({actual_rps:.1f} vs 10)")
    print("=" * 55)


if __name__ == "__main__":
    main()
