#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual message RQ + fresh-tag ACK capture/EOF/receipt/1024-tail coupling.

One retained8193-byte owner, three actual ACK frames and packet releases,
one whole CQ ticket. Posted placement/core/whole-HLS/upstream-frame, memory
visibility, MAC timestamp pins and CQ consumer are MODELS. No actual MR/
PCIe/generated-HLS/board MAC/native hierarchy/Linux/physical qualification.
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

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_receive_message_ack as candidate
import native_receive_fixture as native

QUEUE=ROOT/'rdma/rnic/rtl/rocev2_receive_message_queue.v'
ACK=candidate.ACK
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def bench(ack):
    def ports(t):
        h=t.split(')(\n',1)[1].split('\n);',1)[0]
        return re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',h)
    qports=ports(QUEUE.read_text());aports=ports(ack)
    declarations=[];connections=[]
    wired={'clk':'clk','rst':'rst','parent_fault':'fault','s_owner_context':'m_head_context',
        's_owner_valid':'m_head_valid && m_head_ready','s_core_data':'held_core_data','s_core_valid':'core_proved',
        'm_done_ready':'s_mac_ready','s_retire_context':'m_packet_retire_context',
        's_retire_valid':'m_packet_retire_valid && release_enable'}
    for d,w,n in qports:
        if d=='input'and n in ['m_head_ready','s_mac_data','s_mac_valid','m_packet_retire_ready','parent_fault']:
            declarations.append('wire '+(w or'')+n+';')
        else:declarations.append(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';'))
    for d,w,n in aports:
        if n in wired:connections.append('.'+n+'('+wired[n]+')');continue
        declarations.append(('reg 'if d=='input'else'wire ')+(w or'')+'a_'+n+('=0;'if d=='input'else';'))
        connections.append('.'+n+'(a_'+n+')')
    return r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8,IMMEDIATE_ENABLE=1;
