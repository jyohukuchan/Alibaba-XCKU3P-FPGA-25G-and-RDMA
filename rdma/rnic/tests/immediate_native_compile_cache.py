# SPDX-License-Identifier: BSD-2-Clause-Views
"""Regenerate changed bench; reuse ONLY verified byte-identical compiler inputs.

Old failure logs/report/binary are immutable. This reuses task-owned RAM
objects, not a test result. Every changed C++/header is rebuilt normally.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import check_immediate_native_elaboration as source

ROOT=source.ROOT
digest=source.delivery.digest


def compile(command,run,env,previous_report):
    old=json.loads(previous_report.read_text());oldrun=ROOT/old['directory']
    obj=Path(old['compile_directory']).resolve()
    if obj.parent!=Path('/dev/shm')or not obj.name.startswith('as02-immediate-native-')or obj.is_symlink():
        raise ValueError('exact task-owned Immediate RAM object directory required')
    if oldrun.parent!=ROOT/'rdma/rnic/build'or oldrun.is_symlink():raise ValueError('wrong previous native run')
    if digest(oldrun/'Vtb')!=old['binary_sha256']:raise ValueError('previous exact compiled binary changed')
    # Keep old paths for IDENTICAL generated RTL so filename strings do not
    # cause artificial rebuilds. Every genuinely consumed source is hashed.
    paths={}
    for p in [Path(s)for s in command if s.endswith('.v')]:
        if p.parent==run and p.name!='tb.v':
            earlier=oldrun/p.name
            if digest(earlier)!=old['source_sha256'][str(earlier.relative_to(ROOT))]:
                raise ValueError('previous frozen native RTL was modified '+p.name)
            # Changed RTL is freshly translated under its NEW path; GNU
            # make then rebuilds every changed C++/header normally. Only
            # byte-identical RTL retains its old filename strings/cache.
            if digest(earlier)==digest(p):paths[str(p)]=str(earlier)
    cmd=[paths.get(s,s)for s in command]
    i=cmd.index('--Mdir');cmd[i+1]=str(obj)
    saved={p:(digest(p),p.stat().st_atime_ns,p.stat().st_mtime_ns)for p in obj.iterdir()
        if p.suffix in ['.cpp','.h','.mk']}
    generate=[cmd[0],'--cc','--exe','--main',*cmd[2:]]
    started=time.monotonic()
    with(run/'generate.log').open('x')as log:
        r=subprocess.run(generate,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if r.returncode:raise RuntimeError('fresh native bench translation failed '+str(run/'generate.log'))
    identical=[]
    for p,(sha,atime,mtime)in saved.items():
        if p.is_file()and digest(p)==sha:os.utime(p,ns=(atime,mtime));identical.append(p)
    rtl=[Path(s)for s in cmd if s.endswith('.v')]
    # SV was freshly translated. Ignore identical C++ prerequisites ONLY;
    # all changed headers and generated C++ remain real make dependencies.
    ignored=list(dict.fromkeys([*rtl,*identical]))
    make=['make','-C',str(obj),'-f','Vtb.mk','-j','4',*[v for p in ignored for v in ['-o',str(p)]],'Vtb']
    with(run/'compile.log').open('x')as log:
        r=subprocess.run(make,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,
            timeout=max(1,1200-(time.monotonic()-started)))
    if r.returncode:raise RuntimeError('changed native bench compile failed '+str(run/'compile.log'))
    consumed={str(Path(v).relative_to(ROOT)):digest(Path(v))for v in paths.values()}
    consumed[str(previous_report.relative_to(ROOT))]=digest(previous_report)
    return dict(compilation_seconds=time.monotonic()-started,compile_directory=str(obj),
        fresh_generate_command=generate,compile_command=make,compiler_cache_only_reused=True,
        previous_compiler_report=str(previous_report.relative_to(ROOT)),
        verified_identical_generated_CPP_files=len(identical),extra_source_sha256=consumed)
