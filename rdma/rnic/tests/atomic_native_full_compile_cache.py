# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh full-native translation, only identical compiler inputs reused.

Previous sources/report/frozen executable are immutable. New executables
are frozen in task-owned RAM, not copied onto the nearly full root volume.
This is a compiler cache, never evidence that a functional test passed.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import atomic_native_owned_compile_cache as prior

ROOT=prior.ROOT;digest=prior.digest


def compile(command,run,env,previous_report):
    old=json.loads(previous_report.read_text());oldrun=ROOT/old['directory']
    obj=Path(old['compile_directory'])
    if obj.parent!=Path('/dev/shm') or not obj.name.startswith('as02-immediate-native-') or obj.is_symlink():
        raise ValueError('exact task-owned native RAM compiler directory required')
    if oldrun.parent!=ROOT/'rdma/rnic/build' or oldrun.is_symlink():raise ValueError('wrong previous native run')
    frozen=Path(old.get('frozen_binary_path',oldrun/'Vtb'))
    if 'frozen_binary_path' in old:
        directory=frozen.parent
        if directory.parent!=Path('/dev/shm') or not directory.name.startswith('as02-atomic-native-artifacts-') or directory.is_symlink():
            raise ValueError('wrong previous frozen RAM artifact directory')
        if frozen.name!='Vtb' or frozen.is_symlink() or frozen.resolve()==obj/'Vtb':raise ValueError('mutable/aliased executable')
    if digest(frozen)!=old['binary_sha256']:raise ValueError('previous frozen native executable changed')
    paths={}
    for p in [Path(s) for s in command if s.endswith('.v')]:
        if p.parent==run and p.name!='tb.v':
            earlier=oldrun/p.name
            if digest(earlier)!=old['source_sha256'][str(earlier.relative_to(ROOT))]:
                raise ValueError('previous frozen wrapper changed '+p.name)
            if digest(earlier)==digest(p):paths[str(p)]=str(earlier)
    cmd=[paths.get(s,s) for s in command];i=cmd.index('--Mdir');cmd[i+1]=str(obj)
    saved={p:(digest(p),p.stat().st_atime_ns,p.stat().st_mtime_ns) for p in obj.iterdir() if p.suffix in ['.cpp','.h','.mk']}
    generate=[cmd[0],'--cc','--exe','--main',*cmd[2:]];started=time.monotonic()
    with(run/'generate.log').open('x')as log:
        r=subprocess.run(generate,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if r.returncode:raise RuntimeError('fresh full native translation failed '+str(run/'generate.log'))
    identical=[]
    for p,(sha,atime,mtime)in saved.items():
        if p.is_file() and digest(p)==sha:os.utime(p,ns=(atime,mtime));identical.append(p)
    # RTL was freshly translated; only identical C++/header/make inputs keep
    # old timestamps. Changed headers/C++ remain ordinary make dependencies.
    ignored=list(dict.fromkeys([*[Path(s)for s in cmd if s.endswith('.v')],*identical]))
    make=['make','-C',str(obj),'-f','Vtb.mk','-j','4',*[v for p in ignored for v in ['-o',str(p)]],'Vtb']
    with(run/'compile.log').open('x')as log:
        r=subprocess.run(make,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,1200-(time.monotonic()-started)))
    if r.returncode:raise RuntimeError('changed full native compile failed '+str(run/'compile.log'))
    consumed={str(Path(v).relative_to(ROOT)):digest(Path(v))for v in paths.values()}
    consumed[str(previous_report.relative_to(ROOT))]=digest(previous_report)
    return dict(compilation_seconds=time.monotonic()-started,compile_directory=str(obj),
        fresh_generate_command=generate,compile_command=make,compiler_cache_only_reused=True,
        previous_compiler_report=str(previous_report.relative_to(ROOT)),
        verified_identical_generated_CPP_files=len(identical),extra_source_sha256=consumed)
