#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze pinned READ-capable sources and synthesize a separate reset-all HLS.

Build evidence only: not a physical timing, protocol, or hardware sign-off.
Never edits the pinned checkout or old generated RTL. All tool input files are
copied and hashed before launch; verify both original and frozen inputs after.
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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'rdma/read/hls'))
import check_sources


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--tool', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve evidence: choose a new report')
    source = args.source.resolve()
    source_hashes = check_sources.verify(source)
    profiles = [Path(__file__).resolve(), Path(__file__).with_name('synth.tcl'),
                ROOT / 'rdma/read/hls/check_sources.py', *check_sources.PATCHES,
                ROOT / 'rdma/hls/probe/rocev2_config.hpp']
    profile_hashes = {str(p.relative_to(ROOT)): digest(p) for p in profiles}
    build_root = ROOT / 'rdma/rnic/build'
    build_root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='reset-all-hls-', dir=build_root))
    frozen = run / 'inputs'
    frozen.mkdir()
    for name, value in source_hashes.items():
        target = frozen / 'fns' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        if digest(target) != value:
            raise ValueError('source changed during snapshot: ' + name)
    (frozen / 'adapter').mkdir()
    shutil.copy2(ROOT / 'rdma/hls/probe/rocev2_config.hpp', frozen / 'adapter/rocev2_config.hpp')
    shutil.copy2(Path(__file__).with_name('synth.tcl'), frozen / 'synth.tcl')
    frozen_hashes = {str(p.relative_to(frozen)): digest(p) for p in sorted(frozen.rglob('*')) if p.is_file()}
    (frozen / 'inputs.sha256').write_text(''.join(f'{h}  {p}\n' for p, h in frozen_hashes.items()))
    if source_hashes != check_sources.verify(source) or profile_hashes != {
            str(p.relative_to(ROOT)): digest(p) for p in profiles}:
        raise ValueError('original inputs changed during snapshot')
    project = run / 'project'
    log = run / 'synthesis.log'
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(dict(started_at=started, run=str(run), hls_build=str(project),
                          frozen_manifest=str(frozen / 'inputs.sha256'), log=str(log))), flush=True)
    environment = dict(os.environ, AS02_RNIC_HLS_INPUT=str(frozen), AS02_HLS_BUILD=str(project))
    with log.open('x') as stream:
        result = subprocess.run([str(args.tool.resolve()), '--mode', 'hls', '--tcl',
                                 str(frozen / 'synth.tcl')], env=environment, cwd=run,
                                stdout=stream, stderr=subprocess.STDOUT)
    unchanged = (source_hashes == check_sources.verify(source) and profile_hashes == {
        str(p.relative_to(ROOT)): digest(p) for p in profiles} and frozen_hashes == {
        str(p.relative_to(frozen)): digest(p) for p in frozen.rglob('*')
        if p.is_file() and p.name != 'inputs.sha256'})
    rtl = project / 'solution1/syn/verilog'
    generated = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    aggregate = hashlib.sha256()
    for path in generated:
        aggregate.update(path.name.encode() + b'\0' + path.read_bytes())
    xml_path = project / 'solution1/syn/report/rocev2_top_csynth.xml'
    report = dict(scope=__doc__, started_at=started,
                  finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  hardware_verified=False, physical_signoff=False, reset_policy='all,synchronous,active-low',
                  upstream_commit=check_sources.COMMIT, source_directory=str(source),
                  source_sha256=source_hashes, profile_sha256=profile_hashes,
                  frozen_sha256=frozen_hashes, inputs_unchanged=unchanged,
                  hls_build=str(project), tool=str(args.tool.resolve()),
                  terminal_exit_status=result.returncode, log=str(log), log_sha256=digest(log),
                  generated_hls_sha256=aggregate.hexdigest(), generated_files=len(generated))
    correct_target = False
    if xml_path.is_file():
        xml = ET.fromstring(xml_path.read_bytes())
        correct_target = (xml.findtext('UserAssignments/Part') == 'xcku3p-ffvb676-1-e' and
                          xml.findtext('UserAssignments/TargetClockPeriod') == '4.00')
        report.update(synthesis_report_sha256=digest(xml_path),
                      estimated_period_ns=float(xml.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
                      resources={e.tag: int(e.text) for e in xml.find('AreaEstimates/Resources')})
    report['pass_test'] = result.returncode == 0 and unchanged and correct_target and len(generated) >= 100
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('sha256')}, indent=2), flush=True)
    if not report['pass_test']:
        sys.exit(1)


if __name__ == '__main__':
    main()
