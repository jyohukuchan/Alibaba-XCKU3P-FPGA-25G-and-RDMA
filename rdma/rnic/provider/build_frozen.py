#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Build actual pinned-rdma-core50/PABI34 AS02 provider, never install/open NIC.

Uses real installed libibverbs private34 symbols with upstream50.0 headers.
No kernel module, driver config, network, FPGA or /dev/infiniband is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
PIN='bc6b4bc134532e952fe7f8efc251e1f89b912098'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rdma-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    core=a.rdma_core.resolve();revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
    if revision!=PIN:raise ValueError('unreviewed rdma-core revision')
    inc=core/'build/include'
    if '#define IBVERBS_PABI_VERSION 34'not in (inc/'config.h').read_text():raise ValueError('private ABI mismatch')
    own=[Path(__file__).resolve(),Path(__file__).with_name('as02.c'),Path(__file__).with_name('as02.driver')]
    hashes={str(x.relative_to(ROOT)):digest(x)for x in own}
    run=Path(tempfile.mkdtemp(prefix='provider-frozen-',dir=ROOT/'rdma/rnic/build'))
    for x in own:shutil.copy2(x,run/x.name)
    frozen={x.name:digest(x)for x in run.iterdir()}
    command=['cc','-std=gnu11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-O2','-fPIC','-shared',
        '-isystem',str(inc),'-isystem',str(core),str(run/'as02.c'),'-pthread','-Wl,-z,defs',
        '-libverbs','-o',str(run/'libas02-rdmav34.so')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=hashes,frozen_sha256=frozen,directory=str(run.relative_to(ROOT)),
        rdma_core_commit=revision,rdma_core=str(core),provider_PABI=34,command=command,
        installed=False,NIC_opened=False,hardware_verified=False,bus_driver_wired=False)
    try:
        start=time.monotonic();r=subprocess.run(command,capture_output=True,text=True,timeout=60)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        # Constructor registration is process-local libibverbs bookkeeping,
        # not installation or a kernel/NIC open. Resolve the real shared
        # object's provider descriptor, rather than just inspecting an ELF.
        test=['python3','-c',
            'import ctypes,sys; p=ctypes.CDLL(sys.argv[1]); '
            'assert ctypes.c_char_p.in_dll(p,"verbs_provider_as02").value==b"as02"; '
            'print("PROVIDER_DLOPEN_PASS")',str(run/'libas02-rdmav34.so')]
        start=time.monotonic();probe=subprocess.run(test,capture_output=True,text=True,timeout=10)
        report.update(dynamic_load_seconds=time.monotonic()-start,dynamic_load_command=test,
            dynamic_load_output=probe.stdout+probe.stderr)
        if probe.returncode or probe.stdout.strip()!='PROVIDER_DLOPEN_PASS':raise RuntimeError('provider dlopen failed: '+probe.stdout+probe.stderr)
        if hashes!={n:digest(ROOT/n)for n in hashes}or frozen!={n:digest(run/n)for n in frozen}:raise ValueError('inputs changed')
        report.update(pass_test=True,source_unchanged=True,dynamic_load_only_tested=True,binary_sha256=digest(run/'libas02-rdmav34.so'),
            upstream_headers_sha256={str(x.relative_to(core)):digest(x)for x in [inc/'config.h',core/'libibverbs/driver.h',core/'libibverbs/verbs.h']})
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','directory','compile_seconds','provider_PABI']}))
if __name__=='__main__':main()
