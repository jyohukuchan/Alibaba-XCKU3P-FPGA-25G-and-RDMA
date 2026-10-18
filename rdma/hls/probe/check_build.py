#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind a board build to the exact timer/app RTL regressions. No hardware I/O.

This gate proves input provenance only, not physical timing or the goal.
"""
import argparse
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-build", type=pathlib.Path, required=True)
    args = parser.parse_args()
    rtl = args.hls_build.resolve() / "solution1/syn/verilog"
    require((rtl / "rocev2_top.v").is_file(), "missing generated HLS top")
    generated = hashlib.sha256()
    sources = sorted([*rtl.glob("*.v"), *rtl.glob("*.dat")])
    require(len(sources) >= 100, "incomplete HLS build")
    for source in sources:
        generated.update(source.name.encode() + b"\0" + source.read_bytes())
    identity = generated.hexdigest()
    timer = json.loads((ROOT / "results/2026-10-18/rocev2-timer-rtl.json").read_text())
    require(timer["pass_test"] and not timer["hardware_verified"] and
            timer["core_clock_ps"] == 4000 and timer["max_qps"] == 8 and
            timer["timer_table_storage"] == "registers" and timer["warm_reset_checked"] and
            timer["ack_restart_scan_phases_checked"] == 8 and timer["stop_restart_phases_checked"] == 8 and
            timer["ack_stop_checked"] and timer["retry_output_backpressure_checked"] and
            timer["first_retry_min_clocks"] >= 250000 and timer["first_retry_max_clocks"] <= 250128,
            "missing complete generated-timer regression")
    require(timer["generated_rtl_sha256"] == identity and
            timer["test_sha256"] == digest(ROOT / "rdma/hls/probe/test_timer_rtl.py"),
            "timer test/build identity differs")
    app = json.loads((ROOT / "results/2026-10-17/rocev2-control-transport-rtl.json").read_text())
    require(app["complete"] and not app["hardware_verified"] and len(app["cases"]) == 5 and
            app["generated_rtl_sha256"] == identity, "missing matching board-app integration evidence")
    for case in app["cases"]:
        require(case["pass_test"] and case["boundary"] == "app" and case["rtl_tx_guard_used"] and
                case["all_wire_bytes_checked"] and case["wire_icrcs_valid"] and case["wire_ipv4_checksums_valid"] and
                case["generated_rtl_sha256"] == identity and case["source_sha256"] == app["source_sha256"] and
                case["test_sha256"] == app["test_sha256"] and
                case["boundary_test_dependency_sha256"] == app["boundary_test_dependency_sha256"],
                "incomplete/mixed board-app case")
    require({case["message_bytes"] for case in app["cases"]} == {1, 65, 4096} and
            any(case["ack_every"] == 2 and case["initial_psn"] == 0xFFFFFE for case in app["cases"]),
            "missing tail/full-size/wrap/cumulative ACK cases")
    for name, expected in app["source_sha256"].items():
        source = ROOT / ("rdma/fpga" if name == "mqnic_app_block.v" else "rdma/rtl") / name
        require(digest(source) == expected, "stale application source: " + name)
    for field, name in (("test_sha256", "rdma/hls/probe/test_control_transport.py"),
                        ("boundary_test_dependency_sha256", "rdma/hls/probe/app_boundary.py"),
                        ("axi_test_dependency_sha256", "rdma/tests/test_control_rtl.py")):
        require(app[field] == digest(ROOT / name), "stale application test: " + name)
    print(json.dumps(dict(input_provenance_verified=True, hardware_verified=False,
                          generated_rtl_sha256=identity, generated_files=len(sources)), sort_keys=True))


if __name__ == "__main__":
    main()
