"""Small bootstrap helpers shared by Lab 5 notebooks."""

from pathlib import Path
import subprocess
import sys
from typing import Optional

from dotenv import load_dotenv


def load_shared_environment(start: Optional[Path] = None) -> Path:
    """Load the nearest ancestor ``.env`` and return its path.

    Lab 0 creates this file. Loading it before importing ``src.config.config``
    keeps account, region, and project resolution identical in every Lab 5
    notebook without duplicating ancestor-search code in notebook cells.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            return env_path
    raise RuntimeError("No .env found. Run lab0-setup/setup.ipynb first.")


def ensure_lab5_package(start: Optional[Path] = None) -> Path:
    """Install the Lab 5 package and declared dependencies into this kernel."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / "pyproject.toml").exists() and (directory / "src").is_dir():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(directory), "--quiet"],
                check=True,
            )
            return directory
    raise RuntimeError("Lab 5 pyproject.toml was not found from the current directory.")
