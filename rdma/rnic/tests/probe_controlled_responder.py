#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual AXI mailbox/controller/HLS/guard/paged DMA/RAM end-to-end, offline.

Host AXI master, parent drain/PCIe descriptor engine/host memory are MODELED.
No raw config input is driven; private signals are observed, never forced.
No native DMA, kernel driver/device registration or user pins are claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_protected_paged_dma as integration
import test_control_regs_rtl as registers
from protected_sim import simulate

probe=integration.probe
TOP=probe.ROOT/'rdma/rnic/rtl/rocev2_controlled_responder.v'
CONTROL=probe.ROOT/'rdma/rnic/rtl/rocev2_mr_control.v'

HOST=r'''
integer axi_writes=0,axi_reads=0,host_next_sequence=1,host_pending_sequence=0,host_i,host_limit;
reg [31:0] host_words[0:20],host_value=0,host_reply[0:7];
localparam OWNER0=64'h1234567889abcdef,OWNER1=64'h1234567889abcdf0,OWNER2=64'h1234567889abcdf1;
// AXI_TASKS
task host_stage;
 input [7:0] op;input [63:0] owner;input [2:0] entry;input [31:0] key;
 input [15:0] pd;input [3:0] flags;input [7:0] page_index;input [63:0] dma;
 begin
  for(host_i=0;host_i<21;host_i=host_i+1) host_words[host_i]=0;
  host_pending_sequence=host_next_sequence;host_next_sequence=host_next_sequence+1;
  host_words[0]=host_pending_sequence;host_words[1]=op;host_words[2]=owner[31:0];host_words[3]=owner[63:32];
  host_words[4]=entry;host_words[5]=key;host_words[6]=pd;host_words[7]=flags;
  host_words[8]=32'h76543000;host_words[9]=32'hfedcba98;host_words[10]=4096;host_words[11]=3565;
  host_words[12]=page_index;host_words[13]=dma[31:0];host_words[14]=dma[63:32];
  host_words[15]=2;host_words[16]=196;host_words[17]=32'hc6120b02;host_words[18]=32'hc6120b01;
  host_words[19]=24'h987654;host_words[20]=24'hfffffe;
  for(host_i=0;host_i<21;host_i=host_i+1)
   write_reg(AS02_CTL_STAGE+host_i*4,host_words[host_i],15,host_i%3,(host_i+1)%3);
 end
endtask
task host_finish;
 input [7:0] op;input [63:0] owner;input [2:0] entry;input [31:0] expected_key;input [7:0] flags;
 begin
  write_reg(AS02_CTL_DOORBELL,1,15,0,1);
  host_limit=cycle+5000;host_value=0;
  while(!(host_value & AS02_ST_REPLY) && cycle<host_limit) begin
   read_reg(AS02_CTL_STATUS,host_value);
   if(host_value & (AS02_ST_FATAL | AS02_ST_MMIO_ERROR | AS02_ST_ENDPOINT_FAULT)) $fatal(1,"host control fault %h",host_value);
  end
  if(!(host_value & AS02_ST_REPLY) || !(host_value & AS02_ST_PAUSED)) $fatal(1,"unowned/missing host reply");
  for(host_i=0;host_i<8;host_i=host_i+1) read_reg(AS02_CTL_REPLY_SEQ+host_i*4,host_reply[host_i]);
  if(host_reply[0]!==host_pending_sequence || host_reply[1]!==op || {host_reply[3],host_reply[2]}!==owner ||
     host_reply[4]!==entry || host_reply[5]!==expected_key || host_reply[6]!==0 || host_reply[7]!==flags)
   $fatal(1,"host reply identity/proof mismatch op%d seq%d err%h flags%h key%h",op,host_pending_sequence,host_reply[6],host_reply[7],host_reply[5]);
  if(op==5 && completed!=3) $fatal(1,"invalidation proof preceded active memory/TX completion");
  $display("HOST_REPLY %0d %0d %h %0d %h %h",host_pending_sequence,op,owner,entry,expected_key,flags);
  write_reg(AS02_CTL_REPLY_ACK,host_pending_sequence,15,1,0);
  host_value=0;while(!(host_value & AS02_ST_READY)) read_reg(AS02_CTL_STATUS,host_value);
 end
endtask
task host_api;
 input [7:0] op;input [63:0] owner;input [2:0] entry;input [31:0] key;
 input [15:0] pd;input [3:0] access;input [7:0] index;input [63:0] dma;
 input [31:0] response_key;input [7:0] flags;
 begin host_stage(op,owner,entry,key,pd,access,index,dma);host_finish(op,owner,entry,response_key,flags);end
endtask
task host_pages;
 input [63:0] owner;input [2:0] entry;input [31:0] key;
 begin
  host_api(3,owner,entry,key,0,0,0,64'h8123456789abc000,key,0);
  host_api(3,owner,entry,key,0,0,1,64'hfffffffffffff000,key,0);
  if(!admission_pause) $fatal(1,"last page reopened admission before seal");
  host_api(4,owner,entry,key,0,0,0,0,key,16);
 end
endtask
'''


