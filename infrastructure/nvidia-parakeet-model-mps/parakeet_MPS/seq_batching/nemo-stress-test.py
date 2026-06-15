#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Stress test for ASR API — matches the output format of the existing project's nemo-stress-test.py.
Tests both /v1/audio/transcriptions (OpenAI) and /transcribe/file endpoints.
"""

import asyncio
import aiohttp
import time
import statistics
import json
import argparse
from pathlib import Path


async def send_request(session, url, data_factory):
    """Sends a single transcription request."""
    start_time = time.time()
    try:
        data = data_factory()
        async with session.post(url, data=data) as response:
            if response.status == 200:
                result = await response.json()
                return time.time() - start_time, result, None
            else:
                body = await response.text()
                return time.time() - start_time, None, f"Status {response.status}: {body[:200]}"
    except Exception as e:
        return time.time() - start_time, None, str(e)


async def benchmark(audio_file: str, num_requests: int, base_url: str, endpoint: str, response_format: str):
    audio_data = Path(audio_file).read_bytes()

    if endpoint == "openai":
        url = f"{base_url}/v1/audio/transcriptions"
        def data_factory():
            data = aiohttp.FormData()
            data.add_field("file", audio_data, filename="test.wav", content_type="audio/wav")
            data.add_field("response_format", response_format)
            return data
    else:
        url = f"{base_url}/transcribe/file"
        def data_factory():
            data = aiohttp.FormData()
            data.add_field("audio_file", audio_data, filename="test.wav", content_type="audio/wav")
            data.add_field("timestamps", "false")
            return data

    print(f"Endpoint: {url}")
    print(f"Audio: {audio_file}")
    print(f"Preparing {num_requests} parallel requests...\n")

    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, url, data_factory) for _ in range(num_requests)]

        print(f"Running {num_requests} parallel requests...")
        start_benchmark = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_benchmark
        print("All requests completed.\n")

    response_times = []
    successful = 0
    first_printed = False

    for proc_time, result, error in results:
        if error is None and result is not None:
            response_times.append(proc_time)
            successful += 1
            if not first_printed:
                print(f"Sample response: {json.dumps(result, indent=2)}\n")
                first_printed = True
        else:
            print(f"Failed: {error}")

    if response_times:
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0

        print(f"📊 Benchmark Results:")
        print(f"Total requests: {num_requests}")
        print(f"Successful requests: {successful}")
        print(f"Success rate: {successful/num_requests*100:.1f}%")
        print(f"\n--- Timing per request (server processing time) ---")
        print(f"Average response time: {avg_time:.3f}s")
        print(f"Median response time: {median_time:.3f}s")
        print(f"Min response time: {min_time:.3f}s")
        print(f"Max response time: {max_time:.3f}s")
        print(f"Standard deviation: {std_dev:.3f}s")
        print(f"\n--- Overall performance ---")
        print(f"Total benchmark time for {num_requests} requests: {total_time:.3f}s")
        print(f"Requests per second (RPS): {successful/total_time:.2f}")
    else:
        print("No successful requests.")


def main():
    parser = argparse.ArgumentParser(description="ASR stress test")
    parser.add_argument("--wav", default="record_out2.wav", help="Audio file path")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--base-url", default="http://localhost:8002")
    parser.add_argument("--endpoint", choices=["openai", "simple"], default="simple")
    parser.add_argument("--response-format", default="verbose_json")
    args = parser.parse_args()

    if not Path(args.wav).exists():
        print(f"❌ Audio file {args.wav} not found")
        return

    asyncio.run(benchmark(args.wav, args.requests, args.base_url, args.endpoint, args.response_format))


if __name__ == "__main__":
    main()
