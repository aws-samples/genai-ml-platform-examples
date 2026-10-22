"""
Notebook bootstrap shared by the Lab 5 notebooks (5D, 5E, 5F).

Every Lab 5 notebook starts the same way: find the repo-root `.env` written by
lab0-setup/setup.ipynb, load it, make sure this lab directory is importable as
`src`, and drop any `src.*` modules a previous run left in the kernel so
`src.config.config` re-reads the freshly loaded environment.

Usage, from the first code cell of a notebook in lab5-monitoring/:

    from src.utils.notebook_env import bootstrap
    env = bootstrap()

This module deliberately imports nothing from `src` — it has to run before
`src.config.config` is imported, because config resolves its values from the
environment at import time.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict


def _find_up(start: Path, predicate) -> Path:
    return next((p for p in [start, *start.parents] if predicate(p)), None)


def bootstrap(install_package: bool = False, verbose: bool = True) -> Dict[str, object]:
    """Load the shared .env and make `src` importable with a fresh config.

    Args:
        install_package: `pip install -e` this lab directory first (5D / 5F do,
            so `import src` also resolves from a kernel started elsewhere).
        verbose: print what was loaded.

    Returns:
        {'env_path', 'project_root', 'project_name'}
    """
    from dotenv import load_dotenv

    cwd = Path.cwd()
    env_dir = _find_up(cwd, lambda p: (p / '.env').exists())
    if env_dir is None:
        raise RuntimeError('No .env found. Run lab0-setup/setup.ipynb first.')
    env_path = env_dir / '.env'
    load_dotenv(env_path, override=True)

    project_root = _find_up(
        cwd, lambda p: (p / 'pyproject.toml').exists() and (p / 'src').is_dir()
    ) or cwd

    if install_package:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-e', str(project_root), '--quiet'],
            check=False,
        )

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Drop src.* modules from a previous run (except this one) so config is
    # re-imported against the environment loaded above.
    for name in [k for k in sys.modules if k.startswith('src.') and k != __name__]:
        del sys.modules[name]
    importlib.invalidate_caches()

    project_name = os.environ.get('PROJECT_NAME', 'bank-marketing-prediction')
    if verbose:
        print(f'✓ Loaded shared environment from {env_path}')
        print(f'  PROJECT_NAME = {project_name}')
        print(f'  Lab root     = {project_root}'
              + ('  (installed with pip -e)' if install_package else ''))
    return {'env_path': env_path, 'project_root': project_root, 'project_name': project_name}
