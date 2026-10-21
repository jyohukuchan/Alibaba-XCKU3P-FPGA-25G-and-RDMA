#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Certified-PSN controller lifecycle, suppression and wrap; producer models.

Four-state4ns/10s/100000-cycle checks. Checked frontend/native frontier,
HLS/ACK/MAC receipts and local reject consumer are explicit modeled inputs.
This is NOT actual native/HLS/MAC/data/RQ/PSN/CQ/Linux/physical execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest;DUT=ROOT/'rdma/rnic/rtl/rocev2_write_psn_control.v'
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_native as parser

TB=r'''
`timescale 1ns/1ps
module tb;
parameter [63:0] INITIAL_SERIAL=0;
DECLARATIONS
rocev2_write_psn_control #(.INITIAL_SERIAL(INITIAL_SERIAL)) dut(.*);
always #2 clk=~clk;
integer mode=0,cycle=0,issued=0;
reg [63:0] next_serial;
reg [479:0] expected_owner;
reg [527:0] proof;
reg [355:0] original_context;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded PSN controller deadline");
 if(dut.state!=dut.IDLE && dut.state!=dut.REPORT && (s_ready || m_error_valid))
  $fatal(1,"PSN local reject escaped before actual wire proof and ACK retirement");
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task certify;
 begin s_cert_context=trusted_context;s_cert_received_psn=s_psn;s_cert_expected_psn=trusted_expected_psn;end
endtask
task bad;
 begin
  repeat(7)tick;
  if(!fault || !configuration_guard || queue_guard!==8'hff || s_ready || m_error_valid ||
    s_ack_done_ready || m_ack_retire_valid || m_hls_owner_valid || m_ack_owner_valid || tx_release)
   $fatal(1,"invalid PSN certificate/receipt falsely released ownership");
 end
endtask
task owner_and_event;
 begin
  repeat(17)begin tick;
   if(fault || !configuration_guard || queue_guard!==(8'h01<<s_qpn) || !m_ack_owner_valid ||
    m_ack_owner!==expected_owner || m_hls_owner_valid || tx_release || m_ack_retire_valid)
    $fatal(1,"full certified480 ACK owner must precede actual HLS event");
  end
  m_ack_owner_ready=1;tick;m_ack_owner_ready=0;
  repeat(17)begin tick;if(fault || !m_hls_owner_valid || m_hls_owner!==expected_owner ||
    m_ack_owner_valid || tx_release || m_ack_retire_valid)$fatal(1,"same480 HLS owner not stable/independent");end
  m_hls_owner_ready=1;tick;m_hls_owner_ready=0;
  repeat(37)begin tick;if(fault || !tx_release || s_ready || m_error_valid || m_ack_retire_valid ||
    !configuration_guard)$fatal(1,"HLS acceptance invented wire proof or local completion");end
 end
endtask
task prepare;
 begin
  next_serial=next_serial+64'd1;
  expected_owner={4'd0,s_psn-trusted_expected_psn<24'h800000 ? 8'h60:8'h1f,s_psn,
    s_psn-trusted_expected_psn<24'h800000 ? trusted_expected_psn:trusted_expected_psn-24'd1,next_serial,trusted_context};
  proof={16'h6001+issued[15:0],8'd0,24'habc123,expected_owner};
  tick;
 end
endtask
task complete_wire;
 begin
  m_error_ready=0;s_ack_done=proof;s_ack_done_valid=1;
  @(posedge clk);if(!s_ack_done_ready)$fatal(1,"exact control528 proof rejected");
  @(negedge clk);s_ack_done_valid=0;s_ack_done=0;
  repeat(17)begin tick;if(fault || !m_ack_retire_valid || m_ack_retire_owner!==expected_owner || s_ready ||
    m_error_valid || !configuration_guard)$fatal(1,"full480 retirement must follow wire proof");end
  m_ack_retire_ready=1;tick;m_ack_retire_ready=0;
  repeat(71)begin tick;if(fault || !m_error_valid || s_ready || !configuration_guard ||
    m_ack_retire_valid)$fatal(1,"independent local consumer/backpressure not retained");end
  m_error_ready=1;@(posedge clk);if(!s_ready)$fatal(1,"real independent local reject handshake absent");
  @(negedge clk);s_valid=0;m_error_ready=0;#1;
  issued=issued+1;
  if(fault || configuration_guard || queue_guard || dut.requests!=issued || dut.wire_proofs!=issued ||
    dut.retirements!=issued || dut.reports!=issued)$fatal(1,"whole PSN negative lifecycle counts/guard");
 end
endtask
task exchange;
 begin prepare;owner_and_event;complete_wire;end
endtask
task suppressed_drop;
 begin
  s_valid=1;m_error_ready=0;certify;
  repeat(17)begin tick;if(fault || !m_error_valid || s_ready || m_ack_owner_valid || m_hls_owner_valid ||
    tx_release || dut.requests!=issued)$fatal(1,"repeated future PSN not suppressed without fake wire proof");end
  m_error_ready=1;@(posedge clk);if(!s_ready)$fatal(1,"suppressed local reject handshake");
  @(negedge clk);s_valid=0;m_error_ready=0;#1;
  if(configuration_guard || queue_guard || dut.suppressed!=1 || dut.wire_proofs!=issued || dut.reports!=issued)
   $fatal(1,"suppression fabricated wire/retirement counters");
 end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))$fatal(1,"mode required");
 next_serial=INITIAL_SERIAL;rst=1;repeat(5)@(negedge clk);rst=0;
 enable=1;trusted_valid=1;
 trusted_context={4'd2,48'hb8830367c5d0,48'h8af3fbb97531,32'hc6120b01,32'hc6120b02,
 24'd196,64'h123456789abcdef0,64'hfedcba9876543210,16'd7,24'd2};
 original_context=trusted_context;trusted_expected_psn=24'hffffff;
 s_error=18;s_qpn=2;s_psn=2;s_msn=0;s_keep_message=1;s_valid=1;s_cert_valid=1;certify;
 if(mode==1 || mode==7 || mode==11)begin
  trusted_expected_psn=mode==11 ? 24'd1:24'd0;s_psn=24'hfffffe;certify;
 end
 if(mode==12)begin s_psn=trusted_expected_psn+24'h7fffff;certify;end
 if(mode>=2 && mode<=5)begin
  if(mode==2)s_error=16;
  if(mode==3)enable=0;
  if(mode==4)s_cert_valid=0;
  if(mode==5)begin s_psn=trusted_expected_psn+24'h800000;certify;end
  repeat(17)begin tick;if(fault || !m_error_valid || s_ready || m_ack_owner_valid || m_hls_owner_valid || tx_release)
   $fatal(1,"ordinary/disabled/uncertified/half-window local reject changed");end
  m_error_ready=1;@(posedge clk);if(!s_ready)$fatal(1,"local-only reject consumption");
  @(negedge clk);s_valid=0;m_error_ready=0;#1;
  if(dut.requests || dut.wire_proofs || dut.retirements || dut.reports)$fatal(1,"local reject fabricated wire proof");
 end else if(mode<=15 && mode!=14)begin
  if(mode==15)m_error_ready=1;
  exchange;
  if(mode==6)begin
   suppressed_drop;trusted_expected_psn=0;s_psn=3;certify;tick;s_valid=1;exchange;
  end
  if(mode==7)begin s_valid=1;exchange;if(dut.suppressed)$fatal(1,"duplicate ACK incorrectly suppressed");end
  if(mode==8 || mode==9)begin
   if(mode==8)trusted_context[103:40]=trusted_context[103:40]+64'd1;
   else trusted_context[167:104]=trusted_context[167:104]+64'd1;
   certify;tick;s_valid=1;exchange;
  end
  if(mode==10)begin
   trusted_context[23:0]=3;s_qpn=3;certify;tick;s_valid=1;exchange;
   trusted_context=original_context;s_qpn=2;certify;tick;suppressed_drop;
  end
  if(mode==13)begin s_psn=24'hfffffe;certify;s_valid=1;tick;bad;end
 end else if(mode==14)begin tick;bad;end
 else begin
  case(mode)
   20:trusted_valid=0;
   21:begin trusted_context[23:0]=24'h800002;s_qpn=24'h800002;certify;end
   22:begin trusted_context[39:24]=0;certify;end
   23:begin trusted_context[103:40]=0;certify;end
   24:begin trusted_context[167:104]=0;certify;end
   25:begin trusted_context[353]=0;certify;end
   26:s_cert_context[256]=~s_cert_context[256];
   27:s_cert_received_psn[0]=~s_cert_received_psn[0];
   28:s_cert_expected_psn[0]=~s_cert_expected_psn[0];
   29:s_qpn=3;
   30:s_error[0]=1'bx;
   31:s_valid=1'bx;
   32:s_cert_valid=1'bx;
   33:s_cert_context[100]=1'bx;
   34:trusted_expected_psn[0]=1'bx;
   35:parent_fault=1;
   36:begin s_ack_done=0;s_ack_done_valid=1;end
  endcase
  if(mode<=36)begin tick;bad;end
  else begin
   prepare;
   if(mode==37)begin s_ack_done=proof;s_ack_done_valid=1;bad;end
   else if(mode==38)begin s_valid=0;bad;end
   else if(mode==39)begin s_cert_context[40]=~s_cert_context[40];bad;end
   else if(mode==46)begin s_valid=1'bx;bad;end
   else if(mode==47)begin s_psn=s_psn+24'd1;bad;end
   else begin
    owner_and_event;s_ack_done=proof;s_ack_done_valid=1;
    case(mode)
     40:s_ack_done[40]=~s_ack_done[40];
     41:s_ack_done[356]=~s_ack_done[356];
     42:s_ack_done[504]=1;
     43:s_ack_done[527:512]=16'h4001;
     44:s_ack_done[527:512]=16'h6000;
     45:s_ack_done_valid=1'bx;
     48:s_ack_done[480]=1'bx;
    endcase
    if(mode==49)begin tick;end
    bad;
   end
  end
 end
 $display("WRITE_PSN_CONTROL_RESULT {\"pass_test\":true,\"mode\":%0d,\"issued\":%0d,\"requests\":%0d,\"proofs\":%0d,\"suppressed\":%0d,\"fault\":%0d,\"cycles\":%0d}",
 mode,issued,requests,wire_proofs,suppressed,fault,cycle);$finish;
end
endmodule
'''


