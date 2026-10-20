#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual-HLS protected WRITE/READ boundary and PSN-wrap cases, offline.

Uses only the emitted, authorized 64-bit backend command to address modeled
memory. Not native evidence or a PCIe DMA implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path

import probe_protected_responder as probe
from protected_sim import simulate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve earlier evidence; choose a fresh report')
    fixtures=[];body=[];cases=[];psn=0xfffffe
    for length in (1,64,4096):
        payload=bytes((index*179 ^ index>>7 ^ length ^ 0xd3)&255 for index in range(length))
        for operation in ('write','read'):
            endpoint=dict(source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2,
                psn=psn,remote_address=probe.VA,rkey=8)
            if operation=='write':
                frame=probe.rocev2_wire.write_only_frame(**endpoint,payload=payload,
                    source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',udp_source_port=49152)
            else:frame=probe.read_wire.encode(**endpoint,opcode=probe.read_wire.REQUEST,read_bytes=length)
            parts=probe.words(frame[14:]);start=len(fixtures);fixtures.extend(parts)
            name=f'{operation}_{length}_psn_{psn:06x}'
            body.append(f'$display("CASE {name}");send_frame({start},{len(parts)});allow();')
            if operation=='write' and length<4096:
                # A wire pad MUST NOT overwrite the first byte after the MR
                # request extent. That byte has never previously been written.
                sentinel=((length*37)^0x5a)&255
                body.append(f'if(memory[{length}]!==8\'h{sentinel:02x}) $fatal(1,"wire padding overwrote guard byte");')
            cases.append(dict(name=name,operation=operation,length=length,psn=psn,
                              expected_payload_hex=payload.hex(),expected_payload_sha256=hashlib.sha256(payload).hexdigest()))
            psn=(psn+1)&0xffffff
    tb=probe.TB.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY','\n'.join(body))
    tb=tb.replace("cfg_rx_psn(24'h987654)","cfg_rx_psn(24'hfffffe)")
    tb=tb.replace('ml!=65','(ml<1 || ml>4096)')
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=180)
    print(output,flush=True)
    rows=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['commands']==6
    frames=probe.rw_sim.ethernet_frames(output)
    assert len(frames)==len(cases)
    for case,packet in zip(cases,frames):
        assert probe.rocev2_wire.internet_checksum(packet[:20])==0
        ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if case['operation']=='write':
            decoded=probe.rocev2_wire.decode_ethernet(ethernet)
            assert decoded['opcode']==0x11 and decoded['icrc_valid'] and decoded['aeth_syndrome']&0xe0==0
        else:
            decoded=probe.read_wire.decode(ethernet)
            actual=decoded['payload'];assert actual==bytes.fromhex(case['expected_payload_hex'])
            assert decoded['opcode']==probe.read_wire.ONLY and decoded['syndrome']&0xe0==0
            case['actual_payload_sha256']=hashlib.sha256(actual).hexdigest()
        assert decoded['psn']==case['psn'] and decoded['destination_qpn']==196
        case['response_ipv4_hex']=packet.hex();case['wire_checksums_verified']=True
        del case['expected_payload_hex']
    commands=[];write_frames=[];data=bytearray()
    for line in output.splitlines():
        if line.startswith('COMMAND '):
            _,kind,address,length,tag=line.split()
            commands.append(dict(write=kind=='1',address=f'0x{int(address,16):016x}',length=int(length),tag=int(tag)))
        if line.startswith('DATA '):
            _,last,keep,hex_data=line.split();part=bytes.fromhex(hex_data)
            assert int(keep,16)==(1<<len(part))-1;data.extend(part)
            if last=='1':write_frames.append(bytes(data));data.clear()
    assert not data and len(write_frames)==3 and len(commands)==6
    for actual,case in zip(write_frames,[c for c in cases if c['operation']=='write']):
        assert len(actual)==case['length'] and hashlib.sha256(actual).hexdigest()==case['expected_payload_sha256']
        case['actual_payload_sha256']=hashlib.sha256(actual).hexdigest()
    for command,case in zip(commands,cases):
        assert int(command['address'],16)==probe.DMA and command['length']==case['length']
        assert command['write']==(case['operation']=='write')
    report=dict(scope='Offline actual-HLS protected responder boundaries, one QP/single outstanding',
                hardware_verified=False,board_integrated=False,pci_dma_implemented=False,completion_claim=False,
                cases=cases,summary=rows[0],memory_commands=commands,
                write_bytes_verified=4161,read_bytes_verified=4161,psn_wrap_verified=True,pad_guard_bytes_verified=True,**identity)
    for name in ('rdma/rnic/tests/probe_protected_boundaries.py','rdma/rnic/tests/probe_protected_responder.py',
                 'rdma/rnic/tests/protected_sim.py','rdma/host/rocev2_wire.py','rdma/read/host/read_wire.py'):
        report['source_sha256'][name]=hashlib.sha256((probe.ROOT/name).read_bytes()).hexdigest()
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
