#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual HLS + protected responder + real Corundum clients/RAM/backend.

The PCIe descriptor engine/host memory is explicitly a MODEL. No actual TLP
engine, live device, pinned pages or native host DMA is claimed by this probe.
The old direct memory-source/sink model is removed from the integrated path.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_protected_responder as probe
import test_corundum_dma_backend_rtl as dma_unit
from protected_sim import simulate


def bench():
    tb=probe.TB.replace('reg mr=0,wdr=0,rdv=0,rl=0,sv=0;reg [511:0] rd=0;reg [63:0] rk=0;',
                        'wire mr,wdr,rdv,rl,sv;wire [511:0] rd;wire [63:0] rk;')
    tb=tb.replace('reg [15:0] st=0;reg [7:0] se=0;','wire [15:0] st;wire [7:0] se;')
    old_driver=tb.split('always @(negedge clk) if(!rst) begin',1)[1].split('always @(posedge clk) if(!rst) begin',1)[0]
    tb=tb.replace('always @(negedge clk) if(!rst) begin'+old_driver,
        "always @(negedge clk) if(!rst) begin\n rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};tr=rng[8:6]!=0;\nend\n")
    # Keep front-end payload logging, but NO direct write to model host memory.
    tb=tb.replace('memory[offset+data_offset+lane]=wd[lane*8+:8];','')
    declarations=[];connections=[]
    mapped=dict(clk='clk',rst='rst',enable="1'b1",s_command_write='mw',s_command_address='ma',
                s_command_length='ml',s_command_tag='mt',s_command_valid='mv',
                s_axis_write_tdata='wd',s_axis_write_tkeep='wk',s_axis_write_tvalid='wdv',s_axis_write_tlast='wl',
                m_axis_read_tready='rr',m_status_ready='sr')
    aliases=dict(s_command_ready='mr',s_axis_write_tready='wdr',m_axis_read_tdata='rd',
                 m_axis_read_tkeep='rk',m_axis_read_tvalid='rdv',m_axis_read_tlast='rl',
                 m_status_tag='st',m_status_error='se',m_status_valid='sv')
    ports=dma_unit.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    for line in ports.splitlines():
        match=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
        if not match:continue
        declaration=match[2].rstrip(',');name=declaration.split()[-1]
        signal=mapped.get(name,'backend_fault' if name=='fault' else name)
        connections.append(f'.{name}({signal})')
        if name not in mapped:
            declarations.append(('reg ' if match[1]=='input' else 'wire ')+
                                declaration.replace(name,signal)+('=0;' if match[1]=='input' else ';'))
        if name in aliases:declarations.append(f'assign {aliases[name]}={signal};')
    header='''
localparam RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-6,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
'''+ '\n'.join(declarations)+'\nrocev2_corundum_dma_backend #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH)) backend('+','.join(connections)+');\n'
    model=dma_unit.TB.split('task dma_read_accept;',1)[1].split('task completion;',1)[0]
    model='task dma_read_accept;'+model
    names=('host posted pending_address pending_length posted_pending seed reads writes deadline issued_length issued_tag issued_address ram_address base_index start seg byte_index j k mask dma_read_accept dma_fill_ram read_status dma_write_post fence pattern').split()
    pattern=dma_unit.TB.split('function [7:0] pattern;',1)[1].split('endfunction',1)[0]
    pattern='function [7:0] pattern;'+pattern+'endfunction\n'
    model=model.replace('reads=reads+1;', 'reads=reads+1;$display("DMA_READ %h %d %d %d",issued_address,issued_length,ram_address,issued_tag);')
    model=model.replace('writes=writes+1;', 'writes=writes+1;$display("DMA_WRITE %h %d %d",m_dma_write_address,length,tag);')
    model=model.replace('repeat(25)', 'repeat(200)')
    model=model.replace('posted_pending=0;','posted_pending=0;$display("VISIBLE %h %d",pending_address,pending_length);')
    agent_header='''
reg [7:0] host[0:16383],posted[0:8191];reg [63:0] pending_address=0,issued_address=0;
reg posted_pending=0;reg [1:0] mask=0;
integer pending_length=0,seed=0,reads=0,writes=0,deadline,issued_length,issued_tag,ram_address,base_index,start,seg,byte_index,j,k;
'''
    model=agent_header+pattern+model
    for name in sorted(names,key=len,reverse=True):model=re.sub(r'\b'+name+r'\b','pcie_'+name,model)
    agent=r'''
integer pcie_init,pcie_active_length,pcie_active_tag,pcie_active_offset;
initial begin
 for(pcie_init=0;pcie_init<16384;pcie_init=pcie_init+1) pcie_host[pcie_init]=(pcie_init*37)^8'h5a;
 repeat(20) @(negedge clk);
 forever begin
  @(negedge clk);
  if(m_dma_write_valid) begin
   pcie_active_length=m_dma_write_length;pcie_active_tag=m_dma_write_tag;
   pcie_active_offset=m_dma_write_address-64'h8123456789abc000;
   pcie_dma_write_post(pcie_active_length,pcie_active_offset,pcie_active_tag,0);
   pcie_fence(pcie_active_offset,pcie_active_tag,0);
  end else if(m_dma_read_valid) begin
   pcie_active_length=m_dma_read_length;pcie_active_tag=m_dma_read_tag;
   pcie_active_offset=m_dma_read_address-64'h8123456789abc000;
   if(m_dma_read_ram_address!=0) $fatal(1,"unsolicited readback fence");
   pcie_dma_read_accept(pcie_active_length,0,pcie_active_tag,pcie_active_offset);
   pcie_dma_fill_ram;pcie_read_status(0,pcie_active_tag);
  end
 end
end
always @(posedge clk) if(!rst) begin
 if(backend_fault) $fatal(1,"backend fault %d",fault_code);
 if(sv && (!dma_drained || pcie_posted_pending)) $fatal(1,"backend completed before DMA/fence drain");
end
'''
    # The baseline transport helper already compiles axis_register.v.
    includes='\n'.join('`include "'+str(path)+'"' for path in dma_unit.SOURCES if path.name!='axis_register.v')+'\n'
    tb=includes+tb.replace('rocev2_protected_responder dut(',header+model+agent+'\nrocev2_protected_responder dut(',1)
    tb=tb.replace('if(deferred==0 || statuses!=commands || completed!=commands || fault)',
        'if(deferred==0 || statuses!=commands || completed!=commands || fault || command_count!=5 || fence_count!=2 || completion_count!=5 || pcie_reads!=5 || pcie_writes!=2)')
    return tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve prior evidence: choose fresh report path')
    extra=dma_unit.SOURCES+[Path(__file__),Path(dma_unit.__file__),probe.ROOT/'rdma/rnic/tests/protected_sim.py',Path(probe.__file__)]
    before={str(path.relative_to(probe.ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in extra}
    fixtures,body,cases=probe.stimulus()
    tb=bench().replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY','\n'.join(body))
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=150)
    after={str(path.relative_to(probe.ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in extra}
    if before!=after:raise ValueError('DMA integration source changed during test')
    identity['source_sha256'].update(after)
    print(output,flush=True)
    summaries=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    assert len(summaries)==1 and summaries[0]['pass_test']
    good=[c for c in cases if not c.get('expected_error') and not c.get('expected_integrity_drop')]
    frames=probe.rw_sim.ethernet_frames(output);assert len(frames)==len(good)==5
    responses=[]
    for case,packet in zip(good,frames):
        assert probe.rocev2_wire.internet_checksum(packet[:20])==0
        ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if case['operation']=='read':
            decoded=probe.read_wire.decode(ethernet)
            assert decoded['opcode']==probe.read_wire.ONLY and decoded['payload']==probe.PAYLOAD and decoded['syndrome']&0xe0==0
        else:
            decoded=probe.rocev2_wire.decode_ethernet(ethernet)
            assert decoded['opcode']==0x11 and decoded['icrc_valid'] and decoded['aeth_syndrome']&0xe0==0
        assert decoded['psn']==case['psn'] and decoded['destination_qpn']==196
        responses.append(dict(case=case['name'],ipv4_hex=packet.hex(),wire_checksums_verified=True))
    descriptors=[]
    for line in output.splitlines():
        if line.startswith(('DMA_READ ','DMA_WRITE ')):
            fields=line.split();descriptors.append(dict(kind=fields[0],address=f'0x{int(fields[1],16):016x}',
                length=int(fields[2]),ram_address=int(fields[3]) if fields[0]=='DMA_READ' else 0,tag=int(fields[-1])))
    assert len(descriptors)==7
    assert sum(d['kind']=='DMA_READ' and d['length']==1 and d['ram_address']==8128 for d in descriptors)==2
    assert all(int(d['address'],16)==probe.DMA+0x210 for d in descriptors)
    report=dict(scope='Actual HLS+MR protected responder+Corundum DMA clients/RAM/backend with DESCRIPTOR ENGINE MODEL',
        pass_test=True,hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,native_dma_verified=False,completion_claim=False,
        summary=summaries[0],cases=cases,responses=responses,dma_descriptors=descriptors,
        modeled_posted_visibility_fences=2,write_payload_bytes_checked_in_actual_staging_ram=130,read_payload_bytes_verified=195,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
