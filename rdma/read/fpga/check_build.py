#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fail-closed combined RW build-input gate; not board/hardware signoff."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
RESULTS=ROOT / 'results/2026-10-18'
sys.path.insert(0,str(ROOT / 'rdma/read/hls'))
import check_sources

# Exact immutable native25 gates/clock/board inputs of accepted WRITE003.
# New RW builds reuse these files, not relaxed copies of the physical gate.
PHYSICAL_INPUTS={
 'fpga/fpga_as02mc04_25g_cdc.v':'c437ba26ac31e2ffb9c91cde79993abec1a6056bbdccd654c74fc159917d1ae4',
 'fpga/as02mc04.xdc':'42c93205cbd427c15d779d08ab7e80babbd21768215bd4ba5fbe0afce62c2235',
 'fpga/vio_status_cdc.xdc':'757673b0f768b7fee9cd2fad795e3d03c3260455feba785a2f1edf7af9164a8c',
 'fpga/mac_flow_control_cdc.xdc':'1a2191369820a9232779e078b21afd4afdc5c6426b92f0778f393584dbda4f26',
 'fpga/config_25g.tcl':'6125aea101659836701591c892c68b734d1897136418e8b81074f833c9f50d83',
 'fpga/implement_25g.tcl':'be777468a90ce2b4f9b1744a1ba68f91346c9ef43ea8f5179ffa7e506512128b',
 'fpga/write_verified_25g_eco.tcl':'20e9551ec978ca03bc01c713a5691268f6571359b1ea49e0304694569602bc83',
 'fpga/verify_vio_status_cdc.tcl':'6f67f8faa58c8c12bb72e523cc571a489c958819057a9fcbc88e29ed9f2deb3a',
 'fpga/verify_mac_flow_control_cdc.tcl':'d850262ff5194420e76e8a05f5030321114e429ff8aa5b3e67164a22d0154bbc'}


def require(value,message):
    if not value:raise ValueError(message)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check_hashes(mapping,directory=ROOT):
    for name,value in mapping.items():require(digest(directory / name)==value,'stale input: '+name)


def validate_app(record,kind):
    require(record['hardware_verified'] is False and record['pass_test'],'not a passing offline '+str(kind))
    require(record['physical_mac_completion_modeled'] and record['physical_mac_drain_verified'] is False,
            'model/hardware scope mislabeled')
    if kind=='write':
        require(record['message_bytes']==65 and record['message_count']==3 and record['initial_psn']==0xFFFFFE and
            record['ack_every']==2 and record['wire_writes']==3 and record['wire_payload_bytes']==195 and
            record['all_wire_bytes_checked'] and record['wire_icrcs_valid'] and record['wire_ipv4_checksums_valid'],
            'missing WRITE tail/wrap/cumulative ACK regression')
    elif kind=='warm':
        require(record['warm_runs']==2 and record['message_bytes']==4097 and record['same_qp_and_psn_reused'] and
            record['distinct_payloads'] and len(set(record['payload_sha256']))==2 and
            record['stale_read_first_discarded']==1 and record['host_frame_preserved_under_backpressure'] and
            record['host_bar_readback_bytes_verified']==8194,'missing actual HLS warm/stale/host regression')
    else:
        require(record['message_bytes']==kind and record['message_count']==3 and
            record['initial_psn']==0xFFFFFE and record['host_bar_readback_bytes_verified']==kind*3 and
            record['prior_payload_complement_prefilled'] and record['protected_ram_used'] and record['version2_bar_used'] and
            record['done_after_ram_commit_checked'] and record['rtl_tx_guard_used'] and
            record['all_request_bytes_checked'] and record['wire_icrcs_valid'] and record['wire_ipv4_checksums_valid'],
            'incomplete combined-app READ data/protection regression')


