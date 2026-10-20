#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze a separate STATE-reset HLS with sequential metadata initialization.

Analysis candidate ONLY. Never modifies the pinned FNS checkout, previous
generated RTL, running full-board snapshot, or any hardware. Build success
does not authorize release: full reset/metadata/initiator/protected/physical
gates must separately pass, including reset during the initialization sweep.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from build_reset_profile import ROOT, check_sources, digest

TARGET = 'hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
PATCH = Path(__file__).with_name('sequential_meta_reset.patch')


def patch_copy(frozen_source):
    patch_text = PATCH.read_text()
    headers = [line for line in patch_text.splitlines() if line.startswith(('--- ', '+++ '))]
    if headers != ['--- a/'+TARGET, '+++ b/'+TARGET]:
        raise ValueError('metadata patch target outside allowlist')
    before = {str(p.relative_to(frozen_source)): digest(p) for p in frozen_source.rglob('*') if p.is_file()}
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH.resolve())],
                            cwd=frozen_source, capture_output=True, text=True, check=True)
    after = {str(p.relative_to(frozen_source)): digest(p) for p in frozen_source.rglob('*') if p.is_file()}
    changed = [name for name in set(before) | set(after) if before.get(name) != after.get(name)]
    if changed != [TARGET]:
        raise ValueError('unexpected patched files: '+repr(changed))
    return after, result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--tool', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence')
    source = args.source.resolve()
    original = check_sources.verify(source)
    profiles = [Path(__file__).resolve(), PATCH, Path(__file__).with_name('state_synth.tcl'),
                Path(__file__).with_name('build_reset_profile.py'), ROOT/'rdma/read/hls/check_sources.py',
                *check_sources.PATCHES, ROOT/'rdma/hls/probe/rocev2_config.hpp']
    profile_hashes = {str(p.relative_to(ROOT)): digest(p) for p in profiles}
    run = Path(tempfile.mkdtemp(prefix='meta-reset-hls-', dir=ROOT/'rdma/rnic/build'))
    frozen = run/'inputs'
    frozen.mkdir()
    for name, value in original.items():
        dest = frozen/'fns'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/name, dest)
        if digest(dest) != value:
            raise ValueError('source changed during snapshot: '+name)
    patched, patch_output = patch_copy(frozen/'fns')
    (frozen/'adapter').mkdir()
    shutil.copy2(ROOT/'rdma/hls/probe/rocev2_config.hpp', frozen/'adapter/rocev2_config.hpp')
    shutil.copy2(Path(__file__).with_name('state_synth.tcl'), frozen/'synth.tcl')
    for p in profiles:
        dest = frozen/'profile'/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    snapshot = {str(p.relative_to(frozen)): digest(p) for p in frozen.rglob('*') if p.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(f'{h}  {p}\n' for p, h in sorted(snapshot.items())))
    if original != check_sources.verify(source) or profile_hashes != {
            str(p.relative_to(ROOT)): digest(p) for p in profiles}:
        raise ValueError('source/profile changed during snapshot')
    project = run/'project'
    log = run/'synthesis.log'
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(dict(started_at=started, hls_build=str(project), log=str(log),
                          manifest=str(frozen/'inputs.sha256'), patch_output=patch_output)), flush=True)
    with log.open('x') as out:
        result = subprocess.run([str(args.tool.resolve()), '--mode', 'hls', '--tcl', str(frozen/'synth.tcl')],
                                cwd=run, env=dict(os.environ, AS02_RNIC_HLS_INPUT=str(frozen), AS02_HLS_BUILD=str(project)),
                                stdout=out, stderr=subprocess.STDOUT)
    unchanged = (original == check_sources.verify(source) and profile_hashes == {
        str(p.relative_to(ROOT)): digest(p) for p in profiles} and snapshot == {
        str(p.relative_to(frozen)): digest(p) for p in frozen.rglob('*') if p.is_file() and p.name != 'inputs.sha256'})
    rtl = project/'solution1/syn/verilog'
    generated = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    aggregate = hashlib.sha256()
    for p in generated:
        aggregate.update(p.name.encode()+b'\0'+p.read_bytes())
    report = dict(scope=__doc__, started_at=started, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  reset_policy='state,synchronous,active-low;metadata-sequential-clear',
                  sequential_clear_entries=2000, source_directory=str(source), upstream_commit=check_sources.COMMIT,
                  source_sha256=original, patched_source_sha256=patched, profile_sha256=profile_hashes,
                  frozen_sha256=snapshot, inputs_unchanged=unchanged, hls_build=str(project),
                  log=str(log), log_sha256=digest(log), terminal_exit_status=result.returncode,
                  generated_hls_sha256=aggregate.hexdigest(), generated_files=len(generated),
                  hardware_verified=False, physical_signoff=False, programming_authorized=False,
                  metadata_reset_verified=False, constructor_reset_verified=False, protocol_regression_verified=False)
    xml_path = project/'solution1/syn/report/rocev2_top_csynth.xml'
    target = False
    if xml_path.exists():
        xml = ET.fromstring(xml_path.read_bytes())
        target = (xml.findtext('UserAssignments/Part') == 'xcku3p-ffvb676-1-e' and
                  xml.findtext('UserAssignments/TargetClockPeriod') == '4.00')
        report.update(synthesis_report_sha256=digest(xml_path),
                      estimated_period_ns=float(xml.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
                      resources={e.tag: int(e.text) for e in xml.find('AreaEstimates/Resources')})
    report['pass_test'] = result.returncode == 0 and unchanged and target and len(generated) >= 100
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('sha256')}, indent=2), flush=True)
    if not report['pass_test']:
        sys.exit(1)


if __name__ == '__main__':
    main()