def bench():
    tb=integration.composite_bench()
    start=tb.index('rocev2_paged_responder dut(');end=tb.index(');',start)+2
    mapping=dict(re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end]))
    tb=tb[:start]+'// CONTROLLED_INSTANCE\n'+tb[end:]
    # These aliases inspect the actual private datapath ports. They do not
    # connect new external raw configuration drivers to the controlled top.
    tb=re.sub(r'(assign \w+=)dut\.',r'\1dut.endpoint.',tb)
    tb=tb.replace('reg admission_pause=1,pv=0,par=0;', 'wire admission_pause;reg pv=0,par=0;')
    declarations=['localparam AXIL_ADDR_WIDTH=12;']
    ports=TOP.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    connections=[]
    for line in ports.splitlines():
        m=re.match(r'\s*(input|output) wire (.*?)[,]?$',line)
        if not m:continue
        decl=m[2].rstrip(',');name=decl.split()[-1]
        signal=mapping.get(name,name)
        if name=='admission_paused':signal='admission_pause'
        if name not in mapping and name!='admission_paused':
            declarations.append(('reg ' if m[1]=='input' else 'wire ')+decl+('=0;' if m[1]=='input' else ';'))
        connections.append(f'.{name}({signal})')
    # Observed config replies are not TB-driven controller inputs.
    observed=dict(cr='cfg_mr_ready',cav='cfg_mr_response_valid',cak='cfg_mr_response_key',ce='cfg_mr_response_error',qr='cfg_qp_ready',
        cfg_ready='cfg_page_ready',cfg_response_error='cfg_page_response_error',cfg_response_key='cfg_page_response_key',cfg_response_valid='cfg_page_response_valid')
    declarations += [f'assign {name}=dut.endpoint.{field};' for name,field in observed.items()]
    # Old backend debug counters are now real controlled-top outputs; aliases
    # created by composite_bench still point at actual private memory signals.
    instance='\n'.join(declarations)+'\nrocev2_controlled_responder dut('+','.join(connections)+');\n'
    tb=tb.replace('// CONTROLLED_INSTANCE',instance)
    tasks=registers.TB.split('task write_reg;',1)[1].split('task stage;',1)[0]
    tasks='task write_reg;'+tasks
    tasks=re.sub(r'\bwrites\b','axi_writes',tasks);tasks=re.sub(r'\breads\b','axi_reads',tasks)
    abi=[]
    for name,value in re.findall(r'^#define (AS02_(?:CTL_\w+|ST_\w+)) (0x[0-9a-fA-F]+|\d+)U$',registers.HEADER.read_text(),re.M):
        abi.append(f"localparam {name}=32'h{int(value,0):x};")
    # Status macros use shifts; derive those constants from this same header.
    for name,bit in re.findall(r'^#define (AS02_ST_\w+) \(1U << (\d+)\)$',registers.HEADER.read_text(),re.M):
        abi.append(f"localparam {name}=32'h{1<<int(bit):x};")
    host='\n'.join(abi)+'\n'+HOST.replace('// AXI_TASKS',tasks)
    tb=tb.replace('reg [144:0] stimulus',host+'\nreg [144:0] stimulus',1)
    begin=tb.index(' configure_epoch(0);');end=tb.index(' // TEST_BODY',begin)
    setup=r'''
 parent_dma_drained=1;
 read_reg(AS02_CTL_ID,host_value);if(host_value!==AS02_CTL_ID_VALUE) $fatal(1,"wrong control ABI");
 read_reg(AS02_CTL_ABI,host_value);if(host_value!==AS02_CTL_ABI_VALUE) $fatal(1,"wrong control version");
 host_api(1,99,0,0,0,0,0,0,0,14);
 host_api(2,OWNER0,0,0,17,7,0,0,8,0);host_pages(OWNER0,0,8);
 host_api(2,OWNER1,1,0,18,7,0,0,9,0);host_pages(OWNER1,1,9);
 host_api(2,OWNER2,2,0,17,4,0,0,10,0);host_pages(OWNER2,2,10);
 host_api(6,100,0,0,17,0,0,0,0,0);
 host_api(7,101,0,0,0,0,0,0,0,0);
'''
    tb=tb[:begin]+setup+tb[end:]
    tb=tb.replace('cycle>18000','cycle>35000')
    extras=[TOP,CONTROL,registers.RTL,*registers.SOURCES[1:]]
    return '\n'.join('`include "'+str(p)+'"' for p in extras)+'\n'+tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():parser.error('preserve previous evidence: choose fresh report')
    extra=[TOP,CONTROL,*registers.SOURCES,registers.HEADER,*integration.paged.SOURCES,Path(__file__),
        Path(integration.__file__),Path(probe.__file__),Path(registers.__file__),probe.ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v']
    before={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    fixtures,body,cases=probe.stimulus();body='\n'.join(body)
    body=body.replace('$display("CASE valid_second_write");',
        'host_stage(5,OWNER0,0,8,0,0,0,0);$display("CASE valid_second_write");')
    begin=body.index('fork\n begin');end=body.index('configure_mr(0,17,7,16);',begin)+len('configure_mr(0,17,7,16);')
    body=body[:begin]+r'''
fork
 begin
  while(!mv) @(negedge clk);
  host_finish(5,OWNER0,0,8,3);
 end
 begin
  expiry=cycle+5000;while(completed==completed_before && cycle<expiry) @(negedge clk);
  if(completed!=completed_before+1) $fatal(1,"controller deadlocked active operation");
 end
join
host_api(2,OWNER0+3,0,0,17,7,0,0,16,0);host_pages(OWNER0+3,0,16);pcie_expected_key=16;
'''+body[end:]
    tb=bench().replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=180)
    after={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if before!=after:raise ValueError('controlled-top sources changed during probe')
    identity['source_sha256'].update(after);print(output,flush=True)
    rows=[json.loads(l[7:]) for l in output.splitlines() if l.startswith('RESULT ')]
    assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['completed']==5
    frames=probe.rw_sim.ethernet_frames(output);good=[c for c in cases if not c.get('expected_error') and not c.get('expected_integrity_drop')]
    assert len(frames)==len(good)==5
    responses=[]
    for case,packet in zip(good,frames):
        assert probe.rocev2_wire.internet_checksum(packet[:20])==0
        ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        if case['operation']=='read':
            d=probe.read_wire.decode(ethernet);assert d['opcode']==probe.read_wire.ONLY and d['payload']==probe.PAYLOAD and d['syndrome']&0xe0==0
        else:
            d=probe.rocev2_wire.decode_ethernet(ethernet);assert d['opcode']==0x11 and d['icrc_valid'] and d['aeth_syndrome']&0xe0==0
        assert d['psn']==case['psn'] and d['destination_qpn']==196
        responses.append(dict(case=case['name'],ipv4_hex=packet.hex(),wire_checksums_verified=True))
    replies=[]
    for l in output.splitlines():
        if l.startswith('HOST_REPLY '):
            _,seq,op,cookie,slot,key,flags=l.split();replies.append(dict(sequence=int(seq),command=int(op),cookie=f'0x{int(cookie,16):016x}',slot=int(slot),key=int(key,16),flags=int(flags,16)))
    assert len(replies)==20 and [r['sequence'] for r in replies]==list(range(1,21))
    assert sum(r['command']==5 and r['flags']==3 for r in replies)==1
    report=dict(scope='Actual AXI mailbox/controller/HLS/protected paged DMA/RAM; AXI host and PCIe/parent-drain MODELS',
        pass_test=True,hardware_verified=False,board_integrated=False,native_dma_verified=False,runtime_pins_verified=False,
        kernel_callbacks_executed=False,completion_claim=False,summary=rows[0],host_replies=replies,cases=cases,responses=responses,
        raw_config_ports_externally_driven=False,write_bytes_checked=130,read_bytes_checked=195,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
