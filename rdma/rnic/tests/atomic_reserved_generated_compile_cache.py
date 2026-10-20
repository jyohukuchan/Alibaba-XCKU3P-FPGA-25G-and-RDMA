# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh reserved-owner RTL translation, byte-identical compiler inputs only.

Never reuse a previous test result. Old failed/passed binary/report/logs stay
immutable; changed C++/headers retain normal make dependencies.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from probe_atomic_shared import ROOT,digest


def compile(command,run,env,previous_report):
    old=json.loads(previous_report.read_text());rp=ROOT/old['directory'];op=Path(old['compile_directory'])
    if rp.is_symlink()or op.is_symlink():raise ValueError('no cache/run symlinks')
    oldrun=rp.resolve();obj=op.resolve()
    if not old.get('actual_generated_HLS')or not old.get('two_state'):raise ValueError('actual owned composition required')
    if obj.parent!=Path('/dev/shm')or not obj.name.startswith('as02-atomic-owned-generated-obj-'):
        raise ValueError('exact task-owned compiler cache required')
    if oldrun.parent!=ROOT/'rdma/rnic/build'or not oldrun.name.startswith('atomic-owned-generated-'):
        raise ValueError('exact old owned composition run required')
    binary=oldrun/'Vtb'
    if not binary.is_file()or digest(binary)!=old.get('artifact_sha256',{}).get(str(binary.relative_to(ROOT))):
        raise ValueError('old exact compiled binary missing/changed')
    paths={}
    for p in [Path(s)for s in command if s.endswith('.v')]:
        if p.parent==run and p.name!='tb.v':
            earlier=oldrun/p.name
            # The new reservation wrapper has no counterpart in086. It is
            # freshly translated, not reused; other old wrappers stay strict.
            if p.name=='rocev2_atomic_reserved_mac_integrity_transport.v'and not earlier.exists():continue
            if not earlier.is_file()or digest(earlier)!=old['source_sha256'].get(str(earlier.relative_to(ROOT))):
                raise ValueError('old frozen generated wrapper missing/changed')
            if digest(earlier)==digest(p):paths[str(p)]=str(earlier)
    cmd=[paths.get(s,s)for s in command];cmd[cmd.index('--Mdir')+1]=str(obj)
    saved={p:(digest(p),p.stat().st_atime_ns,p.stat().st_mtime_ns)for p in obj.iterdir()if p.suffix in ['.cpp','.h','.mk']}
    start=time.monotonic();generate=[cmd[0],'--cc','--exe','--main',*cmd[2:]]
    with(run/'generate.log').open('x')as log:
        r=subprocess.run(generate,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if r.returncode:raise RuntimeError('fresh owned RTL translation failed')
    identical=[]
    for p,(sha,atime,mtime)in saved.items():
        if p.is_file()and digest(p)==sha:os.utime(p,ns=(atime,mtime));identical.append(p)
    ignored=list(dict.fromkeys([*[Path(s)for s in cmd if s.endswith('.v')],*identical]))
    make=['make','-C',str(obj),'-f','Vtb.mk','-j','8',*[v for p in ignored for v in ['-o',str(p)]],'Vtb']
    with(run/'compile.log').open('x')as log:
        r=subprocess.run(make,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,1200-(time.monotonic()-start)))
    if r.returncode:raise RuntimeError('changed owned generated compilation failed')
    consumed={str(Path(v).relative_to(ROOT)):digest(Path(v))for v in paths.values()}
    consumed[str(previous_report.relative_to(ROOT))]=digest(previous_report)
    return dict(compile_seconds=time.monotonic()-start,compile_directory=str(obj),fresh_generate_command=generate,
        compile_command=make,compiler_cache_only_reused=True,previous_compiler_report=str(previous_report.relative_to(ROOT)),
        verified_identical_generated_CPP_files=len(identical),extra_source_sha256=consumed)
