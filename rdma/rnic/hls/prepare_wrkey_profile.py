#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze a NEW per-WR-key/retry-context HLS source candidate, no hardware.

No synthesis or feature pass is implied by preparing sources. The existing
metadata HLS/full-board analysis and old running/released images are untouched.
This changes the SQ ABI: 240 existing bits + one validity bit (AXIS rounds
to 248). The previously unused params[191:160] holds the exact 32-bit key;
the validity bit, NEVER key==0, chooses explicit key versus legacy QP key.
An explicit old-SQ adapter and fresh generated-RTL/physical checks remain.
"""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import build_meta_reset_profile as metadata
from build_reset_profile import ROOT, check_sources, digest

PATCH = Path(__file__).with_name('per_wr_context.patch')
TARGETS = (
    'hls/ib_transport_protocol/ib_transport_protocol.hpp',
    'hls/ib_transport_protocol/ib_transport_protocol.cpp',
    'hls/ib_transport_protocol/retransmitter/retransmitter.hpp',
)


def patch_copy(frozen_source):
    """Only the allowlisted new copy may be modified, without fuzzy patches."""
    headers = [s for s in PATCH.read_text().splitlines()
               if s.startswith(('--- ', '+++ '))]
    expected = [s for name in TARGETS for s in ('--- a/'+name, '+++ b/'+name)]
    if headers != expected:
        raise ValueError('per-WR patch target outside exact allowlist')
    before = {str(p.relative_to(frozen_source)): digest(p)
              for p in frozen_source.rglob('*') if p.is_file()}
    command = ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH.resolve())]
    subprocess.run(command+['--dry-run'], cwd=frozen_source,
                   capture_output=True, text=True, check=True)
    result = subprocess.run(command, cwd=frozen_source,
                            capture_output=True, text=True, check=True)
    after = {str(p.relative_to(frozen_source)): digest(p)
             for p in frozen_source.rglob('*') if p.is_file()}
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    if changed != set(TARGETS) or set(before) != set(after):
        raise ValueError('unexpected per-WR patch modifications/artifacts: '+repr(changed))
    return after, result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence; choose a new report')
    source = args.source.resolve()
    original = check_sources.verify(source)
    profiles = [Path(__file__).resolve(), PATCH, metadata.PATCH,
                Path(metadata.__file__).resolve(),
                Path(__file__).with_name('state_synth.tcl'),
                Path(__file__).with_name('build_reset_profile.py'),
                ROOT/'rdma/read/hls/check_sources.py', *check_sources.PATCHES,
                ROOT/'rdma/hls/probe/rocev2_config.hpp']
    profile_hashes = {str(p.relative_to(ROOT)): digest(p) for p in profiles}
    run = Path(tempfile.mkdtemp(prefix='wrkey-hls-', dir=ROOT/'rdma/rnic/build'))
    frozen = run/'inputs'
    frozen.mkdir()
    for name, value in original.items():
        dest = frozen/'fns'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/name, dest)
        if digest(dest) != value:
            raise ValueError('source changed during snapshot: '+name)
    _, first_log = metadata.patch_copy(frozen/'fns')
    patched, second_log = patch_copy(frozen/'fns')
    if {p for p in original if original[p] != patched[p]} != set(TARGETS):
        raise ValueError('unexpected total derived change set')
    (frozen/'adapter').mkdir()
    shutil.copy2(ROOT/'rdma/hls/probe/rocev2_config.hpp', frozen/'adapter/rocev2_config.hpp')
    shutil.copy2(Path(__file__).with_name('state_synth.tcl'), frozen/'synth.tcl')
    for p in profiles:
        dest = frozen/'profile'/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    snapshot = {str(p.relative_to(frozen)): digest(p)
                for p in frozen.rglob('*') if p.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(f'{h}  {p}\n' for p, h in sorted(snapshot.items())))
    if original != check_sources.verify(source) or profile_hashes != {
            str(p.relative_to(ROOT)): digest(p) for p in profiles}:
        raise ValueError('source/profile changed during preparation')
    report = dict(
        scope=__doc__, observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_directory=str(source), upstream_commit=check_sources.COMMIT,
        source_sha256=original, patched_source_sha256=patched,
        profile_sha256=profile_hashes, frozen_sha256=snapshot,
        hls_build=str(run/'project'), inputs_unchanged=True,
        source_freeze_prepared=True, pass_test=False,
        synthesis_executed=False, generated_RTL_verified=False,
        SQ_logical_bits=241, expected_AXIS_SQ_bits=248,
        key_bits=[208, 239], validity_bit=240,
        explicit_key_zero_supported=True, legacy_240_adapter_implemented=False,
        metadata_entries=2000, metadata_fields=13, reset_policy='STATE;full-sequential-metadata',
        host_retry_context_preserved_in_source=True,
        hardware_verified=False, release_authorized=False,
        standard_verbs_or_native_host_source_DMA_implemented=False,
        patch_output=first_log+second_log)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('sha256')}, indent=2))


if __name__ == '__main__':
    main()