'''+ '\n'.join(declarations)+r'''
reg take_enable=0,release_enable=0;
assign parent_fault=a_fault;
assign m_head_ready=take_enable && a_s_owner_ready;
assign s_mac_data=a_m_done_data;assign s_mac_valid=a_m_done_valid;
assign m_packet_retire_ready=release_enable && a_s_retire_ready;
rocev2_receive_message_queue rq(.*);
rocev2_receive_ack_tx #(.IMMEDIATE_ENABLE(1)) ack('''+','.join(connections)+r''');
always #2 clk=~clk;
integer cycle=0,k,i,deadline,psn,msn,which=0,tx_frames=0,mac_receipts=0;
reg [127:0] words[0:3];reg [619:0] owner;reg [751:0] proof;reg [775:0] whole;
reg [160:0] held_frame;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"bounded actual ACK/RQ deadline");
 if(fault || a_fault)$fatal(1,"actual message RQ/ACK fault %h/%h",fault_code,a_fault_code);
 if(a_m_axis_tvalid && a_m_axis_tready && a_m_axis_tlast)tx_frames=tx_frames+1;
 if(a_s_cpl_valid && a_s_cpl_ready)mac_receipts=mac_receipts+1;
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task no_whole;
 begin if(!active || held_context!==owner || taken_count!=1 || queue_guard!==8'h80 || m_ticket_valid)
 $fatal(1,"packet operation retired whole RQ prematurely");end
endtask
task completion;
 input [15:0] tag;
 begin a_s_cpl_tag=tag;a_s_cpl_ts=96'h123456789abcdef;a_s_cpl_valid=1;a_m_cpl_ready=0;
 repeat(7)begin tick;if(a_s_cpl_ready || !a_m_cpl_valid || a_m_cpl_tag!==16'h4000 ||
 a_m_cpl_ts!==a_s_cpl_ts || m_packet_retire_valid)$fatal(1,"MAC receipt stall/fresh tag binding");no_whole;end
 a_m_cpl_ready=1;@(posedge clk);if(!a_s_cpl_ready)$fatal(1,"actual fresh receipt acceptance");
 @(negedge clk);a_s_cpl_valid=0;end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;query_qpn=7;
 owner=0;owner[587:524]=64'hf123456789abc001;owner[523:460]=1;owner[459:396]=64'h9123456700000001;
 owner[395:372]=7;owner[371:356]=17;owner[355:340]=1;owner[339:324]=4;owner[323:308]=1;
 owner[307:276]=1048576;owner[275:244]=32'hf1234567;owner[243:180]=64'hfedcba9876543210;owner[179:116]=64'h210;owner[19:0]=3;
 a_prior_response_drained=1;a_local_mac=48'h8af3fbb97531;a_peer_mac=48'hb8830367c5d0;
 a_local_ip=32'hc6120b02;a_peer_ip=32'hc6120b01;a_peer_qpn=196;
 s_post_context=owner;s_post_valid=1;@(posedge clk);if(!s_post_ready)$fatal(1,"modeled MR-admitted post");
 @(negedge clk);s_post_valid=0;
 for(k=0;k<3;k=k+1)begin
  take_enable=1;@(posedge clk);if(!m_head_valid || !m_head_ready || m_head_context!==owner)$fatal(1,"same whole RQ head/ACK owner");
  @(negedge clk);take_enable=0;memory_drained=0;release_enable=0;
  psn=(24'hfffffe+k)&24'hffffff;msn=k==2 ? 1:0;
  s_placement_context=owner;s_placement_length=k==2 ? 1:4096;s_placement_psn=psn;
  s_placement_notification_flags=k==0 ? 4:k==1 ? 8:17;s_placement_notification=k==2 ? 32'h89abcdef:0;
  s_placement_valid=1;@(posedge clk);if(!s_placement_ready)$fatal(1,"modeled actual placement producer");
  @(negedge clk);s_placement_valid=0;
  proof={8'd0,s_placement_notification_flags,s_placement_notification,msn[23:0],4'd0,psn[23:0],s_placement_length,owner};
  s_core_data=proof;s_core_valid=1;@(posedge clk);if(!s_core_ready)$fatal(1,"modeled same-HLS packet certificate");
  @(negedge clk);s_core_valid=0;
  if(k==2)begin
   whole={4'd0,8'd0,8'd1,32'h89abcdef,24'd1,24'd0,24'hfffffe,32'd8193,owner};
   s_message_data=whole;s_message_valid=1;@(posedge clk);if(!s_message_ready)$fatal(1,"modeled whole HLS certificate");
   @(negedge clk);s_message_valid=0;
  end
  if(k==0)$readmemh("ack0.hex",words);else if(k==1)$readmemh("ack1.hex",words);else $readmemh("ack2.hex",words);
  for(i=0;i<4;i=i+1)begin
   a_s_axis_tdata=words[i];a_s_axis_tkeep=i==3 ? 16'h3fff:16'hffff;a_s_axis_tlast=i==3;
   a_s_axis_tuser={16'h4000,1'b0};a_s_axis_tvalid=1;
   @(posedge clk);if(!a_s_axis_tready)$fatal(1,"actual ACK capture");@(negedge clk);a_s_axis_tvalid=0;
  end
  deadline=cycle+100;
  while(!a_m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"actual ACK full proof/header check");tick;end
  held_frame={a_m_axis_tdata,a_m_axis_tkeep,a_m_axis_tlast,a_m_axis_tuser};
  repeat(7)begin tick;if(!a_m_axis_tvalid || {a_m_axis_tdata,a_m_axis_tkeep,a_m_axis_tlast,a_m_axis_tuser}!==held_frame)$fatal(1,"actual ACK TX backpressure");end
  for(i=0;i<4;i=i+1)begin
   a_m_axis_tready=1;@(posedge clk);
   if(!a_m_axis_tvalid || a_m_axis_tdata!==words[i] || a_m_axis_tkeep!==(i==3 ? 16'h3fff:16'hffff) ||
      a_m_axis_tlast!==(i==3) || a_m_axis_tuser!=={16'h6001+k[15:0],1'b0})$fatal(1,"actual ACK wire/tag unchanged");
   @(negedge clk);a_m_axis_tready=0;
   if(k==0 && i==0)begin
    completion(16'h6001);memory_drained=1;
    // A timestamp plus any quiet delay cannot stand in for actual EOF.
    repeat(1100)begin tick;if(m_packet_retire_valid || a_m_done_valid)$fatal(1,"MAC timestamp without EOF");no_whole;end
   end
  end
  if(k!=0)begin
   memory_drained=1;repeat(1100)begin tick;if(m_packet_retire_valid || a_m_done_valid)$fatal(1,"EOF without real MAC receipt");no_whole;end
   completion(16'h6001+k[15:0]);
  end
  deadline=cycle+1200;
  while(!m_packet_retire_valid)begin if(cycle>deadline)$fatal(1,"actual MAC/tail/visibility packet certificate missing");tick;no_whole;end
  repeat(11)begin tick;if(!m_packet_retire_valid || !a_busy || m_head_valid)$fatal(1,"packet bridge-retire backpressure");no_whole;end
  release_enable=1;@(posedge clk);if(!m_packet_retire_valid || !m_packet_retire_ready)$fatal(1,"actual ACK packet retirement");
  @(negedge clk);release_enable=0;#1;
  if(a_busy || !active || held_context!==owner || packet_retired_count!=k+1 || taken_count!=1)$fatal(1,"ACK packet slot vs whole RQ split");
  if(k!=2 && (!m_head_valid || m_ticket_valid))$fatal(1,"same whole owner continuation missing");
 end
 repeat(7)tick;
 if(!m_ticket_valid || m_ticket_context!==owner || m_ticket_received_bytes!=8193 ||
    m_ticket_notification!=32'h89abcdef || m_ticket_notification_flags!=1 || tx_frames!=3 || mac_receipts!=3 ||
    a_frame_count!=3 || a_receipt_count!=3 || posted_count!=1 || taken_count!=1)$fatal(1,"single whole CQ / three genuine ACK lifetimes");
 m_ticket_ready=1;tick;m_ticket_ready=0;s_commit_context=owner;s_commit_valid=1;
 @(posedge clk);if(!s_commit_ready)$fatal(1,"whole CQ commit");@(negedge clk);s_commit_valid=0;
 if(!active || queue_guard!==8'h80)$fatal(1,"whole commit freed MR/RQ before exact retire");
 s_retire_context=owner;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"whole CQ retire");
 @(negedge clk);s_retire_valid=0;#1;if(active || queue_guard || m_ticket_valid || a_busy)$fatal(1,"whole lifetime not retired");
 $display("MESSAGE_ACK_RESULT {\"pass_test\":true,\"bytes\":8193,\"posted_capacity\":1048576,\"posted_owners\":1,\"ACK_frames\":3,\"fresh_receipts\":3,\"packet_releases\":3,\"whole_CQ\":1,\"actual_ACK_EOF_receipt_1024tail\":true}");
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    ack=candidate.derive();run=Path(tempfile.mkdtemp(prefix='receive-message-ack-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-message-ack-',dir='/dev/shm'))
    inputs=[QUEUE,ACK,Path(__file__).resolve(),Path(candidate.__file__).resolve(),Path(native.__file__).resolve(),
        *list((ROOT/'rdma/rnic/fpga').glob('derive_*.py'))]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs};shutil.copy2(QUEUE,run/QUEUE.name)
    (run/ACK.name).write_text(ack);(run/'tb.v').write_text(bench(ack))
    _,_,_,packet=native.case(True,True)
    for k in range(3):
        b=bytearray(packet);b[37:40]=((0xfffffe+k)&0xffffff).to_bytes(3,'big');b[41:44]=(1 if k==2 else 0).to_bytes(3,'big')
        b=native.qp.main.response.repair(b);frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+b
        (run/f'ack{k}.hex').write_text(''.join(f'{int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(frame),16)))
    command=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/QUEUE.name),str(run/ACK.name)]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,compile_command=command,
        runtime_limit_seconds=10,four_state=True,actual_RQ_and_ACK_RTL=True,other_producer_consumer_boundaries_modeled=True,
        generated_HLS_native_or_physical=False,hardware_verified=False)
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual ACK/RQ compile failed:'+str(run/'compile.log'))
        start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(c.stdout+c.stderr);result.update(simulation_seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode:raise ValueError('actual ACK/RQ failed:'+str(run/'simulation.log'))
        rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('MESSAGE_ACK_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual ACK/RQ full assertions missing')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during execution')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],simulation_seconds=result['simulation_seconds'],summary=result['summary'])))


if __name__=='__main__':main()
