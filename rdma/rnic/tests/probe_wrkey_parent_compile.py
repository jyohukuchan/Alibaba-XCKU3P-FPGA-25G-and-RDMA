#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual patched parent/core/app compile with explicit per-WR delivery.

Uses unchanged parent compile parameters/assertions/library dependencies;
excludes exactly the old bridge and original adapter source (the selected
delivery already contains its identical adapter). No stubs or RTL repair.
Parent/app selects legacy default mode; native per-WR bridge is separately
wire-tested. This is NOT whole-parent traffic, physical timing or hardware.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import probe_native_parent_compile as original
import wrkey_delivery_sim as delivery

ROOT = delivery.ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists(): parser.error('preserve previous evidence')
    record, manifest = delivery.verify_delivery(args.hls_build)
    own = {str(p.relative_to(ROOT)):delivery.digest(p) for p in
           [Path(__file__).resolve(), Path(original.__file__).resolve(),
            Path(delivery.__file__).resolve(), manifest]}
    run = Path(tempfile.mkdtemp(prefix='wrkey-parent-compile-', dir=ROOT/'rdma/rnic/build'))
    temporary_report = run/'original-parent-compile.json'
    excluded = [ROOT/'rdma/rtl/rocev2_integrity_transport.v',
                ROOT/'rdma/rnic/rtl/rocev2_wrkey_sq_adapter.v']
    selected = [args.hls_build.resolve()/'solution1/syn/verilog'/name for name in
                ['rocev2_integrity_transport_wrkey.v','rocev2_wrkey_sq_adapter.v']]
    command_record = []
    actual_run = subprocess.run
    def compile_selected(command, **kwargs):
        if command[0] != 'iverilog' or command.count('-s') != 1 or 'mqnic_core_pcie' not in command:
            raise ValueError('unexpected parent compile command')
        for p in excluded:
            if command.count(str(p)) != 1: raise ValueError('unexpected original source selection')
        for p in selected:
            if command.count(str(p)) != 1: raise ValueError('missing/duplicate delivery source')
        selected_command = [s for s in command if s not in set(map(str,excluded))]
        command_record.append(selected_command)
        return actual_run(selected_command, **kwargs)
    previous_argv = sys.argv
    sys.argv = [sys.argv[0], '--profile', str(args.profile.resolve()),
                '--hls-build', str(args.hls_build.resolve()),
                '--report', str(temporary_report), '--mac-tag-width', '16']
    terminal = 0
    original.subprocess.run = compile_selected
    try:
        try: original.main()
        except SystemExit as error: terminal = int(error.code or 0)
    finally:
        original.subprocess.run = actual_run
        sys.argv = previous_argv
    if len(command_record) != 1: raise ValueError('actual parent compiler not executed exactly once')
    report = json.loads(temporary_report.read_text())
    if report['parameter_values']['DMA_TAG_WIDTH'] != 19 or report['parameter_values']['TX_TAG_WIDTH'] != 16:
        raise ValueError('actual board-width parent parameters changed')
    delivery.verify_delivery(args.hls_build)
    if own != {n:delivery.digest(ROOT/n) for n in own}: raise ValueError('compile helper/input changed')
    report['source_sha256'].update(own)
    report.update(scope=__doc__, source_binding_original_scope=original.__doc__,
        parent_compiler_command=command_record[0], excluded_duplicate_original_sources=list(map(str,excluded)),
        original_generated_HLS_sha256=record['original_generated_HLS_sha256'],
        delivery_sha256=record['delivery_sha256'], explicit_legacy_SQ_adapter_in_parent=True,
        parent_native_per_WR_submission_implemented=False,
        original_compiler_warnings_retained=True, wrapper_terminal_exit_status=terminal,
        retained_directory=str(run))
    with args.report.open('x') as out: out.write(json.dumps(report,indent=2)+'\n')
    if not report['pass_test'] or terminal: raise SystemExit(1)


if __name__ == '__main__':main()
