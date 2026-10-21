#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Selected-WRITE abort RTL consumer; native/HLS/MAC/quarantine inputs modeled.

Four-state4ns/10s/100000-cycle checks. Not integrated native/error CQ/STOP/
QP-global drain/unpin/physical proof. Full proofs and quarantine must stay.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding
ROOT=binding.ROOT;digest=binding.digest;DUT=ROOT/'rdma/rnic/rtl/rocev2_write_abort_control.v'
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_native as parser

TB=r'''
`timescale 1ns/1ps
module tb;
DECLARATIONS
rocev2_write_abort_control dut(.*);
always #2 clk=~clk;
integer mode=0,cycles=0;
reg [423:0] p,last_packet;
reg [479:0] error_owner;
reg [959:0] expected_owner;
reg [999:0] expected_done,observed_done;
reg [23:0] msn;
reg [15:0] last_mac,error_mac;
reg partial;
function [355:0] context_for;
 input [23:0] q;
 begin context_for={4'he,48'hb8830367c5d0,48'h8af3fbb97531,32'hc6120b01,32'hc6120b02,
  24'd196,64'hfedcba9889abcdef,64'h9123456700000001,16'd17,q};end
endfunction
function [423:0] packet_for;
 input [23:0] q;input [31:0] total,offset;input [23:0] psn,first;input [15:0] tag;
 begin packet_for={q,16'd17,64'h9123456700000001,64'hfedcba9876543211,32'h81234567,
  64'he23456789abcdef0,total,first,offset,total-offset>4096 ? 32'd4096:total-offset,psn,tag};end
endfunction
always @(posedge clk)if(!rst)begin cycles=cycles+1;if(cycles>100000)$fatal(1,"original bounded abort consumer deadline");end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task bad;
 begin repeat(8)tick;
  if(!fault || !configuration_guard || queue_guard!==8'hff || error_wire_ready ||
   m_hls_owner_valid || s_hls_done_ready || m_report_release || m_cancel_valid || m_cancel_certified || m_done_valid)
   $fatal(1,"bad abort ownership/proof escaped quarantine or invented selected completion");
 end
endtask
task wire_packet;
 input [423:0] token;input [23:0] packet_msn;input [15:0] mac;
 begin
  trusted_context=context_for(token[423:400]);trusted_expected_psn=token[39:16];
  positive_wire={mac,8'd0,packet_msn,token};positive_wire_taken=1;tick;positive_wire_taken=0;
 end
endtask
task commit_packet;
 input [423:0] token;input [23:0] packet_msn;
 begin
  positive_commit_token=token;positive_commit_msn=packet_msn;positive_commit_proofs=8'h0f;
  positive_commit_taken=1;tick;positive_commit_taken=0;
 end
endtask
task retire_packet;
 input [423:0] token;
 begin trusted_expected_psn=token[39:16]+24'd1;positive_retire_token=token;
  positive_retire_taken=1;tick;positive_retire_taken=0;
 end
endtask
task real_packet;
 input [423:0] token;input [23:0] packet_msn;input [15:0] mac;
 begin wire_packet(token,packet_msn,mac);commit_packet(token,packet_msn);retire_packet(token);
  if(fault)$fatal(1,"genuine modeled full positive ownership was rejected");
 end
endtask
task prepare_error;
 begin
  quarantine_context=trusted_context;quarantine_valid=1;message_active=partial;
  message_context=last_packet[423:104];
  error_owner={4'd0,mode==1 ? 8'h61:mode==2 ? 8'h63:8'h62,trusted_expected_psn,trusted_expected_psn,
   64'ha123456700000001,trusted_context};
  error_wire={error_mac,8'd0,msn,error_owner};
  expected_owner={8'd0,partial ? 8'h0f:8'd0,partial ? last_mac:16'd0,msn,error_owner,partial ? last_packet:424'd0};
  expected_done={8'h07,8'd0,msn,expected_owner};
 end
endtask
task accept_error;
 begin error_wire_valid=1;tick;error_wire_valid=0;
  if(fault || quarantined!==8'h04 || !configuration_guard || requests!=1)$fatal(1,"fatal admission did not retain exact QP quarantine");
  repeat(17)begin tick;if(m_hls_owner_valid || m_report_release || m_cancel_valid || m_done_valid)$fatal(1,"fatal MAC proof substituted for ACK retirement");end
  error_retire_owner=error_owner;error_retire_taken=1;tick;error_retire_taken=0;
 end
endtask
task accept_owner;
 begin
  repeat(17)begin tick;
   if(fault || !m_hls_owner_valid || m_hls_owner!==expected_owner || m_report_release || m_cancel_valid || m_done_valid)
    $fatal(1,"full960 abort owner unstable or completion escaped before actual HLS");
  end
  m_hls_owner_ready=1;tick;m_hls_owner_ready=0;
  repeat(37)begin tick;if(m_report_release || m_cancel_valid || m_done_valid)$fatal(1,"HLS READY invented abort992 proof");end
 end
endtask
task accept_hls;
 begin s_hls_done={8'd0,msn,expected_owner};s_hls_done_valid=1;tick;s_hls_done_valid=0;
  repeat(17)begin tick;if(fault || !m_report_release || m_cancel_valid || m_done_valid)$fatal(1,"actual HLS completion failed to retain local reject ownership");end
 end
endtask
task finish_selected;
 begin
  local_report_owner=error_owner;local_report_taken=1;tick;local_report_taken=0;
  if(partial)begin
   repeat(37)begin tick;if(fault || !m_cancel_valid || !m_cancel_certified || m_cancel_context!==last_packet[423:104] || m_done_valid)
    $fatal(1,"selected native cancel not tied to actual prior packet/HLS/local error proofs");end
   m_cancel_ready=1;tick;m_cancel_ready=0;message_active=0;
  end
  tick;
  repeat(71)begin tick;
   if(fault || !m_done_valid || m_done!==expected_done || queue_guard!==8'h04 || !configuration_guard ||
    m_cancel_valid || m_report_release || m_hls_owner_valid)$fatal(1,"full1000 selected proof lost under withholding");
  end
  observed_done=m_done;m_done_ready=1;tick;m_done_ready=0;repeat(7)tick;
  if(fault || m_done_valid || quarantined!==8'h04 || queue_guard!==8'h04 || !configuration_guard ||
   requests!=1 || hls_completions!=1 || completions!=1 || cancels!=(partial ? 1:0))
   $fatal(1,"selected completion reopened quarantine or duplicated an ownership event");
 end
endtask
// INITIAL_BODY
endmodule
'''

