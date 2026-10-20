# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh RTL translation, reuse only byte-identical task-owned compiler inputs.

Old logs/report/executable remain immutable. Changed generated C++/headers
keep real make dependencies. No prior test result or completion is reused.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from probe_atomic_shared import ROOT,digest


def compile(command,run,env,previous_report):
    old=json.loads(previous_report.read_text());run_path=ROOT/old['directory'];obj_path=Path(old['compile_directory'])
    if run_path.is_symlink()or obj_path.is_symlink():raise ValueError('do not follow cache/run symlinks')
    oldrun=run_path.resolve();obj=obj_path.resolve()
    if not old.get('actual_generated_HLS')or not old.get('two_state'):
        raise ValueError('previous actual Atomic generated composition required')
    if obj.parent!=Path('/dev/shm')or not obj.name.startswith('as02-atomic-generated-obj-')or obj.is_symlink():
        raise ValueError('exact task-owned Atomic compiler directory required')
    if oldrun.parent!=ROOT/'rdma/rnic/build'or not oldrun.name.startswith('atomic-generated-')or oldrun.is_symlink():
        raise ValueError('wrong previous Atomic run')
    binary=oldrun/'Vtb';key=str(binary.relative_to(ROOT))
    if not binary.is_file()or digest(binary)!=old.get('artifact_sha256',{}).get(key):
        raise ValueError('previous exact compiled binary unavailable/changed')
    paths={}
    for p in [Path(s)for s in command if s.endswith('.v')]:
        if p.parent==run and p.name!='tb.v':
            earlier=oldrun/p.name
            if digest(earlier)!=old['source_sha256'].get(str(earlier.relative_to(ROOT))):
                raise ValueError('previous frozen generated RTL changed')
            if digest(earlier)==digest(p):paths[str(p)]=str(earlier)
    cmd=[paths.get(s,s)for s in command];cmd[cmd.index('--Mdir')+1]=str(obj)
    saved={p:(digest(p),p.stat().st_atime_ns,p.stat().st_mtime_ns)for p in obj.iterdir()
        if p.suffix in ['.cpp','.h','.mk']}
    started=time.monotonic();generate=[cmd[0],'--cc','--exe','--main',*cmd[2:]]
    with(run/'generate.log').open('x')as log:
        r=subprocess.run(generate,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if r.returncode:raise RuntimeError('fresh changed RTL translation failed')
    identical=[]
    for p,(sha,atime,mtime)in saved.items():
        if p.is_file()and digest(p)==sha:os.utime(p,ns=(atime,mtime));identical.append(p)
    # Ignore unchanged prerequisites ONLY. All changed headers/C++ remain
    # prerequisites. The selected RTL was freshly consumed by Verilator.
    ignored=list(dict.fromkeys([*[Path(s)for s in cmd if s.endswith('.v')],*identical]))
    make=['make','-C',str(obj),'-f','Vtb.mk','-j','4',*[v for p in ignored for v in ['-o',str(p)]],'Vtb']
    with(run/'compile.log').open('x')as log:
        r=subprocess.run(make,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,
            timeout=max(1,1200-(time.monotonic()-started)))
    if r.returncode:raise RuntimeError('changed generated composition compilation failed')
    consumed={str(Path(v).relative_to(ROOT)):digest(Path(v))for v in paths.values()}
    consumed[str(previous_report.relative_to(ROOT))]=digest(previous_report)
    return dict(compile_seconds=time.monotonic()-started,compile_directory=str(obj),
        fresh_generate_command=generate,compile_command=make,compiler_cache_only_reused=True,
        previous_compiler_report=str(previous_report.relative_to(ROOT)),
        verified_identical_generated_CPP_files=len(identical),extra_source_sha256=consumed)
