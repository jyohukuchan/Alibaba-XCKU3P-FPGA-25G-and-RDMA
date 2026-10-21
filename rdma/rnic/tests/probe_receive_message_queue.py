#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real four-state message RQ: whole owner vs per-packet ACK/CQ lifetimes.

Posted MR-admitted owners, memory visibility, HLS/core/whole certificates,
and ACK-MAC certificates are explicit producer models in this component
test. They are NOT injected into the production native hierarchy. Actual
generated-HLS/native/DMA/MAC/CQ/standard Linux/physical proof remains separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3];RTL=ROOT/'rdma/rnic/rtl/rocev2_receive_message_queue.v'
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def bench():
    header=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',header)
    decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports)
    return r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
'''+decl+r'''
rocev2_receive_message_queue dut(.*);
always #2 clk=~clk;
integer mode=0,cycle=0,i,offset,len,flags,initial_psn,psn,msn,base,seq=0;
integer total,capacity,pad;reg [619:0] owner;reg [751:0] proof;reg [775:0] whole;
always @(posedge clk)if(!rst)begin cycle=cycle+1;if(cycle>100000)$fatal(1,"bounded message RQ deadline");end
function [619:0] make_context;
 input [31:0] cap;input [63:0] wr_seq;
 reg [619:0] c;
 begin c=0;c[587:524]=64'hf123456789abc000+wr_seq;c[523:460]=wr_seq;
 c[459:396]=64'h9123456700000001;c[395:372]=7;c[371:356]=17;c[355:340]=wr_seq;
 c[339:324]=4;c[323:308]=1;c[307:276]=cap;c[19:0]=3;
 if(cap!=0)begin c[275:244]=32'hf1234567;c[243:180]=64'hfedcba9876543210;c[179:116]=64'h210;end
 make_context=c;end
endfunction
task tick;begin @(posedge clk);@(negedge clk);end endtask
task good;
 begin if(fault)$fatal(1,"unexpected message RQ fault %h mode%0d",fault_code,mode);end
