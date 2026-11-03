#!/bin/sh
# Copy the read-only inputs onto the tmpfs workdir, then run forge offline.
set -eu
mkdir -p /work
# Do not preserve host mtimes: the non-root runtime uid cannot change times on
# the tmpfs destination, and preserving them is unnecessary for deterministic
# Foundry grading.
cp -R /inputs/. /work/
cd /work
exec forge test --json "$@"
