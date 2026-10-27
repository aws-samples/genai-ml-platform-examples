"""Create/update and run the SageMaker Pipeline, falling back across training
instance types when a type has no GPU capacity.

On-demand training jobs do not fail when a GPU type has no free capacity. They
wait in Pending ("Preparing the instances for training") until capacity frees
up, which can take hours. That status message is the same as for a normal
start, so starvation can only be detected by time. Native InstancePreferences
is not available for JumpStart estimators in SageMaker Python SDK v2, and the
JumpStart training artifacts depend on the instance family, so the fallback
happens here instead.

For each type in the pipeline module's training pool (see
get_training_fallback_settings() in the pipeline module), this script:
  1. builds the pipeline for that type, upserts it and starts an execution;
  2. waits for the training step's job to leave Pending;
  3. moves to the next type when the job stays Pending longer than the
     timeout (the execution is stopped first) or the step fails with a quota
     or capacity error. The preprocessing step is cached, so it is not re-run.
The last type in the pool is never stopped: its execution stays queued and
starts when capacity frees up.

The script returns as soon as a training job is running. It does not wait for
training to finish. Any other failure (for example in preprocessing) stops the
build with a nonzero exit code.

Pipeline modules without get_training_fallback_settings() are upserted and
started once, as before.
"""
import argparse
import json
import sys
import time
import uuid

from pipelines._utils import convert_struct, get_pipeline_driver, get_pipeline_custom_tags

POLL_SECONDS = 30
STOP_TIMEOUT_SECONDS = 900          # max wait for Stopping -> Stopped
PREPARE_TIMEOUT_SECONDS = 3600      # max wait for the training step to appear
# Training job SecondaryStatus values that mean the instances are working.
STARTED_SECONDARY = {"Downloading", "DownloadingTrainingImage", "Training",
                     "Uploading", "Completed"}
CAPACITY_PATTERNS = ("resourcelimitexceeded", "insufficientinstancecapacity",
                     "capacityerror", "provision requested ml compute capacity",
                     "insufficient capacity", "account-level service limit")
EXEC_TERMINAL = {"Succeeded", "Failed", "Stopped"}

# Outcomes of wait_for_training_start()
STARTED, PENDING_TIMEOUT, CAPACITY_FAILED = "started", "pending_timeout", "capacity_failed"


class PipelineRunError(RuntimeError):
    """The pipeline execution failed in a way a different training type will not fix."""


def is_capacity_error(text):
    """True for capacity and quota errors. Unlike the deploy fallback, quota
    errors (ResourceLimitExceeded) also move on: another type may have quota."""
    t = (text or "").lower()
    return any(p in t for p in CAPACITY_PATTERNS)


def find_step(steps, name):
    for step in steps:
        if step.get("StepName") == name:
            return step
    return None


def _training_job_name(step):
    arn = ((step.get("Metadata") or {}).get("TrainingJob") or {}).get("Arn")
    return arn.split("/")[-1] if arn else None


def step_failure_reason(sm, step):
    """The step's FailureReason plus the training job's, when there is a job."""
    reasons = [step.get("FailureReason") or ""]
    job_name = _training_job_name(step)
    if job_name:
        try:
            reasons.append(sm.describe_training_job(TrainingJobName=job_name).get("FailureReason") or "")
        except Exception as e:  # noqa: BLE001 - the step reason is still useful
            reasons.append(f"(describe_training_job failed: {e})")
    return " | ".join(r for r in reasons if r)


