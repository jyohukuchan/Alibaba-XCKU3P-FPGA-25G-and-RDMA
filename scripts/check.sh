#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Read-only source checks. No compilation, network tests or hardware access.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
for required in git bash tclsh jq; do
    command -v "$required" >/dev/null || { printf 'Missing tool: %s\n' "$required" >&2; exit 2; }
done
for script in scripts/*.sh fpga/*.sh; do bash -n "$script"; done
tclsh tests/check_tcl_syntax.tcl
AS02_SOURCE_CHECK_ONLY=1 tclsh fpga/build_25g.tcl /tmp/as02-unused-source-check
git -C external/corundum apply --check "$repo_dir/patches/mqnic-linux-6.17.patch"
jq -e '
    .date_utc == "2026-10-17" and .sequential_directions == true and
    (.tests | length) == 4 and
    all(.tests[]; .protocol == "TCP" and .num_streams == 4 and
        .omit_seconds == 3 and .error == null and
        .receiver.seconds >= 19 and .receiver.seconds < 25 and
        .receiver.bits_per_second > 10000000000 and
        .sender.retransmits >= 0)
' results/2026-10-17/tcp-summary.json >/dev/null
if env -u AS02_ALLOW_TRAFFIC_TEST bash scripts/benchmark_25g.sh >/dev/null 2>&1; then
    printf 'Traffic helper must refuse without explicit opt-in.\n' >&2
    exit 1
fi
if env -u AS02_JTAG_SERIAL bash scripts/read_temperature.sh >/dev/null 2>&1; then
    printf 'Temperature helper must require an explicit adapter serial.\n' >&2
    exit 1
fi
printf 'Source checks passed. No new Vivado route or hardware validation is implied.\n'