def verify(hls_build,fns_source):
    inputs={Path(__file__),ROOT / 'rdma/read/hls/check_sources.py'}
    check_hashes(PHYSICAL_INPUTS)
    inputs.update(ROOT / name for name in PHYSICAL_INPUTS)
    source_path=RESULTS / 'rocev2-read-hls-source-001.json'
    source=json.loads(source_path.read_text())
    require(source['pass_test'] and source['hardware_verified'] is False and
        source['upstream_commit']==check_sources.COMMIT,'wrong source provenance')
    require(check_sources.verify(fns_source)==source['source_sha256'],'changed upstream/patch source')
    check_hashes(source['profile_sha256'])
    inputs.add(source_path)
    inputs.update(fns_source / name for name in source['source_sha256'])
    inputs.update(ROOT / name for name in source['profile_sha256'])
    rtl=hls_build / 'solution1/syn/verilog'
    generated=sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')])
    aggregate=hashlib.sha256()
    for path in generated:aggregate.update(path.name.encode()+b'\0'+path.read_bytes())
    identity=aggregate.hexdigest()
    require(len(generated)==138 and identity==source['generated_hls_sha256'],'unexpected generated HLS')
    inputs.update(generated)
    for name,count in [('rocev2-read-buffer-rtl-004.json',7),('rocev2-read-engine-rtl-002.json',8),
                       ('rocev2-rw-control-rtl-001.json',5),('rocev2-rw-ingress-rtl-001.json',2),
                       ('rocev2-rw-build-gate-002.json',5)]:
        path=RESULTS / name;record=json.loads(path.read_text());inputs.add(path)
        require(record['complete'] and record['hardware_verified'] is False and len(record['tests'])==count and
            all(t['pass_test'] for t in record['tests'].values()),'missing RW control/ingress tests')
        check_hashes(record['source_sha256']);inputs.update(ROOT / n for n in record['source_sha256'])
        if name=='rocev2-read-buffer-rtl-004.json':
            require(record['tests']['test_full_256k_capacity_four_64k_reads']['checked_bytes']==262144,
                    'missing full capture-extent byte readback')
    path=RESULTS / 'rocev2-read-hls-probe-001.json';wire=json.loads(path.read_text());inputs.add(path)
    require(wire['complete'] and wire['hardware_verified'] is False and wire['generated_hls_sha256']==identity and
        [c['message_bytes'] for c in wire['cases']]==[1,2,3,4,63,64,65,4095,4096,4097,8192,8193,65536] and
        all(c['pass_test'] and c['original_requested_bytes_verified'] for c in wire['cases']),
        'missing actual HLS READ byte/tail/segmentation regression')
    check_hashes(wire['source_sha256']);inputs.update(ROOT / n for n in wire['source_sha256'])
    for name,kind in [('rocev2-rw-write-app-001.json','write'),('rocev2-rw-read-app-003.json',65),
                      ('rocev2-rw-read-app-002.json',4097),('rocev2-rw-warm-app-001.json','warm')]:
        path=RESULTS / name;record=json.loads(path.read_text());inputs.add(path)
        validate_app(record,kind)
        require(record['generated_hls_sha256']==identity,'mixed actual-app/HLS builds')
        check_hashes(record['source_sha256']);inputs.update(ROOT / n for n in record['source_sha256'])
    path=RESULTS / 'rocev2-rw-timer-rtl-002.json';timer=json.loads(path.read_text());inputs.add(path)
    require(timer['hardware_verified'] is False and timer['pass_test'] and timer['core_clock_ps']==4000 and
        timer['max_qps']==8 and timer['timer_table_storage']=='registers' and timer['warm_reset_checked'] and
        timer['ack_restart_scan_phases_checked']==8 and timer['stop_restart_phases_checked']==8 and
        timer['ack_stop_checked'] and timer['retry_output_backpressure_checked'] and
        timer['first_retry_min_clocks']>=250000 and timer['first_retry_max_clocks']<=250128 and
        timer['generated_rtl_sha256']==identity,'missing unchanged real1ms timer regression')
    timer_test=ROOT / 'rdma/hls/probe/test_timer_rtl.py'
    require(digest(timer_test)==timer['test_sha256'],'changed timer test');inputs.add(timer_test)
    return sorted(inputs),identity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--fns-source',type=Path,required=True)
    parser.add_argument('--list-inputs',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    inputs,identity=verify(args.hls_build.resolve(),args.fns_source.resolve())
    report=dict(scope='RW functional RTL/source preflight; not full-board physical or native hardware signoff',
        hardware_verified=False,full_board_verified=False,pass_test=True,generated_hls_sha256=identity,
        immutable_native25_gate_inputs_verified=True,combined_read_write_app_verified_in_rtl=True,
        actual_hls_warm_stale_and_host_routing_verified=True,
        input_sha256={str(f):digest(f) for f in inputs})
    if args.report:
        with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    if args.list_inputs:print('\n'.join(map(str,inputs)))
    else:print(json.dumps({k:v for k,v in report.items() if k!='input_sha256'},indent=2))


if __name__=='__main__':main()
