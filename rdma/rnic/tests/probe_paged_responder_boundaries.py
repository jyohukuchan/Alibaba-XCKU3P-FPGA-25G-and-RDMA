#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual HLS composite/paged DMA/RAM boundary cases, modeled PCIe/host only.

Finite1/64/4096B WRITE+READ, all bytes/host guards/physical pieces and PSN wrap.
No native DMA, actual user-page pins, board or provider claim.
"""
import argparse
import hashlib
import json
from pathlib import Path

import probe_protected_paged_dma as integration
from protected_sim import simulate

probe=integration.probe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve prior evidence: use fresh report')
    extra=[*integration.paged.SOURCES,Path(__file__),Path(integration.__file__),Path(probe.__file__),
        Path(integration.paged.__file__),probe.ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',
        probe.ROOT/'rdma/rnic/tests/protected_sim.py',probe.ROOT/'rdma/host/rocev2_wire.py',
        probe.ROOT/'rdma/read/host/read_wire.py']
    before={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    fixtures=[];body=[];cases=[];expected_descriptors=[];psn=0xfffffe;tag=1
    for length in (1,64,4096):
        payload=bytes((i*179 ^ i>>7 ^ length ^ 0xd3)&255 for i in range(length))
        for operation in ('write','read'):
            endpoint=dict(source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=2,
                psn=psn,remote_address=probe.VA,rkey=8)
            if operation=='write':frame=probe.rocev2_wire.write_only_frame(**endpoint,payload=payload,
                source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',udp_source_port=49152)
            else:frame=probe.read_wire.encode(**endpoint,opcode=probe.read_wire.REQUEST,read_bytes=length)
            parts=probe.words(frame[14:]);start=len(fixtures);fixtures.extend(parts)
            name=f'{operation}_{length}_psn_{psn:06x}'
            body.append(f'$display("CASE {name}");pcie_seed={length};send_frame({start},{len(parts)});allow();')
            cases.append(dict(name=name,operation=operation,length=length,psn=psn,
                payload_sha256=hashlib.sha256(payload).hexdigest(),payload=payload))
            ram=0
            while ram<length:
                linear=4093+ram;page=linear//4096;within=linear%4096;piece=min(length-ram,4096-within)
                dma=[0x8123456789abc000,0xfffffffffffff000][page]+within
                expected_descriptors.append(dict(write=operation=='write',address=f'0x{dma:016x}',length=piece,ram_address=ram,tag=tag))
                tag+=1;ram+=piece
            if operation=='write':
                expected_descriptors.append(dict(write=False,address='0x8123456789abcffd',length=1,ram_address=8128,tag=tag));tag+=1
            psn=(psn+1)&0xffffff
    tb=integration.composite_bench()
    tb=tb.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY','\n'.join(body))
    tb=tb.replace("cfg_rx_psn(24'h987654)","cfg_rx_psn(24'hfffffe)")
    tb=tb.replace('ml!=65','(ml<1 || ml>4096)').replace("mo!==64'h210","mo!==64'd0")
    tb=tb.replace('pcie_first=3565','pcie_first=4093').replace("12'd3565","12'd4093")
    tb=tb.replace('pcie_check<4158','pcie_check<4093+pcie_current_length')
    tb=tb.replace('expiry=cycle+2000','expiry=cycle+3500')
    tb=tb.replace('command_count!=5 || fence_count!=2 || completion_count!=5 || pcie_physical_reads!=8 || '
                  'pcie_physical_writes!=4 || pcie_write_bytes!=130 || pcie_last_tag!=12',
                  'command_count!=6 || fence_count!=3 || completion_count!=6 || pcie_physical_reads!=8 || '
                  'pcie_physical_writes!=5 || pcie_write_bytes!=4161 || pcie_last_tag!=13')
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=180)
    after={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if before!=after:raise ValueError('boundary probe inputs changed')
    identity['source_sha256'].update(after)
    print(output,flush=True)
    summaries=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    assert len(summaries)==1 and summaries[0]['pass_test'] and summaries[0]['completed']==6
    frames=probe.rw_sim.ethernet_frames(output);assert len(frames)==len(cases)==6
    for case,packet in zip(cases,frames):
        assert probe.rocev2_wire.internet_checksum(packet[:20])==0
        ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if case['operation']=='read':
            decoded=probe.read_wire.decode(ethernet)
            assert decoded['opcode']==probe.read_wire.ONLY and decoded['payload']==case['payload'] and decoded['syndrome']&0xe0==0
        else:
            decoded=probe.rocev2_wire.decode_ethernet(ethernet)
            assert decoded['opcode']==0x11 and decoded['icrc_valid'] and decoded['aeth_syndrome']&0xe0==0
        assert decoded['psn']==case['psn'] and decoded['destination_qpn']==196
        case['response_ipv4_hex']=packet.hex();case['wire_checksums_verified']=True
    descriptors=[];write_frames=[];data=bytearray()
    for line in output.splitlines():
        if line.startswith('PAGE_DMA '):
            _,write,address,length,ram,tag=line.split()
            descriptors.append(dict(write=int(write)==1,address=f'0x{int(address,16):016x}',length=int(length),ram_address=int(ram),tag=int(tag)))
        if line.startswith('DATA '):
            _,last,keep,hex_data=line.split();part=bytes.fromhex(hex_data)
            assert int(keep,16)==(1<<len(part))-1;data.extend(part)
            if last=='1':write_frames.append(bytes(data));data.clear()
    assert descriptors==expected_descriptors and len(descriptors)==13
    assert not data and write_frames==[c['payload'] for c in cases if c['operation']=='write']
    for case in cases:del case['payload']
    report=dict(scope='Actual HLS/paged responder/page table/splitter/Corundum staging, PCIe descriptor engine MODEL',
        pass_test=True,hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,native_dma_verified=False,
        runtime_pins_verified=False,completion_claim=False,cases=cases,summary=summaries[0],dma_descriptors=descriptors,
        first_user_page_offset=4093,remote_operation_offset=0,write_bytes_verified=4161,read_bytes_verified=4161,
        host_guard_bytes_checked_after_every_completion=True,psn_wrap_verified=True,pad_guard_bytes_verified=True,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
