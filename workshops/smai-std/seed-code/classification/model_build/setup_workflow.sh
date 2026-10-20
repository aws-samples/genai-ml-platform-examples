#!/bin/bash
# This folder sits at models/<model-name>/ inside the shared model-build repo,
# so the repository root is two levels up. GitHub only runs workflows that live
# at the repository root, which is why the file has to be lifted out of here.
#
# Run this for every model you add, not just the first. The first model moves
# the workflow to the root; later models find it already there and just drop
# their own duplicate copy, leaving the root workflow untouched.
ROOT=../..

mkdir -p "$ROOT/.github/workflows"

if [ -f "$ROOT/.github/workflows/build.yml" ]; then
  echo "build.yml is already at the repository root - an earlier model set it up."
  rm -rf .github
else
  mv .github/workflows/build.yml "$ROOT/.github/workflows/"
  rm -rf .github
  echo "GitHub workflow moved to repository root!"
fi