INITIAL=r'''
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 rst=1;repeat(3)tick;rst=0;enable=1;trusted_valid=1;
 trusted_context=context_for(2);trusted_expected_psn=24'hfffffe;
 p=packet_for(2,8193,0,24'hfffffe,24'hfffffe,1);
 last_packet=p;msn=0;last_mac=16'h6001;error_mac=16'h6002;partial=1;
 if(mode>=20 && mode<=41)begin
  if(mode<=34)begin
   positive_wire={16'h6001,8'd0,24'd0,p};
   case(mode)
    20:positive_wire[423:400]=24'h800002;
    21:positive_wire[399:384]=18;
    22:positive_wire[320]=~positive_wire[320];
    23:positive_wire[319:256]=0;
    24:positive_wire[255:224]=0;
    25:positive_wire[159:128]=4096;
    26:positive_wire[103:72]=1;
    27:positive_wire[71:40]=4095;
    28:positive_wire[16]=~positive_wire[16];
    29:positive_wire[15:0]=0;
    30:positive_wire[455:448]=1;
    31:positive_wire[471:456]=16'h4001;
    32:positive_wire[471:456]=16'h6000;
    33:positive_wire[424]=1'bx;
   endcase
   positive_wire_taken=mode==34 ? 1'bx:1'b1;tick;positive_wire_taken=0;bad;
  end else begin
   if(mode!=38)wire_packet(p,0,16'h6001);
   if(mode>=39)begin
    if(mode!=39)commit_packet(p,0);
    trusted_expected_psn=mode==41 ? 24'd0:24'hffffff;
    positive_retire_token=p;if(mode==40)positive_retire_token[0]=~positive_retire_token[0];
    positive_retire_taken=1;tick;positive_retire_taken=0;
   end else begin
    positive_commit_token=p;positive_commit_msn=0;positive_commit_proofs=8'h0f;
    if(mode==35)positive_commit_proofs=7;
    if(mode==36)positive_commit_token[256]=~positive_commit_token[256];
    if(mode==37)positive_commit_msn=1;
    positive_commit_taken=1;tick;positive_commit_taken=0;
   end
   bad;
  end
 end else begin
  if(mode==4)begin
   real_packet(packet_for(3,4097,0,24'h123456,24'h123456,1),0,16'h6001);last_mac=16'h6002;error_mac=16'h6003;
  end
  if(mode==2)begin partial=0;last_packet=0;last_mac=0;error_mac=16'h6001;end
  else begin
   if(mode==3)p=packet_for(2,4097,0,24'hfffffe,24'hfffffe,1);
   if(mode==67)wire_packet(p,0,last_mac);
   else if(mode==68)begin wire_packet(p,0,last_mac);commit_packet(p,0);end
   else real_packet(p,0,last_mac);
   last_packet=p;
   if(mode==1 || mode==3)begin
    p=packet_for(2,mode==3 ? 4097:8193,4096,24'hffffff,24'hfffffe,2);
    msn=mode==3 ? 1:0;real_packet(p,msn,16'h6002);last_packet=p;last_mac=16'h6002;error_mac=16'h6003;
    if(mode==3)partial=0;
   end
  end
  prepare_error;
  case(mode)
   50:quarantine_valid=0;
   51:quarantine_context[104]=~quarantine_context[104];
   52:error_wire[104]=~error_wire[104];
   53:error_wire[444]=~error_wire[444];
   54:error_wire[420]=~error_wire[420];
   55:error_wire[475:468]=8'h60;
   56:error_wire[476]=1;
   57:error_wire[419:356]=0;
   58:error_wire[504]=1;
   59:error_wire[527:512]=16'h4001;
   60:error_wire[527:512]=16'h6000;
   61:error_wire[527:512]=16'h6001;
   62:error_wire[480]=~error_wire[480];
   63:message_active=0;
   64:message_context[152]=~message_context[152];
   65:trusted_context[39:24]=0;
   87:enable=0;
   88:trusted_valid=0;
  endcase
  if(mode>=50 && mode<=68 || mode==87 || mode==88)begin
   error_wire_valid=mode==66 ? 1'bx:1'b1;tick;error_wire_valid=0;bad;
  end else if(mode==69 || mode==79 || mode==80 || mode==82 || mode==86)begin
   error_wire_valid=1;tick;error_wire_valid=0;
   case(mode)
    69:begin error_retire_owner=error_owner;error_retire_owner[104]=~error_retire_owner[104];error_retire_taken=1;end
    79:trusted_context[104]=~trusted_context[104];
    80:parent_fault=1;
    82:error_retire_taken=1'bx;
    86:error_wire_valid=1;
   endcase
   bad;
  end else begin
   accept_error;
   if(mode==70 || mode==75 || mode==81)begin
    case(mode)
     70:begin s_hls_done={8'd0,msn,expected_owner};s_hls_done_valid=1;end
     75:begin local_report_owner=error_owner;local_report_taken=1;end
     81:positive_wire_taken=1;
    endcase
    bad;
   end else begin
    accept_owner;
    if(mode>=71 && mode<=74)begin
     s_hls_done={8'd0,msn,expected_owner};
     case(mode)
      71:s_hls_done[0]=~s_hls_done[0];
      72:s_hls_done[960]=~s_hls_done[960];
      73:s_hls_done[984]=1;
      74:s_hls_done[904]=1'bx;
     endcase
     s_hls_done_valid=1;bad;
    end else begin
     accept_hls;
     if(mode==76 || mode==83)begin
      local_report_owner=error_owner;if(mode==76)local_report_owner[40]=~local_report_owner[40];
      local_report_taken=mode==83 ? 1'bx:1'b1;bad;
     end else if(mode==77 || mode==78)begin
      local_report_owner=error_owner;local_report_taken=1;tick;local_report_taken=0;
      m_cancel_ready=mode==77 ? 1'bx:1'b1;bad;
     end else begin
      finish_selected;
      if(mode==84)begin error_wire[527:512]=error_mac+16'd1;error_wire_valid=1;bad;end
      else if(mode==85)begin wire_packet(p,0,error_mac+16'd1);bad;end
      else begin
       if(mode==4)real_packet(packet_for(3,4097,4096,24'h123457,24'h123456,2),1,16'h6004);
       if(fault || queue_guard!==8'h04)$fatal(1,"unrelated QP history damaged or fatal quarantine cleared");
       $display("WRITE_ABORT_CONTROL_OWNER %0d %0240h %0250h",mode,expected_owner,observed_done);
      end
     end
    end
   end
  end
 end
 $display("WRITE_ABORT_CONTROL_RESULT {\"pass_test\":true,\"mode\":%0d,\"fault\":%0d,\"cycles\":%0d,\"requests\":%0d,\"completions\":%0d,\"quarantine\":%0d}",mode,fault,cycles,requests,completions,quarantined);
 $finish;
end
'''


