#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual retained READ controller + unchanged bounded executor/unpad children.

Protected placement, HLS command/payload, backend statuses/visibility and CQ
are explicit MODELS. Full saved authority, exact padded raw/data, nonwrapping
tags, all-fragment memory event and retained CQ lease run in four-state RTL.
NOT actual RX/HLS/MR/PTE/DMA/native/Linux/physical/timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
import probe_atomic_responder as helper

ROOT=helper.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_executor as source
RTL=ROOT/'rdma/rnic/rtl/rocev2_segmented_read_executor.v'
digest=helper.digest


def owner(length=8193):
    return (0xf123456789abc007<<524)|(7<<460)|(0x9123456700000001<<396)|(2<<372)|\
        (17<<356)|(9<<340)|(2<<324)|(1<<308)|(length<<276)|(8<<244)|\
        (0xfedcba9876543210<<180)|(0x1234567800000210<<116)|\
        (0xe23456789abcdef0<<52)|(0x81234567<<20)|3


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
always #2 clk=~clk;
reg [747:0] expected=748'hOWNER;
integer cycle=0,b,p,off,count,nonce,fragment_bytes=0,fragment_base=0,fragment_written=0,total_written=0,events=0;
reg memory_stalled=0,command_stalled=0,event_stalled=0,stall_memory_once=0;
reg [576:0] saved_data;
reg [144:0] saved_command;
reg [755:0] saved_event;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>200000)$fatal(1,"bounded READ component clock deadline");
 if(memory_stalled && (!m_axis_memory_tvalid || {m_axis_memory_tdata,m_axis_memory_tkeep,m_axis_memory_tlast}!==saved_data))$fatal(1,"READ data retracted/changed under stall");
 memory_stalled=m_axis_memory_tvalid&&!m_axis_memory_tready;
 saved_data={m_axis_memory_tdata,m_axis_memory_tkeep,m_axis_memory_tlast};
 if(command_stalled && (!m_memory_command_valid || {m_memory_command_write,m_memory_command_offset,m_memory_command_length,m_memory_command_key,m_memory_command_tag}!==saved_command))$fatal(1,"READ command retracted/changed under stall");
 command_stalled=m_memory_command_valid&&!m_memory_command_ready;
 saved_command={m_memory_command_write,m_memory_command_offset,m_memory_command_length,m_memory_command_key,m_memory_command_tag};
 if(event_stalled && (!m_memory_event_valid || {m_memory_event_context,m_memory_event_error}!==saved_event))$fatal(1,"whole READ event retracted/changed under stall");
 event_stalled=m_memory_event_valid&&!m_memory_event_ready;saved_event={m_memory_event_context,m_memory_event_error};
 if(m_axis_memory_tvalid && m_axis_memory_tready)begin
  if(m_axis_memory_tkeep!==((65'd1<<(fragment_bytes-fragment_written>64 ? 64:fragment_bytes-fragment_written))-1) ||
     m_axis_memory_tlast!==(fragment_bytes-fragment_written<=64))$fatal(1,"actual child placement byte extent/TLAST");
  for(b=0;b<64;b=b+1)begin
   if(m_axis_memory_tkeep[b])begin
    if(m_axis_memory_tdata[b*8+:8]!==((((fragment_base+fragment_written)*37)^8'hc3)&255))$fatal(1,"actual child placed payload byte");
    fragment_written=fragment_written+1;total_written=total_written+1;
   end else if(m_axis_memory_tdata[b*8+:8]!==0)$fatal(1,"wire pad/unknown byte escaped into DMA");
  end
 end
 if(m_memory_event_valid && m_memory_event_ready)begin
  if(m_memory_event_context!==expected || m_memory_event_error)$fatal(1,"whole READ event identity/error");events=events+1;
 end
end
function [95:0] raw_at;input integer offset;
 reg [63:0] va;reg [31:0] bytes,padded,total;
 begin total=expected[307:276];va=expected[243:180]+offset;bytes=total-offset>4096 ? 4096:total-offset;padded=(bytes+3)&32'hfffffffc;
  raw_at={2'd0,10'd2,va[51:48],1'b1,1'b0,va[52],offset+bytes==total,padded[27:0],va[47:0]};end
endfunction
task bind_owner;
 begin
  @(negedge clk);s_owner_context=expected;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready)$fatal(1,"full READ owner rejected");
  @(negedge clk);s_owner_valid=0;s_owner_context=0;
  if(!busy || queue_guard!==4)$fatal(1,"whole READ owner lease missing");
 end
endtask
task placement;
 begin
  @(negedge clk);s_read_response_context=expected;s_read_response_valid=1;
  @(posedge clk);if(!s_read_response_ready)$fatal(1,"identical protected placement not accepted");
  @(negedge clk);s_read_response_valid=0;s_read_response_context=0;
 end
endtask
task raw_command;input integer offset;
 integer limit;
 begin
  @(negedge clk);s_hls_command=raw_at(offset);s_hls_command_valid=1;limit=cycle+200;
  @(posedge clk);while(!s_hls_command_ready)begin @(posedge clk);if(cycle>limit)$fatal(1,"READ raw timeout %h",fault_code);end
  @(negedge clk);s_hls_command_valid=0;
 end
endtask
task backend_command;input integer offset;input integer bytes;input [15:0] tag;
 integer limit;
 begin
  limit=cycle+100;
  while(!m_memory_command_valid)begin @(negedge clk);if(cycle>limit)$fatal(1,"bounded actual READ DMA command timeout %h",fault_code);end
  if(!m_memory_command_write || m_memory_command_offset!==64'h1234567800000210+offset ||
   m_memory_command_length!==bytes || m_memory_command_key!==8 || m_memory_command_tag!==tag)$fatal(1,"full64 saved offset/key/fresh child tag/length mismatch");
  repeat(8)@(negedge clk);m_memory_command_ready=1;
  @(posedge clk);@(negedge clk);m_memory_command_ready=0;
 end
endtask
task payload;input integer offset;input integer bytes;
 integer pos,j,padded,limit;
 begin
  fragment_base=offset;fragment_bytes=bytes;fragment_written=0;padded=(bytes+3)&32'hfffffffc;
  if(stall_memory_once)m_axis_memory_tready=0;
  for(pos=0;pos<padded;pos=pos+64)begin
   @(negedge clk);s_axis_hls_tdata=~512'd0;s_axis_hls_tkeep=0;
   for(j=0;j<64 && pos+j<padded;j=j+1)begin
    s_axis_hls_tdata[j*8+:8]=pos+j<bytes ? (((offset+pos+j)*37)^8'hc3):8'hfe;
    s_axis_hls_tkeep[j]=1;
   end
   s_axis_hls_tlast=pos+64>=padded;s_axis_hls_tvalid=1;limit=cycle+400;
   @(posedge clk);while(!s_axis_hls_tready)begin @(posedge clk);if(cycle>limit)$fatal(1,"READ payload timeout %h",fault_code);end
   @(negedge clk);s_axis_hls_tvalid=0;
   if(pos==0 && stall_memory_once)begin
    limit=cycle+100;while(!m_axis_memory_tvalid)begin @(negedge clk);if(cycle>limit)$fatal(1,"stalled child data missing");end
    repeat(15)begin @(negedge clk);if(fragment_written || m_memory_event_valid || s_retire_ready)$fatal(1,"stalled placement invented memory completion");end
    m_axis_memory_tready=1;stall_memory_once=0;
   end
  end
  limit=cycle+100;while(fragment_written!=bytes)begin @(negedge clk);if(cycle>limit)$fatal(1,"actual placed bytes timeout");end
  repeat(5)begin @(negedge clk);if(m_memory_event_valid || s_retire_ready)$fatal(1,"data without actual status completed whole WR");end
 end
endtask
task status;input [15:0] tag;
 integer limit;
 begin
  @(negedge clk);s_memory_status_tag=tag;s_memory_status_error=0;s_memory_status_valid=1;limit=cycle+100;
  @(posedge clk);while(!s_memory_status_ready)begin @(posedge clk);if(cycle>limit)$fatal(1,"actual child status timeout %h",fault_code);end
  @(negedge clk);s_memory_status_valid=0;repeat(5)@(negedge clk);
  if(fault)$fatal(1,"unexpected READ fault %h",fault_code);
 end
endtask
task fragment;input integer offset;input integer bytes;input [15:0] tag;
 begin raw_command(offset);backend_command(offset,bytes,tag);payload(offset,bytes);status(tag);end
endtask
task finish_success;
 begin
  if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error ||
     total_written!=expected[307:276] || !busy || events || s_retire_ready)$fatal(1,"whole READ aggregate event/lease missing or premature CQ");
  repeat(15)@(negedge clk);
  m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
  if(!busy || queue_guard!==4 || retired_count || events!=1)$fatal(1,"memory event released whole READ owner before CQ");
  s_retire_context=expected;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"identical real CQ not ready");
  @(negedge clk);s_retire_valid=0;#1;
  if(busy || queue_guard || fault || retired_count!=1)$fatal(1,"whole READ not released only by CQ");
 end
endtask
task quarantine;
 begin repeat(10)@(negedge clk);if(!fault || !busy || queue_guard!==255 || retired_count || s_retire_ready)$fatal(1,"READ fault lost whole owner");end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;enable=1;downstream_queue_guard=4;m_axis_memory_tready=1;
 // BODY
 $display("SEGMENTED_READ_EXECUTOR {\"pass_test\":true,\"fragments\":%0d,\"bytes\":%0d,\"events\":%0d,\"retired\":%0d,\"padding\":%0d}",fragment_count,total_written,events,retired_count,discarded_padding_bytes);$finish;
end
endmodule
'''


class SegmentedRead(unittest.TestCase):
    reports={}
    inputs={}

    def simulate(self,body,length=8193,tag_width=12):
        run=Path(tempfile.mkdtemp(prefix='segmented-read-executor-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-read-executor-',dir='/dev/shm'))
        child=source.child_source();unpad=source.unpad_source()
        (run/'child.v').write_text(child);(run/'unpad.v').write_text(unpad)
        decl=helper.instance(RTL,'dut','',{})
        if tag_width!=12:
            decl=decl.replace('rocev2_segmented_read_executor dut(',f'rocev2_segmented_read_executor #(.TAG_SEQUENCE_WIDTH({tag_width})) dut(')
        (run/'tb.v').write_text(TB.replace('// DECLARATIONS',decl).replace("748'hOWNER",f"748'h{owner(length):0187x}").replace('// BODY',body))
        item=dict(directory=str(run.relative_to(ROOT)),pass_test=False,four_state=True,READ_bytes=length,runtime_limit_seconds=30)
        self.reports.setdefault(self._testMethodName,[]).append(item)
        try:
            cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(RTL),str(run/'child.v'),str(run/'unpad.v')]
            item['compile_command']=cmd;start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            item['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertFalse(any(re.search(r'(?i)port .*expects .*bits',l)for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],capture_output=True,text=True,timeout=30)
            item.update(seconds=time.monotonic()-start,exit=r.returncode);(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            summaries=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('SEGMENTED_READ_EXECUTOR ')]
            self.assertEqual(len(summaries),1);self.assertTrue(summaries[0]['pass_test']);item.update(pass_test=True,summary=summaries[0])
            self.assertEqual(child,source.child_source());self.assertEqual(unpad,source.unpad_source())
        finally:
            item['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
            item['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}

    def test_tails_one_token_fresh_tags_every_status_and_CQ_lease(self):
        for length in [4097,4098,4099,4100,8192,8193,12289]:
            self.simulate(r'''
bind_owner();placement();s_retire_context=expected;s_retire_valid=1;stall_memory_once=1;nonce=1;
for(off=0;off<expected[307:276];off=off+4096)begin
 count=expected[307:276]-off>4096 ? 4096:expected[307:276]-off;
 fragment(off,count,16'ha000+nonce);nonce=nonce+1;
 if(off+count<expected[307:276] && (m_memory_event_valid || s_retire_ready))$fatal(1,"partial READ completed whole request");
end
if(discarded_padding_bytes!==((-expected[307:276])&3))$fatal(1,"wire padding accounting");
finish_success();
''',length)

    def test_full_1MiB_256_fragments_four_state(self):
        self.simulate(r'''
bind_owner();placement();nonce=1;
for(off=0;off<1048576;off=off+4096)begin
 fragment(off,4096,16'ha000+nonce);nonce=nonce+1;
 if(off!=1044480 && m_memory_event_valid)$fatal(1,"1MiB partial completion");
end
if(fragment_count!=256 || discarded_padding_bytes)$fatal(1,"full1MiB extent");finish_success();
''',1048576)

    def test_next_command_and_data_wait_for_real_previous_status(self):
        self.simulate(r'''
bind_owner();placement();raw_command(0);backend_command(0,4096,16'ha001);payload(0,4096);
fork
 begin raw_command(4096);backend_command(4096,1,16'ha002);end
 begin payload(4096,1);end
 begin
  repeat(20)begin @(negedge clk);if(s_hls_command_ready || s_axis_hls_tready || m_memory_command_valid || m_memory_event_valid || fault)$fatal(1,"next fragment escaped withheld actual status");end
  status(16'ha001);
 end
join
status(16'ha002);finish_success();
''',4097)

    def test_early_correct_status_waits_for_actual_data_transfer(self):
        self.simulate(r'''
bind_owner();placement();raw_command(0);backend_command(0,4096,16'ha001);
s_retire_context=expected;s_retire_valid=1;
fork
 begin
  @(negedge clk);s_memory_status_tag=16'ha001;s_memory_status_error=0;s_memory_status_valid=1;
  repeat(20)begin @(negedge clk);if(s_memory_status_ready || m_memory_event_valid || s_retire_ready || fragment_count)$fatal(1,"early status bypassed actual data transfer");end
  @(posedge clk);while(!s_memory_status_ready)@(posedge clk);
  @(negedge clk);s_memory_status_valid=0;
 end
 begin repeat(25)@(negedge clk);payload(0,4096);end
join
repeat(5)@(negedge clk);if(fault || fragment_count!=1 || m_memory_event_valid)$fatal(1,"early pending status not joined to genuine first data");
fragment(4096,1,16'ha002);finish_success();
''',4097)

    def test_missing_wrong_duplicate_or_unknown_protected_token_fail_closed(self):
        for body in [
            'bind_owner();s_hls_command=raw_at(0);s_hls_command_valid=1;',
            'bind_owner();s_read_response_context=expected^1;s_read_response_valid=1;',
            "bind_owner();s_read_response_context=expected;s_read_response_context[400]=1'bx;s_read_response_valid=1;",
            'bind_owner();placement();s_read_response_context=expected;s_read_response_valid=1;']:
            self.simulate(body+'quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"bad placement created DMA/event");')

    def test_wrong_raw_order_pad_length_ctl_reserved_and_address_refused(self):
        for change in ['raw_at(4096)','raw_at(0)^96\'h800000000000000000000000','raw_at(0)^96\'h000010000000000000000000','raw_at(0)^1']:
            self.simulate('bind_owner();placement();s_hls_command='+change+';s_hls_command_valid=1;quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"bad raw issued DMA");')
        self.simulate(r'''
bind_owner();placement();fragment(0,4096,16'ha001);
s_hls_command=raw_at(4096);s_hls_command[75:48]=1;s_hls_command_valid=1;
quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"unpadded raw tail accepted");
''',4097)

    def test_stale_or_unknown_backend_status_never_completes_next_fragment(self):
        for tag in ["16'ha001","16'hax02"]:
            self.simulate(r'''
bind_owner();placement();fragment(0,4096,16'ha001);raw_command(4096);backend_command(4096,4096,16'ha002);
s_memory_status_tag=TAG;s_memory_status_valid=1;quarantine();
if(s_memory_status_ready || m_memory_event_valid)$fatal(1,"wrong physical-model status completed new fragment");
'''.replace('TAG',tag))

    def test_bad_payload_keep_TLAST_or_unknown_never_creates_success(self):
        for change in ["s_axis_hls_tkeep=64'hfffffffffffffffd;","s_axis_hls_tlast=1;","s_axis_hls_tdata[9]=1'bx;"]:
            self.simulate(r'''
bind_owner();placement();raw_command(0);backend_command(0,4096,16'ha001);
s_axis_hls_tdata=0;s_axis_hls_tkeep=~64'd0;s_axis_hls_tlast=0;CHANGE s_axis_hls_tvalid=1;
quarantine();if(s_axis_hls_tready || m_axis_memory_tvalid || m_memory_event_valid)$fatal(1,"bad padded payload copied/completed");
'''.replace('CHANGE',change))

    def test_parent_fault_keeps_already_offered_command_and_whole_owner(self):
        self.simulate(r'''
bind_owner();placement();raw_command(0);while(!m_memory_command_valid)@(negedge clk);
parent_fault=1;repeat(20)begin @(negedge clk);if(!m_memory_command_valid || m_memory_command_tag!==16'ha001 || m_memory_event_valid)$fatal(1,"fault retracted authorized pending command");end
quarantine();
''')

    def test_parent_fault_keeps_pending_whole_event_but_blocks_CQ_release(self):
        self.simulate(r'''
bind_owner();placement();fragment(0,4096,16'ha001);fragment(4096,1,16'ha002);
if(!m_memory_event_valid || m_memory_event_error || m_memory_event_context!==expected)$fatal(1,"pending event missing");
parent_fault=1;s_retire_context=expected;s_retire_valid=1;quarantine();
repeat(15)begin @(negedge clk);if(!m_memory_event_valid || m_memory_event_error || m_memory_event_context!==expected || s_retire_ready || events)$fatal(1,"late fault retracted event/released owner");end
''',4097)

    def test_lost_downstream_lease_and_foreign_CQ_quarantine(self):
        for body in ['downstream_queue_guard=0;',"downstream_queue_guard=8'hx4;",'s_retire_context=expected^1;s_retire_valid=1;']:
            self.simulate('bind_owner();placement();'+body+'quarantine();if(m_memory_event_valid)$fatal(1,"lost authority completed READ");')

    def test_nonwrapping_child_tag_exhaustion_blocks_fourth_DMA(self):
        self.simulate(r'''
bind_owner();placement();fragment(0,4096,16'ha001);fragment(4096,4096,16'ha002);fragment(8192,4096,16'ha003);
if(!tags_exhausted || fragment_count!=3 || m_memory_event_valid)$fatal(1,"child tags wrapped or partial success");
s_hls_command=raw_at(12288);s_hls_command_valid=1;quarantine();
if(m_memory_command_valid || s_hls_command_ready || m_memory_event_valid)$fatal(1,"exhausted child tag authorized DMA");
''',12289,2)

    def test_actual_child_error_is_not_whole_success_or_release(self):
        self.simulate(r'''
bind_owner();placement();raw_command(0);backend_command(0,4096,16'ha001);
s_memory_status_tag=16'ha001;s_memory_status_error=7;s_memory_status_valid=1;
@(posedge clk);while(!s_memory_status_ready)@(posedge clk);
@(negedge clk);s_memory_status_valid=0;quarantine();
if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error!==7 || s_retire_ready)$fatal(1,"actual DMA error lost/turned success");
''')

    def test_noncanonical_unknown_overflow_and_unsupported_owner_refused(self):
        for body in ["expected[400]=1'bx;",'expected[243:180]=64\'hfffffffffffffff0;',
                     'expected[339:324]=7;','expected[307:276]=1048577;']:
            self.simulate(body+'s_owner_context=expected;s_owner_valid=1;quarantine();if(s_owner_ready || m_memory_command_valid || m_memory_event_valid)$fatal(1,"bad READ authority accepted");')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    inputs=[*list((ROOT/'rdma/rnic/fpga').glob('*.py')),*list((ROOT/'rdma/rnic/rtl').glob('*.v')),
        Path(__file__).resolve(),Path(helper.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs};start=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedRead);methods=suite.countTestCases()
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    same=all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=result.wasSuccessful()and same,methods=methods,cases=sum(map(len,SegmentedRead.reports.values())),
        seconds=time.monotonic()-start,source_unchanged=same,source_sha256=before,tests=SegmentedRead.reports,
        hardware_verified=False,native_integration=False,actual_HLS=False,MR_PTE_DMA_visibility_modeled=True,
        protected_RX_placement_modeled=True,CQ_retirement_modeled=True,full_board_timing=False,default_graph_changed=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['pass_test']else 1)
