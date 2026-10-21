#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE RECV/WRITE/RNR allocator: all58 old modes plus20 typed RNR modes.

Actual MAC/FIFO/XGMII/FCS/SFD/receipt CDC and1024-tail execute; RNR body,
privileged owners/HLS/error controller boundaries are MODELS. Checked WRITE
C++ trace identity is retained, not a claim of live native RNR/DMA/software.
No posted RQ or positive WRITE/HLS/CQ receipt is invented for a negative ACK.
"""
import ast
from pathlib import Path
import probe_receive_write_ack as parent
import derive_receive_write_rnr_ack as candidate

ROOT=parent.ROOT;once=candidate.once

TASKS=r'''
reg [367:0] rnr_records[0:0];reg [367:0] rnr_token;
reg [383:0] rnr_stalled;
integer rnr_proofs=0;
always @(posedge clk)if(!rst && mode>=80)begin
 if(m_rnr_done_valid && (cycle-last_cpl<1024 || cycle-last_eof<1024 || m_done_valid || m_write_done_valid))
  $fatal(1,"RNR lacks real EOF/SFD/tail or fabricated positive/RQ proof");
 if(m_rnr_done_valid && m_rnr_done_ready)rnr_proofs=rnr_proofs+1;
end
task bind_rnr;
 begin
  $readmemh("rnr.hex",words);route;rnr_token=rnr_records[0];
  case(mode)
   82:rnr_token[319:296]=24'h800002;
   83:rnr_token[279:216]=0;
   84:rnr_token[215:152]=0;
   85:rnr_token[151:120]=0;
   86:rnr_token[55:24]=4096;
   87:rnr_token[320]=~rnr_token[320];
   88:rnr_token[344]=1'bx;
  endcase
  s_rnr_owner=rnr_token;s_rnr_owner_valid=1;if(mode==89)s_write_owner_valid=1;
  @(posedge clk);
  if(mode<=81 || mode>=90)if(!s_rnr_owner_ready || queue_guard!==4)$fatal(1,"typed RNR admission/guard");
  @(negedge clk);s_rnr_owner_valid=0;s_write_owner_valid=0;
  if(mode<=81 || mode>=90)begin
   expect_held=1;
   if(!busy || !dut.rnr_mode || dut.rnr_owner!==rnr_token || dut.owner!==0 || dut.write_owner!==0)
    $fatal(1,"RNR fabricated RQ/WRITE owner instead of distinct retained message");
  end
 end
endtask
task await_rnr;
 begin
  deadline=cycle+1200;
  while(!m_rnr_done_valid)begin if(cycle>deadline)$fatal(1,"actual RNR EOF/SFD/tail proof missing");tick;end
  if(m_rnr_done_data!=={16'h6000+next_tag[15:0],rnr_token} || m_done_valid || m_write_done_valid)
   $fatal(1,"full typed RNR proof or false positive/RQ proof");
  rnr_stalled=m_rnr_done_data;
  repeat(17)begin tick;if(!m_rnr_done_valid || m_rnr_done_data!==rnr_stalled || !busy)
   $fatal(1,"full RNR proof changed under consumer backpressure");end
 end
endtask
task retire_rnr;
 begin
  s_rnr_retire_owner=rnr_token;s_rnr_retire_valid=1;
  repeat(17)begin tick;if(s_rnr_retire_ready || !busy)$fatal(1,"RNR retired before proof acceptance");end
  m_rnr_done_ready=1;tick;m_rnr_done_ready=0;
  @(posedge clk);if(!s_rnr_retire_ready)$fatal(1,"exact RNR retire missing");
  @(negedge clk);s_rnr_retire_valid=0;
  if(busy || queue_guard || m_rnr_done_valid || m_done_valid || m_write_done_valid)$fatal(1,"RNR owner leaked/false completion");
  expect_held=0;operations=operations+1;next_tag=next_tag+1;
 end
endtask
task rnr_operation;
 begin bind_rnr;capture;send_wire;await_rnr;retire_rnr;end
endtask
task run_rnr;
 begin
  $readmemh("rnr-owner.hex",rnr_records);
  if(mode==80 || mode==81 || mode==96 || mode==99)begin
   rnr_operation;
   if(mode==81)begin write_operation(0,0);recv_operation;rnr_operation;end
   if(mode==96)begin
    for(k=1;k<7;k=k+1)rnr_operation;
    s_rnr_owner=rnr_records[0];s_rnr_owner_valid=1;
    repeat(17)begin tick;if(s_rnr_owner_ready || s_owner_ready || s_write_owner_ready || !tags_exhausted || busy || fault)
     $fatal(1,"shared RNR tag exhaustion wrapped/reused sequence");end
    s_rnr_owner_valid=0;
   end
   if(fault || busy || frame_count!=operations || receipt_count!=operations || rnr_proofs!=(mode==81 ? 2:mode==96 ? 7:1))
    $fatal(1,"complete RNR/shared tag/packet counters");
  end else begin
   bind_rnr;
   if(mode>=90 && mode<=94)begin
    if(mode==90)words[3][53]=0; // Frame octet54 bit5: RNR0x20 -> ACK0x00.
    if(mode==91)words[3][56]=~words[3][56];
    if(mode==92)words[3][24]=~words[3][24];
    capture;
    if(mode==93)begin
     deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"RNR SEND before stale tag");tick;end
     tx_gate=1;tick;tx_gate=0;model_cpl_tag=16'h6002;model_cpl_valid=1;m_cpl_ready=1;tick;model_cpl_valid=0;
    end
    if(mode==94)begin
     send_wire;await_rnr;m_rnr_done_ready=1;tick;m_rnr_done_ready=0;
     s_rnr_retire_owner=rnr_token^368'd1;s_rnr_retire_valid=1;
    end
   end
   if(mode==95)begin s_retire_context=0;s_retire_valid=1;tick;
    if(!busy || s_retire_ready || s_rnr_retire_ready || fault)$fatal(1,"fake RQ retirement stole RNR owner");
    s_retire_valid=0;s_rnr_retire_owner=rnr_token^368'd1;s_rnr_retire_valid=1;end
   if(mode==97)parent_fault=1;
   if(mode==98)begin s_rnr_owner_valid=1'bx;tick;end
   quarantine;
   if(m_rnr_done_valid || s_rnr_retire_ready)$fatal(1,"faulted RNR emitted/released proof");
  end
 end
endtask
'''


def rnr_bench(text):
    t=parent.bench(text).replace('rocev2_receive_write_ack_tx #(',candidate.NAME+' #(',1)
    t=once(t,'task tick;',TASKS+'\ntask tick;')
    t=once(t,'real_mac=mode==5;','real_mac=mode==5 || mode==81;')
    t=once(t,'allow_fault=mode>=20;','allow_fault=mode>=20 && !(mode==80 || mode==81 || mode==96 || mode==99);')
    return once(t,' if(mode<=10)begin',' if(mode>=80)begin run_rnr;end else if(mode<=10)begin')


def runner_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_receive_write_ack as candidate','import derive_receive_write_rnr_ack as candidate')
    t=once(t,'MODES=list(range(11))+list(range(20,67))','MODES=list(range(11))+list(range(20,67))+list(range(80,100))')
    a=t.index('def bench(text):');b=t.index('\ndef main():',a)
    t=t[:a]+'def bench(text):return rnr_bench(text)\n\n'+t[b:]
    t=once(t,"prefix='receive-write-ack-'","prefix='receive-write-rnr-ack-'")
    t=once(t,"prefix='as02-receive-write-ack-'","prefix='as02-receive-write-rnr-ack-'")
    t=once(t,'inputs=[Path(__file__).resolve(),','inputs=[ROOT/\'rdma/rnic/tests/probe_receive_write_ack.py\',Path(__file__).resolve(),')
    t=once(t,"        recv_frame=ackfile('recv.hex',0x987654,7)",r'''
        recv_frame=ackfile('recv.hex',0x987654,7)
        v=trace['write-rx'][2];first=trace['write-rx'][0]
        rnr_owner=(first['msn']<<344)|(v['psn']<<320)|(v['token']>>104)
        (run/'rnr-owner.hex').write_text(f'{rnr_owner:092x}\n')
        b=bytearray(packet);b[37:40]=v['psn'].to_bytes(3,'big');b[40]=0x20;b[41:44]=first['msn'].to_bytes(3,'big')
        rnr_frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+old_message.native.qp.main.response.repair(b)
        (run/'rnr.hex').write_text(''.join(f'{int.from_bytes(rnr_frame[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(rnr_frame),16)))''')
    t=once(t,'                if mode==5:',r'''
                if mode==81:
                    if physical.frames(c.stdout)!=[(0x6001,rnr_frame),(0x6002,frames[0]),(0x6003,recv_frame),(0x6004,rnr_frame)]:
                        raise ValueError('actual mixed RNR/WRITE/RECV/RNR frames/FCS/SFD/fresh shared tags')
                    item['actual_RNR_WRITE_RECV_RNR_MAC_frames_verified']=True
                if mode==5:''')
    t=once(t,'        result.update(pass_test=True,source_unchanged=True,',
        '        result.update(RNR_owner_bits=368,RNR_proof_bits=384,RNR_component_modes=20,old_component_modes=58,\n'
        '            RNR_body_and_producer_modeled=True,RNR_real_MAC_frames=4,\n'
        '            pass_test=True,source_unchanged=True,')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),rnr_bench=rnr_bench))
