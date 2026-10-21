#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual READ C128 codec -> SQ admission -> real full-range local MR table.

Raw fetched-record source/consumer and MMIO management are models, not PCIe
fetch/native DMA/HLS/CQ/Linux proof. Original eight Atomic admission methods
are retained; no modeled MR grant or internal force supplies authorization.
"""
import argparse
import ctypes as C
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import test_atomic128_admission_rtl as old
import test_segmented_read_wqe as codec

ROOT=old.ROOT;digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_profile as source


def read_entry():
    t=source.once(inspect.getsource(old.Atomic128AdmissionTests.entry),
        'as02_atomic_wqe_encode','as02_segmented_read_wqe_encode')
    scope=dict(old.Atomic128AdmissionTests.entry.__globals__)
    exec(compile('class InheritedEntry:\n'+t,__file__+':entry','exec'),scope)
    return scope['InheritedEntry'].entry


class ReadAdmission(old.Atomic128AdmissionTests):
    reports={}
    entry=read_entry()
    @classmethod
    def setUpClass(cls):codec.SegmentedReadWQE.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def simulate(self,body,receive_only=False,extent=8192):
        run=Path(tempfile.mkdtemp(prefix='segmented-read-admission-',dir=ROOT/'rdma/rnic/build'))
        generated=source.derive();tb=old.bench(body,receive_only)
        tb=source.once(tb,'rocev2_atomic128_sq_wqe_admission #(','rocev2_sq_wqe_admission #(')
        if extent!=8192:
            if tb.count("64'd8192")!=2:raise ValueError('two actual registered local MR extents required')
            tb=tb.replace("64'd8192",f"64'd{extent}")
        (run/'tb.v').write_text(tb);leaves=[]
        for n in ['rocev2_wqe_admission.v','rocev2_sq_wqe_admission.v']:
            q=run/n;q.write_text(generated[source.RTL/n]);leaves.append(q)
        info=dict(pass_test=False,directory=str(run.relative_to(ROOT)),registered_MR_extent=extent,runtime_limit_seconds=10)
        self.reports.setdefault(self._testMethodName,[]).append(info)
        try:
            command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),
                *map(str,leaves),str(source.RTL/'rocev2_mr_table.v')]
            c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=10)
            info['seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('WQE_ADMISSION_PASS',r.stdout)
            info.update(pass_test=True,observed_summary=r.stdout.strip().splitlines()[-1])
        finally:info['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}

    def test_large_READ_actual_C_and_real_MR_full_range_with_stalls(self):
        self.simulate(''.join(self.entry(old.candidate(2,length=n,remote_key=k))
            for n in [4097,8192,8193,65537,1048576]for k in [0,0xffffffff]),extent=1052672)

    def test_large_READ_actual_MR_denies_key_PD_readonly_and_last_byte_range(self):
        self.simulate(''.join([
            self.entry(old.candidate(2,length=8193,local_key=0),error=1),
            self.entry(old.candidate(2,length=8193,local_key=old.old.original.KEY+1),error=3),
            self.entry(old.candidate(2,length=8193),context=(1,8,0xf123,old.old.original.SEQ,old.old.original.EPOCH),error=2),
            self.entry(old.candidate(2,length=8193,local_address=old.old.original.BASE+1),error=4)]))

    def test_large_READ_size_epoch_sequence_reserved_and_operands_fail_before_MR(self):
        cases=[(lambda b:b.__setitem__(slice(32,36),(1048577).to_bytes(4,'little')),0x26),
            (lambda b:b.__setitem__(slice(56,64),(1).to_bytes(8,'little')),0x22),
            (lambda b:b.__setitem__(slice(8,16),(1).to_bytes(8,'little')),0x23),
            (lambda b:b.__setitem__(72,1),0x20),(lambda b:b.__setitem__(127,1),0x20)]
        self.simulate(''.join(self.entry(old.candidate(2,length=8193),mutate=mutation,error=error,queries=0)
            for mutation,error in cases),extent=1052672)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*helpers,*list((ROOT/'rdma/rnic/fpga').glob('*.py')),*[codec.KERNEL/n for n in codec.SOURCES],
        *codec.KERNEL.glob('wqe*.h'),source.RTL/'rocev2_mr_table.v',Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadAdmission))
    same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,cases=sum(map(len,ReadAdmission.reports.values())),
        seconds=time.monotonic()-start,source_sha256=before,source_unchanged=same,actual_MR_table=True,
        all_eight_original_Atomic_admission_methods_retained=True,actual_C128_READ_codec=True,
        raw_SQ_source_and_consumer_modeled=True,native_runtime=False,hardware_verified=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors],tests=ReadAdmission.reports)
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
