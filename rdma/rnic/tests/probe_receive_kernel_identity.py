#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual new IO C: exact RQC31/CQC255 geometry; old identities preserved.

Explicit CSR read models, not full binding/callback/native/hardware proof.
No synthetic kernel build report, install/load or support advertisement.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3];KERNEL=ROOT/'rdma/rnic/kernel'
sys.path.insert(0,str(KERNEL))
import derive_segmented_receive_kernel as candidate
import build_frozen as binding


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    run=Path(tempfile.mkdtemp(prefix='receive-kernel-identity-',dir=ROOT/'rdma/rnic/build'))
    derived=candidate.derive()
    names=['sq_io.c','cq_io.c','wqe.c','wqe_atomic.c','wqe_zero.c','wqe_segmented.c','wqe_segmented_read.c','wqe_segmented_immediate.c','wqe_segmented_receive.c']
    inputs=[KERNEL/n for n in names]+list(KERNEL.glob('*.h'))
    inputs+=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/receive_kernel_identity.c']
    inputs+=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(KERNEL)]
    before={str(p.relative_to(ROOT)):binding.digest(p)for p in inputs}
    for src in inputs:
        if src.parent==KERNEL and src.suffix in ['.c','.h']:
            if src in derived:(run/src.name).write_text(derived[src])
            else:shutil.copy2(src,run/src.name)
    shutil.copy2(ROOT/'rdma/rnic/tests/receive_kernel_identity.c',run/'cases.c')
    frozen={str(p.relative_to(ROOT)):binding.digest(p)for p in run.iterdir()if p.is_file()}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        frozen_input_sha256=frozen,actual_IO_C=True,CSR_reads_modeled=True,full_kernel_binding_or_native_or_physical=False,hardware_verified=False)
    try:
        command=['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
            '-I',str(run),'-include',str(run/'atomic_profile.h'),*[str(run/n)for n in names],str(run/'cases.c'),'-o',str(run/'cases')]
        report['compile_command']=command
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('actual new IO C compile failed')
        start=time.monotonic();c=subprocess.run([str(run/'cases')],capture_output=True,text=True,timeout=10)
        (run/'cases.log').write_text(c.stdout+c.stderr);report.update(seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode:raise ValueError('actual IO identity/geometry unit failed')
        rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith('RECEIVE_KERNEL_IDENTITY ')]
        if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['cases']!=2442:raise ValueError('all exact384 SQ/RQ+2048 CQ+10 notification cases required')
        binding.checked(before,ROOT);binding.checked(frozen,ROOT)
        report.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):binding.digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=2442,seconds=report['seconds'])),flush=True)


if __name__=='__main__':main()
