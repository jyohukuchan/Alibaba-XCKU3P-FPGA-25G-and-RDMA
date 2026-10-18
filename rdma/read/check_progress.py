#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Verify current staged READ evidence, explicitly NOT completion of the goal.

This gate binds the implemented offline prototype to its source/results.
It cannot authorize programming or replace a full-board/native test gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'rdma/read/hls'))
import check_sources

RESULTS = ROOT / 'results/2026-10-18'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    result = json.loads((RESULTS / name).read_text())
    require(result['hardware_verified'] is False, 'not an offline report: ' + name)
    return result


def check_hashes(mapping, directory):
    for name, expected in mapping.items():
        require(digest(directory / name)==expected, 'stale source: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--fns-source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    require(not args.report.exists(), 'preserve prior progress record')
    names = dict(source='rocev2-read-hls-source-001.json',
        wire='rocev2-read-hls-probe-001.json',buffer='rocev2-read-buffer-rtl-004.json',
        engine='rocev2-read-engine-rtl-002.json',capture='rocev2-read-capture-probe-003.json',
        control='rocev2-read-control-probe-001.json',ooc='rocev2-read-buffer-ooc-003.json',
        write='rocev2-read-hls-write-regression-001.json')
    records={key:load(name) for key,name in names.items()}
    source=records['source']
    require(source['pass_test'] and source['upstream_commit']==check_sources.COMMIT, 'wrong source baseline')
    require(check_sources.verify(args.fns_source.resolve())==source['source_sha256'], 'changed FNS source')
    check_hashes(source['profile_sha256'],ROOT)
    rtl=args.hls_build.resolve() / 'solution1/syn/verilog'
    aggregate=hashlib.sha256()
    generated=sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')])
    for file in generated:
        aggregate.update(file.name.encode()+b'\0'+file.read_bytes())
    identity=aggregate.hexdigest()
    require(len(generated)==138 and identity==source['generated_hls_sha256'], 'different HLS outputs')
    for key in ('wire','capture','control'):
        record=records[key]
        require(record['complete'] and record['generated_hls_sha256']==identity, 'incomplete/mixed ' + key)
        require(all(c['pass_test'] for c in record['cases']), 'failed case: ' + key)
        check_hashes(record['source_sha256'],ROOT)
    require([c['message_bytes'] for c in records['wire']['cases']]==
        [1,2,3,4,63,64,65,4095,4096,4097,8192,8193,65536], 'missing wire/tail/PMTU cases')
    for key in ('capture','control'):
        cases=records[key]['cases']
        require([c['message_bytes'] for c in cases]==[65,4097], 'missing protected capture sizes')
        require(all(c['host_readback_bytes_verified']==c['message_bytes'] and
            c['untouched_sentinel_bytes_verified']==127 and c['early_ack_before_commit_observed']
            for c in cases), 'incomplete byte-readback/early-completion evidence')
    require(all(c['read_controller_used'] and c['done_after_ram_commit_checked']
        for c in records['control']['cases']), 'controller/commit ordering not tested')
    for key,count in (('buffer',7),('engine',8)):
        record=records[key]
        require(record['complete'] and len(record['tests'])==count and
            all(t['pass_test'] for t in record['tests'].values()), 'missing unit evidence: ' + key)
        check_hashes(record['source_sha256'],ROOT)
    require(records['buffer']['tests']['test_full_256k_capacity_four_64k_reads']['checked_bytes']==262144,
            'full protected capture extent not checked')
    ooc=records['ooc']
    require(ooc['pass_test'] and ooc['full_board_verified'] is False and
        ooc['target_period_ns']==4.0 and ooc['setup_wns_ns']>=0 and ooc['hold_whs_ns']>=0 and
        ooc['bram_primitives']==64, 'missing isolated physical probe')
    require(ooc['source_sha256']==digest(ROOT / 'rdma/read/rtl/rocev2_read_buffer.v'), 'different OOC buffer')
    for name,expected in ooc['artifacts_sha256'].items():
        require(digest(Path(name))==expected,'changed OOC artifact: ' + name)
    write=records['write']
    require(write['generated_rtl_sha256']==identity and write['pass_test'] and
        write['boundary']=='app' and write['message_bytes']==65 and write['wire_writes']==3 and
        write['wire_payload_bytes']==195 and write['wire_icrcs_valid'] and write['wire_ipv4_checksums_valid'] and
        write['initial_psn']==0xFFFFFE and write['ack_every']==2, 'missing WRITE app regression')
    for name,expected in write['source_sha256'].items():
        directory=ROOT / ('rdma/fpga' if name=='mqnic_app_block.v' else 'rdma/rtl')
        require(digest(directory / name)==expected,'stale WRITE source: ' + name)
    for field,name in (('test_sha256','rdma/hls/probe/test_control_transport.py'),
        ('axi_test_dependency_sha256','rdma/tests/test_control_rtl.py'),
        ('boundary_test_dependency_sha256','rdma/hls/probe/app_boundary.py')):
        require(digest(ROOT / name)==write[field],'stale WRITE test: ' + name)
    dependencies=[RESULTS / name for name in names.values()]+[Path(__file__),
        ROOT / 'rdma/read/Makefile',ROOT / 'rdma/read/README.md',ROOT / 'docs/ROCEV2_READ_PROGRESS.md',
        ROOT / 'rdma/logs/read-wire-buffer-engine-002.log',
        ROOT / 'rdma/logs/read-baseline-source-check-001.log',ROOT / 'rdma/logs/read-baseline-regression-001.log']
    report=dict(objective='READ機能を追加して。',goal_complete=False,hardware_verified=False,
        scope='Verified offline READ prototype only; not a combined board image or native READ result',
        staged_evidence_verified=True,generated_hls_sha256=identity,
        current_buffer_sha256=ooc['source_sha256'],read_unit_tests=19,legacy_unit_tests=73,
        protected_host_readback_sizes=[65,4097],standalone_full_buffer_bytes_verified=262144,
        isolated_buffer_setup_wns_ns=ooc['setup_wns_ns'],isolated_buffer_hold_whs_ns=ooc['hold_whs_ns'],
        completion_requirements=[
            dict(id=1,status='not achieved',missing='Actual native CX455A READ and REMOTE_READ peer'),
            dict(id=2,status='offline prototype only',missing='PCIe BAR readback, native per-run data, multi-op/wrap cases'),
            dict(id=3,status='offline protected RAM/controller tested',missing='Combined Ethernet ingress and exclusive BAR API'),
            dict(id=4,status='new-HLS legacy WRITE RTL regression only',missing='WRITE regression on new combined hardware image'),
            dict(id=5,status='isolated buffer OOC only',missing='Source-bound full-board image, full physical gates and CDC review'),
            dict(id=6,status='no hardware mutation this step',missing='Finite thermal-supervised SRAM native bringup')],
        next_action='Integrate exclusive versioned READ/WRITE BAR control, protected RAM and response-only Ethernet ingress',
        artifact_sha256={str(f.relative_to(ROOT)):digest(f) for f in dependencies})
    with args.report.open('x') as out:
        out.write(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='artifact_sha256'},indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
