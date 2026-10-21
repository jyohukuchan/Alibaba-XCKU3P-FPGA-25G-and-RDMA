#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real full-range MR admission and owner-before-HLS-SQ for large Immediate.

Actual new C128 codec and real MR table; fetched-record/MMIO management and
owner/HLS executor endpoints are MODELS, not native DMA/CQ/Linux/physical.
Retain all11 READ/Atomic MR methods and all8 READ/Atomic HLS staging methods.
"""
import argparse
import inspect
import json
from pathlib import Path
import sys
import time
import unittest
import test_segmented_read_admission_rtl as admission
import test_segmented_read_hls_sq_rtl as staging
import test_segmented_immediate_wqe as codec

ROOT=admission.ROOT;digest=admission.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_immediate as candidate


def entry():
    method=admission.old.Atomic128AdmissionTests.entry
    text=candidate.once(inspect.getsource(method),'as02_atomic_wqe_encode','as02_segmented_immediate_wqe_encode')
    namespace=dict(method.__globals__)
    exec(compile('class ExactEntry:\n'+text,__file__+':entry','exec'),namespace)
    return namespace['ExactEntry'].entry


class ImmediateAdmission(admission.ReadAdmission):
    reports={};entry=entry()
    @classmethod
    def setUpClass(cls):codec.SegmentedImmediateWQE.setUpClass.__func__(cls)

    def simulate(self,*args,**kwargs):
        saved=admission.source
        try:admission.source=candidate;super().simulate(*args,**kwargs)
        finally:admission.source=saved

    def test_Immediate_actual_C_full_range_MR_values_and_stalls(self):
        for op in [5,6]:
            self.simulate(''.join(self.entry(admission.old.candidate(op,length=n,immediate=imm))
                for n in [4097,8193,65537,1048576]for imm in [0,0x89abcdef,0xffffffff]),extent=1052672)

    def test_Immediate_real_MR_rejects_bad_key_PD_and_final_byte(self):
        for op in [5,6]:
            self.simulate(''.join([
                self.entry(admission.old.candidate(op,length=8193,local_key=0),error=1),
                self.entry(admission.old.candidate(op,length=8193,local_key=admission.old.old.original.KEY^0x80000000),error=1),
                self.entry(admission.old.candidate(op,length=8193),context=(1,8,0xf123,admission.old.old.original.SEQ,admission.old.old.original.EPOCH),error=2),
                self.entry(admission.old.candidate(op,length=8193),error=4)]))

    def test_Immediate_source_MR_does_not_require_local_write_permission(self):
        # The second real MR is valid but has no local-write permission.
        # SEND/WRITE Immediate READ their source, unlike an RDMA READ result.
        for op in [5,6]:
            self.simulate(self.entry(admission.old.candidate(op,length=8193,
                local_key=admission.old.old.original.KEY+1)),extent=1052672)

    def test_Immediate_oversize_reserved_or_atomic_operands_fail_before_MR(self):
        mutations=[(lambda b:b.__setitem__(slice(32,36),(1048577).to_bytes(4,'little')),0x26),
            (lambda b:b.__setitem__(64,1),0x20),(lambda b:b.__setitem__(72,1),0x20),
            (lambda b:b.__setitem__(127,1),0x20)]
        for op in [5,6]:
            self.simulate(''.join(self.entry(admission.old.candidate(op,length=8193),mutate=m,error=e,queries=0)
                for m,e in mutations),extent=1052672)


class ImmediateHLSSQ(staging.ReadHLSSQ):
    reports={}
    def simulate(self,*args,**kwargs):
        saved=staging.source
        try:staging.source=candidate;super().simulate(*args,**kwargs)
        finally:staging.source=saved

    def test_Immediate_full_owner_before_SQ_and_full_values(self):
        for op in [5,6]:
            fields=dict(remote=0,rkey=0)if op==5 else dict(remote=0xe23456789abcdef0,rkey=0xffffffff)
            body=''
            for length in [4097,8193,65537,1048576]:
                for imm in [0,0x89abcdef,0xffffffff]:
                    ctx=staging.old.context(op,compare=0,operand=0,immediate=imm,length=length,**fields)
                    sq=staging.old.expected(op,compare=0,operand=0,immediate=imm,length=length,**fields)
                    body+=f'submit({ctx});owner({ctx},7);sq({sq});\n'
            self.simulate(body)

    def test_Immediate_oversize_or_atomic_operand_never_gets_SQ(self):
        for op in [5,6]:
            fields=dict(remote=0,rkey=0)if op==5 else {}
            bad=[staging.old.context(op,compare=0,operand=0,immediate=0x89abcdef,length=1048577,**fields),
                 staging.old.context(op,compare=1,operand=0,immediate=0x89abcdef,length=8193,**fields)]
            for ctx in bad:self.simulate(f's_work_context={ctx};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);
if(fault!==1'b1 || s_work_ready || m_owner_valid || m_axis_sq_tvalid || owner_handoff_count ||
 HLS_SQ_handoff_count || queue_guard!==255)$fatal(1,"bad Immediate became HLS authority");
''')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*helpers,*candidate.RTL.glob('*.v'),*[codec.KERNEL/n for n in codec.SOURCES],*codec.KERNEL.glob('wqe*.h'),Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in [ImmediateAdmission,ImmediateHLSSQ]])
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite)
    same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,tests=dict(MR=ImmediateAdmission.reports,HLS_SQ=ImmediateHLSSQ.reports),
        actual_MR_table=True,actual_C128_Immediate_codec=True,all11_old_admission_methods_and8_old_staging_retained=True,
        raw_SQ_MMIO_owner_HLS_endpoints_modeled=True,four_state=True,native_or_hardware_runtime=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
