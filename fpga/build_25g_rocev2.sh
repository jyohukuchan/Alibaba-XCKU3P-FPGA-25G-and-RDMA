#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Build only: no programming, network or fan changes.
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
: "${AS02_HLS_BUILD:?Set AS02_HLS_BUILD to the source-bound tested HLS build}"
export AS02_ENABLE_ROCE=1
exec bash "$task_dir/build_25g.sh"
