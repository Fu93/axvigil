#!/bin/sh
# Copy the read-only inputs onto the tmpfs workdir, then run forge offline.
set -eu
mkdir -p /work
cp -a /inputs/. /work/
cd /work
exec forge test --json "$@"