def bench():
    # The shared declaration reader expects a parameter-list separator. Adapt
    # only its input text; the actual compiled parameterless DUT is unchanged.
    text=DUT.read_text();anchor='module rocev2_write_abort_control('
    if text.count(anchor)!=1:raise ValueError('actual module header changed')
    declarations=text.replace(anchor,'module rocev2_write_abort_control #()(\n')
    decl='\n'.join(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';')
        for d,w,n in parser.ports(declarations))
    return TB.replace('DECLARATIONS',decl).replace('// INITIAL_BODY',INITIAL)


def verify_owner(output,mode):
    rows=[s.split()for s in output.splitlines()if s.startswith('WRITE_ABORT_CONTROL_OWNER ')]
    if len(rows)!=1 or len(rows[0])!=4 or int(rows[0][1])!=mode:raise ValueError('actual complete960/1000 owner output missing')
    context=0
    for w,v in [(4,14),(48,0xb8830367c5d0),(48,0x8af3fbb97531),(32,0xc6120b01),(32,0xc6120b02),
        (24,196),(64,0xfedcba9889abcdef),(64,0x9123456700000001),(16,17),(24,2)]:context=(context<<w)|v
    empty=mode in [2,3];msn=int(mode==3);psn=0 if mode in [1,3]else 0xfffffe if mode==2 else 0xffffff
    control=((0x61 if mode==1 else 0x63 if mode==2 else 0x62)<<468)|(psn<<444)|(psn<<420)|(0xa123456700000001<<356)|context
    packet=0;mac=0
    if not empty:
        off=4096 if mode==1 else 0
        for w,v in [(24,2),(16,17),(64,0x9123456700000001),(64,0xfedcba9876543211),(32,0x81234567),
            (64,0xe23456789abcdef0),(32,8193),(24,0xfffffe),(32,off),(32,4096),(24,0xffffff if mode==1 else 0xfffffe),(16,2 if mode==1 else 1)]:packet=(packet<<w)|v
        mac=0x6002 if mode in [1,4]else 0x6001
    owner=packet|(control<<424)|(msn<<904)|(mac<<928)|((0 if empty else 15)<<944)
    done=owner|(msn<<960)|(7<<992)
    if int(rows[0][2],16)!=owner or int(rows[0][3],16)!=done:raise ValueError('independent every960/1000 selected owner/receipt bit mismatch')
    return dict(owner960=f'{owner:0240x}',selected_receipt1000=f'{done:0250x}',not_QP_global_or_unpin=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='write-abort-control-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-abort-control-',dir='/dev/shm'))
    before={str(n.relative_to(ROOT)):digest(n)for n in [Path(__file__).resolve(),DUT,Path(parser.__file__).resolve()]}
    modes=[*range(5),*range(20,42),*range(50,89)]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},planned_modes=modes,
        clock_ns=4,runtime_limit_seconds=10,compile_limit_seconds=10,cycle_limit=100000,producer_boundaries_modeled=True,
        actual_native_or_HLS_or_MAC=False,QP_global_drain_or_unpin=False,hardware_verified=False,overall_goal_complete=False)
    try:
        (run/'tb.v').write_text(bench());(run/DUT.name).write_text(DUT.read_text())
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/DUT.name)],capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);r['compilation']=dict(exit=c.returncode,seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('actual bridge compile failed')
        for n in modes:
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test'),'+MODE='+str(n)],capture_output=True,text=True,timeout=10)
            (run/(str(n)+'.log')).write_text(c.stdout+c.stderr);t=dict(exit=c.returncode,seconds=time.monotonic()-start);r['tests'][str(n)]=t
            if c.returncode:raise ValueError('actual abort controller failed:'+str(n))
            rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_ABORT_CONTROL_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['mode']!=n or bool(rows[0]['fault'])!=(n>=20):raise ValueError('actual assertion/fail-closed witness missing')
            t['summary']=rows[0]
            if n<5:t['independent_oracles']=verify_owner(c.stdout,n)
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during execution')
        r.update(pass_test=True,source_unchanged=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        r['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(r['tests']),maximum_seconds=max(t['seconds']for t in r['tests'].values()),native=False)))


if __name__=='__main__':main()
