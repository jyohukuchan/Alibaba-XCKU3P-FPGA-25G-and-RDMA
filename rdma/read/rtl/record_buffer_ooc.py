#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Record an OOC probe, including failures, without claiming board timing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--archive-current-source', action='store_true',
                        help='For initial probe only: assert source is unchanged since launching it')
    args = parser.parse_args()
    build = args.build.resolve()
    source = build / 'rocev2_read_buffer.v'
    if args.archive_current_source:
        if source.exists():
            parser.error('refusing to replace frozen source')
        shutil.copy2(ROOT / 'rdma/read/rtl/rocev2_read_buffer.v', source)
    log = args.log.read_text()
    matches = re.findall(r'^READ_BUFFER_OOC WNS=([-\d.]+) WHS=([-\d.]+) BRAM_PRIMITIVES=(\d+)$', log, re.M)
    if len(matches)!=1 or args.report.exists():
        parser.error('need a terminal OOC report and a new output path')
    wns, whs, brams = float(matches[0][0]), float(matches[0][1]), int(matches[0][2])
    artifacts = [source, build / 'utilization.rpt', build / 'timing.rpt', build / 'drc.rpt',
                 build / 'routed.dcp', args.log.resolve()]
    frozen_script = build / 'buffer_ooc.tcl'
    if frozen_script.exists():
        artifacts.append(frozen_script)
    report = dict(scope='Isolated READ buffer OOC, not full-board timing or hardware',
        hardware_verified=False, full_board_verified=False, target_period_ns=4.0,
        setup_wns_ns=wns, hold_whs_ns=whs, bram_primitives=brams,
        isolated_io_model=dict(input_min_ns=0.2 if frozen_script.exists() else 0.0,
            input_max_ns=0.5 if frozen_script.exists() else 0.0,
            output_min_ns=0.0,output_max_ns=0.5 if frozen_script.exists() else 0.0),
        pass_test=wns>=0 and whs>=0 and brams>0,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        artifacts_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in artifacts},
        collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
