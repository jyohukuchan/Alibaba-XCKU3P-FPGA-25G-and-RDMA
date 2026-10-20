#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual HLS/authorization/key-offset lease/paged backend/Corundum RAM.

PCIe descriptor engine, host memory and ordered visibility are MODELED.
No actual page pins, native PCIe DMA, kernel provider or board claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import probe_protected_responder as probe
import test_paged_memory_backend_rtl as paged
from protected_sim import simulate


def bench():
    tb=probe.TB.replace('reg mr=0,wdr=0,rdv=0,rl=0,sv=0;reg [511:0] rd=0;reg [63:0] rk=0;',
                        'wire mr,wdr,rdv,rl,sv;wire [511:0] rd;wire [63:0] rk;')
    tb=tb.replace('reg [15:0] st=0;reg [7:0] se=0;','wire [15:0] st;wire [7:0] se;')
    old=tb.split('always @(negedge clk) if(!rst) begin',1)[1].split('always @(posedge clk) if(!rst) begin',1)[0]
    tb=tb.replace('always @(negedge clk) if(!rst) begin'+old,
        'always @(negedge clk) if(!rst) begin\n rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};tr=rng[8:6]!=0;\nend\n')
    tb=tb.replace('memory[offset+data_offset+lane]=wd[lane*8+:8];','')
    declarations=[];connections=[]
    mapped=dict(clk='clk',rst='rst',enable="1'b1",s_command_write='mw',s_command_offset='mo',s_command_key='mk',
        s_command_length='ml',s_command_tag='mt',s_command_valid='mv',
        s_axis_write_tdata='wd',s_axis_write_tkeep='wk',s_axis_write_tvalid='wdv',s_axis_write_tlast='wl',
        m_axis_read_tready='rr',m_status_ready='sr',cfg_quiescent='quiet',
        cfg_command='pc',cfg_slot='pi',cfg_key='pk',cfg_length="32'd4096",cfg_first_offset="12'd3565",
        cfg_page_index='pp',cfg_dma_page='pa',cfg_valid='pv',cfg_response_ready='par')
    aliases=dict(s_command_ready='mr',s_axis_write_tready='wdr',m_axis_read_tdata='rd',
        m_axis_read_tkeep='rk',m_axis_read_tvalid='rdv',m_axis_read_tlast='rl',
        m_status_tag='st',m_status_error='se',m_status_valid='sv')
    ports=paged.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    for line in ports.splitlines():
        m=re.match(r'\s*(input|output) wire (.*?)[,]?$',line)
        if not m:continue
        declaration=m[2].rstrip(',');name=declaration.split()[-1]
        signal=mapped.get(name,'backend_fault' if name=='fault' else name)
        connections.append(f'.{name}({signal})')
        if name not in mapped:
            declarations.append(('reg ' if m[1]=='input' else 'wire ')+declaration.replace(name,signal)+('=0;' if m[1]=='input' else ';'))
        if name in aliases:declarations.append(f'assign {aliases[name]}={signal};')
    header='''
localparam RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
reg admission_pause=1,pv=0,par=0;reg [2:0] pc=0,pi=0;reg [31:0] pk=0;
reg [7:0] pp=0;reg [63:0] pa=0;wire [31:0] mk;wire [63:0] mo;
'''+ '\n'.join(declarations)+'\nrocev2_paged_memory_backend backend('+','.join(connections)+');\n'
    functions=paged.TB.split('function [63:0] dma_page;',1)[1].split('always @(negedge clk)',1)[0]
    tasks=paged.TB.split('task accept_descriptor;',1)[1].split('task completion;',1)[0]
    model='''
reg [7:0] host[0:16383],posted[0:16383];reg posted_valid[0:16383];
integer first=3565,seed=0,last_tag=0,current_length=0,current_offset=0,current_tag=0;
integer physical_reads=0,physical_writes=0,write_bytes=0;
integer deadline,amount,issued_tag,issued_len,ram_start,base_index,seg,k;
reg [63:0] issued_address=0;reg [1:0] mask=0;
'''+ 'function [63:0] dma_page;'+functions+'task accept_descriptor;'+tasks
    # Keep a deliberately long SIMULATED fence latency, not a wall-clock load
    # test. HLS must have a buffered ACK but cannot expose it before visibility.
    model=model.replace('repeat(17)','repeat(200)').replace('cycles','cycle')
    model=model.replace('issued_address=a;issued_len=l;ram_start=r;issued_tag=t;last_tag=t;',
        'issued_address=a;issued_len=l;ram_start=r;issued_tag=t;last_tag=t;'
        '$display("PAGE_DMA %0d %h %d %d %d",write_op,a,l,r,t);')
    names=('host posted posted_valid first seed last_tag current_length current_offset current_tag physical_reads physical_writes write_bytes '
           'deadline amount issued_tag issued_len ram_start base_index seg k issued_address mask dma_page host_index expected_dma '
           'pattern keep accept_descriptor fill_ram post_ram physical_status service_payload service_fence').split()
    for name in sorted(names,key=len,reverse=True):model=re.sub(r'\b'+name+r'\b','pcie_'+name,model)
    agent=r'''
integer pcie_init,pcie_check;reg [31:0] pcie_expected_key=8;
reg lease_stalled=0;reg [144:0] saved_lease;
always @(posedge clk) if(!rst) begin
 if(lease_stalled && (!mv || {mk,mo,mw,ml,mt}!==saved_lease)) $fatal(1,"authorized key/offset ownership");
 lease_stalled=mv&&!mr;saved_lease={mk,mo,mw,ml,mt};
 if(mv && mr) begin
  if(mk!==pcie_expected_key || mo!==64'h210) $fatal(1,"unbound authorized MR lease %h/%h",mk,mo);
  pcie_current_length=ml;pcie_current_offset=mo;pcie_current_tag=mt;
 end
 if(backend_fault) $fatal(1,"paged backend fault %d",fault_code);
 if(revoke_watch && (cfg_ready || cfg_response_valid)) $fatal(1,"PTE mutation before packet/TX drain");
 if(sv && !dma_drained) $fatal(1,"completion before DMA/RAM drain");
 if(sv && sr) for(pcie_check=0;pcie_check<16384;pcie_check=pcie_check+1) begin
  if(pcie_posted_valid[pcie_check]) $fatal(1,"completion before posted visibility");
  if(pcie_host[pcie_check]!==((pcie_check>=4093 && pcie_check<4158) ?
     pcie_pattern(pcie_check-4093) : (((pcie_check*37)^8'h5a)&255)))
   $fatal(1,"host payload/guard mismatch byte%d",pcie_check);
 end
end
initial begin
 for(pcie_init=0;pcie_init<16384;pcie_init=pcie_init+1) begin
  pcie_host[pcie_init]=(pcie_init*37)^8'h5a;pcie_posted_valid[pcie_init]=0;
 end
 repeat(20) @(negedge clk);
 forever begin
  @(negedge clk);
  if(m_dma_write_valid) begin pcie_service_payload(1,-1);pcie_service_fence(0);end
  else if(m_dma_read_valid) begin
   if(m_dma_read_ram_address==8128) $fatal(1,"unsolicited visibility fence");
   pcie_service_payload(0,-1);
  end
 end
end
task page_management;
 input [2:0] op,slot;input [31:0] key;input [7:0] index;
 begin
  if(!admission_pause) $fatal(1,"PTE update without admission freeze");
  @(negedge clk);pc=op;pi=slot;pk=key;pp=index;pa=pcie_dma_page(index);pv=1;par=0;
  @(posedge clk);while(!cfg_ready) @(posedge clk);
  @(negedge clk);pv=0;
  while(!cfg_response_valid) @(negedge clk);
  if(cfg_response_error!=0 || cfg_response_key!==key) $fatal(1,"PTE config failed");
  repeat(4) @(negedge clk);par=1;@(negedge clk);par=0;
 end
endtask
task publish_pages;
 input [2:0] slot;input [31:0] key;
 begin
  page_management(1,slot,key,0);page_management(2,slot,key,0);
  page_management(2,slot,key,1);page_management(3,slot,key,0);
 end
endtask
'''
    includes='\n'.join('`include "'+str(p)+'"' for p in paged.SOURCES if p.name!='axis_register.v')+'\n'
    tb=includes+tb.replace('rocev2_protected_responder dut(',header+model+agent+
        '\nrocev2_protected_responder #(.EXTERNAL_ADMISSION_CONTROL(1)) dut(\n .cfg_admission_pause(admission_pause),.m_memory_command_key(mk),.m_memory_command_offset(mo),',1)
    tb=tb.replace('configure_mr(0,17,7,8);configure_mr(1,18,7,9);configure_mr(2,17,4,10);',
        'configure_mr(0,17,7,8);configure_mr(1,18,7,9);configure_mr(2,17,4,10);'
        'publish_pages(0,8);publish_pages(1,9);publish_pages(2,10);')
    tb=tb.replace('while(!qready) @(negedge clk);','while(!qready) @(negedge clk);admission_pause=0;')
    tb=tb.replace('if(deferred==0 || statuses!=commands || completed!=commands || fault)',
        'if(deferred==0 || statuses!=commands || completed!=commands || fault || '
        'command_count!=5 || fence_count!=2 || completion_count!=5 || pcie_physical_reads!=8 || '
        'pcie_physical_writes!=4 || pcie_write_bytes!=130 || pcie_last_tag!=12)')
    return tb


