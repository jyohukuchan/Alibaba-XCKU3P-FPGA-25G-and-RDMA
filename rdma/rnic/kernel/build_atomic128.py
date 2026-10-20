#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze/build full checked128-byte kernel cohort against running headers.

Actual SQ allocation/posting/MR/CQ/standard callbacks compile and link; no
callback is executed in Linux, no install/load/MMIO/DMA/hardware/signoff.
Original default sources and IB_ATOMIC_NONE advertisement remain unchanged.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import build_frozen as old
import derive_atomic128 as candidate

ROOT=old.ROOT;KERNEL=old.SOURCE;digest=old.digest


def freeze(run,parent):
    derived=candidate.derive()
    names=list(dict.fromkeys(old.OWN+['wqe_atomic.c','wqe_atomic.h','atomic_profile.h','verbs_atomic_wqe.c']))
    before={str((KERNEL/n).relative_to(ROOT)):digest(KERNEL/n)for n in names}
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [Path(__file__).resolve(),Path(candidate.__file__).resolve(),Path(old.__file__).resolve()]})
    for n in names:
        if KERNEL/n in derived:(run/n).write_text(derived[KERNEL/n])
        else:shutil.copy2(KERNEL/n,run/n)
    (run/'parent').mkdir()
    for n in old.HEADERS:
        shutil.copy2(parent/n,run/'parent'/n);before[str((parent/n).relative_to(ROOT))]=digest(parent/n)
    frozen={str(p.relative_to(run)):digest(p)for p in run.rglob('*')if p.is_file()}
    return before,frozen


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh1GiB source-build guard')
    parent=ROOT/'external/corundum/modules/mqnic'
    revision=subprocess.check_output(['git','-C',str(parent),'rev-parse','HEAD'],text=True).strip()
    if revision!=old.PARENT_COMMIT:raise ValueError('reviewed pinned parent required')
    run=Path(tempfile.mkdtemp(prefix='atomic128-kernel-frozen-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),default_sources_changed=False,
        atomic_cap_advertised=False,installed=False,module_load_performed=False,hardware_verified=False,
        actual_kernel_callback_runtime=False,standard_provider_runtime=False)
    try:
        before,frozen=freeze(run,parent);report.update(source_sha256=before,frozen_input_sha256=frozen)
        compiler=Path(shutil.which('x86_64-linux-gnu-gcc-13')).resolve()
        command=['make','-C',str(run),'-j4','CC='+str(compiler),'AS02_BUILD_AUX=1','MQNIC_SRC='+str(run/'parent'),'module']
        report.update(command=command,kernel=os.uname().release,compiler=str(compiler),compiler_sha256=digest(compiler),W=1)
        print(json.dumps(dict(directory=str(run),compile_limit_seconds=180)),flush=True)
        start=time.monotonic()
        with(run/'build.log').open('x')as log:c=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        report.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('matched kernel build failed: '+str(run/'build.log'))
        symbols=subprocess.check_output(['nm','-g','--defined-only',str(run/'as02_mr_support.ko')],text=True)
        wanted=['as02_atomic_wqe_validate','as02_atomic_wqe_encode','as02_atomic_wqe_decode',
            'as02_atomic_wqe_from_ib_send_wr','as02_atomic_wqe_from_ib_recv_wr','as02_sq_post','as02_sq_post_recv',
            'as02_sq_complete_event','as02_sq_bind_transport_profile','as02_cq_io_poll','as02_device_publish']
        names={l.split()[-1]for l in symbols.splitlines()if l.split()}
        if not set(wanted)<=names:raise ValueError('actual matched kernel paths not linked')
        metadata={}
        for n in ['as02_mr_support','as02_rnic_ctrl']:
            metadata[n]={f:subprocess.check_output(['modinfo','-F',f,str(run/(n+'.ko'))],text=True).strip()for f in ['vermagic','alias','parm']}
            if not metadata[n]['vermagic'].startswith(os.uname().release+' '):raise ValueError('wrong running kernel')
        old.checked(before,ROOT);old.checked(frozen,run)
        report.update(pass_test=True,source_and_frozen_inputs_unchanged=True,actual_kernel_symbols_linked=wanted,modules=metadata)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()and
            (p.suffix=='.ko'or p.name=='build.log')}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],directory=report['directory'])),flush=True)


if __name__=='__main__':main()

