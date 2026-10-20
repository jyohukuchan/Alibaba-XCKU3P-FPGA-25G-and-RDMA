#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded four-state execution of explicit per-WR transport delivery copies.

All original generated HLS bytes remain identical. The original old bridge
is excluded exactly once in favor of the source-frozen SQ-interface derivative.
No implicit port padding, bench/assertion repair or internal RTL modifications.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bounded_transport_sim as bounded

ROOT = bounded.ROOT
ORIGINAL_SIMULATE = bounded.simulate
ORIGINAL_MODULES = bounded.rw_sim.modules
OLD_BRIDGE = ROOT/'rdma/rtl/rocev2_integrity_transport.v'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_delivery(project):
    project = project.resolve()
    path = project/'wrkey-delivery.json'
    record = json.loads(path.read_text())
    if (record.get('profile') != 'per-wr-key-context-v1' or not record.get('prepared') or
            record.get('output_directory') != str(project) or
            record.get('legacy_default_mode') != 1 or record.get('explicit_key_mode') != 0 or
            record.get('original_generated_files') != 138 or record.get('delivery_files') != 140):
        raise ValueError('unreviewed delivery profile')
    for name, value in record['source_sha256'].items():
        if digest(ROOT/name) != value: raise ValueError('delivery source changed: '+name)
    rtl = project/'solution1/syn/verilog'
    files = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    raw_names = set(record['copied_raw_sha256'])
    expected_names = raw_names | {'rocev2_integrity_transport_wrkey.v','rocev2_wrkey_sq_adapter.v'}
    if (len(raw_names) != 138 or len(files) != 140 or
            {p.name for p in files} != expected_names or
            {p.name:digest(p) for p in files} != record['generated_sha256']):
        raise ValueError('delivery files changed/added/missing')
    hls = json.loads(Path(record['hls_record']).read_text())
    if (not hls.get('pass_test') or hls.get('terminal_exit_status') != 0 or
            hls.get('generated_files') != 138 or
            hls.get('generated_hls_sha256') != record['original_generated_HLS_sha256']):
        raise ValueError('delivery does not match the bound actual HLS construction')
    original = Path(hls['hls_build'])/'solution1/syn/verilog'
    original_files = sorted([*original.glob('*.v'), *original.glob('*.dat')])
    if {p.name:digest(p) for p in original_files} != record['copied_raw_sha256']:
        raise ValueError('delivery differs from original generated HLS bytes')
    raw = hashlib.sha256()
    for name, value in sorted(record['copied_raw_sha256'].items()):
        p = rtl/name
        if digest(p) != value: raise ValueError('raw HLS bytes modified: '+name)
        raw.update(name.encode()+b'\0'+p.read_bytes())
    if raw.hexdigest() != record['original_generated_HLS_sha256']:
        raise ValueError('wrong raw HLS aggregate')
    delivered = hashlib.sha256()
    for p in files: delivered.update(p.name.encode()+b'\0'+p.read_bytes())
    if delivered.hexdigest() != record['delivery_sha256']:
        raise ValueError('wrong full delivery aggregate')
    # Reconstruct the permitted interface derivation from the recorded current
    # source, rather than trusting self-consistent but edited output manifests.
    generator = ROOT/'rdma/rnic/fpga/prepare_wrkey_transport.py'
    spec = importlib.util.spec_from_file_location('as02_wrkey_delivery_generator', generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if ((rtl/'rocev2_integrity_transport_wrkey.v').read_text() != module.derive_bridge(OLD_BRIDGE.read_text()) or
            (rtl/'rocev2_wrkey_sq_adapter.v').read_bytes() !=
            (ROOT/'rdma/rnic/rtl/rocev2_wrkey_sq_adapter.v').read_bytes()):
        raise ValueError('delivery contains an unreviewed bridge/adapter transformation')
    return record, path


def simulate(tb, fixtures, hls_build, wall_timeout=120):
    record, path = verify_delivery(hls_build)
    helpers = [Path(__file__).resolve(), path]
    before = {str(p.relative_to(ROOT)):digest(p) for p in helpers}
    def modules(project):
        if project.resolve() != hls_build.resolve():
            raise ValueError('unexpected selected delivery')
        sources, data = ORIGINAL_MODULES(project)
        if sources.count(OLD_BRIDGE) != 1:
            raise ValueError('original bridge source selection changed')
        sources.remove(OLD_BRIDGE)
        derived = project.resolve()/'solution1/syn/verilog/rocev2_integrity_transport_wrkey.v'
        if sources.count(derived) != 1:
            raise ValueError('missing/duplicate explicit bridge')
        return sources, data
    bounded.rw_sim.modules = modules
    try:
        output, identity = ORIGINAL_SIMULATE(tb, fixtures, hls_build, wall_timeout=120)
    finally:
        bounded.rw_sim.modules = ORIGINAL_MODULES
    verify_delivery(hls_build)
    if before != {n:digest(ROOT/n) for n in before}:
        raise ValueError('delivery test helper/profile changed')
    identity['source_sha256'].update(before)
    identity.update(generated_hls_sha256=record['original_generated_HLS_sha256'],
        generated_files=138, delivery_sha256=record['delivery_sha256'], delivery_files=140,
        raw_generated_HLS_bytes_unchanged=True, explicit_SQ_adapter_integrated=True,
        original_bridge_excluded_exactly_once=True,
        bridge_change_scope='static key-mode/explicit32-bit key input/adapter connections only',
        delivery_hardware_verified=False, delivery_standard_verbs_implemented=False)
    return output, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=['original-app','native-control',
        'legacy-read','legacy-write','read-error','fence-error'])
    args, remaining = parser.parse_known_args()
    if args.case == 'original-app':
        import bounded_original_app as app
        app.ORIGINAL_SIMULATE = simulate
        sys.argv = [sys.argv[0], *remaining]
        app.main()
    else:
        bounded.simulate = simulate
        sys.argv = [sys.argv[0], '--case', args.case, *remaining]
        bounded.main()


if __name__ == '__main__':
    main()
