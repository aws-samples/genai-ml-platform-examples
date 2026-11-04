"""Small bootstrap helpers shared by Lab 5 notebooks."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


_SHARED_CONFIG_VALUES = (
    "PROJECT_NAME",
    "DATA_S3_BUCKET",
    "AWS_DEFAULT_REGION",
)


def _validate_cached_config(env_path: Path) -> None:
    """Fail when this kernel has configuration from a different environment."""
    cached_config = sys.modules.get("src.config.config")
    if cached_config is None:
        return

    mismatches = []
    for name in _SHARED_CONFIG_VALUES:
        environment_value = os.environ.get(name)
        cached_value = getattr(cached_config, name, None)
        if environment_value is not None and cached_value != environment_value:
            mismatches.append(
                f"{name}: cached={cached_value!r}, .env={environment_value!r}"
            )

    if mismatches:
        details = "; ".join(mismatches)
        raise RuntimeError(
            f"Lab 5 configuration is stale after loading {env_path}: {details}. "
            "To recover, restart the kernel, run lab0-setup/setup.ipynb, then "
            "rerun Lab 5D setup."
        )


def load_shared_environment(start: Path | None = None) -> Path:
    """Load the nearest ancestor ``.env`` and return its path.

    ``lab0-setup/setup.ipynb`` creates this file. Loading it before importing
    ``src.config.config`` keeps account, region, and project resolution
    identical in every Lab 5 notebook without duplicating ancestor-search code
    in notebook cells. If that module is already cached with different shared
    values, the user must restart the kernel so existing imports cannot retain
    stale references.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            _validate_cached_config(env_path)
            return env_path
    raise RuntimeError("No .env found. Run lab0-setup/setup.ipynb first.")


def ensure_lab5_package(start: Path | None = None) -> Path:
    """Install the Lab 5 package and declared dependencies into this kernel.

    Successful installer output is captured because setuptools emits a noisy
    editable-install warning when the notebook runs beside the local ``src``
    package. If installation fails, the complete captured diagnostics are
    replayed before the exception is raised.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / "pyproject.toml").exists() and (directory / "src").is_dir():
            command = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-e",
                str(directory),
                "--quiet",
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                if completed.stdout:
                    print(completed.stdout, end="", file=sys.stdout)
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                raise subprocess.CalledProcessError(
                    completed.returncode,
                    command,
                    output=completed.stdout,
                    stderr=completed.stderr,
                )
            return directory
    raise RuntimeError("Lab 5 pyproject.toml was not found from the current directory.")
