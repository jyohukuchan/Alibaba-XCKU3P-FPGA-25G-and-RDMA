#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual zero native SQ/result-pad and real-framer/lifetime proof join.

All previous Atomic128 staging cases run on the new checked RTL. Real HLS,
protected token, memory, MAC pins and CQ endpoints remain explicit models;
the actual Ethernet framer/owner/core-receipt decision logic is not stubbed.
No generated-HLS/full-native/Linux/physical/timing runtime claim follows.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import test_zero_native_leaves as actual
import test_atomic128_hls_sq_rtl as sq
import test_atomic128_result_pad_rtl as pad

ROOT=actual.ROOT;digest=actual.digest
actual.use_actual(sq,['rocev2_wqe_admission','rocev2_sq_wqe_admission','rocev2_wqe_hls_sq'])
pad.source=SimpleNamespace(**vars(pad.source))
pad.source.leaf=lambda name:actual.renamed([name])[actual.source.RTL/(name+'.v')]


class ZeroHLSSQ(sq.Atomic128HLSSQTests):
    reports={}
    def test_zero_full_owner_before_exact408bit_SQ_and_all_wire_fields(self):
        body=''
        for op in [1,2,3,5,6]:
            ctx=actual.zero_owner(op);imm=0x89abcdef if op in [5,6]else 0
            expected=sq.expected(op,compare=0,operand=0,immediate=imm,length=0,address=0,
                remote=(1<<64)-1 if op in [1,2,6]else 0,rkey=0xfedcba98 if op in [1,2,6]else 0)
            body+=f'submit({ctx});owner({ctx},7);sq({expected});\n'
        self.simulate(body)

    def test_zero_noncanonical_local_authority_never_offers_HLS(self):
        for fields in [dict(lkey=1),dict(address=1),dict(offset=1),dict(authorized=0),dict(epoch=0)]:
            self.simulate(f's_work_context={actual.zero_owner(**fields)};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);if(!fault || s_work_ready || m_owner_valid || m_axis_sq_tvalid || queue_guard!==255)
 $fatal(1,"zero noncanonical context acquired HLS authority");
''')


def request(op,psn):
    p=bytearray(actual.life.packet(psn=psn)[:40]);p[28]={1:10,2:12,3:4,5:5,6:11}[op]
    if op in [1,2,6]:p+=struct.pack('!QII',(1<<64)-1,0xfedcba98,0)
    if op in [5,6]:p+=struct.pack('!I',0x89abcdef)
    p+=bytes(4)
    return actual.response.old.repair(p)


class ZeroLifetime(actual.life.Atomic128LifetimeTests):
    reports={}
    def test_zero_five_real_frames_wait_for_MAC_core_receipt_and_CQ_commit(self):
        for op in [1,2,3,5,6]:
            psn=0xffffff if op==2 else 0xfffffe;pkt=request(op,psn);owner=actual.zero_owner(op)
            wire_op={1:10,2:12,3:4,5:5,6:11}[op]
            done=int(owner.split("'h")[1],16)|(psn<<748)|(((psn+1)&0xffffff)<<772)|(wire_op<<796)
            body=f"owner({owner});transmit({len(pkt)});expectation(24'h{psn:06x});memory();"
            body+=f"response(24'h{psn:06x},8'h{16 if op==2 else 17:02x});ack(40'h{(psn<<11)|(7<<1)|int(op!=2):010x});"
            body+=r'''
repeat(1100)begin @(negedge clk);if(m_cq_valid || committed_count || !busy || proof_flags[5] || receipt_count)
 $fatal(1,"zero ACK or no-memory became MAC completion");end
mac();
'''
            body+=actual.life.FINISH.replace('CORE_DONE',f"816'h{done:0204x}")
            self.simulate(body,op=op,psn=psn,pkt=pkt)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    files=list(dict.fromkeys([*actual.OUT,*[Path(m.__file__).resolve()for m in list(sys.modules.values())
        if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]]))
    before={str(p.relative_to(ROOT)):digest(p)for p in files}
    run=Path(tempfile.mkdtemp(prefix='zero-native-staging-',dir=ROOT/'rdma/rnic/build'))
    for f in files:
        target=run/'inputs'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    classes=[ZeroHLSSQ,pad.Atomic128ResultPadTests,ZeroLifetime]
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in classes))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,directory=str(run.relative_to(ROOT)),four_state=True,
        tests={c.__name__:c.reports for c in classes},simulations=sum(sum(map(len,c.reports.values()))for c in classes),
        frozen_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()},
        generated_HLS_or_full_native_runtime=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