endtask
task post;
 input [619:0] c;
 begin s_post_context=c;s_post_valid=1;@(posedge clk);if(!s_post_ready)$fatal(1,"actual post admission");
 @(negedge clk);s_post_valid=0;owner=c;seq=seq+1;query_qpn=7;good;
 if(queue_guard!==8'h80 || active)$fatal(1,"posted owner guard");end
endtask
task take;
 begin m_head_ready=1;@(posedge clk);if(!m_head_valid || m_head_context!==owner)$fatal(1,"exact head take/continue");
 @(negedge clk);m_head_ready=0;good;if(!active || held_context!==owner || taken_count!=seq)$fatal(1,"one whole take, not per-packet pop");end
endtask
task place;
 input integer n;input integer f;input integer p;
 begin s_placement_context=owner;s_placement_length=n;s_placement_psn=p;
 s_placement_notification_flags=f;s_placement_notification=(f&1)!=0 ? 32'h89abcdef:0;s_placement_valid=1;
 @(posedge clk);if(!s_placement_ready)$fatal(1,"exact packet placement");@(negedge clk);s_placement_valid=0;good;end
endtask
task make_proof;
 input integer n;input integer f;input integer p;input integer m;
 begin proof={8'd0,f[7:0],((f&1)!=0 ? 32'h89abcdef:32'd0),m[23:0],4'd0,p[23:0],n[31:0],owner};end
endtask
task core;
 begin s_core_data=proof;s_core_valid=1;@(posedge clk);if(!s_core_ready)$fatal(1,"actual packet core join");
 @(negedge clk);s_core_valid=0;good;if(!core_proved || held_core_data!==proof)$fatal(1,"full stored core proof");end
endtask
task mac;
 input integer index;
 begin s_mac_data={16'h6001+index[15:0],proof};s_mac_valid=1;
 @(posedge clk);if(!s_mac_ready)$fatal(1,"exact MAC packet owner");@(negedge clk);s_mac_valid=0;good;end
endtask
task packet_release;
 begin
 memory_drained=0;repeat(4)begin tick;if(m_packet_retire_valid || m_ticket_valid || m_head_valid || !active)$fatal(1,"missing actual backend visibility");end
 memory_drained=1;repeat(4)tick;good;
 if(!m_packet_retire_valid || m_packet_retire_context!==owner || m_ticket_valid)$fatal(1,"packet proof readiness");
 // Once genuinely certified, a different global client's activity cannot
 // retract the already offered packet certificate under backpressure.
 memory_drained=0;repeat(7)begin tick;if(!m_packet_retire_valid || m_packet_retire_context!==owner || m_ticket_valid)$fatal(1,"packet stable under backpressure");end
 m_packet_retire_ready=1;@(posedge clk);if(!m_packet_retire_valid)$fatal(1,"packet retire handshake");
 @(negedge clk);m_packet_retire_ready=0;good;
 if(!active || held_context!==owner || queue_guard!==8'h80 || m_ticket_valid)$fatal(1,"packet release freed whole RQ");
 end
endtask
task make_whole;
 input integer n;input integer first;input integer last;input integer m;input integer f;
 begin whole={4'd0,8'd0,f[7:0],((f&1)!=0 ? 32'h89abcdef:32'd0),m[23:0],last[23:0],first[23:0],n[31:0],owner};end
endtask
task message;
 begin s_message_data=whole;s_message_valid=1;@(posedge clk);if(!s_message_ready)$fatal(1,"whole HLS proof");
 @(negedge clk);s_message_valid=0;good;end
endtask
task finish;
 input integer n;input integer f;
 begin
 memory_drained=0;repeat(7)begin tick;if(m_ticket_valid || m_head_valid)$fatal(1,"whole final visibility missing");end
 memory_drained=1;repeat(4)tick;good;
 if(!m_ticket_valid || m_ticket_context!==owner || m_ticket_received_bytes!==n || m_ticket_notification_flags!==f ||
 m_ticket_notification!==((f&1)!=0 ? 32'h89abcdef:32'd0))$fatal(1,"one whole CQ ticket/actual bytes");
 memory_drained=0;repeat(7)begin tick;if(!m_ticket_valid || m_ticket_context!==owner || m_head_valid)$fatal(1,"whole CQ backpressure");end
 s_retire_context=owner;s_retire_valid=1;s_commit_context=owner;s_commit_valid=1;
 repeat(7)begin tick;if(s_retire_ready || s_commit_ready || !active)$fatal(1,"early CQ cannot free");end
 s_commit_valid=0;s_retire_valid=0;m_ticket_ready=1;
 @(posedge clk);if(!m_ticket_valid)$fatal(1,"CQ ticket handshake");@(negedge clk);m_ticket_ready=0;
 s_commit_valid=1;@(posedge clk);if(!s_commit_ready)$fatal(1,"actual CQ commit");@(negedge clk);s_commit_valid=0;
 if(!active || queue_guard!==8'h80)$fatal(1,"commit alone freed RQ");
 s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"exact whole CQ retirement");@(negedge clk);s_retire_valid=0;
 // Let the combinational protocol guard settle after deasserting VALID;
 // retain the exact release assertion and original4ns clock/deadline.
 #1;good;
 if(active || queue_guard || m_head_valid || m_ticket_valid || m_packet_retire_valid)
 $fatal(1,"whole owner not released once active%h guard%h head%h ticket%h packet%h",active,queue_guard,m_head_valid,m_ticket_valid,m_packet_retire_valid);
 end
endtask
task first_packet;
 begin post(make_context(capacity,1));take;place(4096,4,24'hfffffe);make_proof(4096,4,24'hfffffe,7);core;mac(0);packet_release;
 if(!m_head_valid || received_bytes!=4096)$fatal(1,"genuine same-owner continuation");take;end
endtask
task final_packet;
 begin first_packet;place(1,17,24'hffffff);make_proof(1,17,24'hffffff,8);core;
 make_whole(4097,24'hfffffe,24'hffffff,8,1);end
endtask
task retained;
 begin repeat(5)tick;if(!fault || !active || held_context!==owner || queue_guard!==8'hff ||
 m_ticket_valid || m_packet_retire_valid || m_head_valid || s_commit_ready || s_retire_ready)$fatal(1,"bad evidence freed whole RQ");end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 rst=1;repeat(5)@(negedge clk);rst=0;query_qpn=7;capacity=1048576;
 if(mode<6)begin
  total=mode==0 ? 8193:mode==1 ? 1048576:mode==2 ? 8192:mode==3 ? 0:65;
  capacity=mode==3 ? 0:mode==4 ? 128:mode==5 ? 1:1048576;
  post(make_context(capacity,1));initial_psn=24'hfffffe;psn=initial_psn;base=24'hffffff;
  for(offset=0;offset<total || (total==0 && offset==0);offset=offset+4096)begin
   take;len=total-offset>4096 ? 4096:total-offset;
   flags=total<=4096 ? (mode==5 ? 3:mode==4 ? 1:0):offset==0 ? 4:offset+len==total ? (mode==2 ? 16:17):8;
   msn=offset+len==total ? 0:base;place(len,flags,psn);make_proof(len,flags,psn,msn);
   // Memory and MAC certificates cannot replace the actual core proof.
   memory_drained=1;repeat(5)begin tick;if(m_packet_retire_valid || m_ticket_valid)$fatal(1,"no core proof yet");end
   core;repeat(5)begin tick;if(m_packet_retire_valid || m_ticket_valid)$fatal(1,"no MAC receipt yet");end
   if(offset+len==total && mode!=1)begin make_whole(total,initial_psn,psn,msn,flags&3);message;end
   mac(offset/4096);packet_release;
   if(offset+len==total)begin
    if(mode==1)begin repeat(5)begin tick;if(m_ticket_valid)$fatal(1,"no whole HLS receipt yet");end
     make_whole(total,initial_psn,psn,msn,flags&3);message;end
    finish(total,flags&3);
   end else if(!m_head_valid || taken_count!=1 || received_bytes!=offset+len)$fatal(1,"one retained RQ across packets");
   psn=(psn+1)&24'hffffff;if(total==0)offset=4096;
  end
  if(posted_count!=1 || taken_count!=1 || packet_retired_count!=(total==0 ? 1:(total+4095)/4096))$fatal(1,"exact whole/packet counts");
 end else if(mode<16)begin
  owner=make_context(1048576,1);
  case(mode)
   10:owner[395:372]=24'h800007;11:owner[275:244]=0;12:owner[243:180]=64'hfffffffffffff000;
   13:owner[179:116]=64'hfffffffffffff000;14:owner[339:324]=3;15:owner[619:588]=1;
  endcase
  s_post_context=owner;s_post_valid=1;repeat(5)tick;
  if(!fault || active || queue_guard!==8'hff || m_head_valid || s_post_ready)$fatal(1,"invalid posted owner admitted");
 end else if(mode<30)begin
  if(mode==23)capacity=4096;post(make_context(capacity,1));take;
  s_placement_context=owner;s_placement_length=4096;s_placement_notification_flags=4;s_placement_psn=24'hfffffe;
  case(mode)
   20:s_placement_notification_flags=8;21:s_placement_notification_flags=16;22:s_placement_length=4095;
   24:s_placement_context[395:372]=24'h800007;25:s_placement_context[523:460]=2;
   26:s_placement_context[459:396]=64'h9123456700000002;27:s_placement_context[371:356]=18;
   28:s_placement_context[275:244]=32'hf1234566;29:s_placement_notification=1;
  endcase
  s_placement_valid=1;retained;
 end else if(mode<35)begin
  if(mode==33)capacity=4097;first_packet;
  s_placement_context=owner;s_placement_length=1;s_placement_psn=24'hffffff;s_placement_notification_flags=17;s_placement_notification=32'h89abcdef;
  case(mode)
   30:begin s_placement_notification_flags=0;s_placement_notification=0;end
   31:begin s_placement_notification_flags=4;s_placement_length=4096;s_placement_notification=0;end
   32:s_placement_psn=0;
   33:begin s_placement_notification_flags=8;s_placement_length=4096;s_placement_notification=0;end
   34:s_placement_length=0;
  endcase
  s_placement_valid=1;retained;
 end else if(mode<42 || mode==54)begin
  first_packet;place(1,17,24'hffffff);make_proof(1,17,24'hffffff,8);
  if(mode==35)proof[703:680]=7;
  if(mode==36)proof[743:736]=20;
  if(mode==37)proof[651:620]=2;
  if(mode==38)proof[523:460]=2;
  if(mode==54)proof[703:680]=24'hxxxxxx;
  if(mode<39 || mode==54)begin s_core_data=proof;s_core_valid=1;end
  else begin
   if(mode!=41)core;
   s_mac_data={16'h6002,proof};s_mac_valid=1;
   if(mode==39)s_mac_data[767:752]=16'h4000;
   if(mode==40)s_mac_data[735:704]=32'h89abcdee;
  end
  memory_drained=1;retained;
 end else begin
  if(mode==50)begin
   post(make_context(capacity,1));take;place(4096,4,24'hfffffe);make_proof(4096,4,24'hfffffe,7);core;
   make_whole(4096,24'hfffffe,24'hfffffe,7,0);
  end else final_packet;
  case(mode)
   42:whole[651:620]=1048576;43:whole[523:460]=2;44:whole[675:652]=0;
   45:whole[699:676]=0;46:whole[723:700]=7;47:whole[755:724]=32'h89abcdee;
   48:whole[775:772]=1;49:whole[763:756]=3;55:whole[651:620]=32'hxxxxxxxx;
  endcase
  if(mode==51)begin message;s_message_data=whole;s_message_valid=1;end
  else if(mode==52 || mode==53)begin
   message;mac(1);packet_release;memory_drained=1;repeat(5)tick;m_ticket_ready=1;tick;m_ticket_ready=0;
   s_commit_context=owner;
   if(mode==52)begin s_commit_context[523:460]=2;s_commit_valid=1;end
   else begin s_commit_valid=1;tick;s_commit_valid=0;s_retire_context=owner;s_retire_context[523:460]=2;s_retire_valid=1;end
  end else begin s_message_data=whole;s_message_valid=1;end
  retained;
 end
 $display("MESSAGE_RQ_RESULT {\"pass_test\":true,\"mode\":%0d,\"posted\":%0d,\"taken\":%0d,\"packets\":%0d,\"bytes\":%0d}",mode,posted_count,taken_count,packet_retired_count,received_bytes);
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='receive-message-queue-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-message-queue-',dir='/dev/shm'))
    before={str(n.relative_to(ROOT)):digest(n)for n in [RTL,Path(__file__).resolve()]}
    shutil.copy2(RTL,run/RTL.name);(run/'tb.v').write_text(bench())
    modes=[*range(6),*range(10,16),*range(20,56)]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        tests={},case_limit_seconds=10,four_state=True,actual_message_RQ_RTL=True,
        all_proof_and_owner_producers_modeled=True,generated_HLS_or_native_integration=False,hardware_verified=False)
    command=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/RTL.name)]
    result['compile_command']=command
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('message RQ compile failed:'+str(run/'compile.log'))
        for mode in modes:
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test'),'+MODE='+str(mode)],capture_output=True,text=True,timeout=10)
            (run/(str(mode)+'.log')).write_text(c.stdout+c.stderr);t=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=t
            if c.returncode:raise ValueError('actual message RQ failure:'+str(run/(str(mode)+'.log')))
            rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith('MESSAGE_RQ_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['mode']!=mode:raise ValueError('missing actual RTL assertions')
            t['summary']=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,planned_cases=len(modes))
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),compile_seconds=result['compile_seconds'],
        max_case_seconds=max(v['seconds']for v in result['tests'].values()))))


if __name__=='__main__':main()
