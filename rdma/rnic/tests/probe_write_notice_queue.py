#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual late-WRITE notice RQ RTL plus all48 qualified SEND queue cases.

Remote-message MR identity, placement/core/MAC/visibility producers are
explicit component models, NOT injected into the native graph. This is
not actual MR/DMA/HLS/MAC/CQ/native/Linux or physical qualification.
"""
import ast
from pathlib import Path
import sys
import probe_receive_message_queue as parent

ROOT=parent.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_notice_queue as candidate
once=candidate.once


EXTRA=r'''
 if(mode>=100)begin
  total=mode==101 ? 1048576:mode==102 ? 4097:mode==103 ? 8192:8193;
  capacity=mode==100 ? 0:mode==101 ? 1:mode==102 ? 17:8194;
  initial_psn=24'hfffffe;psn=(initial_psn+(total-1)/4096)&24'hffffff;
  s_write_notice_context={24'd7,16'd17,64'h9123456700000001,64'hfedcba9876543210,
      32'hf1234567,64'he23456789abcdef0,total[31:0],initial_psn[23:0]};
  s_write_notice_last_psn=psn;s_write_notice_valid=1;
  if(mode==112)repeat(5)begin tick;if(fault || active || m_head_valid || s_write_notice_ready)$fatal(1,"notice without RQ cannot create owner");end
  // A valid notice can wait for a genuinely posted owner, not synthesize it.
  post(make_context(capacity,1));
  case(mode)
   104:s_write_notice_context[295:280]=18;
   105:s_write_notice_context[279:216]=64'h9123456700000002;
   106:s_write_notice_context[151:120]=0;
   107:s_write_notice_context[119:56]=64'hfffffffffffff000;
   111:s_write_notice_context[319:296]=24'h800007;
   113:s_write_notice_valid=1'bx;
  endcase
  if((mode>=104 && mode<=107) || mode==111 || mode==113)begin
   m_head_ready=1;repeat(5)tick;
   if(!fault || active || taken_count || queue_guard!==8'hff || m_head_valid || s_write_notice_ready || m_ticket_valid)
    $fatal(1,"unmatched remote MR identity cannot take late RQ");
  end else begin
   m_head_ready=1;@(posedge clk);if(!m_head_valid || !s_write_notice_ready || m_head_context!==owner)$fatal(1,"matched remote message and genuine RQ join");
   @(negedge clk);m_head_ready=0;s_write_notice_valid=0;good;
   if(!active || held_context!==owner || taken_count!=1)$fatal(1,"one distinct late RQ");
   len=((total-1)%4096)+1;
   if(mode==110)begin
    s_placement_context=owner;s_placement_length=len;s_placement_notification_flags=3;
    s_placement_notification=32'h89abcdef;s_placement_psn=psn+1;s_placement_valid=1;retained;
   end else begin
    place(len,3,psn);make_proof(len,3,psn,9);core;
    make_whole(total,initial_psn,psn,9,3);
    if(mode==108 || mode==109)begin
     if(mode==108)whole[651:620]=len;else whole[675:652]=psn;
     s_message_data=whole;s_message_valid=1;retained;
    end else begin
     message;mac(0);packet_release;
     if(received_bytes!=total || taken_count!=1 || packet_retired_count!=1)$fatal(1,"whole WRITE bytes not last packet or RQ capacity");
     finish_write(total,3);
     if(posted_count!=1 || taken_count!=1 || packet_retired_count!=1)$fatal(1,"one exact late RQ life");
    end
   end
  end
 end else'''


def write_notice_bench(rtl):
    saved=parent.RTL
    try:
        parent.RTL=rtl;t=parent.bench()
    finally:parent.RTL=saved
    t=once(t,'rocev2_receive_message_queue dut(.*);',candidate.NAME+' dut(.*);')
    a=t.index('task finish;');b=t.index('endtask',a)+len('endtask');task=t[a:b]
    task=once(task,'task finish;','task finish_write;')
    task=once(task,' s_retire_valid=1;@(posedge clk);if(!s_retire_ready)',r'''
 m_write_retire_ready=0;s_retire_valid=1;
 repeat(7)begin tick;
  if(s_retire_ready || !m_write_retire_valid || m_write_retire_context!==s_write_notice_context ||
     !active || held_context!==owner || queue_guard!==8'h80)$fatal(1,"remote MR retirement backpressure must retain late RQ");
 end
 m_write_retire_ready=1;
 @(posedge clk);if(!s_retire_ready)''')
    t=t[:b]+'\n'+task+t[b:]
    return once(t,' if(mode<6)begin',EXTRA+' if(mode<6)begin')


def runner_source():
    t=Path(parent.__file__).read_text()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import time','import time\nfrom probe_write_notice_queue import candidate,write_notice_bench')
    t=once(t,"prefix='receive-message-queue-'","prefix='write-notice-receive-queue-'")
    t=once(t,"prefix='as02-receive-message-queue-'","prefix='as02-write-notice-receive-queue-'")
    t=once(t,'    before={str(n.relative_to(ROOT)):digest(n)for n in [RTL,Path(__file__).resolve()]}',
        "    original=RTL;RTL=run/(candidate.NAME+'.v');RTL.write_text(candidate.derive())\n"
        "    before={str(n.relative_to(ROOT)):digest(n)for n in [original,RTL,Path(__file__).resolve(),Path(candidate.__file__).resolve(),ROOT/'rdma/rnic/tests/probe_receive_message_queue.py']}")
    # Assignment makes RTL local: retain the original source before deriving.
    t=once(t,'    original=RTL;RTL=run/', '    original=candidate.SOURCE;RTL=run/')
    t=once(t,"    shutil.copy2(RTL,run/RTL.name);(run/'tb.v').write_text(bench())", "    (run/'tb.v').write_text(write_notice_bench(RTL))")
    t=once(t,'modes=[*range(6),*range(10,16),*range(20,56)]',
        'modes=[*range(6),*range(10,16),*range(20,56),*range(100,114)]')
    t=once(t,'all_proof_and_owner_producers_modeled=True,',
        'all_proof_and_owner_producers_modeled=True,remote_MR_identity_producer_modeled=True,all48_prior_cases_retained=True,late_WRITE_notification_cases=14,')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
