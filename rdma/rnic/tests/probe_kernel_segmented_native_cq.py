#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual matched kernel C consumes unedited8191 native large/old SQ/CQs.

Require ALL29 terminal native success and matched real-header kernel build.
Compare all128 actual posted bytes; decode genuine native31/748/0xa0 events
and retire actual C CQ/MR refs. Linux/pins/DMA/MMIO remain separate MODELS,
not actual Linux/provider/live RTL/page-table coupling or hardware proof.
"""
import ast
from pathlib import Path
import probe_kernel_atomic128_native_cq as parent

CASES=[('CAS',7,8),('FADD',8,8),('READ',2,65),('SEND_IMM',5,65),('WRITE',1,65),('SEND',3,65),
       ('LARGE_WRITE',1,8193),('LARGE_SEND',3,8193),('ZERO_WRITE',1,0),('ZERO_READ',2,0),
       ('ZERO_SEND',3,0),('ZERO_SEND_IMM',5,0),('ZERO_WRITE_IMM',6,0)]


def runner_source():
    t=Path(parent.__file__).read_text()
    from segmented_kernel_models import once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import atomic128_kernel_models as model','import segmented_kernel_models as model')
    t=once(t,'import build_atomic128 as build','import build_zero as build')
    marker="    frozen=ROOT/kernel['directory'];"
    t=once(t,marker,"    if len(native.get('tests',{}))!=29 or (native.get('RNC_features'),native.get('CQC_features'))!=(8191,31) or \\\n"
        "       (kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(8191,31,4):\n"
        "        raise ValueError('exact all29 native8191/31 and matched kernel profile4 required')\n"+marker)
    t=once(t,"prefix='atomic128-kernel-native-cq-'","prefix='segmented-kernel-native-cq-'")
    t=t.replace('kernel_atomic128_native_cq.c','kernel_segmented_native_cq.c')
    t=once(t,"k/'wqe_atomic.c',k/'verbs_atomic_wqe.c',",
        "k/'wqe_atomic.c',k/'verbs_atomic_wqe.c',k/'wqe_zero.c',k/'verbs_zero_wqe.c',\n"
        "                k/'wqe_segmented.c',k/'verbs_segmented_wqe.c',")
    t=once(t,"for n in ['CAS','FADD','READ','SEND_IMM']for kind",f"for n in {[n for n,_,_ in CASES]!r}for kind")
    marker='    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}'
    t=once(t,marker,'    own.extend(Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,"__file__",None)and\n'
        '        Path(m.__file__).resolve().is_relative_to(ROOT/"rdma/rnic"))\n'+marker)
    t=once(t,'hardware_verified=False,simulation_limit_seconds=10,tests={})',
        'hardware_verified=False,simulation_limit_seconds=10,RNC_features=8191,CQC_features=31,software_profile=4,\n'
        '        actual_Linux_runtime=False,standard_provider_execution=False,page_tables_live_coupled=False,tests={})')
    t=once(t,"for name,op in [('CAS',7),('FADD',8),('READ',2),('SEND_IMM',5)]:",
        f'for name,op,length in {CASES!r}:')
    t=once(t,'for mutation in range(3):','for mutation in range(5):')
    t=once(t,'str(op),str(mutation)],','str(op),str(length),str(mutation)],')
    t=once(t,"startswith('KERNEL_ATOMIC128_NATIVE_CQ ')","startswith('KERNEL_SEGMENTED_NATIVE_CQ ')")
    t=once(t,'        report.update(pass_test=True,source_unchanged=True)',
        "        if len(report['tests'])!=65:raise ValueError('all13 genuine snapshot pairs andfour mutations each required')\n"
        '        report.update(pass_test=True,source_unchanged=True)')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
         dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
