#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Offline build only: never programs SRAM/flash, changes NICs, or changes fans.
set -euo pipefail
rw_profile_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
rw_repo_dir="$(cd -- "$rw_profile_dir/../../.." && pwd)"
: "${AS02_HLS_BUILD:?Set AS02_HLS_BUILD to the tested READ-capable HLS build}"
: "${AS02_FNS_SOURCE:?Set AS02_FNS_SOURCE to the separate pinned READ FNS checkout}"
rw_vivado_bin="${VIVADO_BIN:-$(command -v vivado || true)}"
if [[ -z "$rw_vivado_bin" || ! -x "$rw_vivado_bin" ]]; then
    echo 'Vivado 2025.2 Standard with KU3P support is required.' >&2
    exit 2
fi
export AS02_ENABLE_ROCE=1
export PYTHONDONTWRITEBYTECODE=1
python3 "$rw_profile_dir/check_build.py" --hls-build "$AS02_HLS_BUILD" --fns-source "$AS02_FNS_SOURCE"
mkdir -p "$rw_repo_dir/fpga/builds"
rw_build_dir="$(mktemp -d "$rw_repo_dir/fpga/builds/as02mc04-25g-rw-XXXXXXXX")"
echo "Build directory: $rw_build_dir"
"$rw_vivado_bin" -mode batch -source "$rw_profile_dir/build_board.tcl" \
    -log "$rw_build_dir/vivado.log" -journal "$rw_build_dir/vivado.jou" -tclargs "$rw_build_dir" \
    2>&1 | tee "$rw_build_dir/console.log"
test -s "$rw_build_dir/as02mc04_25g.bit"
sha256sum "$rw_build_dir/as02mc04_25g.bit"
echo 'Build only; no JTAG, PCIe, network, or fan changes were made.'
