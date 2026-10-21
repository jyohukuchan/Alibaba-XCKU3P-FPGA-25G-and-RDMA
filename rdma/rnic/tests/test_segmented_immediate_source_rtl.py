#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual large-Immediate source controller and unchanged bounded child RTL.

Retain all seven old source methods; add full-owner Immediate, replay after
aggregate memory receipt, foreign retirement and bounded backend failures.
Backend/data/status/CQ endpoints are MODELS; no HLS/native/physical proof.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import test_segmented_source_executor_rtl as old
import test_segmented_immediate_wire_rtl as wire

ROOT=old.ROOT;digest=old.digest;candidate=wire.candidate


class SegmentedImmediateSource(old.SegmentedSource):
    reports={};runs=[]
    @classmethod
    def setUpClass(cls):
        cls.frozen=Path(tempfile.mkdtemp(prefix='segmented-immediate-source-',dir=ROOT/'rdma/rnic/build'))
        cls.leaf=cls.frozen/'rocev2_segmented_source_executor.v'
        cls.leaf.write_text(candidate.derive()[candidate.RTL/cls.leaf.name])

    def simulate(self,body,op=1,tag_width=14):
        saved=(old.RTL,old.owner)
        try:
            old.RTL=self.leaf;old.owner=wire.owner
            super().simulate(body,op,tag_width)
        finally:old.RTL,old.owner=saved

    def test_Immediate_three_fragments_replays_and_full_owner_retained_until_CQ(self):
        for op in [5,6]:
            self.simulate(r'''
bind_owner();fragment(0,4096,16'hc001);fragment(0,4096,16'hc002);
fragment(4096,4096,16'hc003);fragment(8192,1,16'hc004);
if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error ||
 !busy || s_retire_ready || queue_guard!==4)$fatal(1,"Immediate whole owner/event/lease missing");
repeat(12)begin @(negedge clk);if(!m_memory_event_valid || m_memory_event_context!==expected)$fatal(1,"Immediate held event changed");end
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(8192,1,16'hc005);
if(m_memory_event_valid || events!=1 || fragment_count!=3 || replay_count!=2 || !busy || queue_guard!==4)
 $fatal(1,"Immediate final replay lost whole WR authority");
s_retire_context=expected;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"Immediate exact CQ refused");
@(negedge clk);s_retire_valid=0;#1;
if(busy || queue_guard || retired_count!=1 || fault)$fatal(1,"Immediate whole owner not retired exactly once");
''',op)

    def test_Immediate_foreign_retirement_and_nonsequential_raw_never_authorize(self):
        for op in [5,6]:
            for body in ['bind_owner();s_retire_context=expected^(748\'h1<<588);s_retire_valid=1;',
                         'bind_owner();s_hls_command=raw_at(4096);s_hls_command_valid=1;']:
                self.simulate(body+'quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"foreign Immediate authority");',op)

    def test_small_Immediate_also_retains_full_source_lease(self):
        for op in [5,6]:
            self.simulate(r'''
expected[307:276]=8;bind_owner();fragment(0,8,16'hc001);
if(!m_memory_event_valid || !busy)$fatal(1,"small Immediate whole event/lease missing");
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(0,8,16'hc002);
if(m_memory_event_valid || events!=1 || fragment_count!=1 || replay_count!=1 || !busy || queue_guard!==4)
 $fatal(1,"small Immediate replay authority released too early");
s_retire_context=expected;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"small Immediate exact CQ refused");
@(negedge clk);s_retire_valid=0;#1;
if(busy || queue_guard || retired_count!=1 || fault)$fatal(1,"small Immediate retirement mismatch");
''',op)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*helpers,*candidate.RTL.glob('*.v'),Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedImmediateSource))
    same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,tests=SegmentedImmediateSource.reports,four_state=True,
        all7_prior_methods_retained=True,actual_bounded_native_child=True,backend_and_CQ_endpoints_modeled=True,
        all_run_artifact_sha256={str(p.relative_to(ROOT)):digest(p)for run in SegmentedImmediateSource.runs for p in run.iterdir()if p.is_file()},
        reserved_backend_namespace_globally_integrated=False,native_or_hardware_runtime=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
