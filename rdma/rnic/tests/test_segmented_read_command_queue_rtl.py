#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact READ metadata queue + all17 prior real mux/unpad/child/nonce cases.

Owner/placement, coupled HLS producer, backend status/fence and CQ endpoints
are explicit models. New coupled-command/data and full-queue cases preserve
independent full-owner/byte/command/status/CQ checks; not native HLS/DMA proof.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import unittest
import test_segmented_read_memory_mux_rtl as prior

ROOT=prior.ROOT;digest=prior.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_command_queue as source

ORIGINAL_FIXTURE=prior.read_fixture


def fixture(mux,unpad):
    t=ORIGINAL_FIXTURE(mux,unpad)
    t=source.once(t,'module tb;','module tb;\nreg coupled_cmd_data=0,ahead_accepted=0;integer coupled_limit;\n')
    t=source.once(t,'  for(pos=0;pos<padded;pos=pos+64)begin',r'''
  for(pos=0;pos<padded;pos=pos+64)begin
   // Legal coupled producer: final command acceptance releases the rest of
   // the prior packet. Do not fabricate data/status to break this dependency.
   if(coupled_cmd_data && offset==4096 && pos==1920)begin
    coupled_limit=cycle+200;
    while(!ahead_accepted)begin
     @(negedge clk);if(cycle>coupled_limit)$fatal(1,"next command/prior payload dependency deadlock");
     if(m_memory_event_valid || s_retire_ready)$fatal(1,"metadata completed missing payload/status");
    end
   end''')
    return t


class QueuedRead(prior.ReadMemory):
    reports={};runs=[]

    def simulate(self,body,read_case=False):
        old_source,old_fixture=prior.source,prior.read_fixture
        prior.source,prior.read_fixture=source,fixture
        try:return super().simulate(body,read_case)
        finally:prior.source,prior.read_fixture=old_source,old_fixture

    def test_coupled_HLS_metadata_and_payload_complete_all8193_bytes(self):
        self.simulate(r'''
expected[307:276]=8193;bind_owner();placement();coupled_cmd_data=1;
fork
 begin raw_command(0);raw_command(4096);raw_command(8192);ahead_accepted=1;end
 begin
  backend_command(0,4096,1);payload(0,4096);status(1);
  if(m_memory_event_valid || s_retire_ready)$fatal(1,"first packet completed whole READ");
  backend_command(4096,4096,2);payload(4096,4096);status(2);
  if(m_memory_event_valid || s_retire_ready)$fatal(1,"second packet completed whole READ");
  backend_command(8192,1,3);payload(8192,1);status(3);
 end
join
finish_success();
if(!ahead_accepted || command_count!=3 || memory_status_count!=3 || n_command_count!=3 ||
 n_retired_count!=3 || n_fault || up_fault || discarded_padding_bytes!=3 || dut.read_cmd_count)
 $fatal(1,"coupled complete READ/nonce/queue cardinality");
''',True)

    def test_full_two_command_queue_stalls_without_releasing_any_owner(self):
        self.simulate(r'''
expected[307:276]=16385;bind_owner();placement();
raw_command(0);raw_command(4096);raw_command(8192);
@(negedge clk);s_hls_command=raw_at(12288);s_hls_command_valid=1;
repeat(20)begin
 @(negedge clk);
 if(dut.read_cmd_count!==2 || s_hls_command_ready || fault || m_memory_event_valid || s_retire_ready ||
    dut.read_cmd_offset!==12288 || s_hls_command!==raw_at(12288))$fatal(1,"full READ metadata queue lost backpressure/authority");
end
fork
 begin
  @(posedge clk);while(!s_hls_command_ready)@(posedge clk);
  @(negedge clk);s_hls_command_valid=0;raw_command(16384);
 end
 begin
  backend_command(0,4096,1);payload(0,4096);status(1);
  backend_command(4096,4096,2);payload(4096,4096);status(2);
  backend_command(8192,4096,3);payload(8192,4096);status(3);
  backend_command(12288,4096,4);payload(12288,4096);status(4);
  backend_command(16384,1,5);payload(16384,1);status(5);
 end
join
finish_success();
if(command_count!=5 || memory_status_count!=5 || n_retired_count!=5 || n_fault || up_fault || dut.read_cmd_count)
 $fatal(1,"full queue dropped/reordered command or retired before all five fragments");
''',True)

    def test_foreign_unknown_or_unprotected_future_metadata_never_queues(self):
        for mutation in ["s_hls_command[0]=~s_hls_command[0];",
                         "s_hls_command[76]=~s_hls_command[76];",
                         "s_hls_command[84]=1'bx;",
                         "s_hls_command_valid=1'bx;"]:
            self.simulate('bind_owner();placement();raw_command(0);\n'
                's_hls_command=raw_at(4096);s_hls_command_valid=1;'+mutation+\
                'quarantine();if(dut.read_cmd_offset!==4096 || m_memory_event_valid || s_retire_ready || command_count>1)'
                '$fatal(1,"foreign/unknown queued metadata authorized a later DMA/CQ");',True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier queue evidence')
    inputs=[*list((ROOT/'rdma/rnic/fpga').glob('*.py')),*list((ROOT/'rdma/rnic/rtl').glob('*.v')),
        Path(__file__).resolve(),Path(prior.__file__).resolve(),Path(prior.old.__file__).resolve(),
        Path(prior.old.previous.__file__).resolve(),Path(prior.read.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    old=source.parent.derive();new=source.derive()
    if {n.name for n in new if new[n]!=old[n]}!={source.MUX.name}:raise ValueError('only READ metadata mux may change')
    start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(QueuedRead);methods=suite.countTestCases()
    result=unittest.TextTestRunner(verbosity=2).run(suite);same=all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=result.wasSuccessful()and same,methods=methods,cases=sum(map(len,QueuedRead.reports.values())),
        seconds=time.monotonic()-start,source_sha256=before,source_unchanged=same,tests=QueuedRead.reports,
        all17_prior_mux_cases_retained=True,actual_common_physical_command_nonce=True,READ_command_queue_depth=2,
        modeled_HLS_command_data_dependency=True,actual_HLS_native_DMA_runtime=False,hardware_verified=False,
        simulation_limit_seconds=10,default_graph_changed=False,original_child_and_unpad_unchanged=True)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['pass_test']else 1)


if __name__=='__main__':main()
