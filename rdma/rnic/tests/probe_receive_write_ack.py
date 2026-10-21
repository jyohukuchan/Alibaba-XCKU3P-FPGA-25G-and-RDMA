#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Shared real ACK allocator, distinct WRITE424/RQ620, real MAC/FCS/SFD/CDC.

WRITE receipts/ACK bodies replay exact checked actual HLS C++8193-byte
traces, not a live generated-HLS instance. Native owner admission, memory
visibility, HLS/whole-CQ producers and retirement consumers are MODELS.
Actual MAC clocks/PTP/physical pins are modeled; its FIFO/XGMII/FCS/SFD/tag
and receipt CDC execute real RTL. No native/DMA/Linux/timing/physical proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import atomic_mac_wire_fixture as physical
import probe_receive_message_ack as old_message
import test_receive_ack_rtl as old_packet
import probe_segmented_write_rx_frontend as crc
from probe_segmented_write_owned_hls import verify_packet_receipts

ROOT=old_message.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_receive_write_ack as candidate

MODES=list(range(11))+list(range(20,67))


def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def traces():
    p=ROOT/'results/2026-10-18/rocev2-rnic-segmented-write-owned-hls-001.json'
    r=json.loads(p.read_text());out={};paths=[p]
    if not r['pass_test'] or not r['source_unchanged']:raise ValueError('actual87-mode HLS trace required')
    for mode in ['write-rx','write-rx-imm']:
        log=ROOT/r['directory']/(mode+'.log');paths.append(log);text=log.read_text()
        if digest(log)!=r['artifact_sha256'][str(log.relative_to(ROOT))]:raise ValueError('actual HLS log changed')
        verify_packet_receipts(text)
        receipts=[];acks=[]
        for s in text.splitlines():
            v=s.split()
            if s.startswith('WRITE_PACKET_RECEIPT ')and v[1]=='8193':
                total,off,psn,msn=map(int,v[1:5]);token=int(v[5],16)
                receipts.append(dict(total=total,offset=off,psn=psn,msn=msn,token=token,receipt=token|(msn<<424)))
            if s.startswith('WRITE_RECEIVE_ACK ')and v[2]=='8193':acks.append(bytes.fromhex(v[4]))
        if len(receipts)!=3 or len(acks)!=3:raise ValueError('exact three packet trace required')
        for v,b in zip(receipts,acks):
            if int.from_bytes(b[9:12],'big')!=v['psn']or int.from_bytes(b[13:16],'big')!=v['msn']:
                raise ValueError('actual HLS ACK and typed receipt disagree')
            v['ACK_body']=b.hex()
        out[mode]=receipts
    return out,paths


