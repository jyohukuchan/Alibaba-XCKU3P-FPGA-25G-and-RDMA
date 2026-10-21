#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C128 RECV -> real full-range local-write MR/SQ admission.

The fetched record/privileged context/MMIO management and work consumer
are models, NOT actual PCIe/RQ posting/HLS/DMA/CQ/Linux/physical proof. All
old25 MR/HLS-staging methods remain, and RECV is never sent to a TX HLS SQ.
"""
import argparse
import inspect
import json
from pathlib import Path
import sys
import time
import unittest
import probe_segmented_immediate_admission as base
import test_segmented_receive_wqe as codec

ROOT=base.ROOT;digest=base.digest;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive as candidate


def original_entry():
    method=base.admission.old.Atomic128AdmissionTests.entry
    t=candidate.once(inspect.getsource(method),'as02_atomic_wqe_encode','as02_segmented_receive_wqe_encode')
    namespace=dict(method.__globals__);exec(compile('class ExactEntry:\n'+t,__file__+':entry','exec'),namespace)
    return namespace['ExactEntry'].entry


class ReceiveAdmission(base.ImmediateAdmission):
    reports={};encoded_entry=original_entry()
    @classmethod
    def setUpClass(cls):codec.SegmentedReceiveWQE.setUpClass.__func__(cls)

    def entry(self,w=None,**kwargs):
        w=w or base.admission.old.candidate()
        b=w.base
        # Monitor the REAL MR request, independently of both serialization
        # internals and downstream owner fields. A length1 grant is wrong.
        prefix=f'''monitor_receive={int(b.opcode==4)};expected_capacity=32'd{b.length};
expected_local_address=64'h{b.local_address:016x};expected_local_key=32'h{b.local_key:08x};
'''
        return prefix+self.encoded_entry(w,**kwargs)

    def simulate(self,*args,**kwargs):
        saved=base.admission.source;prior=base.admission.old.bench
        def checked_bench(*a,**kw):
            t=prior(*a,**kw)
            return candidate.once(t,'reg clk=0;',r'''
reg monitor_receive=0;reg [31:0] expected_capacity=0,expected_local_key=0;
reg [63:0] expected_local_address=0;
always @(posedge clk)if(!rst && monitor_receive && qv && qr && allow_q)begin
 if(qlen!==expected_capacity || qa!==expected_local_address || qkey!==expected_local_key || qop!==3'd1)
 $fatal(1,"RECV full capacity/full key/VA/local-write permission lost on actual MR query");
end
reg clk=0;''')
        try:
            base.admission.source=candidate;base.admission.old.bench=checked_bench
            base.admission.ReadAdmission.simulate(self,*args,**kwargs)
        finally:base.admission.source=saved;base.admission.old.bench=prior

    def test_receive_full_posted_capacity_real_MR_query_and_stalls(self):
        self.simulate(''.join(self.entry(base.admission.old.candidate(4,length=n))for n in
            [1,65,4096,4097,8192,8193,65537,1048576]),receive_only=True,extent=1052672)

    def test_receive_actual_MR_denies_readonly_stale_full_key_PD_and_final_byte(self):
        old=base.admission.old;key=old.old.original.KEY
        self.simulate(''.join([
            self.entry(old.candidate(4,length=8193,local_key=0),error=1),
            self.entry(old.candidate(4,length=8193,local_key=key^0x80000000),error=1),
            self.entry(old.candidate(4,length=8193,local_key=key+1),error=3),
            self.entry(old.candidate(4,length=8193),context=(1,8,0xf123,old.old.original.SEQ,old.old.original.EPOCH),error=2),
            self.entry(old.candidate(4,length=8193),error=4),
            self.entry(old.candidate(4,length=4097,local_address=(old.old.original.BASE+1)&((1<<48)-1)),error=4)
        ]),receive_only=True)
        self.simulate(self.entry(old.candidate(4,length=1048576,local_address=old.old.original.BASE))+
            self.entry(old.candidate(4,length=1048576,local_address=old.old.original.BASE+1),error=4),receive_only=True,extent=1048576)

    def test_receive_full_bytes_no_remote_Immediate_Atomic_or_reserved_authority(self):
        mutations=[(lambda b:b.__setitem__(24,1),0x20),(lambda b:b.__setitem__(40,1),0x20),
            (lambda b:b.__setitem__(48,1),0x20),(lambda b:b.__setitem__(64,1),0x20),
            (lambda b:b.__setitem__(72,1),0x20),(lambda b:b.__setitem__(127,1),0x20),
            (lambda b:b.__setitem__(46,0),0x25),
            (lambda b:b.__setitem__(slice(32,36),(1048577).to_bytes(4,'little')),0x26)]
        self.simulate(''.join(self.entry(base.admission.old.candidate(4,length=8193),mutate=m,error=e,queries=0)
            for m,e in mutations),receive_only=True,extent=1052672)

    def test_receive_unknown_capacity_key_or_trusted_epoch_never_gains_MR(self):
        for byte in [16,32,36,56,63,127]:
            self.simulate(self.entry(base.admission.old.candidate(4,length=8193),unknown_byte=byte,error=0x20,queries=0),
                receive_only=True,extent=1052672)

    def test_receive_revoked_registered_MR_never_reuses_old_grant(self):
        old=base.admission.old
        self.simulate(self.entry(old.candidate(4,length=8193))+
            "monitor_receive=0;manage(2,0,32'h80000008,0,0,0,0);\n"+
            self.entry(old.candidate(4,length=8193),error=1),receive_only=True,extent=1052672)


class ReceiveHLSSQ(base.ImmediateHLSSQ):
    reports={}
    def simulate(self,*a,**kw):
        saved=base.staging.source
        try:base.staging.source=candidate;base.staging.ReadHLSSQ.simulate(self,*a,**kw)
        finally:base.staging.source=saved

    def test_receive_owner_can_never_be_transmitted_as_SEND_SQ(self):
        for n in [0,65,4096,4097,8193,1048576]:
            ctx=base.staging.old.context(4,compare=0,operand=0,remote=0,rkey=0,length=n)
            self.simulate(f's_work_context={ctx};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);
if(fault!==1'b1 || s_work_ready || m_owner_valid || m_axis_sq_tvalid || owner_handoff_count ||
 HLS_SQ_handoff_count || queue_guard!==255)$fatal(1,"posted receive became an outgoing SEND request");
''')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    files=[*helpers,*candidate.RTL.glob('*.v'),*[codec.KERNEL/n for n in codec.SOURCES],*codec.KERNEL.glob('wqe*.h'),Path(__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in dict.fromkeys(files)}
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in [ReceiveAdmission,ReceiveHLSSQ])
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite);same=all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,all25_prior_methods_retained=True,
        actual_C128_receive_codec=True,actual_MR_table=True,real_query_full_capacity_key_VA_local_write_monitored=True,
        RECV_never_TX_SQ=True,receive_source_limit=1048576,native_or_hardware_runtime=False,
        raw_SQ_MMIO_context_and_work_HLS_endpoints_modeled=True,four_state=True,hardware_verified=False,
        tests=dict(MR=ReceiveAdmission.reports,HLS_SQ=ReceiveHLSSQ.reports),
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not result['pass_test'])


if __name__=='__main__':main()
