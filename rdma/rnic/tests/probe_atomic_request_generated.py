#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated full Atomic requester HLS/integrity RTL execution.

QP/connection, owner/SQ and peer/physical-memory endpoints are MODELS, NOT
actual PCIe/MR admission or protected result DMA/MAC/CQ/kernel/provider.
Check generated packed408/748/816 ABIs, whole IP/UDP/ICRC wire, AtomicACK
result bytes and stable exported offers. HLS done is NOT host visibility,
safe unpin or WR/CQ proof: native result-DMA lifetimes still must be joined.
Each execution <=30s. Fast two-state Verilator and optional four-state
Icarus are labeled independently. No hardware is opened or programmed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from probe_atomic_request_hls import ROOT,digest
import probe_atomic_responder as helper
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_request_bridge as bridge
sys.path.insert(0,str(ROOT/'rdma/host'))
import rocev2_wire as wire

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=0;always #2 clk=~clk;
// INSTANCE
// CONSTANTS
reg [144:0] response[0:7];
integer cycles=0,deadline,k,i,tx_frames=0,commands=0,results=0,completions=0;
reg [31:0] random_state=32'h76543210;
reg command_stalled=0,result_stalled=0,done_stalled=0;
reg [95:0] held_command;reg [576:0] held_result;reg [815:0] held_done;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>18000)$fatal(1,"bounded RTL deadline");
 if(w_request_fault || w_recv_fault || w_rnr_fault || w_integrity_overflow_count || w_tx_integrity_drop_count)
  $fatal(1,"actual core/integrity fault");
 if(w_m_axis_mem_read_cmd_tvalid)$fatal(1,"Atomic requester invented source DMA");
 if(command_stalled && (!w_m_axis_mem_write_cmd_tvalid || w_m_axis_mem_write_cmd_tdata!==held_command))
  $fatal(1,"held actual command retracted");
 if(result_stalled && (!w_m_axis_mem_write_tvalid || {w_m_axis_mem_write_tlast,w_m_axis_mem_write_tkeep,w_m_axis_mem_write_tdata}!==held_result))
  $fatal(1,"held actual result retracted");
 if(done_stalled && (!w_m_request_done_tvalid || w_m_request_done_tdata!==held_done))
  $fatal(1,"held actual core receipt retracted");
 command_stalled=w_m_axis_mem_write_cmd_tvalid&&!w_m_axis_mem_write_cmd_tready;
 result_stalled=w_m_axis_mem_write_tvalid&&!w_m_axis_mem_write_tready;
 done_stalled=w_m_request_done_tvalid&&!w_m_request_done_tready;
 held_command=w_m_axis_mem_write_cmd_tdata;
 held_result={w_m_axis_mem_write_tlast,w_m_axis_mem_write_tkeep,w_m_axis_mem_write_tdata};held_done=w_m_request_done_tdata;
 if(w_m_axis_mem_write_cmd_tvalid && w_m_axis_mem_write_cmd_tready)begin
  if(w_m_axis_mem_write_cmd_tdata!==EXPECTED_COMMAND)$fatal(1,"actual result command/provenance mismatch");
  commands=commands+1;
 end
 if(w_m_axis_mem_write_tvalid && w_m_axis_mem_write_tready)begin
  if(results>1 || w_m_axis_mem_write_tdata!=={448'd0,old_values[results]} ||
     w_m_axis_mem_write_tkeep!==64'hff || !w_m_axis_mem_write_tlast)$fatal(1,"actual LE8 result mismatch");
  $display("ATOMIC_REQUEST_RTL_RESULT %0128h",w_m_axis_mem_write_tdata);results=results+1;
 end
 if(w_m_request_done_tvalid && w_m_request_done_tready)begin
  if(completions>1 || w_m_request_done_tdata!==done_values[completions])$fatal(1,"actual full owner/PSN receipt mismatch");
  completions=completions+1;
 end
 if(w_m_axis_tx_tvalid && w_m_axis_tx_tready)begin
  $display("ATOMIC_REQUEST_RTL_OUT %032h %04h %0d",w_m_axis_tx_tdata,w_m_axis_tx_tkeep,w_m_axis_tx_tlast);
  if(w_m_axis_tx_tlast)tx_frames=tx_frames+1;
 end
end
always @(negedge clk)if(!rst)begin
 random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
 w_m_axis_tx_tready=random_state[2:0]!=0;
end
task input_response;
 input integer first;
 begin
  for(k=0;k<4;k=k+1)begin
   @(negedge clk);{w_s_axis_rx_tlast,w_s_axis_rx_tkeep,w_s_axis_rx_tdata}=response[first+k];w_s_axis_rx_tvalid=1;
   @(posedge clk);while(!w_s_axis_rx_tready)@(posedge clk);
  end
  @(negedge clk);w_s_axis_rx_tvalid=0;
 end
endtask
initial begin
 $readmemh("response.hex",response);rst=1;repeat(6)@(negedge clk);rst=0;
 w_local_ip_address={4{32'h020b12c6}};w_m_axis_ack_tready=1;w_m_axis_debug_tready=1;
 w_m_atomic_request_ready=1;w_m_atomic_done_ready=1;w_m_recv_done_tready=1;
 repeat(2100)@(negedge clk);
 w_s_axis_qp_tdata={32'd0,48'd0,24'h987654,24'hfffffe,24'd2,32'd3};w_s_axis_qp_tvalid=1;
 @(posedge clk);while(!w_s_axis_qp_tready)@(posedge clk);@(negedge clk);w_s_axis_qp_tvalid=0;
 deadline=cycles+2000;while(!w_m_axis_qp_apply_tvalid && cycles<deadline)@(negedge clk);
 if(!w_m_axis_qp_apply_tvalid || w_m_axis_qp_apply_tdata!=={8'd1,24'h987654,24'hfffffe,24'd2})$fatal(1,"actual QP apply receipt");
 w_m_axis_qp_apply_tready=1;@(negedge clk);w_m_axis_qp_apply_tready=0;
 w_s_axis_conn_tdata={16'd4791,{4{32'h010b12c6}},24'hf12347,16'd2};w_s_axis_conn_tvalid=1;
 @(posedge clk);while(!w_s_axis_conn_tready)@(posedge clk);@(negedge clk);w_s_axis_conn_tvalid=0;
 repeat(40)@(negedge clk);
 for(i=0;i<2;i=i+1)begin
  w_s_request_owner_tdata=owners[i];w_s_request_owner_tvalid=1;
  @(posedge clk);while(!w_s_request_owner_tready)@(posedge clk);@(negedge clk);w_s_request_owner_tvalid=0;
  w_s_axis_sq_tdata=sq_values[i];w_s_axis_sq_tvalid=1;
  @(posedge clk);while(!w_s_axis_sq_tready)@(posedge clk);@(negedge clk);w_s_axis_sq_tvalid=0;
  deadline=cycles+3000;while(tx_frames<i+1 && cycles<deadline)@(negedge clk);
  if(tx_frames!=i+1 || w_m_request_done_tvalid || commands!=i || results!=i)$fatal(1,"missing actual TX or premature result");
  input_response(i*4);
  // Exported result/command and core receipt are deliberately held. The
  // core receipt may be offered before physical placement: it is NOT CQ.
  repeat(32)@(negedge clk);
  deadline=cycles+2000;while(!w_m_axis_mem_write_cmd_tvalid && cycles<deadline)@(negedge clk);
  if(!w_m_axis_mem_write_cmd_tvalid || commands!=i || results!=i || completions!=i)
   $fatal(1,"missing held actual command cmd=%b/data=%b",w_m_axis_mem_write_cmd_tvalid,w_m_axis_mem_write_tvalid);
  // The real command producer can block until command handoff BEFORE
  // producing its data token. Model an ordered command-then-data sink.
  w_m_axis_mem_write_cmd_tready=1;
  deadline=cycles+2000;while((commands!=i+1 || !w_m_axis_mem_write_tvalid) && cycles<deadline)@(negedge clk);
  if(commands!=i+1 || !w_m_axis_mem_write_tvalid)$fatal(1,"actual command/data ordering failed");
  w_m_axis_mem_write_cmd_tready=0;repeat(32)@(negedge clk);
  if(results!=i || completions!=i || !w_m_axis_mem_write_tvalid)$fatal(1,"held result/receipt consumed early");
  w_m_axis_mem_write_tready=1;
  deadline=cycles+2000;while((commands!=i+1 || results!=i+1 || !w_m_request_done_tvalid) && cycles<deadline)@(negedge clk);
  if(commands!=i+1 || results!=i+1 || !w_m_request_done_tvalid)$fatal(1,"actual consumers failed progress");
  w_m_axis_mem_write_cmd_tready=0;w_m_axis_mem_write_tready=0;
  w_m_request_done_tready=1;@(negedge clk);w_m_request_done_tready=0;repeat(16)@(negedge clk);
  if(completions!=i+1)$fatal(1,"actual receipt not handed off");
 end
 if(w_rx_integrity_good_count!=2 || w_rx_integrity_drop_count || w_m_atomic_request_valid || w_m_recv_done_tvalid)
  $fatal(1,"wrong actual RX integrity/operation class");
 $display("ATOMIC_REQUEST_GENERATED {\"pass_test\":true,\"operations\":2,\"commands\":%0d,\"results\":%0d,\"core_receipts\":%0d,\"cycles\":%0d}",commands,results,completions,cycles);
 $finish;
end
endmodule
'''


def fixtures():
    constants="reg [747:0] owners[0:1];reg [407:0] sq_values[0:1];reg [815:0] done_values[0:1];reg [63:0] old_values[0:1];\ninitial begin\n"
    frames=[]
    for k,op in enumerate([7,8]):
        seq=k+1;psn=0xfffffe+k;compare=0xfedcba9876543210 if op==7 else 0;arg=0x8123456789abcdef+seq
        owner=3|(0x81234567<<20)|(0xe23456789abcd008<<52)|(0x210<<116)|(0xfedcba9876543210<<180)|\
            (8<<244)|(8<<276)|(1<<308)|(op<<324)|(seq<<340)|(17<<356)|(2<<372)|(0x9123456700000001<<396)|\
            (seq<<460)|((0xf123456789abc000+seq)<<524)|(compare<<620)|(arg<<684)
        params=0xfedcba9876543210|(0xe23456789abcd008<<64)|(8<<128)|(0x81234567<<160)
        sq=(19+k)|(2<<32)|(1<<42)|(1<<43)|(params<<48)|(1<<240)|(compare<<280)|(arg<<344)
        done=owner|(psn<<748)|(((psn+1)&0xffffff)<<772)|((19+k)<<796)
        old=0xfedcba9876543210^seq
        constants+=f"owners[{k}]=748'h{owner:0187x};sq_values[{k}]=408'h{sq:0102x};done_values[{k}]=816'h{done:0204x};old_values[{k}]=64'h{old:016x};\n"
        body=bytes([18,0x40])+struct.pack('!H',0xffff)+(2).to_bytes(4,'big')+psn.to_bytes(4,'big')+bytes([0x1f if k else 0])+bytes([0,0,1])+old.to_bytes(8,'big')
        ip=bytearray(struct.pack('!BBHHHBBH4s4s',0x45,0,56,0,0x4000,64,17,0,bytes([198,18,11,1]),bytes([198,18,11,2])))
        ip[10:12]=wire.internet_checksum(ip).to_bytes(2,'big')
        raw=bytes(ip)+struct.pack('!HHHH',49152,4791,36,0)+body+bytes(4);frames.append(raw[:-4]+wire.icrc_ipv4(raw))
    command=0xba9876543210|(8<<48)|(1<<76)|(1<<77)|(1<<79)|(12<<80)|(2<<84)|(2<<94)
    return constants+f"end\nlocalparam [95:0] EXPECTED_COMMAND=96'h{command:024x};\n",frames


def instance(path):
    # This bridge has a one-line parameter list followed by ') (', whereas
    # the older fixture helper requires ')(\n'. Parse only its ANSI header.
    header=path.read_text().split('\n);',1)[0];decl=[];connections=[]
    ports=helper.re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',header)
    if len(ports)<70 or len({n for _,_,n in ports})!=len(ports):raise ValueError('unexpected bridge interface')
    for direction,width,name in ports:
        signal=name if name in ['clk','rst']else 'w_'+name
        connections.append('.'+name+'('+signal+')')
        if name not in ['clk','rst']:
            decl.append(('reg 'if direction=='input'else'wire ')+(width or '')+signal+('=0;'if direction=='input'else';'))
    return '\n'.join(decl)+'\n'+path.stem+' network('+','.join(connections)+');\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--simulator',choices=['verilator','iverilog'],default='verilator');a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    build=json.loads(a.build_report.read_text())
    if not build.get('pass_test')or build.get('HLS_top')!='rocev2_native_atomic_request_top':p.error('matched completed HLS required')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM artifact1GiB guard')
    raw=ROOT/build['directory']/'project/solution1/syn/verilog'
    for n,h in build['generated_sha256'].items():
        if digest(raw/n)!=h:raise ValueError('changed generated HLS')
    run=Path(tempfile.mkdtemp(prefix='atomic-request-generated-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic-request-generated-',dir='/dev/shm'))
    wrapper=run/'rocev2_atomic_request_integrity_transport.v';wrapper.write_text(bridge.derive())
    inst=instance(wrapper)
    inst=bridge.once(inst,wrapper.stem+' network(',wrapper.stem+' #(.LEGACY_QP_KEY(0),.REQUEST_CQ_ENABLE(1),.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1)) network(')
    constants,frames=fixtures();(run/'tb.v').write_text(TB.replace('// INSTANCE',inst).replace('// CONSTANTS',constants))
    words=[]
    for frame in frames:
        for off in range(0,len(frame),16):
            data=frame[off:off+16];words.append(int.from_bytes(data.ljust(16,b'\0'),'little')|(((1<<len(data))-1)<<128)|(int(off+16>=len(frame))<<144))
    (run/'response.hex').write_text(''.join(f'{w:037x}\n'for w in words))
    axis=ROOT/'external/corundum/fpga/lib/axis/rtl';eth=ROOT/'external/corundum/fpga/lib/eth/rtl'
    sources=[*sorted(raw.glob('*.v')),wrapper,ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'rdma/rtl/rocev2_tx_padding.v',
        axis/'axis_adapter.v',axis/'axis_fifo.v',axis/'axis_register.v',eth/'lfsr.v']
    for f in raw.glob('*.dat'):shutil.copy2(f,run/f.name)
    own=[a.build_report.resolve(),Path(__file__).resolve(),Path(helper.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',
        ROOT/'rdma/rtl/rocev2_integrity_transport.v',*[Path(m.__file__).resolve()for m in [bridge,bridge.base,bridge.base.base,
            bridge.base.base.parent,bridge.base.base.parent.bridge,bridge.base.base.parent.bridge.legacy]],run/'tb.v',run/'response.hex']
    before={str(x.relative_to(ROOT)):digest(x)for x in [*sources,*raw.glob('*.dat'),*own]}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        actual_generated_HLS=True,four_state=a.simulator=='iverilog',simulator=a.simulator,
        native_integrated=False,hardware_verified=False,simulation_limit_seconds=30)
    print(json.dumps(dict(directory=report['directory'],phase='compile')),flush=True)
    try:
        if a.simulator=='iverilog':
            command=['iverilog','-g2012','-s','tb','-o',str(ram/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
            runtime=['vvp',str(ram/'test.vvp')];artifact=ram/'test.vvp'
        else:
            tool=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator')
            command=[str(tool),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','8',
                '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
                '-CFLAGS','-O0','--Mdir',str(ram/'obj'),str(run/'tb.v'),*map(str,sources)]
            runtime=[str(ram/'obj/Vtb')];artifact=ram/'obj/Vtb'
        report['compile_command']=command;env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        with(run/'compile.log').open('x')as log:
            c=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1200,env=env)
        report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise RuntimeError('generated requester compile: '+str(run/'compile.log'))
        report['RAM_artifact_sha256']={str(artifact):digest(artifact)}
        start=time.monotonic()
        try:
            with(run/'simulation.log').open('x')as log:
                r=subprocess.run(runtime,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30)
        finally:report['simulation_seconds']=time.monotonic()-start
        if r.returncode:raise RuntimeError('actual generated requester: '+str(run/'simulation.log'))
        output=(run/'simulation.log').read_text()
        rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ATOMIC_REQUEST_GENERATED ')]
        packets=[];buf=bytearray()
        for line in output.splitlines():
            if not line.startswith('ATOMIC_REQUEST_RTL_OUT '):continue
            _,data,keep,last=line.split();keep=int(keep,16);count=keep.bit_count()
            if not count or keep!=(1<<count)-1:raise ValueError('noncanonical actual wire keep')
            buf.extend(int(data,16).to_bytes(16,'little')[:count])
            if int(last):packets.append(bytes(buf));buf.clear()
        if len(rows)!=1 or not rows[0]['pass_test']or len(packets)!=2 or buf:raise ValueError('incomplete actual RTL assertions/wire')
        for k,pkt in enumerate(packets):
            body=bytes([19+k,0x40])+struct.pack('!H',0xffff)+(0xf12347).to_bytes(4,'big')+(0x80fffffe+k).to_bytes(4,'big')
            body+=struct.pack('!QIQQ',0xe23456789abcd008,0x81234567,0x8123456789abcdf0+k,0xfedcba9876543210 if k==0 else 0)
            if len(pkt)!=72 or pkt[0]!=0x45 or int.from_bytes(pkt[2:4],'big')!=72 or pkt[9]!=17 or \
               pkt[12:20]!=bytes([198,18,11,2,198,18,11,1])or pkt[28:-4]!=body or \
               wire.internet_checksum(pkt[:20])or pkt[-4:]!=wire.icrc_ipv4(pkt) or int.from_bytes(pkt[24:26],'big')!=52:
                raise ValueError('independent actual wire/ICRC oracle mismatch')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,summary=rows[0],actual_packets=[p.hex()for p in packets],independent_wire_ICRC_oracle=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
