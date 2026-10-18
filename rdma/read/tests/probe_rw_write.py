#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Existing WRITE byte/ACK/guard test on the actual NEW combined RW board app."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import rw_sim
ROOT=rw_sim.ROOT
sys.path.insert(0,str(ROOT / 'rdma/hls/probe'))
import test_control_transport as old
import app_boundary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--message-bytes',type=int,default=65)
    parser.add_argument('--count',type=int,default=3)
    parser.add_argument('--initial-psn',type=lambda s:int(s,0),default=0xFFFFFE)
    parser.add_argument('--ack-every',type=int,choices=(1,2),default=2)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists() or not 1<=args.message_bytes<=4096 or not 1<=args.count<=32:
        parser.error('new report and valid finite sizes/count required')
    acks,after=[],[]
    for sequence in range(args.count):
        if (sequence+1)%args.ack_every and sequence!=args.count-1:continue
        ack=bytearray(old.CX_ACK)
        ack[47:50]=(2).to_bytes(3,'big')
        ack[51:54]=((args.initial_psn+sequence)&0xFFFFFF).to_bytes(3,'big')
        ack[54:58]=bytes([0x1F])+(sequence+1).to_bytes(3,'big')
        ack[-4:]=old.icrc_ipv4(ack[14:])
        acks.extend(old.words(bytes(ack)));after.append(sequence+1)
    tasks=old.CONTROL_TB[old.CONTROL_TB.index('task write_reg;'):old.CONTROL_TB.index('\ninitial begin')]
    tb=app_boundary.make_tb(old.TB.replace('AXIL_TASKS',tasks),'app')
    for name,value in dict(MESSAGE_BYTES=args.message_bytes,MESSAGE_COUNT=args.count,
        TOTAL_BYTES=args.message_bytes*args.count,INITIAL_PSN=args.initial_psn,ACK_WORDS=len(acks),ACK_FRAMES=len(after)).items():
        tb=tb.replace(name,str(value))
    output,identity=rw_sim.simulate(tb,{'acks.hex':acks,'ack_after.hex':after},args.hls_build)
    print(output,flush=True)
    frames=rw_sim.ethernet_frames(output)
    if len(frames)!=args.count:raise ValueError('wrong WRITE count')
    for index,frame in enumerate(frames):
        decoded=old.decode_ethernet(frame)
        start=index*args.message_bytes
        payload=bytes(((i*131)^(i>>8)^0x5A)&255 for i in range(start,start+args.message_bytes))
        if frame[:14]!=bytes.fromhex('b8830367c5d08af3fbb975310800') or decoded['opcode']!=10 or \
           decoded['destination_qpn']!=0xABCDEF or decoded['psn']!=((args.initial_psn+index)&0xFFFFFF) or \
           decoded['rkey']!='0xfedcba98' or int(decoded['remote_address'],0)!=0xFEDCBA9876543210+start or \
           decoded['dma_length']!=args.message_bytes or decoded['payload_bytes']!=args.message_bytes or \
           not decoded['icrc_valid'] or old.internet_checksum(frame[14:34])!=0 or frame[70:70+args.message_bytes]!=payload:
            raise ValueError('new RW app changed WRITE semantics: '+repr(decoded))
    rows=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    if len(rows)!=1:raise ValueError('missing completed WRITE result')
    dependencies=[Path(__file__),Path(rw_sim.__file__),Path(old.__file__),Path(app_boundary.__file__),
        ROOT / 'rdma/tests/test_control_rtl.py',ROOT / 'rdma/host/rocev2_wire.py',ROOT / 'rdma/tests/test_icrc_rtl.py']
    identity['source_sha256'].update({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dependencies})
    report=dict(scope='Actual combined RW board-app/HLS RTL WRITE; not hardware',hardware_verified=False,
        pass_test=True,**rows[0],**identity,message_bytes=args.message_bytes,message_count=args.count,
        initial_psn=args.initial_psn,ack_every=args.ack_every,all_wire_bytes_checked=True,
        wire_icrcs_valid=True,wire_ipv4_checksums_valid=True,physical_mac_completion_modeled=True,
        physical_mac_drain_verified=False,boundary='combined-rw-app')
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