def wait_for_training_start(sm, execution_arn, step_name, pending_timeout, *,
                            poll_seconds=POLL_SECONDS, prepare_timeout=PREPARE_TIMEOUT_SECONDS,
                            sleep=time.sleep, clock=time.monotonic, log=print):
    """Poll the execution until its training job is running, or has no capacity.

    Returns (outcome, info). outcome is STARTED, PENDING_TIMEOUT or
    CAPACITY_FAILED. info has training_job_name, secondary_status, reason and
    waited_seconds. Raises PipelineRunError on any other failure.
    """
    started_at = clock()
    step_seen_at = None
    info = {"training_job_name": None, "secondary_status": None, "reason": "", "waited_seconds": 0}

    while True:
        ex = sm.describe_pipeline_execution(PipelineExecutionArn=execution_arn)["PipelineExecutionStatus"]
        steps = sm.list_pipeline_execution_steps(PipelineExecutionArn=execution_arn)["PipelineExecutionSteps"]

        for step in steps:
            if step.get("StepName") != step_name and step.get("StepStatus") == "Failed":
                raise PipelineRunError(
                    f"Step {step.get('StepName')} failed: {step.get('FailureReason', '')}")

        ft = find_step(steps, step_name)
        if ft is None:
            if ex in EXEC_TERMINAL:
                raise PipelineRunError(f"Execution ended ({ex}) before {step_name} started")
            if clock() - started_at >= prepare_timeout:
                raise PipelineRunError(
                    f"{step_name} did not start within {prepare_timeout}s (execution {ex})")
            log(f"  ... waiting for {step_name} (preprocessing, execution {ex})")
            sleep(poll_seconds)
            continue

        if step_seen_at is None:
            step_seen_at = clock()
        elapsed = int(clock() - step_seen_at)
        info["waited_seconds"] = elapsed
        info["training_job_name"] = _training_job_name(ft) or info["training_job_name"]
        status = ft.get("StepStatus")

        if status == "Failed":
            reason = step_failure_reason(sm, ft)
            info["reason"] = reason
            if is_capacity_error(reason):
                return CAPACITY_FAILED, info
            raise PipelineRunError(f"{step_name} failed: {reason}")
        if status in ("Stopping", "Stopped") or ex == "Stopped":
            raise PipelineRunError(f"{step_name} was stopped outside this build (execution {ex})")
        if status == "Succeeded":
            return STARTED, info

        if info["training_job_name"]:
            job = sm.describe_training_job(TrainingJobName=info["training_job_name"])
            secondary = job.get("SecondaryStatus")
            info["secondary_status"] = secondary
            if job.get("TrainingJobStatus") == "Failed":
                reason = job.get("FailureReason") or ""
                info["reason"] = reason
                if is_capacity_error(reason):
                    return CAPACITY_FAILED, info
                raise PipelineRunError(f"Training job {info['training_job_name']} failed: {reason}")
            if job.get("TrainingJobStatus") == "Stopped":
                raise PipelineRunError(f"Training job {info['training_job_name']} was stopped")
            if secondary in STARTED_SECONDARY:
                return STARTED, info

        if pending_timeout is not None and elapsed >= pending_timeout:
            return PENDING_TIMEOUT, info
        job_label = info["training_job_name"] or "training job (creating)"
        log(f"  ... {job_label} {info['secondary_status'] or 'Pending'} for {elapsed}s "
            f"(timeout {pending_timeout}s)")
        sleep(poll_seconds)


def stop_execution_and_wait(sm, execution_arn, *, poll_seconds=POLL_SECONDS,
                            timeout=STOP_TIMEOUT_SECONDS, sleep=time.sleep,
                            clock=time.monotonic, log=print):
    """Stop the execution and wait until it is terminal. Returns its last status.
    A slow stop is logged, never raised."""
    log(f"  stopping execution {execution_arn}")
    try:
        sm.stop_pipeline_execution(PipelineExecutionArn=execution_arn,
                                   ClientRequestToken=str(uuid.uuid4()))
    except Exception as e:  # noqa: BLE001 - e.g. the execution is already terminal
        log(f"  (stop request not accepted: {str(e)[:150]})")
    deadline = clock() + timeout
    status = None
    while True:
        status = sm.describe_pipeline_execution(PipelineExecutionArn=execution_arn)["PipelineExecutionStatus"]
        if status in EXEC_TERMINAL:
            log(f"  execution is {status}")
            return status
        if clock() >= deadline:
            log(f"  WARNING: execution still {status} after {timeout}s; continuing anyway")
            return status
        log(f"  ... execution {status}")
        sleep(poll_seconds)


