#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthesize the source-frozen per-WR-key candidate after actual C++ checks.

HLS-only construction: no board selection, bitstream or hardware commands.
A successful synthesis/port-width check is NOT a generated-RTL function,
reset, wire, physical timing, native DMA or standard verbs qualification.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from build_reset_profile import ROOT, digest


def verify(mapping, base):
    for path, value in mapping.items():
        if digest(base/path) != value:
            raise ValueError('input changed: '+str(base/path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-record', type=Path, required=True)
    parser.add_argument('--csim-record', type=Path, required=True)
    parser.add_argument('--tool', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence')
    source = json.loads(args.source_record.read_text())
    tested = json.loads(args.csim_record.read_text())
    if not source.get('source_freeze_prepared') or source.get('metadata_entries') != 2000 or source.get('metadata_fields') != 13:
        raise ValueError('wrong source candidate')
    if (not tested.get('pass_test') or tested.get('metadata_entries') != 2000 or
            tested.get('metadata_fields') != 13 or tested.get('actual_RETH_headers', 0) < 41 or
            tested.get('metadata_responses', 0) != 6001 or tested.get('actual_retry_events', 0) != 13 or
            not tested.get('READ_partial_PSN_wrap') or
            Path(tested['source_record']).resolve() != args.source_record.resolve()):
        raise ValueError('actual per-WR C++ coverage missing/wrong source')
    project = Path(source['hls_build'])
    frozen = project.parent/'inputs'
    if project.exists():
        raise ValueError('never overwrite prior HLS output')
    def inputs_current():
        verify(source['source_sha256'], Path(source['source_directory']))
        verify(source['profile_sha256'], ROOT)
        verify(source['frozen_sha256'], frozen)
        verify(tested['source_sha256'], ROOT)
        verify(tested['actual_include_sha256'], Path('/'))
        verify(tested['artifact_sha256'], ROOT)
    inputs_current()
    launch = project.parent/'launch'
    launch.mkdir()
    originals = [Path(__file__).resolve(), args.source_record.resolve(), args.csim_record.resolve()]
    current = {str(p): digest(p) for p in originals}
    for n, p in enumerate(originals):
        shutil.copy2(p, launch/(str(n)+'-'+p.name))
    launch_sha = {str(p.relative_to(launch)): digest(p) for p in launch.iterdir() if p.is_file()}
    command = [str(args.tool.resolve()), '--mode', 'hls', '--tcl', str(frozen/'synth.tcl')]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (launch/'inputs.json').write_text(json.dumps(dict(started_at=started, command=command,
        original_sha256=current, frozen_launch_sha256=launch_sha), indent=2)+'\n')
    log = project.parent/'wrkey-synthesis.log'
    print(json.dumps(dict(started_at=started, hls_build=str(project), log=str(log),
                          source_frozen_before_synthesis=True, release_authorized=False)), flush=True)
    with log.open('x') as out:
        result = subprocess.run(command, cwd=project.parent,
            env=dict(os.environ, AS02_RNIC_HLS_INPUT=str(frozen), AS02_HLS_BUILD=str(project)),
            stdout=out, stderr=subprocess.STDOUT)
    inputs_current()
    verify(current, Path('/'))
    verify(launch_sha, launch)
    rtl = project/'solution1/syn/verilog'
    files = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    aggregate = hashlib.sha256()
    for p in files: aggregate.update(p.name.encode()+b'\0'+p.read_bytes())
    top = rtl/'rocev2_top.v'
    width_ok = top.exists() and bool(re.search(
        r'input\s+\[\s*247\s*:\s*0\s*\]\s+s_axis_sq_meta_TDATA\b', top.read_text()))
    report = dict(scope=__doc__, started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        terminal_exit_status=result.returncode, source_and_frozen_inputs_unchanged=True,
        source_sha256=current, frozen_launch_sha256=launch_sha, hls_build=str(project),
        source_record=str(args.source_record), csim_record=str(args.csim_record),
        generated_hls_sha256=aggregate.hexdigest(), generated_files=len(files),
        SQ_AXIS_width_248_verified=width_ok, metadata_entries=2000, metadata_fields=13,
        hardware_verified=False, generated_RTL_function_tested=False,
        hardware_reset_verified=False, physical_signoff=False,
        standard_verbs_implemented=False, programming_authorized=False,
        pass_test=False, artifact_sha256={str(log.relative_to(ROOT)): digest(log)})
    xmlpath = project/'solution1/syn/report/rocev2_top_csynth.xml'
    if xmlpath.exists():
        xml = ET.fromstring(xmlpath.read_bytes())
        target = (xml.findtext('UserAssignments/Part') == 'xcku3p-ffvb676-1-e' and
                  xml.findtext('UserAssignments/TargetClockPeriod') == '4.00')
        report.update(target_part_and_4ns_verified=target,
            estimated_period_ns=float(xml.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
            resources={e.tag:int(e.text) for e in xml.find('AreaEstimates/Resources')},
            synthesis_report_sha256=digest(xmlpath),
            pass_test=result.returncode == 0 and target and width_ok and len(files) >= 100)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')}, indent=2))
    if not report['pass_test']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
