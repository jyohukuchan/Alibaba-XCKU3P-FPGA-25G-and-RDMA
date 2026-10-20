#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged original combined-app regressions on a selected HLS, short only.

Actual original APP/READ/WRITE/HLS RTL; peer/MAC/AXI remain models. Shared
four-state runner limits compilation30s and simulation120s, saves partial
logs and preserves all original testbench assertions/cycle bounds. This
does not prove native DMA, complete release coverage or authorize an image.
"""
import argparse
import hashlib
from pathlib import Path
import sys

import bounded_transport_sim as bounded

ROOT = bounded.ROOT
ORIGINAL_SIMULATE = bounded.simulate


def simulate(tb, fixtures, hls_build, wall_timeout=120):
    helper = Path(__file__).resolve()
    before = hashlib.sha256(helper.read_bytes()).hexdigest()
    output, identity = ORIGINAL_SIMULATE(tb, fixtures, hls_build, wall_timeout=120)
    if before != hashlib.sha256(helper.read_bytes()).hexdigest():
        raise ValueError('original-app bounded helper changed')
    identity['source_sha256'][str(helper.relative_to(ROOT))] = before
    identity.update(original_app_regression=True, native_hardware_verified=False,
                    generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest())
    return output, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', choices=['read', 'write', 'warm'], required=True)
    args, remaining = parser.parse_known_args()
    sys.path.insert(0, str(ROOT/'rdma/read/tests'))
    if args.probe == 'read':
        import probe_rw_read as probe
    elif args.probe == 'write':
        import probe_rw_write as probe
    else:
        import probe_rw_warm as probe
    probe.rw_sim.simulate = simulate
    sys.argv = [sys.argv[0], *remaining]
    if args.probe != 'write':
        sys.argv += ['--wall-timeout', '120']
    probe.main()


if __name__ == '__main__':
    main()