def run_with_training_fallback(sm, pool, build_and_start, pending_timeout,
                               step_name="FineTuneLlama", *, poll_seconds=POLL_SECONDS,
                               sleep=time.sleep, clock=time.monotonic, log=print):
    """Start the pipeline on each training type in turn until a training job runs.

    build_and_start(instance_type) must upsert the pipeline for that type,
    start an execution and return its ARN. Returns a dict with instance_type,
    execution_arn, outcome ("started" or "queued") and attempts.
    """
    pool = list(dict.fromkeys(pool or []))
    if not pool:
        raise ValueError("Training instance pool is empty")
    log(f"Training instance pool, in order: {pool} (Pending timeout {pending_timeout}s)")
    attempts = []
    for i, instance_type in enumerate(pool):
        is_last = i == len(pool) - 1
        log(f"[attempt {i + 1}/{len(pool)}] training on {instance_type}")
        arn = build_and_start(instance_type)
        log(f"  execution started: {arn}")
        outcome, info = wait_for_training_start(
            sm, arn, step_name, pending_timeout,
            poll_seconds=poll_seconds, sleep=sleep, clock=clock, log=log)
        attempts.append({"instance_type": instance_type, "execution_arn": arn,
                         "outcome": outcome, **info})
        result = {"instance_type": instance_type, "execution_arn": arn,
                  "outcome": outcome, "attempts": attempts}

        if outcome == STARTED:
            log(f"✓ Training started on {instance_type} (job {info['training_job_name']}, "
                f"{info['secondary_status']}). The pipeline continues without this build.")
            return result

        if outcome == PENDING_TIMEOUT:
            if is_last:
                log(f"NOTE: {instance_type} is still Pending after {info['waited_seconds']}s. "
                    f"It is the last type in the pool, so the execution is left queued "
                    f"and starts when capacity frees up. It is not stopped.")
                result["outcome"] = "queued"
                return result
            log(f"  no capacity for {instance_type} after {info['waited_seconds']}s; "
                f"stopping this execution and trying the next type")
            stop_execution_and_wait(sm, arn, poll_seconds=poll_seconds,
                                    sleep=sleep, clock=clock, log=log)
            continue

        # CAPACITY_FAILED: the execution has already failed, nothing to stop.
        if is_last:
            raise PipelineRunError(
                f"No training capacity or quota on any of {pool}. Last: {info['reason']}")
        log(f"  capacity or quota error on {instance_type}; trying the next type. "
            f"{info['reason'][:200]}")

    raise PipelineRunError("unreachable")  # pragma: no cover


def main():
    """Main entry point for running the pipeline."""
    parser = argparse.ArgumentParser(
        description="Create/Update and run SageMaker Pipeline"
    )
    parser.add_argument(
        "--module-name",
        type=str,
        default="pipelines.llama_finetuning.pipeline",
        help="Python module name for the pipeline",
    )
    parser.add_argument(
        "--role-arn",
        type=str,
        required=True,
        help="SageMaker execution role ARN",
    )
    parser.add_argument(
        "--tags",
        type=str,
        default="[]",
        help="JSON string of tags to apply to pipeline",
    )
    parser.add_argument(
        "--kwargs",
        type=str,
        default="{}",
        help="JSON string of keyword arguments for get_pipeline()",
    )
    args = parser.parse_args()

    # Parse tags
    tags = json.loads(args.tags)

    print(f"Creating/Updating pipeline from module: {args.module_name}")
    print(f"Pipeline kwargs: {args.kwargs}")

    module = __import__(args.module_name, fromlist=["get_pipeline"])
    # Get custom tags if defined
    tags = get_pipeline_custom_tags(args.module_name, args.kwargs, tags)

    def upsert_and_start(overrides=None):
        # Get pipeline using dynamic import
        pipeline = get_pipeline_driver(args.module_name, args.kwargs, overrides=overrides)
        print(f"Pipeline name: {pipeline.name}")
        # Upsert pipeline (create or update)
        print("Upserting pipeline...")
        pipeline.upsert(
            role_arn=args.role_arn,
            tags=tags
        )
        print(f"✓ Pipeline upserted: {pipeline.name}")
        # Start pipeline execution
        print("Starting pipeline execution...")
        execution = pipeline.start()
        print(f"✓ Pipeline execution started: {execution.arn}")
        return execution

    try:
        get_settings = getattr(module, "get_training_fallback_settings", None)
        if get_settings is None:
            execution = upsert_and_start()
            # Print execution details
            print(f"\nExecution details:")
            print(f"  ARN: {execution.arn}")
            print(f"  Status: {execution.describe()['PipelineExecutionStatus']}")
            return 0

        import boto3
        from botocore.config import Config as BotoConfig

        settings = get_settings()
        sm = boto3.client(
            "sagemaker",
            region_name=convert_struct(args.kwargs).get("region"),
            config=BotoConfig(retries={"mode": "standard", "max_attempts": 10}),
        )
        result = run_with_training_fallback(
            sm,
            settings["pool"],
            lambda t: upsert_and_start({"training_instance_type": t}).arn,
            settings["pending_timeout_seconds"],
            step_name=settings.get("training_step_name", "FineTuneLlama"),
        )
        print(f"\nExecution details:")
        print(f"  ARN: {result['execution_arn']}")
        print(f"  Training instance type: {result['instance_type']}")
        print(f"  Outcome: {result['outcome']}")
        return 0
    except Exception as e:
        print(f"✗ Pipeline run failed: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
