#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Prove READ HLS source is the pinned upstream plus exactly two patches.

Reconstructs expected changed files in a temporary fixture. Never changes
the selected checkout or its git index; a passing result is not timing or
hardware evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
COMMIT = '75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c'
PATCHES = [ROOT / 'rdma/hls/fns-compat.patch', ROOT / 'rdma/read/hls/fns-read-fixes.patch']


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args])


def verify(source):
    if git(source, 'rev-parse', 'HEAD').decode().strip() != COMMIT:
        raise ValueError('unexpected upstream revision')
    names = set()
    for patch in PATCHES:
        for line in git(source, 'apply', '--numstat', str(patch)).decode().splitlines():
            names.add(line.split('\t', 2)[2])
    changed = set(git(source, 'diff', 'HEAD', '--name-only').decode().splitlines())
    if changed != names:
        raise ValueError('source change set differs from the two recorded patches')
    if git(source, 'ls-files', '--others', '--exclude-standard', '--', 'hls').strip():
        raise ValueError('untracked HLS sources may shadow pinned headers')
    with tempfile.TemporaryDirectory(prefix='as02-read-source-fixture-') as directory:
        fixture = Path(directory)
        for name in names:
            target = fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(source, 'show', f'{COMMIT}:{name}'))
        for patch in PATCHES:
            subprocess.run(['git', 'apply', str(patch)], cwd=fixture, check=True, capture_output=True)
        for name in names:
            if (fixture / name).read_bytes() != (source / name).read_bytes():
                raise ValueError('unrecorded source modifications: ' + name)
    paths = git(source, 'ls-files', '-z', '--', 'hls').decode().strip('\0').split('\0')
    return {name:hashlib.sha256((source / name).read_bytes()).hexdigest() for name in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve prior evidence: choose a new report')
    source = args.source.resolve()
    hashes = verify(source)
    build = args.hls_build.resolve()
    xml_path = build / 'solution1/syn/report/rocev2_top_csynth.xml'
    xml = ET.fromstring(xml_path.read_bytes())
    if xml.findtext('UserAssignments/Part') != 'xcku3p-ffvb676-1-e' or \
       xml.findtext('UserAssignments/TargetClockPeriod') != '4.00':
        raise ValueError('wrong part or HLS target period')
    rtl = build / 'solution1/syn/verilog'
    generated = sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')])
    if len(generated)<100 or not (rtl / 'rocev2_top.v').is_file():
        raise ValueError('missing complete HLS output')
    aggregate = hashlib.sha256()
    for path in generated:
        aggregate.update(path.name.encode() + b'\0' + path.read_bytes())
    dependencies = PATCHES + [ROOT / 'rdma/hls/probe/rocev2_config.hpp',
        ROOT / 'rdma/read/hls/synth.tcl', Path(__file__)]
    report = dict(scope='Source reconstruction/provenance, not physical timing or hardware',
        hardware_verified=False, pass_test=True, upstream_commit=COMMIT,
        source_directory=str(source), source_sha256=hashes,
        profile_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dependencies},
        hls_build=str(build), generated_hls_sha256=aggregate.hexdigest(), generated_files=len(generated),
        synthesis_report_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest(),
        estimated_period_ns=float(xml.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
        resources={e.tag:int(e.text) for e in xml.find('AreaEstimates/Resources')})
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')}, indent=2))


if __name__ == '__main__':
    main()
