#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual RX refs with the exact production continuation-enable expression.

QP/MR/pause/group/pending/trusted context and checker are explicit boundary
models. This unit is NOT a received-payload/native completion proof. Preserve
offered-frame/context/reference guards and reject unknown pending/group. An
unchanged old-gate negative control must fail the SAME continuation assertion.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive_continuation as source
REFS=source.RTL/'rocev2_native_rx_refs.v'


def digest(p):
    with Path(p).open('rb')as f:return __import__('hashlib').file_digest(f,'sha256').hexdigest()


def enable(text):
    start=text.index('rocev2_native_rx_refs input_references(');start=text.index('.enable(',start)+len('.enable(')
    end=start;depth=1
    while depth:
        if text[end]=='(':depth+=1
        elif text[end]==')':depth-=1
        end+=1
    return text[start:end-1]


TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1;always #2 clk=~clk;
reg qp_ready=1,admission_paused=0,mr_management_idle=1,cfg_qp_valid=0;
localparam RECV_CQ_ENABLE=1;
reg recv_completion_pending=0,recv_group_active=0;
reg trusted_valid=1,parent_fault=0;
reg [355:0] trusted_context={4'd3,48'hb8830367c5d0,48'h8af3fbb97531,32'hc6120b01,32'hc6120b02,24'd196,
 64'hfedcba9889abcdef,64'h9123456700000001,16'd17,24'd2};
reg [127:0] s_data=128'h11223344;reg [15:0] s_keep=16'hffff;
reg s_valid=0,s_last=0,s_user=0,m_ready=0,checked_eof=0,checker_drop=0;
wire s_ready,m_valid,m_last,m_user,configuration_guard,fault;
wire [127:0] m_data;wire [15:0] m_keep;wire [355:0] held_context;
wire [7:0] queue_guard;wire [15:0] refs;
wire actual_enable=ENABLE_EXPRESSION;
rocev2_native_rx_refs dut(.clk(clk),.rst(rst),.enable(actual_enable),.parent_fault(parent_fault),
 .trusted_valid(trusted_valid),.trusted_context(trusted_context),.s_data(s_data),.s_keep(s_keep),
 .s_valid(s_valid),.s_ready(s_ready),.s_last(s_last),.s_user(s_user),.m_data(m_data),.m_keep(m_keep),
 .m_valid(m_valid),.m_ready(m_ready),.m_last(m_last),.m_user(m_user),.checked_eof(checked_eof),
 .checker_drop(checker_drop),.held_context(held_context),.configuration_guard(configuration_guard),
 .queue_guard(queue_guard),.references(refs),.fault(fault));
integer scenario=0;
initial begin
 if($value$plusargs("case=%d",scenario))begin end
 repeat(4)@(negedge clk);rst=0;
 if(scenario!=0)begin recv_completion_pending=1;recv_group_active=1;end
 case(scenario)
 2:recv_group_active=0;3:admission_paused=1;4:mr_management_idle=0;5:cfg_qp_valid=1;
 6:qp_ready=0;7:recv_completion_pending=1'bx;8:recv_group_active=1'bx;
 endcase
 s_valid=1;#1;
 if(scenario<=1)begin
  if(m_valid!==1 || s_ready!==0 || configuration_guard!==1 || queue_guard!==4 || fault)
   $fatal(1,"KNOWN_CONTINUATION_OR_NORMAL_SOP_NOT_OFFERED");
  repeat(3)@(negedge clk);
  if(held_context!==trusted_context || refs || m_valid!==1)$fatal(1,"offered receive context was not retained");
  // Actual refs preserve an offered packet after a later management pause.
  admission_paused=1;mr_management_idle=0;recv_group_active=0;m_ready=1;
  @(posedge clk);@(negedge clk);
  if(refs!==1 || !configuration_guard || queue_guard!==4 || fault)$fatal(1,"actual raw receive reference not acquired");
  s_data=128'h55667788;s_last=1;#1;
  if(m_valid!==1 || s_ready!==1 || m_data!==s_data || !m_last)$fatal(1,"already-offered frame did not drain");
  @(posedge clk);@(negedge clk);s_valid=0;
  if(refs!==1 || !configuration_guard || queue_guard!==4)$fatal(1,"raw EOF invented checker completion");
  checked_eof=1;@(posedge clk);@(negedge clk);checked_eof=0;#1;
  if(refs || configuration_guard || queue_guard || fault)$fatal(1,"actual checked EOF did not release its own raw reference");
 end else begin
  repeat(7)@(negedge clk);
  if(m_valid || s_ready || refs || configuration_guard || queue_guard || fault)
   $fatal(1,"blocked/unknown metadata granted raw receive authority");
 end
 $display("RECEIVE_CONTINUATION_GATE {\"pass_test\":true,\"case\":%0d}",scenario);$finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    current=source.derive();previous=source.base.derive()
    expressions={'current':enable(current[source.GUARD]),'old':enable(previous[source.GUARD])}
    if current[REFS]!=previous[REFS]:raise ValueError('actual RX reference state machine must remain byte-identical')
    run=Path(tempfile.mkdtemp(prefix='receive-continuation-gate-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-continuation-',dir='/dev/shm'))
    rtl=run/REFS.name;rtl.write_text(current[REFS])
    inputs=[Path(__file__).resolve(),REFS,*list((ROOT/'rdma/rnic/fpga').glob('derive_*.py'))]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        runtime_limit_seconds=10,actual_reference_RTL=True,production_enable_expressions=expressions,
        metadata_and_checker_models=True,native_or_payload_or_physical=False,hardware_verified=False)
    try:
        for label,expression in expressions.items():
            tb=run/(label+'.v');tb.write_text(TB.replace('ENABLE_EXPRESSION',expression))
            command=['iverilog','-g2012','-s','tb','-o',str(ram/label),str(tb),str(rtl)]
            c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/(label+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('actual reference/gate compile failed:'+str(run/(label+'-compile.log')))
            for case in range(9)if label=='current'else[1]:
                start=time.monotonic();c=subprocess.run(['vvp',str(ram/label),'+case='+str(case)],capture_output=True,text=True,timeout=10)
                (run/(label+'-'+str(case)+'.log')).write_text(c.stdout+c.stderr)
                result['tests'][label+'-'+str(case)]=dict(exit=c.returncode,seconds=time.monotonic()-start,old_gate_negative_control=label=='old')
                if label=='old':
                    if c.returncode==0 or 'KNOWN_CONTINUATION_OR_NORMAL_SOP_NOT_OFFERED'not in c.stdout:
                        raise ValueError('unchanged old gate must fail the SAME continuation assertion')
                elif c.returncode or 'RECEIVE_CONTINUATION_GATE 'not in c.stdout:raise ValueError('actual reference/control test failed')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,all9_current_cases=True,old_gate_negative_control_failed_as_expected=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        result['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,current_cases=9,old_gate_negative_control=True,maximum_case_seconds=max(v['seconds']for v in result['tests'].values()))),flush=True)


if __name__=='__main__':main()
