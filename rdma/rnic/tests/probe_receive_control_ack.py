#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Single control/RECV/WRITE/RNR ACK allocator, real MAC and modeled producers.

Retain all78 previous modes and both original legacy benches. Control480,
HLS512 and independent control frame inputs are MODELS, not live generated
HLS/native/physical proof. Real MAC/FIFO/XGMII/FCS/SFD/receipt CDC execute,
with the original4ns/10s/100000-cycle gates and distinct528-bit MAC proof.
"""
import ast
from pathlib import Path
import probe_receive_write_rnr_ack as parent
import derive_receive_control_ack as candidate

ROOT=parent.ROOT;once=candidate.once
MODES=list(range(110,176))
POSITIVE=[110,111,112,113,114,115,116,168,172,173]

TASKS=r'''
reg [479:0] control_records[0:4];reg [511:0] control_cores[0:4];
reg [479:0] control_token=0;reg [511:0] control_core=0;
reg [527:0] control_stalled=0;
integer control_proofs=0,control_index=0;
always @(posedge clk)if(!rst && mode>=110)begin
 if(m_control_done_valid && (cycle-last_cpl<1024 || cycle-last_eof<1024 ||
    m_done_valid || m_write_done_valid || m_rnr_done_valid))
  $fatal(1,"control completion lacks actual EOF/SFD/tail or fabricated data/RQ/RNR proof");
 if(m_control_done_valid && m_control_done_ready)control_proofs=control_proofs+1;
end
task choose_control;
 input integer n;
 begin
  route;control_index=n;control_token=control_records[n];
  control_token[419:356]=64'h1000000000000000+next_tag;
  if(mode==117 && operations==0)control_token[419:356]=64'hffffffffffffffff;
  if(mode==117 && operations!=0)control_token[419:356]=1;
  if(mode==118 && operations!=0)control_token[419:356]=64'h1000000000000001;
  if(mode==119 && operations!=0)control_token[419:356]=64'h1000000000000000;
  case(mode)
   120:control_token[479]=1;
   121:control_token[475:468]=0;
   122:control_token[475:468]=8'h20;
   123:control_token[475:468]=8'h40;
   124:control_token[475:468]=8'h64;
   125:control_token[419:356]=0;
   126:control_token[23:0]=24'h800002;
   127:control_token[39:24]=0;
   128:control_token[103:40]=0;
   129:control_token[167:104]=0;
   130:control_token[256]=~control_token[256];
   131:control_token[304]=~control_token[304];
   132:control_token[192]=~control_token[192];
   133:control_token[224]=~control_token[224];
   134:control_token[168]=~control_token[168];
   135:control_token[400]=1'bx;
   136:control_token[467:444]=control_token[443:420]+24'd1;
   137:control_token[467:444]=control_token[443:420]+24'd1-24'h800000;
   138:begin control_token[475:468]=8'h60;control_token[467:444]=control_token[443:420];end
   139:begin control_token[475:468]=8'h60;control_token[467:444]=control_token[443:420]-24'd1;end
   140:begin control_token[475:468]=8'h61;control_token[467:444]=control_token[443:420]+24'd1;end
  endcase
  control_core={control_cores[n][511:480],control_token};
  case(n)
   0:$readmemh("control0.hex",words);
   1:$readmemh("control1.hex",words);
   2:$readmemh("control2.hex",words);
   3:$readmemh("control3.hex",words);
   4:$readmemh("control4.hex",words);
  endcase
 end
endtask
task bind_control;
 input integer n;
 begin
  choose_control(n);s_control_owner=control_token;s_control_owner_valid=1;
  if(mode==141)s_control_owner_valid=1'bx;
  if(mode==142)s_owner_valid=1;
  if(mode==143)s_write_owner_valid=1;
  if(mode==144)s_rnr_owner_valid=1;
  if(mode==175)s_owner_valid=1'bx;
  @(posedge clk);
  if(mode<=116 || mode>=145 && mode<=174 || mode>=117 && mode<=119 && operations==0)
   if(!s_control_owner_ready || queue_guard!==4)$fatal(1,"distinct control admission/full local QPN guard");
  @(negedge clk);s_control_owner_valid=0;s_owner_valid=0;s_write_owner_valid=0;s_rnr_owner_valid=0;
  if(!fault)begin
   expect_held=1;
   if(!busy || !dut.control_mode || dut.control_owner!==control_token || dut.owner!==0 || dut.write_owner!==0 || dut.rnr_owner!==0)
    $fatal(1,"control token not full or fabricated old owner/data/RQ grant");
   // Config changes cannot rewrite the captured full native route.
   local_mac=0;peer_mac=0;local_ip=0;peer_ip=0;peer_qpn=0;
  end
 end
endtask
task offer_control_core;
 begin
  s_control_core_data=control_core;s_control_core_valid=1;
  case(mode)
   145:s_control_core_data[104]=~s_control_core_data[104];
   146:s_control_core_data[356]=~s_control_core_data[356];
   147:s_control_core_data[504]=1;
   148:s_control_core_data[480]=1'bx;
   149:s_control_core_valid=1'bx;
  endcase
  @(posedge clk);if(!s_control_core_ready && mode!=149)$fatal(1,"full control HLS receipt handshake missing");
  @(negedge clk);s_control_core_valid=0;s_control_core_data=0;
 end
endtask
task await_control;
 begin
  deadline=cycle+1200;
  while(!m_control_done_valid)begin if(cycle>deadline)$fatal(1,"actual control EOF/SFD/tail proof absent");tick;end
  if(m_control_done_data!=={16'h6000+next_tag[15:0],control_core} || m_done_valid || m_write_done_valid || m_rnr_done_valid)
   $fatal(1,"distinct full control528/MACtag/MSN/480-owner proof");
  control_stalled=m_control_done_data;
  repeat(17)begin tick;if(!busy || !m_control_done_valid || m_control_done_data!==control_stalled)
   $fatal(1,"control528 proof unstable under independent backpressure");end
 end
endtask
task retire_control;
 begin
  s_control_retire_owner=control_token;s_control_retire_valid=1;
  repeat(17)begin tick;if(s_control_retire_ready || !busy)$fatal(1,"control owner retired before proof consumer");end
  m_control_done_ready=1;tick;m_control_done_ready=0;
  @(posedge clk);if(!s_control_retire_ready)$fatal(1,"exact full480 control retirement absent");
  @(negedge clk);s_control_retire_valid=0;
  if(busy || queue_guard || m_control_done_valid || m_done_valid || m_write_done_valid || m_rnr_done_valid)
   $fatal(1,"control retirement leaked owner or synthesized positive completion");
  expect_held=0;operations=operations+1;next_tag=next_tag+1;
 end
endtask
task control_operation;
 input integer n;
 begin
  bind_control(n);
  if(mode==112)begin offer_control_core;capture;end
  else begin capture;blocked(37);offer_control_core;end
  send_wire;await_control;retire_control;
 end
endtask
task run_control;
 begin
  $readmemh("control-owner.hex",control_records);$readmemh("control-core.hex",control_cores);
  $readmemh("rnr-owner.hex",rnr_records);
  if(mode==110 || mode==114)begin for(k=0;k<5;k=k+1)control_operation(k);end
  else if(mode==111)begin control_operation(0);write_operation(0,0);recv_operation;rnr_operation;control_operation(1);end
  else if(mode==112 || mode==116)begin
   if(mode==116)begin s_core_valid=1;s_core_data=0;s_write_core_valid=1;s_write_core_data=0;end
   control_operation(2);s_core_valid=0;s_write_core_valid=0;
  end else if(mode==113)begin
   for(k=0;k<7;k=k+1)control_operation(k%5);
   choose_control(1);s_control_owner=control_token;s_control_owner_valid=1;
   repeat(17)begin tick;if(s_control_owner_ready || s_owner_ready || s_write_owner_ready || s_rnr_owner_ready ||
    !tags_exhausted || busy || fault)$fatal(1,"four-path shared tag sequence exhaustion wrapped");end
   s_control_owner_valid=0;
  end else if(mode==115)begin
   choose_control(0);s_control_owner=control_token;s_control_owner_valid=1;prior_response_drained=0;
   repeat(17)begin tick;if(s_control_owner_ready || busy || fault)$fatal(1,"control invented prior response drain");end
   prior_response_drained=1'bx;
   repeat(17)begin tick;if(s_control_owner_ready || busy || fault)$fatal(1,"unknown prior response drain accepted");end
   s_control_owner_valid=0;prior_response_drained=1;control_operation(0);
  end else if(mode==168)begin
   bind_control(1);s_control_retire_owner=control_token;s_control_retire_valid=1;capture;
   repeat(37)begin tick;if(fault || s_control_retire_ready || !busy || m_control_done_valid)$fatal(1,"early exact control retire escaped join");end
   offer_control_core;send_wire;await_control;retire_control;
  end else if(mode==172 || mode==173)begin
   bind_control(1);capture;
   if(mode==173)begin
    offer_control_core;deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"control SEND deadline");tick;end
    for(i=0;i<4;i=i+1)begin tx_gate=1;tick;tx_gate=0;end
   end
   repeat(1300)begin tick;if(fault || !busy || m_control_done_valid || m_done_valid || m_write_done_valid || m_rnr_done_valid ||
    s_control_retire_ready || mode==172 && m_axis_tvalid)$fatal(1,"missing actual HLS/MAC proof invented success");end
  end else begin
   if(mode>=117 && mode<=119)begin
    control_operation(0);if(mode==118)write_operation(0,0);bind_control(0);
   end else if(mode==150 || mode==169)begin
    if(mode==150)begin s_control_core_valid=1;s_control_core_data=0;end
    else begin s_control_retire_valid=1;s_control_retire_owner=0;end
   end else if(mode==152)begin choose(0);bind_write(0);s_control_core_valid=1;s_control_core_data=0;end
   else if(mode==170)begin control_operation(0);s_control_retire_owner=control_token;s_control_retire_valid=1;end
   else begin
    bind_control(0);
    if(mode>=145 && mode<=149)offer_control_core;
    if(mode==151)begin offer_control_core;s_control_core_valid=1;s_control_core_data=control_core;end
    if(mode>=153 && mode<=164)begin
     if(mode==153)words[3][56]=~words[3][56];
     if(mode==154)words[3][48]=~words[3][48];
     if(mode==155)words[3][24]=~words[3][24];
     if(mode==156)words[0][0]=~words[0][0];
     if(mode==157)words[2][16]=~words[2][16];
     capture;
     if(mode<=157 || mode>=162)offer_control_core;
     if(mode==162 || mode==164)begin
      deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"control negative SEND deadline");tick;end
      tx_gate=1;tick;tx_gate=0;model_cpl_tag=mode==162 ? 16'h6002:16'h6xxx;model_cpl_valid=1;m_cpl_ready=1;
     end
     if(mode==163)begin send_wire;await_control;model_cpl_tag=16'h6001;model_cpl_valid=1;m_cpl_ready=1;end
    end
    if(mode==165)begin s_control_retire_owner=control_token^(480'd1<<40);s_control_retire_valid=1;end
    if(mode==166)s_control_retire_valid=1'bx;
    if(mode==167)begin s_retire_context=0;s_retire_valid=1;end
    if(mode==171)parent_fault=1;
    if(mode==174)begin s_control_core_data=control_core;s_control_core_data[40]=~s_control_core_data[40];s_control_core_valid=1;end
   end
   quarantine;
   if(m_control_done_valid || s_control_retire_ready)$fatal(1,"quarantined control owner falsely completed/released");
  end
  if(mode<=116 || mode==168)begin
   if(fault || busy || frame_count!=operations || receipt_count!=operations ||
    control_proofs!=(mode==110 || mode==114 ? 5:mode==111 ? 2:mode==113 ? 7:1))
    $fatal(1,"complete control/shared owner lifecycle counters");
  end
  $display("CONTROL_ACK_RESULT {\"mode\":%0d,\"control_proofs\":%0d,\"serial\":\"%016h\"}",mode,control_proofs,dut.last_control_serial);
 end
endtask
'''


def control_bench(text):
    t=parent.rnr_bench(text).replace(parent.candidate.NAME+' #(',candidate.NAME+' #(',1)
    t=once(t,'task tick;',TASKS+'\ntask tick;')
    t=once(t,'real_mac=mode==5 || mode==81;','real_mac=mode==5 || mode==81 || mode==111 || mode==114;')
    t=once(t,'allow_fault=mode>=20 && !(mode==80 || mode==81 || mode==96 || mode==99);',
        'allow_fault=mode>=20 && !('+' || '.join('mode=='+str(n)for n in [80,81,96,99,*POSITIVE])+');')
    t=once(t,'if(mode==50 && i==2)','if((mode==50 || mode==158) && i==2)')
    t=once(t,'if(mode==51 && i==2)','if((mode==51 || mode==159) && i==2)')
    t=once(t,"s_axis_tuser={16'h4000,1'b0};s_axis_tvalid=1;", "s_axis_tuser={mode==160 && i==2 ? 16'h4001:mode==161 && i==2 ? 16'h6000:16'h4000,1'b0};s_axis_tvalid=1;")
    t=once(t,'if(m_done_valid || m_write_done_valid || !busy)',
        'if(m_control_done_valid || m_done_valid || m_write_done_valid || !busy)')
    t=once(t,' if(mode>=80)begin run_rnr;', ' if(mode>=110)begin run_control;end else if(mode>=80)begin run_rnr;')
    return t


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_receive_write_rnr_ack as candidate','import derive_receive_control_ack as candidate')
    t=once(t,'+list(range(80,100))','+list(range(80,100))+list(range(110,176))')
    t=once(t,'def bench(text):return rnr_bench(text)','def bench(text):return control_bench(text)')
    t=once(t,"prefix='receive-write-rnr-ack-'","prefix='receive-control-ack-'")
    t=once(t,"prefix='as02-receive-write-rnr-ack-'","prefix='as02-receive-control-ack-'")
    t=once(t,'inputs=[ROOT/\'rdma/rnic/tests/probe_receive_write_ack.py\',',
        'inputs=[ROOT/\'rdma/rnic/tests/probe_receive_write_rnr_ack.py\',ROOT/\'rdma/rnic/tests/probe_receive_write_ack.py\',')
    t=once(t,"        recv_frame=ackfile('recv.hex',0x987654,7)",r'''
        recv_frame=ackfile('recv.hex',0x987654,7)
        # Independent modeled native-context packing and HLS header receipts.
        # No captured native/HLS output is rewritten or called live execution.
        context=(4<<352)|(0xb8830367c5d0<<304)|(0x8af3fbb97531<<256)|(0xc6120b01<<224)|(0xc6120b02<<192)|(196<<168)|(0x123456789abcdef0<<104)|(0xfedcba9876543210<<40)|(7<<24)|2
        controls=[(0x1f,0xfffffe,0),(0x60,2,0xffffff),(0x61,0x987654,0x987654),(0x62,0x987654,0x987654),(0x63,0x987654,0x987654)]
        control_frames=[];owners=[];cores=[]
        for n,(syndrome,received,response)in enumerate(controls):
            owner=(syndrome<<468)|(received<<444)|(response<<420)|((0x1000000000000001)<<356)|context
            msn=0xabc120+n;owners.append(owner);cores.append((msn<<480)|owner)
            b=bytearray(packet);b[37:40]=response.to_bytes(3,'big');b[40]=syndrome;b[41:44]=msn.to_bytes(3,'big')
            f=bytes.fromhex('b8830367c5d08af3fbb975310800')+old_message.native.qp.main.response.repair(b);control_frames.append(f)
            (run/f'control{n}.hex').write_text(''.join(f'{int.from_bytes(f[k:k+16].ljust(16,bytes(1)),"little"):032x}\n'for k in range(0,len(f),16)))
        (run/'control-owner.hex').write_text(''.join(f'{n:0120x}\n'for n in owners))
        (run/'control-core.hex').write_text(''.join(f'{n:0128x}\n'for n in cores))''')
    t=once(t,'                if mode==81:',r'''
                if mode is not None and mode>=110:
                    rows=[json.loads(s[len('CONTROL_ACK_RESULT '):])for s in c.stdout.splitlines()if s.startswith('CONTROL_ACK_RESULT ')]
                    if len(rows)!=1 or rows[0]['mode']!=mode:raise ValueError('missing control independent lifecycle assertions')
                    item['control_summary']=rows[0]
                if mode==111 or mode==114:
                    expected=control_frames if mode==114 else[control_frames[0],frames[0],recv_frame,rnr_frame,control_frames[1]]
                    if physical.frames(c.stdout)!=[(0x6001+i,f)for i,f in enumerate(expected)]:
                        raise ValueError('actual control mixed/full headers/FCS/SFD/fresh shared tags differ')
                    item['actual_control_MAC_all5_frames_verified']=True
                if mode==81:''')
    t=once(t,'        result.update(RNR_owner_bits=368,',
        '        result.update(control_owner_bits=480,control_HLS_header_bits=512,control_MAC_proof_bits=528,\n'
        '            control_component_modes=66,all78_old_modes_and_both_legacy_retained=True,control_producers_modeled=True,\n'
        '            RNR_owner_bits=368,')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),control_bench=control_bench))
