#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Separate, offline verification-only release. Preserve the original build's
# source manifest and failed verifier. Never program hardware or alter XDC.
set -euo pipefail
if [[ $# != 3 || ! $2 =~ ^[0-9a-f]{64}$ || ! $3 =~ ^[0-9a-f]{64}$ ]]; then
    echo 'Usage: bash rdma/scripts/release_routed_candidate.sh BUILD_DIR COMPILE_MANIFEST_SHA256 ROUTED_DCP_SHA256' >&2
    exit 2
fi
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="$(realpath -e -- "$1")"
case "$build_dir" in
    "$task_root"/fpga/builds/as02mc04-25g-rocev2-*) ;;
    *) echo 'Expected an original RoCE build directory in this checkout.' >&2; exit 2 ;;
esac
compile_manifest="$build_dir/rocev2-source-identity.txt"
checkpoint="$build_dir/as02mc04_25g_routed.dcp"
test -s "$compile_manifest"
test -s "$checkpoint"
# The caller must first confirm the parent build's actual terminal state.
# A saved checkpoint/lock alone is not evidence that a process is terminal.
if [[ "${AS02_BUILD_TERMINAL_CONFIRMED:-}" != YES ]]; then
    echo 'First confirm the original build process/session is terminal, then set AS02_BUILD_TERMINAL_CONFIRMED=YES.' >&2
    exit 2
fi
printf '%s  %s\n' "$2" "$compile_manifest" "$3" "$checkpoint" | sha256sum --check --status
sha256sum --check --status "$compile_manifest"
if [[ -e "$build_dir/as02mc04_25g.bit" ]]; then
    echo 'Original build already produced an image; inspect it instead of making an alternate release.' >&2
    exit 2
fi
# Fail closed if the byte-identical gate, VIO checker, or tested LFC revision
# no longer matches the reviewed versions. Changes need a new qualification.
printf '%s  %s\n' \
    20e9551ec978ca03bc01c713a5691268f6571359b1ea49e0304694569602bc83 "$task_root/fpga/write_verified_25g_eco.tcl" \
    6f67f8faa58c8c12bb72e523cc571a489c958819057a9fcbc88e29ed9f2deb3a "$task_root/fpga/verify_vio_status_cdc.tcl" \
    d850262ff5194420e76e8a05f5030321114e429ff8aa5b3e67164a22d0154bbc "$task_root/fpga/verify_mac_flow_control_cdc.tcl" \
    acb5a830f734b56ac6fe4fd0c95c6742f7434d82de0e66970d443f9c50089ff3 "$task_root/rdma/scripts/verify_lfc_equivalent.tcl" \
    03a8e68dd9c375e7da7d3bbec491cb3796cd26139deed8bd3b4d36b0f72c740a "$task_root/external/corundum/fpga/mqnic/Nexus_K3P_S/fpga_25g/rtl/fpga_core.v" \
    a3e3e6102c747ad7d29a7e87252b2fbb9484f480dad768bcf19fda82b10f7e8d "$task_root/external/corundum/fpga/lib/eth/rtl/eth_mac_10g.v" \
    08453b7781cbea80aaa4810a1a2631f3862bd34221fce0f10faef8f1b8bdb40c "$task_root/external/corundum/fpga/common/rtl/mqnic_port.v" \
    1a2191369820a9232779e078b21afd4afdc5c6426b92f0778f393584dbda4f26 "$task_root/fpga/mac_flow_control_cdc.xdc" \
    | sha256sum --check --status
vivado_bin="${VIVADO_BIN:-$(command -v vivado || true)}"
if [[ -z "$vivado_bin" || ! -x "$vivado_bin" ]]; then
    echo 'Vivado implementation/bitstream tools are required.' >&2
    exit 2
fi
package_dir="$(mktemp -d "$task_root/fpga/builds/as02mc04-25g-rocev2-release-XXXXXXXX")"
mkdir "$package_dir/verifiers"
cp -- "$compile_manifest" "$package_dir/rocev2-source-identity.txt"
cp -- "$task_root/fpga/write_verified_25g_eco.tcl" "$task_root/fpga/verify_vio_status_cdc.tcl" "$package_dir/verifiers/"
cp -- "$task_root/fpga/verify_mac_flow_control_cdc.tcl" "$package_dir/verifiers/original_verify_mac_flow_control_cdc.tcl"
cp -- "$task_root/rdma/scripts/verify_lfc_equivalent.tcl" "$package_dir/verifiers/"
cp -- "$task_root/rdma/scripts/release_verify_mac_flow_control_cdc.tcl" "$package_dir/verifiers/verify_mac_flow_control_cdc.tcl"
cp -- "$task_root/rdma/scripts/release_routed_candidate.tcl" "$package_dir/release_routed_candidate.tcl"
cmp -- "$compile_manifest" "$package_dir/rocev2-source-identity.txt"
cmp -- "$task_root/fpga/write_verified_25g_eco.tcl" "$package_dir/verifiers/write_verified_25g_eco.tcl"
cmp -- "$task_root/fpga/verify_vio_status_cdc.tcl" "$package_dir/verifiers/verify_vio_status_cdc.tcl"
# This additive manifest explicitly binds both original and revised verifiers,
# the original compile identity, immutable DCP, and every executable release
# input. It does not rewrite the original compile manifest or backdate policy.
sha256sum -- \
    "$checkpoint" "$compile_manifest" \
    "$task_root/fpga/write_verified_25g_eco.tcl" \
    "$task_root/fpga/verify_vio_status_cdc.tcl" \
    "$task_root/fpga/verify_mac_flow_control_cdc.tcl" \
    "$task_root/rdma/scripts/verify_lfc_equivalent.tcl" \
    "$task_root/rdma/scripts/release_verify_mac_flow_control_cdc.tcl" \
    "$task_root/rdma/scripts/release_routed_candidate.tcl" \
    "$task_root/rdma/scripts/release_routed_candidate.sh" \
    "$package_dir/rocev2-source-identity.txt" \
    "$package_dir/release_routed_candidate.tcl" \
    "$package_dir/verifiers/write_verified_25g_eco.tcl" \
    "$package_dir/verifiers/verify_vio_status_cdc.tcl" \
    "$package_dir/verifiers/original_verify_mac_flow_control_cdc.tcl" \
    "$package_dir/verifiers/verify_mac_flow_control_cdc.tcl" \
    "$package_dir/verifiers/verify_lfc_equivalent.tcl" \
    > "$package_dir/verification-source-identity.txt"
verification_sha="$(sha256sum -- "$package_dir/verification-source-identity.txt")"
verification_sha="${verification_sha%% *}"
printf 'Verification-only release package: %s\nOriginal compile manifest SHA256: %s\nVerification revision manifest SHA256: %s\n' "$package_dir" "$2" "$verification_sha"
"$vivado_bin" -mode batch -source "$package_dir/release_routed_candidate.tcl" \
    -log "$package_dir/release.log" -journal "$package_dir/release.jou" \
    -tclargs "$checkpoint" "$package_dir" "$verification_sha" "$2" \
    2>&1 | tee "$package_dir/console.log"
sha256sum --check --status "$package_dir/verification-source-identity.txt"
sha256sum --check --status "$package_dir/rocev2-source-identity.txt"
test -s "$package_dir/as02mc04_25g.bit"
test -s "$package_dir/as02mc04_25g.ltx"
sha256sum -- "$package_dir/as02mc04_25g.bit" "$package_dir/as02mc04_25g.ltx"
echo 'Offline static gate only. Review actual final CDC/operating conditions before any finite SRAM hardware test.'
