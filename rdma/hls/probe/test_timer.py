#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run the actual patched HLS timer C model with ASan/UBSan at 250MHz.

This verifies source behavior and clock constants, not generated RTL timing
or actual RNIC retry interoperability.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fns-source", required=True, type=pathlib.Path)
    parser.add_argument("--vitis-include", required=True, type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    here = pathlib.Path(__file__).resolve().parent
    source = args.fns_source.resolve()
    if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != "75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c":
        parser.error("unexpected FNS revision")
    patch = here.parent / "fns-compat.patch"
    subprocess.run(["git", "-C", str(source), "apply", "--reverse", "--check", str(patch)], check=True)
    with tempfile.TemporaryDirectory(prefix="as02-hls-timer-") as temporary:
        executable = pathlib.Path(temporary) / "timer"
        subprocess.run(["g++", "-std=c++17", "-O1", "-g", "-Wno-unknown-pragmas",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-I" + str(here), "-I" + str(source / "hls"),
                        "-I" + str(args.vitis_include.resolve()), "-DFNS_DATA_WIDTH=64",
                        "-DFNS_ROCE_STACK_MAX_QPS=8", "-D__VITIS_HLS__",
                        str(here / "test_timer.cpp"), "-o", str(executable)], check=True, timeout=120)
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
        completed = subprocess.run([str(executable)], check=True, capture_output=True,
                                   text=True, env=env, timeout=120)
        records = [json.loads(line[7:]) for line in completed.stdout.splitlines() if line.startswith("RESULT ")]
        if len(records) != 1 or not records[0]["pass_test"]:
            raise ValueError("missing successful timer evidence")
        tracked = {"test_timer.cpp": here / "test_timer.cpp", "rocev2_config.hpp": here / "rocev2_config.hpp",
                   "transport_timer.hpp": source / "hls/ib_transport_protocol/transport_timer.hpp",
                   "fns-compat.patch": patch}
        record = dict(evidence_type="sanitized HLS C-model timer test, not RTL or hardware",
                      hardware_verified=False, generated_rtl_verified=False, sanitizers=["address", "undefined"],
                      **records[0], source_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in tracked.items()},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
