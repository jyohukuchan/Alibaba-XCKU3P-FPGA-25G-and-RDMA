#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Read-only JTAG status sampling; no reset/configuration/flash commands.
set -euo pipefail
: "${AS02_JTAG_SERIAL:?Set the serial of the explicitly selected JTAG adapter}"
diagnostic_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
openocd_bin=${OPENOCD_BIN:-$(command -v openocd || true)}
if [[ -z "$openocd_bin" || ! -x "$openocd_bin" ]]; then
    printf 'Install a suitable OpenOCD or set OPENOCD_BIN to its absolute path.\n' >&2
    exit 2
fi
if [[ "$openocd_bin" != /* ]]; then
    printf 'OPENOCD_BIN must resolve to an absolute executable path.\n' >&2
    exit 2
fi
exec sudo -n env AS02_JTAG_SERIAL="$AS02_JTAG_SERIAL" \
    timeout --kill-after=2s 25s "$openocd_bin" -f "$diagnostic_dir/read_temperature.cfg"