def composite_bench():
    """Exercise the actual composite. Hierarchy is observed, NEVER forced.

    Internal command/stream aliases let the same independent monitors inspect
    the real guard/backend connection, not a testbench replacement connection.
    """
    tb=bench()
    old_backend=tb.split('rocev2_paged_memory_backend backend(',1)[1].split(');',1)[0]
    tb=tb.replace('rocev2_paged_memory_backend backend('+old_backend+');','')
    start=tb.index('rocev2_protected_responder #(.EXTERNAL_ADMISSION_CONTROL(1)) dut(')
    end=tb.index(');',start)+2
    old_guard=tb[start:end]
    guard_map=dict(re.findall(r'\.(\w+)\(([^()]*)\)',old_guard))
    # Debug aliases observe the actual private connection; they drive NO DUT
    # input. The composite sets MR contiguous base0; it never escapes to PCIe.
    observed=dict(mw='m_memory_command_write',ma='m_memory_command_address',mo='m_memory_command_offset',
        mk='m_memory_command_key',ml='m_memory_command_length',mt='m_memory_command_tag',mv='m_memory_command_valid',
        wd='m_axis_memory_write_tdata',wk='m_axis_memory_write_tkeep',wdv='m_axis_memory_write_tvalid',
        wl='m_axis_memory_write_tlast',rr='s_axis_memory_read_tready',sr='s_memory_status_ready',
        s_command_ready='m_memory_command_ready',s_axis_write_tready='m_axis_memory_write_tready',
        m_axis_read_tdata='s_axis_memory_read_tdata',m_axis_read_tkeep='s_axis_memory_read_tkeep',
        m_axis_read_tvalid='s_axis_memory_read_tvalid',m_axis_read_tlast='s_axis_memory_read_tlast',
        m_status_tag='s_memory_status_tag',m_status_error='s_memory_status_error',m_status_valid='s_memory_status_valid',
        backend_fault='backend_fault',fault_code='backend_fault_code',idle='backend_idle',dma_drained='backend_drained')
    page_map=dict(cfg_page_command='pc',cfg_page_slot='pi',cfg_page_key='pk',cfg_page_length="32'd4096",
        cfg_page_first_offset="12'd3565",cfg_page_page_index='pp',cfg_page_dma_page='pa',cfg_page_valid='pv',
        cfg_page_ready='cfg_ready',cfg_page_response_error='cfg_response_error',cfg_page_response_key='cfg_response_key',
        cfg_page_response_valid='cfg_response_valid',cfg_page_response_ready='par',memory_drained='')
    page_map.update({f'dma_{n}':n for n in ('command_count','fence_count','completion_count')})
    rtl=probe.ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v'
    ports=rtl.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    names=re.findall(r'^\s*(?:input|output) wire (?:\[[^\]]+\] )?(\w+),?$',ports,re.M)
    connections=[]
    for name in names:
        signal=page_map.get(name,guard_map.get(name,name))
        # Legacy probes deliberately leave the optional local client OFF.
        # Enabled-layer tests replace these explicit tie-offs with a real WQE
        # frontend; do not invent undeclared implicit nets in old fixtures.
        if name=='local_work_guard' or name.startswith('s_local_mr_request_') or name=='m_local_mr_response_ready':
            signal="'0" if name!='s_local_mr_request_ready' else ''
        elif name=='local_configuration_idle' or name.startswith('m_local_mr_response_'):
            signal=''
        elif name.startswith(('s_local_memory_command_','s_axis_local_memory_write_')):
            signal=''if name.endswith('ready')else "'0"
        elif name.startswith(('m_local_memory_status_','m_axis_local_memory_read_')):
            signal="'0"if name.endswith('ready')else ''
        elif name=='local_memory_busy':signal=''
        connections.append(f'.{name}({signal})')
    instance='rocev2_paged_responder dut('+','.join(connections)+');\n'
    instance+='\n'.join(f'assign {signal}=dut.{name};' for signal,name in observed.items())
    tb='`include "'+str(rtl)+'"\n'+tb[:start]+instance+tb[end:]
    tb=tb.replace("ma<64'h8123456789abc000 || ma+ml>64'h8123456789abd000", "ma+ml>64'd4096")
    tb=tb.replace("offset=ma-64'h8123456789abc000;",'offset=ma;')
    return tb


