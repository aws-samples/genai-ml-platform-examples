#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""Latency benchmark for the ASR gateway — tests both /transcribe/file and /v1/audio/transcriptions."""

import argparse
import concurrent.futures
import io
import json
import statistics
import time
import wave
from http.client import HTTPConnection


def make_wav_bytes(sample_rate: int, duration_sec: float) -> bytes:
    n_samples = max(1, int(sample_rate * duration_sec))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def read_wav_file(wav_path: str) -> bytes:
    with open(wav_path, "rb") as f:
        return f.read()


BOUNDARY = "----BenchBoundary"


def build_multipart(fields: dict[str, str], file_field: str, file_bytes: bytes) -> bytes:
    parts = []
    for k, v in fields.items():
        parts.append(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"audio.wav\"\r\n"
        f"Content-Type: audio/wav\r\n\r\n".encode() + file_bytes + b"\r\n"
    )
    parts.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(parts)


def run_request(host: str, port: int, path: str, body: bytes, headers: dict) -> tuple[float, dict]:
    conn = HTTPConnection(host, port)
    t0 = time.perf_counter()
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    data = json.loads(resp.read())
    latency = time.perf_counter() - t0
    conn.close()
    return latency, data


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(pct / 100 * (len(s) - 1)))))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ASR transcription latency")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--wav", default=None)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--duration-sec", type=float, default=15.0, help="Sustained load duration")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--timestamps", action="store_true")
    parser.add_argument("--openai", action="store_true", help="Use /v1/audio/transcriptions endpoint")
    parser.add_argument("--response-format", default="json", choices=["json", "verbose_json", "text"])
    args = parser.parse_args()

    url = args.base_url.replace("http://", "")
    host, port = url.split(":") if ":" in url else (url, 8002)
    port = int(port)

    if args.wav:
        wav_bytes = read_wav_file(args.wav)
        print(f"Audio: {args.wav}")
    else:
        wav_bytes = make_wav_bytes(args.sample_rate, args.duration)
        print(f"Synthetic: {args.duration}s silence @ {args.sample_rate}Hz")

    # Build request
    headers = {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}
    if args.openai:
        path = "/v1/audio/transcriptions"
        fields = {"response_format": args.response_format}
        if args.timestamps:
            fields["timestamp_granularities"] = "word"
        body = build_multipart(fields, "file", wav_bytes)
    else:
        path = "/transcribe/file"
        fields = {"timestamps": str(args.timestamps).lower()}
        body = build_multipart(fields, "audio_file", wav_bytes)

    print(f"Endpoint: {path}")
    print(f"Concurrency: {args.concurrency}, duration: {args.duration_sec}s, warmup: {args.warmup}")
    print(f"Timestamps: {args.timestamps}")

    # Warmup
    for _ in range(args.warmup):
        run_request(host, port, path, body, headers)
    print("Warmup done.\n")

    # Benchmark — sustained load (keep concurrency in-flight for duration)
    duration_sec = args.duration_sec
    import threading
    latencies = []
    sample_text = None
    deadline = time.perf_counter() + duration_sec
    sem = threading.Semaphore(args.concurrency)

    def worker():
        results = []
        while time.perf_counter() < deadline:
            sem.acquire()
            try:
                lat, data = run_request(host, port, path, body, headers)
                results.append((lat, data))
            finally:
                sem.release()
        return results

    wall_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency * 2) as pool:
        futures = [pool.submit(worker) for _ in range(args.concurrency * 2)]
        for f in futures:
            for lat, data in f.result():
                latencies.append(lat)
                if sample_text is None:
                    sample_text = data.get("text", "")
    wall_time = time.perf_counter() - wall_start

    rps = len(latencies) / wall_time

    print(f"{'='*60}")
    print(f"  Requests:    {len(latencies)}")
    print(f"  Wall time:   {wall_time:.2f}s")
    print(f"  Throughput:  {rps:.1f} RPS")
    print()
    print(f"  Mean:        {statistics.fmean(latencies)*1000:>8.1f} ms")
    print(f"  p50:         {percentile(latencies, 50)*1000:>8.1f} ms")
    print(f"  p95:         {percentile(latencies, 95)*1000:>8.1f} ms")
    print(f"  p99:         {percentile(latencies, 99)*1000:>8.1f} ms")
    print(f"  Max:         {max(latencies)*1000:>8.1f} ms")
    print(f"  Min:         {min(latencies)*1000:>8.1f} ms")
    if len(latencies) > 1:
        print(f"  Stdev:       {statistics.stdev(latencies)*1000:>8.1f} ms")
    if sample_text:
        print(f"\n  Sample: {sample_text[:120]}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
