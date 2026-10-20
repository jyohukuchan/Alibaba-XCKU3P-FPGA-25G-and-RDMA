#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual RQC mailbox + fetcher + posted-owner queue cancellation.

AXI/registers, fetch selection and scoped owner cancellation are actual RTL.
Descriptor backend, admission/MR context construction and external drain are
MODELS. No generated HLS, physical DMA, Linux lifetime or full-board proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import test_sq_control_regs_rtl as old
import test_receive_queue_rtl as owners

ROOT=old.ROOT
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('ambiguous test derivation: '+a)
    return s.replace(a,b)

EXTRA=r'''
integer target_fetched=1;
wire [7:0] owner_guard;wire owner_fault,owner_held;
wire rq_post_ready,rq_head_valid;reg rq_take=0;
wire [587:0] rq_context,rq_head_context;
wire [31:0] posted,cancelled;wire [15:0] result_tag;
wire rq_cancel_ready;
reg [7:0] extra_guard=0;
assign work_queue_guard=owner_guard|extra_guard;
assign cancel_ready=rq_cancel_ready && fetch_queue_guard==0;
assign rq_context=BASE_CONTEXT|({524'd0,result_sequence}<<460)|({572'd0,result_tag}<<340);
rocev2_receive_queue #(.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.RECV_CANCEL_ENABLE(1)) owners(
 .clk(clk),.rst(rst),.parent_fault(1'b0),
 .cancel_block(cancel_block),.cancel_valid(cancel_valid && fetch_queue_guard==0),
 .cancel_safe(fetch_queue_guard==0),.cancel_qpn(cancel_qpn),.cancel_pd(cancel_pd),.cancel_epoch(cancel_epoch),
 .cancel_ready(rq_cancel_ready),.cancelled_count(cancelled),
 .s_post_context(rq_context),.s_post_valid(result_valid && allow_result),.s_post_ready(rq_post_ready),
 .query_qpn(24'd7),.m_head_context(rq_head_context),.m_head_valid(rq_head_valid),.m_head_ready(rq_take),
 .s_placement_context(588'd0),.s_placement_length(32'd0),.s_placement_psn(24'd0),.s_placement_valid(1'b0),.s_placement_ready(),
 .s_core_data(680'd0),.s_core_valid(1'b0),.s_core_ready(),.core_proved(),.core_proof_count(),.core_msn(),
 .held_context(),.held_core_data(),.s_mac_data(696'd0),.s_mac_valid(1'b0),.s_mac_ready(),
 .memory_drained(parent_dma_drained),.m_ticket_context(),.m_ticket_received_bytes(),.m_ticket_valid(),.m_ticket_ready(1'b0),
 .s_commit_context(588'd0),.s_commit_valid(1'b0),.s_commit_ready(),
 .s_retire_context(588'd0),.s_retire_valid(1'b0),.s_retire_ready(),
 .queue_guard(owner_guard),.active(owner_held),.fault(owner_fault),.fault_code(),
 .posted_count(posted),.taken_count(),.placement_count(),.received_bytes());
'''
BODY=r'''
initial begin
 scenario=0;i=$value$plusargs("case=%d",scenario);
 rst=0;repeat(2)@(negedge clk);rst=1;parent_dma_drained=1;
 repeat(8)@(negedge clk);rst=0;
 target_fetched=scenario==1 ? 0:scenario==2 ? 2:1;
 read_reg(AS02_SQC_FEATURES,value);if(value!==3)$fatal(1,"missing genuine cancel feature");
 allocate();allow_backend=1;allow_result=1;
 defaults(2,1,0);stage_words();bell();reply(0,0);ack();
 defaults(2,2,0);stage_words();bell();reply(0,0);ack();
 while(results<target_fetched)@(negedge clk);
 repeat(8)@(negedge clk);
 if(posted!=target_fetched || owner_fault)$fatal(1,"actual fetched posted owners missing");
 if(scenario==3)begin rq_take=1;@(posedge clk);@(negedge clk);rq_take=0;if(!owner_held)$fatal(1,"held owner not taken");end
 defaults(4,2,64'h8123456789abcdef);
 if(scenario==4)words[7]=32'h7edcba98;
 stage_words();
 if(scenario==0)parent_dma_drained=0;
 bell();
 if(scenario==4)begin
  reply(32,0);if(cancel_valid || cancelled || !owner_guard[7])$fatal(1,"wrong cookie reclaimed owner");
 end else if(scenario==3)begin
  repeat(24)@(negedge clk);
  if(response_valid || cfg_valid || cancelled || !owner_held || !owner_guard[7] || !owner_active[7])
   $fatal(1,"in-flight receive fabricated cancellation certificate");
 end else begin
  if(scenario==0)begin
   repeat(24)@(negedge clk);
   if(response_valid || cancelled || !owner_guard[7] || cfg_valid)$fatal(1,"missing parent drain released owner");
   parent_dma_drained=1;
  end
  reply(0,63);read_reg(AS02_SQC_REPLY_CONSUMER_LO,value);
  if(value!==2 || owner_guard || owner_active || fetch_active || cancelled!=target_fetched ||
     results!=target_fetched || fetches!=target_fetched || owner_fault || fatal || !cancel_block)
   $fatal(1,"actual cancelled final-producer/owner certificate");
  ack();if(cancel_block)$fatal(1,"cancel blocker did not follow owned reply ACK");
 end
 $display("RECV_CANCEL_RESULT {\"pass_test\":true,\"scenario\":%0d,\"fetched\":%0d,\"cancelled_posted\":%0d,\"held_retained\":%0d,\"reply_flags\":%0d}",scenario,results,cancelled,owner_held,scenario>=3 ? 0:63);
 $finish;
end
endmodule
'''
def bench():
    s=old.TB.split('initial begin\n scenario=0;',1)[0]+BODY
    s=once(s,'// DECLARATIONS','// DECLARATIONS\n'+EXTRA.replace('BASE_CONTEXT',owners.context(7,0)))
    s=once(s,'#(.INITIAL_SEQUENCE(INITIAL_SEQUENCE_VALUE))','#(.CONTROL_ID(32\'h52514331),.RECV_CANCEL_ENABLE(1))')
    s=once(s,'rocev2_sq_fetch fetch(','rocev2_sq_fetch #(.SEPARATE_RQ_ENABLE(1),.RECV_CANCEL_ENABLE(1)) fetch(')
    s=once(s,'.enable(fetch_enable),','.enable(fetch_enable && results<target_fetched && !cancel_block),\n .cfg_receive(1\'b1),.admission_available(2\'b11),\n .receive_downstream_guard(work_queue_guard|wire_queue_guard|completion_queue_guard),\n .receive_queue_guard(fetch_queue_guard),.receive_queue_active(fetch_active),.receive_queue_pending(),.receive_queue_halted(),.m_result_receive(),')
    s=once(s,'.queue_guard(fetch_queue_guard),.queue_active(fetch_active),','.queue_guard(),.queue_active(),')
    s=once(s,'.downstream_queue_guard(work_queue_guard|wire_queue_guard|completion_queue_guard),','.downstream_queue_guard(8\'d0),')
    s=once(s,'.m_result_tag(),','.m_result_tag(result_tag),')
    s=once(s,'.m_result_ready(allow_result),','.m_result_ready(allow_result && rq_post_ready),')
    s=once(s,'if(result_valid&&allow_result)begin','if(result_valid&&allow_result&&rq_post_ready)begin')
    ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(?:\[([^]]+)\]\s+)?(\w+)',old.RTL.read_text().split('\n);',1)[0])
    driven={'cfg_ready','cfg_response_error','cfg_response_qpn','cfg_response_epoch','cfg_response_consumer','cfg_response_valid','fetch_queue_guard','work_queue_guard','cancel_ready'}
    declarations='\n'.join(old.pcie.declaration(n,old.pcie.width(e,dict(ADDR_WIDTH=12,MAX_QPS=8)),'reg'if d=='input'and n not in driven else'wire')for d,e,n in ports)
    macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'for n,v in re.findall(r'^#define (AS02_SQC_\w+) (\w+)',old.HEADER.read_text(),re.M))
    return s.replace('// DECLARATIONS',declarations).replace('// ABI',macros).replace('INITIAL_SEQUENCE_VALUE','0')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    sources=[*old.SOURCES,owners.RTL]
    inputs=[*sources,old.HEADER,Path(__file__).resolve(),Path(old.__file__).resolve(),Path(owners.__file__).resolve(),Path(old.pcie.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,hardware_verified=False,tests={},simulation_limit_seconds=10)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-recv-cancel-')as folder:
            d=Path(folder);tb=bench();(d/'tb.v').write_text(tb)
            report['bench_sha256']=hashlib.sha256(tb.encode()).hexdigest()
            cmd=['iverilog','-g2012','-s','tb','-o',str(d/'test'),str(d/'tb.v'),*map(str,sources)]
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            if r.returncode:raise RuntimeError(r.stdout+r.stderr)
            for n in range(5):
                start=time.monotonic();r=subprocess.run(['vvp',str(d/'test'),f'+case={n}'],capture_output=True,text=True,timeout=10)
                report['tests'][n]=dict(seconds=time.monotonic()-start,output=r.stdout+r.stderr)
                if r.returncode:raise RuntimeError(r.stdout+r.stderr)
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('RECV_CANCEL_RESULT ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing real RTL assertions')
                report['tests'][n]['summary']=rows[0]
            if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
            report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','tests']}))
if __name__=='__main__':main()
