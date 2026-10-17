#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
vivado_bin="${VIVADO_BIN:-}"
if [[ -z "$vivado_bin" ]]; then
    vivado_bin="$(command -v vivado || true)"
fi
if [[ -z "$vivado_bin" || ! -x "$vivado_bin" ]]; then
    echo 'Vivado synthesis/implementation tools are not installed or are not in PATH.' >&2
    echo 'Install Vivado 2025.2 Standard with Kintex UltraScale+ support (not Lab Edition).' >&2
    echo 'Then set VIVADO_BIN=/absolute/path/to/Vivado/2025.2/bin/vivado and run this script.' >&2
    exit 2
fi
mkdir -p "$task_dir/builds"
build_dir="$(mktemp -d "$task_dir/builds/as02mc04-25g-XXXXXXXX")"
echo "Build directory: $build_dir"
"$vivado_bin" -mode batch -source "$task_dir/build_25g.tcl" \
    -log "$build_dir/vivado.log" -journal "$build_dir/vivado.jou" -tclargs "$build_dir" \
    2>&1 | tee "$build_dir/console.log"
test -s "$build_dir/as02mc04_25g.bit"
sha256sum "$build_dir/as02mc04_25g.bit"
echo 'Build only; no JTAG, PCIe, network, or flash changes were made.'