def bench(text):
    ports=old_message.re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',
        text.split(')(\n',1)[1].split('\n);',1)[0])
    wired={'m_axis_tready','s_cpl_tag','s_cpl_ts','s_cpl_valid'}
    decl='\n'.join(('wire 'if d=='output'or n in wired else'reg ')+(w or'')+n+
        ('=0;'if d=='input'and n not in wired else';')for d,w,n in ports)
    return r'''
`timescale 1ns/1ps
module tb;
localparam IMMEDIATE_ENABLE=1;
'''+decl+r'''
rocev2_receive_write_ack_tx #(.TAG_SEQUENCE_WIDTH(3),.IMMEDIATE_ENABLE(1)) dut(.*);
'''+physical.LINK+r'''
reg real_mac=0,tx_gate=0,receipt_gate=0,model_cpl_valid=0;
reg [15:0] model_cpl_tag=0;reg [95:0] model_cpl_ts=96'h123456789abcdef;
assign link_s_data=m_axis_tdata;assign link_s_keep=m_axis_tkeep;
assign link_s_valid=real_mac && tx_gate && m_axis_tvalid;assign link_s_last=m_axis_tlast;assign link_s_user=m_axis_tuser;
assign m_axis_tready=tx_gate && (!real_mac || link_s_ready);
assign s_cpl_tag=real_mac ? link_m_cpl_tag:model_cpl_tag;
assign s_cpl_ts=real_mac ? link_m_cpl_ts:model_cpl_ts;
assign s_cpl_valid=real_mac ? link_m_cpl_valid && receipt_gate:model_cpl_valid;
assign link_m_cpl_ready=real_mac && receipt_gate && s_cpl_ready;
always #2 clk=~clk;
integer mode=0,cycle=0,i,j,k,deadline,next_tag=1,frames=0,cpls=0,wr_dones=0,rq_dones=0;
integer last_cpl=-10000,last_eof=-10000,operations=0;
reg allow_fault=0,expect_held=0;
reg [127:0] words[0:3];reg [455:0] write_records[0:2];
reg [423:0] token=0;reg [455:0] core=0;
reg [619:0] rq=0;reg [751:0] rq_core=0;
reg [160:0] stalled_word;reg [471:0] stalled_write;reg [767:0] stalled_rq;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded component deadline");
 if(fault && !allow_fault)$fatal(1,"shared ACK fault mode%0d code%h",mode,fault_code);
 if(m_axis_tvalid && m_axis_tready && m_axis_tlast)begin frames=frames+1;last_eof=cycle;end
 if(s_cpl_valid && s_cpl_ready)begin cpls=cpls+1;last_cpl=cycle;end
 if(m_write_done_valid || m_done_valid)begin
  if(cycle-last_cpl<1024 || cycle-last_eof<1024)$fatal(1,"receipt or EOF1024 tail gate omitted");
 end
 if(m_write_done_valid && m_write_done_ready)wr_dones=wr_dones+1;
 if(m_done_valid && m_done_ready)rq_dones=rq_dones+1;
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task route;
 begin local_mac=48'h8af3fbb97531;peer_mac=48'hb8830367c5d0;
 local_ip=32'hc6120b02;peer_ip=32'hc6120b01;peer_qpn=196;end
endtask
task choose;
 input integer n;
 begin
  core=write_records[n];token=core[423:0];
  rq=620'hRQC;
  if(mode==2)begin rq[307:276]=0;rq[275:116]=0;end
  rq_core={8'd0,8'd3,32'h89abcdef,core[447:424],4'd0,token[39:16],token[71:40],rq};
  if(n==0)$readmemh("write0.hex",words);else if(n==1)$readmemh("write1.hex",words);else $readmemh("write2.hex",words);
 end
endtask
task bind_write;
 input integer notify;
 begin
  route;s_write_owner=token;s_write_owner_notify=notify;s_write_owner_rq_context=notify ? rq:620'd0;
  s_write_owner_valid=1;s_core_valid=0;
  @(posedge clk);if(!s_write_owner_ready || queue_guard!==8'h04)$fatal(1,"WRITE admission/guard");
  @(negedge clk);s_write_owner_valid=0;expect_held=1;
  s_write_owner=0;s_write_owner_rq_context=0;s_write_owner_notify=0;
  local_mac=0;peer_mac=0;local_ip=0;peer_ip=0;peer_qpn=0;
  if(!busy || queue_guard!==8'h04 || dut.write_owner!==token || dut.owner!==(notify ? rq:620'd0))
   $fatal(1,"separate snapshot identity / fabricated RQ");
 end
endtask
task offer_core;
 begin s_write_core_data=core;s_write_core_valid=1;
 @(posedge clk);if(!s_write_core_ready)$fatal(1,"typed HLS receipt ready");
 @(negedge clk);s_write_core_valid=0;s_write_core_data=0;end
endtask
task capture;
 begin
  for(i=0;i<4;i=i+1)begin
   s_axis_tdata=words[i];s_axis_tkeep=i==3 ? 16'h3fff:16'hffff;s_axis_tlast=i==3;
   if(mode==50 && i==2)s_axis_tkeep=16'h7fff;
   if(mode==51 && i==2)s_axis_tlast=1;
   s_axis_tuser={16'h4000,1'b0};s_axis_tvalid=1;
   @(posedge clk);if(!s_axis_tready && !fault)$fatal(1,"actual ACK capture");
   @(negedge clk);s_axis_tvalid=0;if(fault)i=4;
  end
 end
endtask
task blocked;
 input integer count;
 begin repeat(count)begin tick;if(m_done_valid || m_write_done_valid || !busy)$fatal(1,"missing real consumer/EOF/receipt/tail");end end
endtask
task manual_receipt;
 input [15:0] tag;
 begin
  model_cpl_tag=tag;model_cpl_valid=1;m_cpl_ready=0;
  repeat(7)begin tick;if(s_cpl_ready || !m_cpl_valid || m_cpl_tag!==16'h4000 || m_cpl_ts!==model_cpl_ts)
   $fatal(1,"exact live CPL translation under stall");end
  m_cpl_ready=1;@(posedge clk);if(!s_cpl_ready)$fatal(1,"manual boundary CPL acceptance");
  @(negedge clk);model_cpl_valid=0;
 end
endtask
task send_wire;
 begin
  deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"actual typed/header join missing");tick;end
  stalled_word={m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser};
  repeat(17)begin tick;if(!m_axis_tvalid || {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser}!==stalled_word)
   $fatal(1,"actual ACK beat/tag changed under stall");end
  for(i=0;i<4;i=i+1)begin
   tx_gate=1;@(posedge clk);while(!m_axis_tready)@(posedge clk);
   if(!m_axis_tvalid || m_axis_tdata!==words[i] || m_axis_tkeep!==(i==3 ? 16'h3fff:16'hffff) ||
      m_axis_tlast!==(i==3) || m_axis_tuser!=={16'h6000+next_tag[15:0],1'b0})$fatal(1,"wire byte/KEEP/EOF/single tag sequence");
   @(negedge clk);tx_gate=0;
   if(mode==4 && i==0)begin manual_receipt(16'h6000+next_tag[15:0]);blocked(1100);end
  end
  if(mode!=4)begin
   blocked(1100);
   if(real_mac)begin
    if(!link_m_cpl_valid || actual_SFD_count!=next_tag)$fatal(1,"actual MAC SFD/CDC pending receipt absent");
    m_cpl_ready=0;receipt_gate=1;repeat(7)begin tick;if(s_cpl_ready || !m_cpl_valid || m_cpl_tag!==16'h4000)
     $fatal(1,"real receipt FIFO stall/translation");end
    m_cpl_ready=1;deadline=cycle+50;while(cpls<next_tag)begin if(cycle>deadline)$fatal(1,"real MAC receipt not accepted");tick;end
    receipt_gate=0;
   end else manual_receipt(16'h6000+next_tag[15:0]);
   blocked(900);
  end
 end
endtask
task await_done;
 input integer write_op,notify;
 begin
  deadline=cycle+1200;
  while(!(write_op ? m_write_done_valid:m_done_valid))begin if(cycle>deadline)$fatal(1,"actual EOF/SFD/tail completion missing");tick;end
  if(write_op && (m_write_done_data!=={16'h6000+next_tag[15:0],core} || m_done_valid!==notify))
   $fatal(1,"independent424/456 proof, no fake RQ");
  if((!write_op || notify) && m_done_data!=={16'h6000+next_tag[15:0],rq_core})$fatal(1,"full real620/752 proof");
  stalled_write=m_write_done_data;stalled_rq=m_done_data;
  repeat(17)begin tick;if(!busy || write_op && (!m_write_done_valid || m_write_done_data!==stalled_write) ||
   (!write_op || notify) && (!m_done_valid || m_done_data!==stalled_rq))$fatal(1,"independent completion backpressure");end
 end
endtask
task retire;
 input integer write_op,notify;
 begin
  s_write_retire_token=token;s_retire_context=rq;
  if(write_op && notify)begin
   if(mode==8)begin
    m_write_done_ready=1;tick;m_write_done_ready=0;
    repeat(11)begin tick;if(m_write_done_valid || !m_done_valid || !busy || s_write_retire_ready || s_retire_ready)
     $fatal(1,"WRITE completion accepted must retain independent RQ");end
    m_done_ready=1;tick;m_done_ready=0;
   end else begin
    m_done_ready=1;tick;m_done_ready=0;
    repeat(11)begin tick;if(m_done_valid || !m_write_done_valid || !busy || s_write_retire_ready || s_retire_ready)
     $fatal(1,"RQ completion accepted must retain independent WRITE");end
    m_write_done_ready=1;tick;m_write_done_ready=0;
   end
   s_write_retire_valid=1;
   repeat(11)begin tick;if(!busy || s_write_retire_valid && s_write_retire_ready || s_retire_valid && s_retire_ready)
    $fatal(1,"WRITE retired without real RQ retire");end
   s_write_retire_valid=0;s_retire_valid=1;
   repeat(11)begin tick;if(!busy || s_write_retire_valid && s_write_retire_ready || s_retire_valid && s_retire_ready)
    $fatal(1,"RQ retired without WRITE retire");end
   s_write_retire_valid=1;
  end else if(write_op)begin m_write_done_ready=1;tick;m_write_done_ready=0;s_write_retire_valid=1;end
  else begin m_done_ready=1;tick;m_done_ready=0;s_retire_valid=1;end
  @(posedge clk);if(write_op ? !s_write_retire_ready:!s_retire_ready)$fatal(1,"exact packet retirement missing");
  @(negedge clk);s_write_retire_valid=0;s_retire_valid=0;s_core_valid=0;expect_held=0;
  if(busy || queue_guard || m_done_valid || m_write_done_valid)$fatal(1,"packet slot not released");
  operations=operations+1;next_tag=next_tag+1;
 end
endtask
task write_operation;
 input integer n,notify;
 begin
  choose(n);bind_write(notify);capture;blocked(37);offer_core;
  if(notify)begin blocked(37);s_core_data=rq_core;s_core_valid=1;end
  send_wire;await_done(1,notify);retire(1,notify);
 end
endtask
task recv_operation;
 begin
  rq=620'hRQC;rq_core={8'd0,8'd0,32'd0,24'd7,4'd0,24'h987654,32'd65,rq};
  $readmemh("recv.hex",words);route;s_owner_context=rq;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready || queue_guard!==8'h04)$fatal(1,"legacy owner admission");
  @(negedge clk);s_owner_valid=0;expect_held=1;capture;blocked(37);s_core_data=rq_core;s_core_valid=1;
  send_wire;await_done(0,0);retire(0,0);
 end
endtask
task quarantine;
 begin
  repeat(17)tick;
  if(!fault || !busy || queue_guard!==8'hff || m_done_valid || m_write_done_valid ||
     expect_held && !dut.held || s_write_retire_ready || s_retire_ready)$fatal(1,"bad owner/proof released/falsely completed");
 end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))$fatal(1,"mode required");real_mac=mode==5;
 allow_fault=mode>=20;rst=1;$readmemh("write-proofs.hex",write_records);
 repeat(5)@(negedge clk);rst=0;prior_response_drained=1;route;
 if(mode<=10)begin
  if(mode==3 || mode==5)recv_operation;
  if(mode==6)begin
   for(k=0;k<7;k=k+1)begin if(k%2)recv_operation;else write_operation(0,0);end
   if(!tags_exhausted || active_tag!==16'h6007)$fatal(1,"shared sequence exhaustion missing");
   s_write_owner_valid=1;repeat(17)begin tick;if(s_owner_ready || s_write_owner_ready || busy || fault)
    $fatal(1,"nonwrapping tag exhaustion");end s_write_owner_valid=0;
  end else begin
   if(mode==7)begin
    choose(0);s_write_owner=token;s_write_owner_valid=1;prior_response_drained=0;
    repeat(17)begin tick;if(s_write_owner_ready || busy || fault)$fatal(1,"fake prior drain");end
    prior_response_drained=1'bx;repeat(17)begin tick;if(s_write_owner_ready || busy || fault)$fatal(1,"unknown prior drain");end
    s_write_owner_valid=0;prior_response_drained=1;
   end
   if(mode==9)begin
    choose(2);bind_write(1);capture;offer_core;s_core_data=rq_core;s_core_valid=1;
    send_wire;await_done(1,1);
    s_write_retire_token=token;s_retire_context=rq;s_write_retire_valid=1;s_retire_valid=1;
    repeat(17)begin tick;if(!busy || s_write_retire_ready || s_retire_ready)$fatal(1,"early matching VALID retired before proof acceptance");end
    s_write_retire_valid=0;s_retire_valid=0;retire(1,1);
   end else begin
    if(mode==10)begin
     for(j=0;j<5;j=j+1)begin
      model_cpl_tag=j==0 ? 16'h0001:j==1 ? 16'h2001:j==2 ? 16'h4000:j==3 ? 16'h4001:16'h8001;
      s_axis_tdata=128'h12345678;s_axis_tkeep=16'hffff;s_axis_tlast=1;
      s_axis_tuser={model_cpl_tag,1'b0};s_axis_tvalid=1;tx_gate=1;
      @(posedge clk);if(!s_axis_tready || !m_axis_tvalid || m_axis_tdata!==s_axis_tdata || m_axis_tuser!==s_axis_tuser)
       $fatal(1,"other tag classes lost passthrough");
      @(negedge clk);s_axis_tvalid=0;tx_gate=0;
      model_cpl_valid=1;m_cpl_ready=1;@(posedge clk);
      if(!s_cpl_ready || !m_cpl_valid || m_cpl_tag!==model_cpl_tag)$fatal(1,"other CPL class stolen");
      @(negedge clk);model_cpl_valid=0;
     end
     frames=0;cpls=0;last_cpl=-10000;last_eof=-10000;
    end
    for(k=0;k<3;k=k+1)write_operation(k,k==2 && (mode==1 || mode==2 || mode==5 || mode==8));
   end
  end
  if(mode==3 || mode==5)recv_operation;
  if(fault || busy || frame_count!=operations || receipt_count!=operations || wr_dones+rq_dones<operations)
   $fatal(1,"complete shared packet counters");
 end else begin
  choose(mode>=35 && mode<=41 || mode>=55 ? 2:0);
  case(mode)
   20:token[423:400]=24'h800002;
   21:token[399:384]=0;
   22:token[383:320]=0;
   23:token[319:256]=0;
   24:token[255:224]=0;
   25:token[15:0]=0;
   26:token[159:128]=4096;
   27:token[159:128]=1048577;
   28:token[223:160]=64'hfffffffffffffff0;
   29:token[72]=1;
   30:token[71:40]=0;
   31:token[71:40]=4097;
   32:token[103:72]=32'hfffff000;
   33:token[71:40]=4095;
   34:token[16]=~token[16];
   35:begin choose(0);end
   37:rq[356]=~rq[356];
   38:rq[396]=~rq[396];
   39:rq[372]=~rq[372];
   40:rq[339:324]=1;
   41:begin rq[307:276]=0;rq[244]=1;end
   42:token[320]=1'bx;
   64:begin rq[307:276]=17;rq[243:180]=64'hfffffffffffffff0;end
   65:rq[396]=1'bx;
  endcase
  if(mode<=43 || mode>=64)begin
   route;if(mode==66)peer_ip[31]=1'bx;
   s_write_owner=token;s_write_owner_notify=(mode>=35 && mode<=41 && mode!=36)||mode==64||mode==65;
   s_write_owner_rq_context=(s_write_owner_notify || mode==36) ? rq:620'd0;
   if(mode==43)s_owner_valid=1;
   s_write_owner_valid=1;tick;s_write_owner_valid=0;s_owner_valid=0;quarantine;
   if(frame_count || receipt_count || dut.held)$fatal(1,"bad admission used tag/owner");
  end else begin
   bind_write(mode>=55 && mode<=61);
   if(mode==44)core[320]=~core[320];
   if(mode==45)core[448]=1;
   if(mode==46)core[256]=1'bx;
   if(mode==63)core[424]=~core[424];
   if(mode==47)words[3][24]=~words[3][24];
   if(mode==48)words[3][56]=~words[3][56];
   if(mode==49)words[0][0]=~words[0][0];
   if(mode==54)begin model_cpl_tag=16'h6001;model_cpl_valid=1;m_cpl_ready=1;tick;model_cpl_valid=0;end
   else begin
    capture;
    if(!fault)begin
     offer_core;
     if(mode>=55 && mode<=61)begin
      if(mode==57)rq_core[680]=~rq_core[680];
      if(mode==58)rq_core[652]=~rq_core[652];
      if(mode==59)rq_core[620]=~rq_core[620];
      if(mode==60)rq_core[396]=~rq_core[396];
      if(mode==61)rq_core[743:736]=1;
      s_core_data=rq_core;s_core_valid=1;
     end
     if(mode==52 || mode==53 || mode==55 || mode==56 || mode==62)begin
      if(mode==52)begin
       deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"SEND missing before stale tag");tick;end
       tx_gate=1;tick;tx_gate=0;model_cpl_tag=16'h6002;model_cpl_valid=1;m_cpl_ready=1;tick;model_cpl_valid=0;
      end else begin
       send_wire;
       if(mode==53)begin model_cpl_tag=16'h6001;model_cpl_valid=1;tick;model_cpl_valid=0;end
       if(mode==55 || mode==56)begin
        await_done(1,1);
        if(mode==55)begin s_write_retire_token=token^424'd1;s_write_retire_valid=1;end
        else begin s_retire_context=rq^620'd1;s_retire_valid=1;end
       end
       if(mode==62)parent_fault=1;
      end
     end
    end
   end
   quarantine;
  end
 end
 $display("SHARED_ACK_RESULT {\"pass_test\":true,\"mode\":%0d,\"fault\":%0d,\"operations\":%0d,\"frames\":%0d,\"receipts\":%0d,\"WRITE_proofs\":%0d,\"RQ_proofs\":%0d,\"actual_SFDs\":%0d,\"cycles\":%0d}",
 mode,fault,operations,frame_count,receipt_count,wr_dones,rq_dones,actual_SFD_count,cycle);
 $finish;
end
endmodule
'''.replace('RQC',old_packet.context(qpn=2).split("'h")[1])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    run=Path(tempfile.mkdtemp(prefix='receive-write-ack-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-write-ack-',dir='/dev/shm'))
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),candidate.ACK,
        Path(old_message.__file__).resolve(),old_message.QUEUE,Path(old_packet.__file__).resolve(),
        Path(physical.__file__).resolve(),Path(crc.__file__).resolve(),*physical.SOURCES,
        *sorted((ROOT/'rdma/rnic/fpga').glob('derive_*.py'))]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        tests={},legacy_tests={},planned_modes=MODES,compile_limit_seconds=10,runtime_limit_seconds=10,
        clock_ns=4,MAC_clock_ns=2.56,cycle_limit=100000,actual_shared_class6000_allocator=True,
        full_WRITE424_and_RQ620_distinct=True,actual_ACK_capture_EOF_receipt_1024_tail=True,
        actual_MAC_FIFO_XGMII_FCS_SFD_receipt_CDC=True,generated_HLS_live=False,full_native_integration=False,
        native_DMA_or_visibility=False,live_Linux=False,hardware_verified=False)
    try:
        trace,paths=traces();result['actual_HLS_trace_sha256']={str(n.relative_to(ROOT)):digest(n)for n in paths}
        text=candidate.derive();(run/(candidate.NAME+'.v')).write_text(text)
        (run/'lfsr_constant_masks.v').write_text(crc.compiletime_lfsr())
        (run/'tb.v').write_text(bench(text));(run/'rocev2_receive_message_queue.v').write_text(old_message.QUEUE.read_text())
        (run/'write-proofs.hex').write_text(''.join(f'{v["receipt"]:0114x}\n'for v in trace['write-rx']))
        _,_,_,packet=old_message.native.case(True,True)
        frames=[]
        for i,v in enumerate(trace['write-rx']):
            b=bytearray(packet);b[28:-4]=bytes.fromhex(v['ACK_body']);b=old_message.native.qp.main.response.repair(b)
            f=bytes.fromhex('b8830367c5d08af3fbb975310800')+b;frames.append(f)
            (run/f'write{i}.hex').write_text(''.join(f'{int.from_bytes(f[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(f),16)))
        def ackfile(name,psn,msn):
            b=bytearray(packet);b[37:40]=psn.to_bytes(3,'big');b[41:44]=msn.to_bytes(3,'big')
            f=bytes.fromhex('b8830367c5d08af3fbb975310800')+old_message.native.qp.main.response.repair(b)
            (run/name).write_text(''.join(f'{int.from_bytes(f[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(f),16)))
            return f
        recv_frame=ackfile('recv.hex',0x987654,7)
        for seq in [1,2]:ackfile(f'ack{seq}.hex',0x987653+seq,seq)
        for k in range(3):ackfile(f'ack{k}.message.hex',(0xfffffe+k)&0xffffff,1 if k==2 else 0)
        old=old_packet.bench()
        # Only adapt the interface declaration to this EXACT new module. All
        # old stimulus/6000 tags/byte/receipt/tail/retirement assertions remain.
        a0=old.index('reg clk=');b0=old.index('rocev2_receive_ack_tx #(',a0)
        ports=old_message.re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',text.split(')(\n',1)[1].split('\n);',1)[0])
        declarations='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports)+'\n'
        old=old[:a0]+declarations+old[b0:]
        old=old.replace('rocev2_receive_ack_tx #(',candidate.NAME+' #(',1)
        (run/'legacy-packet.v').write_text(old)
        old=old_message.bench(text).replace('rocev2_receive_ack_tx #(',candidate.NAME+' #(',1)
        # Message fixture names clash with the independent packet fixture;
        # change only filenames, not data/handshakes/assertions/deadlines.
        for k in range(3):old=old.replace(f'"ack{k}.hex"',f'"ack{k}.message.hex"')
        (run/'legacy-message.v').write_text(old)
        for name in ['legacy-packet','legacy-message','shared']:
            sources=[run/('tb.v'if name=='shared'else name+'.v'),run/(candidate.NAME+'.v')]
            if name=='legacy-message':sources.append(run/'rocev2_receive_message_queue.v')
            if name=='shared':sources +=[run/'lfsr_constant_masks.v'if n.name=='lfsr.v'else n for n in physical.SOURCES]
            cmd=['iverilog','-g2012','-s','tb','-o',str(ram/name),*map(str,sources)]
            start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr)
            result[name+'_compile_seconds']=time.monotonic()-start
            if c.returncode:raise ValueError('compile failed:'+name)
            modes=MODES if name=='shared'else[None]
            for mode in modes:
                label=name if mode is None else str(mode)
                start=time.monotonic();c=subprocess.run(['vvp',str(ram/name),*([f'+MODE={mode}']if mode is not None else[])],cwd=run,capture_output=True,text=True,timeout=10)
                (run/(label+'.log')).write_text(c.stdout+c.stderr)
                item=dict(exit=c.returncode,seconds=time.monotonic()-start)
                (result['legacy_tests']if mode is None else result['tests'])[label]=item
                if c.returncode:raise ValueError('simulation failed:'+label)
                marker='SHARED_ACK_RESULT 'if mode is not None else'RECEIVE_ACK_RESULT 'if name=='legacy-packet'else'MESSAGE_ACK_RESULT '
                rows=[json.loads(s[len(marker):])for s in c.stdout.splitlines()if s.startswith(marker)]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing full assertions:'+label)
                item['summary']=rows[0]
                if mode==5:
                    actual=physical.frames(c.stdout);expected=[recv_frame,*frames,recv_frame]
                    if actual!=[(0x6001+i,f)for i,f in enumerate(expected)]:raise ValueError('actual whole XGMII/SFD/FCS/bytes/shared tags differ')
                    item['actual_MAC_all5_frames_FCS_SFD_tags_bytes_verified']=True
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during run')
        result.update(pass_test=True,source_unchanged=True,actual_HLS_trace_replay_only=trace,
            simulation_LFSR_masks_exact_prior_proof='results/2026-10-18/rocev2-rnic-CRC-constant-masks-001.json')
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),legacy=len(result['legacy_tests']),max_seconds=max(v['seconds']for v in result['tests'].values()),actual_MAC_frames=5)),flush=True)


if __name__=='__main__':main()