def failure_bench(kind):
    tb=composite_bench().replace('if(backend_fault) $fatal', 'if(backend_fault && !expect_fault) $fatal')
    tb=tb.replace('if(sv && sr) for(pcie_check=', 'if(sv && sr && !expect_fault) for(pcie_check=')
    # An error status is NOT a release proof: the paged backend deliberately
    # keeps dma_drained false on faults, including matching completed leaves.
    # Preserve the success-only drain assertion; explicitly forbid release in
    # the failure body instead of applying a success invariant to errors.
    tb=tb.replace('if(sv && !dma_drained)', 'if(sv && se==0 && !dma_drained)')
    if kind=='read':tb=tb.replace('pcie_service_payload(0,-1);','pcie_service_payload(0,1);')
    elif kind=='write':tb=tb.replace('pcie_service_payload(1,-1);pcie_service_fence(0);','pcie_service_payload(1,1);')
    elif kind=='fence':tb=tb.replace('pcie_service_fence(0);','pcie_service_fence(5);')
    else:raise ValueError(kind)
    return tb


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--composite',action='store_true',help='exercise actual rocev2_paged_responder wiring/config arbitration')
    parser.add_argument('--dma-error',choices=['read','write','fence'],help='actual HLS composite fail-closed finite case')
    args=parser.parse_args()
    if args.dma_error and not args.composite:parser.error('--dma-error requires --composite')
    if args.report.exists():parser.error('preserve prior evidence: use a fresh report')
    extra=[*paged.SOURCES,Path(__file__),Path(paged.__file__),Path(probe.__file__),probe.ROOT/'rdma/rnic/tests/protected_sim.py']
    if args.composite:extra.append(probe.ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v')
    before={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if args.dma_error:
        endpoint=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
            destination_qpn=2,psn=probe.PSN,remote_address=probe.VA+0x210,rkey=8)
        frame=(probe.read_wire.encode(**endpoint,opcode=probe.read_wire.REQUEST,read_bytes=65) if args.dma_error=='read'
               else probe.rocev2_wire.write_only_frame(**endpoint,payload=probe.PAYLOAD))
        fixtures=probe.words(frame[14:]);cases=[dict(name='partial_dma_'+args.dma_error,operation='read' if args.dma_error=='read' else 'write')]
        body='''
expect_fault=1;send_frame(0,FRAME_COUNT);
expiry=cycle+3000;while(!dut.guard_fault && cycle<expiry) @(negedge clk);
if(!dut.guard_fault || fc!=34 || completed || txframes || commands!=1 || statuses!=1 || accepted!=1 || se!=EXPECTED_ERROR)
 $fatal(1,"DMA error failed to reach guarded completion");
repeat(200) @(negedge clk);
if(tv || mv || wdv || rr || sr || quiet || cr || cfg_ready || dut.memory_drained || completed || txframes)
 $fatal(1,"DMA failure released lease or exposed success");
$display("RESULT {\\"pass_test\\":true,\\"guard_fault\\":%0d,\\"commands\\":%0d,\\"statuses\\":%0d,\\"completed\\":%0d,\\"tx_frames\\":%0d,\\"page_release_proof\\":false}",fc,commands,statuses,completed,txframes);
$finish;
'''.replace('FRAME_COUNT',str(len(fixtures))).replace('EXPECTED_ERROR','5' if args.dma_error=='fence' else '4')
        tb=failure_bench(args.dma_error)
    else:
        fixtures,body,cases=probe.stimulus()
        body='\n'.join(body).replace('ci=0;cp=17;cc=2;ck=8;cv=1;', 'admission_pause=1;ci=0;cp=17;cc=2;ck=8;cv=1;')
        body=body.replace('configure_mr(0,17,7,16);',
            'page_management(4,0,8,0);configure_mr(0,17,7,16);publish_pages(0,16);pcie_expected_key=16;admission_pause=0;')
        tb=composite_bench() if args.composite else bench()
    tb=tb.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
    output,identity=simulate(tb,{'input.hex':fixtures},args.hls_build,wall_timeout=150)
    after={str(p.relative_to(probe.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    if before!=after:raise ValueError('paged integration sources changed')
    identity['source_sha256'].update(after)
    print(output,flush=True)
    summaries=[json.loads(line[7:]) for line in output.splitlines() if line.startswith('RESULT ')]
    assert len(summaries)==1 and summaries[0]['pass_test']
    if args.dma_error:
        assert not probe.rw_sim.ethernet_frames(output)
        assert summaries[0]['guard_fault']==34 and summaries[0]['completed']==summaries[0]['tx_frames']==0
        assert summaries[0]['commands']==summaries[0]['statuses']==1 and not summaries[0]['page_release_proof']
        report=dict(scope='Actual HLS composite DMA-failure zero-drain/commit gate; PCIe descriptor engine MODEL',
            pass_test=True,hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,native_dma_verified=False,
            runtime_pins_verified=False,completion_claim=False,composite_top=True,dma_error=args.dma_error,
            summary=summaries[0],cases=cases,successful_wire_responses=0,**identity)
        with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));return
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
        if line.startswith('PAGE_DMA '):
            _,write,address,length,ram,tag=line.split()
            descriptors.append(dict(write=int(write)==1,dma_address=f'0x{int(address,16):016x}',length=int(length),ram_address=int(ram),tag=int(tag)))
    assert len(descriptors)==12 and [d['tag'] for d in descriptors]==list(range(1,13))
    assert sum(d['write'] for d in descriptors)==4
    assert sum(d['ram_address']==8128 for d in descriptors)==2
    assert all(d['dma_address'] in ['0x8123456789abcffd','0xfffffffffffff000'] for d in descriptors)
    assert all((d['length'],d['ram_address']) in [(3,0),(62,3),(1,8128)] for d in descriptors)
    report=dict(scope='Actual HLS/guard/authorized key+offset/page table/splitter/backend/Corundum RAM; DESCRIPTOR ENGINE MODEL',
        pass_test=True,hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,native_dma_verified=False,
        runtime_pins_verified=False,completion_claim=False,composite_top=args.composite,summary=summaries[0],cases=cases,responses=responses,
        dma_descriptors=descriptors,user_first_page_offset=3565,remote_operation_offset=528,
        write_bytes_checked_in_actual_staging_ram=130,read_wire_bytes_verified=195,**identity)
    with args.report.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
