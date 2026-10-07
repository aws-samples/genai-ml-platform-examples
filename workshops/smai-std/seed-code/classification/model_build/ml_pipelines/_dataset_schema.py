"""Dataset feature schema for the model-build pipeline.

Reads the vendored ``config/dataset_schema.yaml`` — the ONE place this repo
defines the dataset's columns and their order. Nothing else here re-types a
feature list.

DO NOT RENAME THIS MODULE TO ``schema.py``. ``run_pipeline.py`` is executed as a
script from ``ml_pipelines/``, which puts that directory at ``sys.path[0]``. A
module named ``schema`` there shadows the PyPI ``schema`` package that
``sagemaker.clarify`` imports (``from schema import Schema, And, Use, Or``),
which breaks ``import sagemaker`` itself with a confusing ImportError.

This mirrors ``workshop_common/schema.py`` in the workshop repo. It is a
separate copy because this directory is seeded into its own GitHub repository
and cannot import from the workshop repo. See the header of
``config/dataset_schema.yaml`` for the sync rule.

Used at pipeline-DEFINITION time (in the GitHub Actions runner). The resolved
feature list is then passed down to the pipeline steps as arguments, so the
step containers need neither this module nor the YAML on their path.

Depends only on the standard library + PyYAML.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

# ml_pipelines/_dataset_schema.py -> repo root -> config/dataset_schema.yaml
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "dataset_schema.yaml"

# Bump whenever the `features` list in dataset_schema.yaml changes. This travels
# with the model in baseline.json, so Lab 5 can tell which feature schema a
# given drift verdict was computed against. Kept here rather than in the YAML so
# the vendored YAML stays byte-comparable with the canonical upstream copy.
FEATURE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Feature:
    name: str
    type: str


@functools.lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(f"dataset_schema.yaml not found at {_SCHEMA_PATH}")
    with open(_SCHEMA_PATH, "r") as f:
        doc = yaml.safe_load(f) or {}
    dataset = doc.get("dataset")
    if not dataset:
        raise ValueError(
            f"{_SCHEMA_PATH} is missing the top-level 'dataset:' key."
        )
    return dataset


def identifier_column() -> str:
    return _load()["identifier_column"]


def timestamp_column() -> str:
    return _load()["timestamp_column"]


def target_column() -> str:
    return _load()["target_column"]


def target_type() -> str:
    return _load().get("target_type", "boolean")


def features() -> List[Feature]:
    return [Feature(f["name"], f["type"]) for f in _load()["features"]]


def feature_names() -> List[str]:
    """The 20 feature column names, in positional-contract order."""
    return [f.name for f in features()]


if __name__ == "__main__":
    print(f"Schema file:       {_SCHEMA_PATH}")
    print(f"Identifier column: {identifier_column()}")
    print(f"Target column:     {target_column()} ({target_type()})")
    print(f"Feature count:     {len(features())}")
    print(f"Feature names:     {feature_names()}")
