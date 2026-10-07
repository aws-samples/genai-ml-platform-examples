#!/usr/bin/env python3
"""Verify the seed-code vendored dataset schema matches the canonical one.

The workshop defines its dataset's columns, their order and their roles in ONE
place:

    lab5-monitoring/src/config/dataset_schema.yaml

The Lab 4A model-build seed code needs the same definition, but it is seeded into
a SEPARATE GitHub repository and so cannot import `workshop_common.schema`. It
therefore carries a vendored copy at:

    seed-code/classification/model_build/config/dataset_schema.yaml

WHY THIS CHECK EXISTS
---------------------
Feature ORDER is a positional contract. Lab 2 writes the Iceberg tables with
these columns; the pipeline materializes header-less CSVs in this order; and the
trained booster knows its inputs only by position (f0..f19). If the two files
drift, nothing errors -- you get a model that predicts confidently on
misaligned columns. This script makes that drift a build failure instead.

Compares the parsed `dataset:` mapping rather than raw bytes, so comments and
formatting may differ (the vendored copy documents the sync rule) while the
definition itself must be identical.

Usage:
    python3 scripts/check-vendored-schema.py

Exit status: 0 if the definitions match, 1 if they have drifted.
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("SKIP: PyYAML is not installed; cannot verify the vendored schema.")
    print("      pip install PyYAML")
    sys.exit(0)

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = REPO_ROOT / "lab5-monitoring" / "src" / "config" / "dataset_schema.yaml"
VENDORED = (
    REPO_ROOT / "seed-code" / "classification" / "model_build"
    / "config" / "dataset_schema.yaml"
)


def load(path):
    if not path.exists():
        print(f"FAIL: {path.relative_to(REPO_ROOT)} does not exist.")
        sys.exit(1)
    with open(path) as handle:
        doc = yaml.safe_load(handle) or {}
    dataset = doc.get("dataset")
    if not dataset:
        print(f"FAIL: {path.relative_to(REPO_ROOT)} has no top-level 'dataset:' key.")
        sys.exit(1)
    return dataset


def main():
    canonical = load(CANONICAL)
    vendored = load(VENDORED)

    if canonical == vendored:
        features = [f["name"] for f in canonical["features"]]
        print(
            "OK: vendored dataset schema matches the canonical definition "
            f"({len(features)} features, target '{canonical['target_column']}')."
        )
        return 0

    print("FAIL: the vendored dataset schema has DRIFTED from the canonical one.")
    print(f"  canonical: {CANONICAL.relative_to(REPO_ROOT)}")
    print(f"  vendored : {VENDORED.relative_to(REPO_ROOT)}")
    print()

    # Feature order first: it is the contract most likely to break silently.
    canonical_features = [(f["name"], f["type"]) for f in canonical.get("features", [])]
    vendored_features = [(f["name"], f["type"]) for f in vendored.get("features", [])]
    if canonical_features != vendored_features:
        print("  FEATURE LIST DIFFERS (this silently corrupts predictions):")
        if [n for n, _ in canonical_features] == [n for n, _ in vendored_features]:
            print("    names match but types differ")
        else:
            only_canonical = [n for n, _ in canonical_features
                              if n not in {m for m, _ in vendored_features}]
            only_vendored = [n for n, _ in vendored_features
                             if n not in {m for m, _ in canonical_features}]
            if only_canonical:
                print(f"    missing from vendored: {only_canonical}")
            if only_vendored:
                print(f"    extra in vendored    : {only_vendored}")
            if not only_canonical and not only_vendored:
                print("    same names, DIFFERENT ORDER -- the positional contract is broken")
        print(f"    canonical order: {[n for n, _ in canonical_features]}")
        print(f"    vendored  order: {[n for n, _ in vendored_features]}")
        print()

    for key in sorted(set(canonical) | set(vendored)):
        if key == "features":
            continue
        if canonical.get(key) != vendored.get(key):
            print(f"  '{key}' differs:")
            print(f"    canonical: {canonical.get(key)}")
            print(f"    vendored : {vendored.get(key)}")

    print()
    print("  Fix: re-sync the vendored copy in the SAME commit as the canonical one.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
