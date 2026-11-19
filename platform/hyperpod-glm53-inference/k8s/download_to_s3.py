#!/usr/bin/env python3
"""Copy a Hugging Face model repository into S3, one file at a time.

Runs inside k8s/download-model-job.yaml. The GLM-5.3 checkpoint is about 756 GB in
141 shards of at most 5.4 GB, so instead of needing 800 GB of local disk the job
downloads a handful of files, uploads each one with a multipart upload, and deletes
it. Files already in S3 with the right size are skipped, so the job can be re-run
after an interruption and picks up where it left off.

Environment:
  HF_REPO       repository id, for example zai-org/GLM-5.3
  HF_REVISION   branch, tag or commit (default: main)
  MODEL_BUCKET  destination bucket
  MODEL_PREFIX  destination key prefix
  HF_TOKEN      optional; GLM-5.3 is not gated
  WORKERS       files in flight at once (default: 4)
  ONLY          optional comma-separated file names; copies just those (smoke test)
  SCRATCH       local scratch directory (default: /scratch)
"""

import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from huggingface_hub import HfApi, hf_hub_download

REPO = os.environ["HF_REPO"]
REVISION = os.environ.get("HF_REVISION", "main")
BUCKET = os.environ["MODEL_BUCKET"]
PREFIX = os.environ["MODEL_PREFIX"].strip("/")
TOKEN = os.environ.get("HF_TOKEN") or None
WORKERS = int(os.environ.get("WORKERS", "4"))
ONLY = {f for f in os.environ.get("ONLY", "").split(",") if f}
SCRATCH = os.environ.get("SCRATCH", "/scratch")

s3 = boto3.client("s3")
transfer = TransferConfig(multipart_chunksize=256 * 1024 * 1024, max_concurrency=16)


def already_uploaded(key, size):
    try:
        return s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"] == size
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def copy_one(path, size):
    key = f"{PREFIX}/{path}"
    if already_uploaded(key, size):
        return path, size, "skipped"
    local_dir = os.path.join(SCRATCH, str(abs(hash(path))))
    try:
        local = hf_hub_download(REPO, path, revision=REVISION, token=TOKEN,
                                local_dir=local_dir)
        s3.upload_file(local, BUCKET, key, Config=transfer)
        return path, size, "copied"
    finally:
        shutil.rmtree(local_dir, ignore_errors=True)


def main():
    info = HfApi(token=TOKEN).model_info(REPO, revision=REVISION, files_metadata=True)
    files = [(s.rfilename, s.size or 0) for s in info.siblings]
    if ONLY:
        files = [f for f in files if f[0] in ONLY]
    total = sum(size for _, size in files)
    print(f"{REPO}@{REVISION}: {len(files)} files, {total / 1e9:.1f} GB "
          f"-> s3://{BUCKET}/{PREFIX}/", flush=True)

    done = moved = 0
    failures = []
    start = time.time()
    # Largest first, so the long transfers overlap with the rest.
    files.sort(key=lambda f: -f[1])
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(copy_one, p, s): p for p, s in files}
        for fut in as_completed(futures):
            try:
                path, size, state = fut.result()
                done += size
                moved += size if state == "copied" else 0
                rate = moved / max(time.time() - start, 1) / 1e6
                print(f"{state:7} {path} ({size / 1e9:.2f} GB) "
                      f"[{done / max(total, 1):.0%}, {rate:.0f} MB/s]", flush=True)
            except Exception as e:  # keep going; report at the end
                failures.append((futures[fut], repr(e)))
                print(f"FAILED  {futures[fut]}: {e}", flush=True)

    print(f"finished in {(time.time() - start) / 60:.1f} min, "
          f"{len(failures)} failure(s)", flush=True)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