def bench():
    fields=parser.ports(DUT.read_text())
    decl='\n'.join(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';')for d,w,n in fields)
    return TB.replace('DECLARATIONS',decl)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    run=Path(tempfile.mkdtemp(prefix='write-psn-control-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-psn-control-',dir='/dev/shm'))
    before={str(n.relative_to(ROOT)):digest(n)for n in [Path(__file__).resolve(),DUT]}
    modes=[*range(16),*range(20,50)]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},compilations={},planned_modes=modes,
        clock_ns=4,runtime_limit_seconds=10,compile_limit_seconds=10,cycle_limit=100000,producer_boundaries_modeled=True,
        actual_native_or_HLS_or_MAC=False,hardware_verified=False,overall_goal_complete=False)
    try:
        (run/'tb.v').write_text(bench());(run/DUT.name).write_text(DUT.read_text())
        for name,initial in [('normal',0),('near-exhausted',2**64-2),('exhausted',2**64-1)]:
            start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-Ptb.INITIAL_SERIAL='+str(initial),'-o',str(ram/name),str(run/'tb.v'),str(run/DUT.name)],capture_output=True,text=True,timeout=10)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr);r['compilations'][name]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            if c.returncode:raise ValueError('compile failed:'+name)
        for n in modes:
            name='near-exhausted'if n==13 else'exhausted'if n==14 else'normal'
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/name),'+MODE='+str(n)],capture_output=True,text=True,timeout=10)
            (run/(str(n)+'.log')).write_text(c.stdout+c.stderr);t=dict(exit=c.returncode,seconds=time.monotonic()-start);r['tests'][str(n)]=t
            if c.returncode:raise ValueError('simulation failed:'+str(n))
            rows=[json.loads(s.removeprefix('WRITE_PSN_CONTROL_RESULT '))for s in c.stdout.splitlines()if s.startswith('WRITE_PSN_CONTROL_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['mode']!=n:raise ValueError('actual controller assertions absent')
            t['summary']=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during execution')
        r.update(pass_test=True,source_unchanged=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        r['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(r['tests']),maximum_seconds=max(t['seconds']for t in r['tests'].values()),native=False)))


if __name__=='__main__':main()
