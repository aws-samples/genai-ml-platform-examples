#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Benchmark ASR throughput and latency under load.
Sends real or synthetic WAV files concurrently and measures RPS + latency distribution.
"""

import argparse
import concurrent.futures
import io
import json
import statistics
import time
import urllib.parse
import urllib.request
import wave


def make_wav_bytes(sample_rate: int, duration_sec: float) -> bytes:
    n_samples = max(1, int(sample_rate * duration_sec))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def post_multipart(url: str, fields: dict, file_bytes: bytes) -> tuple[float, dict]:
    boundary = "----BenchBoundary"
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio_file\"; filename=\"a.wav\"\r\n"
        f"Content-Type: audio/wav\r\n\r\n".encode() + file_bytes + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    t0 = time.perf_counter()
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {url}")
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected
        result = json.loads(resp.read())
    return time.perf_counter() - t0, result


def percentile(vals: list[float], p: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))]


def main():
    parser = argparse.ArgumentParser(description="ASR throughput benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--wav", default=None, help="Path to 16kHz mono WAV file")
    parser.add_argument("--duration", type=float, default=15.0, help="Synthetic audio duration (seconds)")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100, help="Total requests")
    parser.add_argument("--timestamps", action="store_true")
    args = parser.parse_args()

    if args.wav:
        with open(args.wav, "rb") as f:
            wav_bytes = f.read()
        print(f"Audio: {args.wav}")
    else:
        wav_bytes = make_wav_bytes(16000, args.duration)
        print(f"Synthetic: {args.duration}s silence")

    print(f"Concurrency: {args.concurrency}, total requests: {args.requests}")
    print(f"Timestamps: {args.timestamps}\n")

    url = f"{args.base_url}/transcribe/file"
    fields = {"timestamps": str(args.timestamps).lower()}

    latencies = []
    wall_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(post_multipart, url, fields, wav_bytes)
            for _ in range(args.requests)
        ]
        for f in futures:
            lat, _ = f.result()
            latencies.append(lat)
    wall_time = time.perf_counter() - wall_start

    rps = len(latencies) / wall_time

    print("=" * 55)
    print(f"{'RESULTS':^55}")
    print("=" * 55)
    print(f"  Total requests:  {len(latencies)}")
    print(f"  Wall time:       {wall_time:.2f}s")
    print(f"  Throughput:      {rps:.1f} RPS")
    print()
    print(f"  Latency ({len(latencies)} requests):")
    print(f"    Mean:   {statistics.fmean(latencies)*1000:>8.1f} ms")
    print(f"    p50:    {percentile(latencies, 50)*1000:>8.1f} ms")
    print(f"    p95:    {percentile(latencies, 95)*1000:>8.1f} ms")
    print(f"    p99:    {percentile(latencies, 99)*1000:>8.1f} ms")
    print(f"    Max:    {max(latencies)*1000:>8.1f} ms")
    print("=" * 55)


if __name__ == "__main__":
    main()
