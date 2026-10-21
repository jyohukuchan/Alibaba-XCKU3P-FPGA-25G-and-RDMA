#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual Immediate LAST normalization/ICRC RTL, preserving old pad tests.

Independent complete packets, every tail/pad position and poisoned padding.
Selected actual HLS C++ wire captures also traverse this RTL in a separate
snapshot execution, not live generated HLS/native/physical qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import test_segmented_padding_rtl as old
import test_segmented_immediate_wire_rtl as wire

ROOT=old.ROOT;digest=old.digest;candidate=wire.candidate


class SegmentedImmediatePadding(old.SegmentedPadding):
    all_runs={}
    def simulate(self,*args,**kwargs):
        saved=old.PAD
        try:old.PAD=self.leaf;return super().simulate(*args,**kwargs)
        finally:old.PAD=saved

    def test_Immediate_LAST_all_pad_counts_and_tail_positions(self):
        frames=[wire.packet(op,4096+n,4096,0)for op in [5,6]for n in [*range(1,34),63,64,65,4095,4096]]
        self.simulate([(p[:-4],None,None)for p in frames],frames,0)

    def test_Immediate_LAST_poisoned_pad_never_repaired(self):
        prefix=[old.legacy.packet(4095,i)for i in range(8)]
        good=wire.packet(6,4097,4096,0);raw=good[:-4];bad=[]
        for byte in range(len(raw)-3,len(raw)):
            p=bytearray(raw);p[byte]=0x80;bad.append((bytes(p),None,None))
        bad.extend([(old.legacy.unpadded(good),None,None),(raw,1,None),(raw,None,1)])
        inputs=[(old.legacy.unpadded(p),None,None)for p in prefix]
        for b in bad:inputs.extend([b,(raw,None,None)])
        self.simulate(inputs,[*prefix,*([good]*len(bad))],len(bad))

    def test_unedited_actual_HLS_CPP_first_middle_LAST_captures_through_ICRC(self):
        report=json.loads((ROOT/'results/2026-10-18/rocev2-rnic-segmented-immediate-hls-001.json').read_text())
        self.assertTrue(report['pass_test']);frames=[]
        for mode in ['imm-send','imm-write']:
            for line in (ROOT/report['directory']/(mode+'.log')).read_text().splitlines():
                if not line.startswith('IMMEDIATE_SEGMENT_WIRE '):continue
                _,op,total,offset,psn,replay,imm,raw=line.split()
                if int(total)!=8193 or int(replay):continue
                header=wire.packet(int(op),int(total),int(offset),int(psn))[:28]
                frames.append(wire.old.packets.repair(header+bytes.fromhex(raw)+bytes(4)))
        self.assertEqual(len(frames),6)
        # Bulk valid prefix retains the original scoreboard's mandatory
        # actual input-backpressure coverage; no ready signal is forced.
        prefix=[old.legacy.packet(4095,i)for i in range(8)]
        inputs=[(old.legacy.unpadded(p),None,None)for p in prefix]+[(p[:-4],None,None)for p in frames]
        self.simulate(inputs,[*prefix,*frames],0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-padding-source-',dir=ROOT/'rdma/rnic/build'))
    leaf=run/'rocev2_segmented_tx_padding.v';leaf.write_text(candidate.derive()[candidate.PAD])
    SegmentedImmediatePadding.leaf=leaf
    helpers=[Path(m.__file__).resolve()for m in list(wire.sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    hls_report=ROOT/'results/2026-10-18/rocev2-rnic-segmented-immediate-hls-001.json'
    hls=json.loads(hls_report.read_text());hls_inputs=[ROOT/hls['directory']/(m+'.log')for m in ['imm-send','imm-write']]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys([*helpers,leaf,hls_report,*hls_inputs,Path(__file__).resolve()])}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedImmediatePadding))
    same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,tests=SegmentedImmediatePadding.all_runs,
        tested_padding_sha256=digest(leaf),all_prior_padding_methods_retained=True,
        actual_HLS_CPP_captures_are_separate_snapshot=True,live_HLS_RTL=False,native_runtime=False,hardware_verified=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
