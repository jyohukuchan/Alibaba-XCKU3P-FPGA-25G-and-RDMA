#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real retained-WRITE RNR controller handshakes; owner/ACK/HLS edges modeled.

No generated HLS, actual MAC/native RX/RQ/DMA/PSN or software proof follows.
Never interpret READY, idle, local report or a reset as a wire certificate.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest;DUT=ROOT/'rdma/rnic/rtl/rocev2_segmented_write_rnr_control.v'

TB=r'''
`timescale 1ns/1ps
module tb;
DECLARATIONS
rocev2_segmented_write_rnr_control dut(.*);
always #2 clk=~clk;
integer mode=0,cycle=0;
reg [319:0] msg={24'd2,16'd17,64'h9123456700000001,64'd1,32'd8,64'hfedcba9876543210,32'd8193,24'h987654};
reg [367:0] expected_owner;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded controller geometry");
 if(mode!=1 && mode!=2 && !fault && dut.state!=dut.REPORT && (s_ready || m_error_valid))
  $fatal(1,"local rejection consumed before real wire proof and exact retirement");
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task held;
 begin tick;if(!configuration_guard || queue_guard!==4 || fault || s_ready || m_error_valid)$fatal(1,"held authentic RNR identity/guard");end
endtask
task admit;
 begin
  repeat(17)begin held;if(!m_ack_owner_valid || m_ack_owner!==expected_owner || m_hls_event_valid || tx_release)
   $fatal(1,"full RNR owner must precede actual HLS event");end
  m_ack_owner_ready=1;tick;m_ack_owner_ready=0;
 end
endtask
task issue;
 begin
  repeat(17)begin held;if(!m_hls_event_valid || m_hls_event!=={8'h20,24'h987656,24'd2} || tx_release || m_ack_retire_valid)
   $fatal(1,"actual HLS RNR event must transfer before TX permission");end
  m_hls_event_ready=1;tick;m_hls_event_ready=0;
 end
endtask
task bad;
 begin
  repeat(4)tick;
  if(!fault || !configuration_guard || queue_guard!==8'hff || s_ready || m_error_valid || s_ack_done_ready || m_ack_retire_valid)
   $fatal(1,"bad RNR context/proof released owner or acknowledged reject");
 end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))$fatal(1,"mode required");rst=1;repeat(5)@(negedge clk);rst=0;
 enable=1;trusted_valid=1;trusted_identity={64'h9123456700000001,16'd17,24'd2};expected_psn=24'h987656;
 message_context=msg;message_active=1;mr_guard=1;message_queue_guard=4;
 s_error=38;s_qpn=2;s_psn=24'h987656;s_msn=0;s_keep_message=1;s_valid=1;m_error_ready=0;
 expected_owner={24'd0,24'h987656,msg};
 if(mode==1 || mode==2)begin
  if(mode==1)s_error=16;else enable=0;
  repeat(17)begin tick;if(!m_error_valid || s_ready || configuration_guard || m_ack_owner_valid || m_hls_event_valid)
   $fatal(1,"ordinary/disabled reject pass-through changed");end
  m_error_ready=1;@(posedge clk);if(!s_ready)$fatal(1,"ordinary reject consumer handshake");@(negedge clk);s_valid=0;
 end else begin
  case(mode)
   3:trusted_identity[23:0]=24'h800002;
   4:trusted_identity[39:24]=0;
   5:trusted_identity[103:40]=0;
   6:message_context[151:120]=0;
   7:message_context[215:152]=0;
   8:message_context[55:24]=4096;
   9:mr_guard=0;
   10:message_queue_guard=0;
   11:s_keep_message=0;
   12:s_psn=24'h987655;
   13:message_context[280]=~message_context[280];
   14:s_msn[0]=1'bx;
  endcase
  tick;
  if(mode>=3 && mode<=14)bad;
  else begin
   if(mode==19)s_valid=0;
   if(mode==20)trusted_identity[103]=~trusted_identity[103];
   if(mode==22)s_valid=1'bx;
   if(mode==19 || mode==20 || mode==22)bad;
   else begin
    admit;
    if(mode==15)begin s_ack_done={16'h6001,expected_owner};s_ack_done_valid=1;bad;end
    else if(mode==21)begin parent_fault=1;bad;end
    else begin
     issue;
     if(!tx_release)$fatal(1,"real HLS event acceptance lost RNR TX lease");
     s_ack_done={16'h6001,expected_owner};
     repeat(17)begin held;if(wire_proofs || m_ack_retire_valid)$fatal(1,"READY/data without proof VALID counted");end
     if(mode==16)s_ack_done[0]=~s_ack_done[0];
     if(mode==17)s_ack_done[383:368]=16'h4000;
     if(mode==18)s_ack_done[344]=~s_ack_done[344];
     s_ack_done_valid=mode==23 ? 1'bx:1'b1;
     if(mode>=16 && mode<=18 || mode==23)bad;
     else begin
      tick;s_ack_done_valid=0;
      if(wire_proofs!=1 || !m_ack_retire_valid || m_ack_retire_owner!==expected_owner)$fatal(1,"exact typed wire proof before ACK retirement");
      repeat(17)held;m_ack_retire_ready=1;tick;m_ack_retire_ready=0;
      repeat(17)begin tick;if(!m_error_valid || s_ready || !configuration_guard || retirements!=1 || reports)
       $fatal(1,"independent local reject consumer escaped");end
      m_error_ready=1;@(posedge clk);if(!s_ready)$fatal(1,"local reject exact handshake after actual negative wire proof");
      // Observe after continuous assignments settle, within the SAME4ns cycle.
      // Frozen002 plus the read-only observer retain the original failure.
      @(negedge clk);s_valid=0;#1;
      if(configuration_guard || queue_guard || requests!=1 || wire_proofs!=1 || retirements!=1 || reports!=1 || fault)
       $fatal(1,"complete RNR control lifecycle counts");
     end
    end
   end
  end
 end
 $display("WRITE_RNR_CONTROL_RESULT {\"pass_test\":true,\"mode\":%0d,\"fault\":%0d,\"requests\":%0d,\"proofs\":%0d,\"retirements\":%0d,\"reports\":%0d}",mode,fault,requests,wire_proofs,retirements,reports);$finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every earlier report')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-rnr-control-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-write-rnr-control-',dir='/dev/shm'))
    inputs=[DUT,Path(__file__).resolve()];before={str(q.relative_to(ROOT)):digest(q)for q in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        compile_limit_seconds=10,runtime_limit_seconds=10,clock_ns=4,cycle_limit=100000,actual_native_or_HLS_or_MAC=False,hardware_verified=False)
    try:
        header=DUT.read_text().split('module rocev2_segmented_write_rnr_control(',1)[1].split('\n);',1)[0]
        fields=[];direction=None;width=''
        for part in header.split(','):
            part=part.strip();m=re.fullmatch(r'(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s*)?(\w+)(?:=\S+)?',part)
            if m:direction,width,n=m[1],m[2]or'',m[3]
            else:
                n=part.split('=')[0]
                if direction is None or not re.fullmatch(r'\w+',n):raise ValueError('exact helper port required:'+part)
            fields.append(('reg 'if direction=='input'else'wire ')+width+n+('=0;'if direction=='input'else';'))
        (run/'tb.v').write_text(TB.replace('DECLARATIONS','\n'.join(fields)))
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(DUT)],capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual RNR control compile failed')
        for mode in range(24):
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test'),f'+MODE={mode}'],cwd=run,capture_output=True,text=True,timeout=10)
            (run/f'{mode}.log').write_text(c.stdout+c.stderr);r=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=r
            if c.returncode:raise ValueError('actual RNR control failed:'+str(mode))
            rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_RNR_CONTROL_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('full control assertions missing')
            r['summary']=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=24)),flush=True)


if __name__=='__main__':main()
