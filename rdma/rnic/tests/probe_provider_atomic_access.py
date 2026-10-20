#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual matched provider public QP/MR access and Atomic serialization.

Installed libibverbs and pinned rdma-core50/PABI34 headers; ONLY fake-fd
ioctl/write replies model kernel. No real NIC/context/driver/provider install,
DMA, kernel callback or device capability claim. ASan/UBSan, <=10s/case.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
import probe_provider_commands as old
sys.path.insert(0,str(old.ROOT/'rdma/rnic/provider'))
import derive_atomic_access as candidate

ROOT=old.ROOT;digest=old.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rdma-core',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    core=a.rdma_core.resolve()
    if subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()!=old.PIN:
        raise ValueError('unreviewed pinned headers')
    run=Path(tempfile.mkdtemp(prefix='provider-atomic-access-',dir=ROOT/'rdma/rnic/build'))
    (run/'tests').mkdir();(run/'provider').mkdir()
    own=[Path(__file__).resolve(),Path(old.__file__).resolve(),ROOT/'rdma/rnic/tests/provider_atomic_commands.c',
        ROOT/'rdma/rnic/tests/provider_commands.c',ROOT/'rdma/rnic/provider/as02.c',Path(candidate.__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in own}
    for n in ['provider_atomic_commands.c','provider_commands.c']:
        shutil.copy2(ROOT/'rdma/rnic/tests'/n,run/'tests'/n)
    # Original main has the C-standard implicit return0. Once renamed as a
    # library fixture it needs an explicit return; retain -Werror unchanged.
    legacy=run/'tests/provider_commands.c';t=legacy.read_text()
    if not t.endswith('\n}\n')or t.count('int main(int argc,char **argv)')!=1:
        raise ValueError('exact original main fixture changed')
    legacy.write_text(t[:-2]+'    return 0;\n}\n')
    (run/'provider/as02.c').write_text(candidate.derive())
    # Extend ONLY the explicit fake-fd kernel boundary; actual serialization
    # and generated production provider bodies remain real.
    model=legacy.read_text()
    model=candidate.once(model,'static bool immediate_profile,poll_immediate,poll_write_immediate;',
        'static bool access_profile;\nstatic bool immediate_profile,poll_immediate,poll_write_immediate;')
    model=candidate.once(model,'uint64_t profile=immediate_profile ? AS02_FW_IMMEDIATE:AS02_FW;',
        'uint64_t profile=access_profile ? AS02_FW_ATOMIC_ACCESS:immediate_profile ? AS02_FW_IMMEDIATE:AS02_FW;')
    model=candidate.once(model,'q->access_flags==7','q->access_flags==(access_profile ? 15U:7U)')
    model=candidate.once(model,'CHECK(q->qp_handle==44 && q->attr_mask==IBV_QP_STATE && q->qp_state==IBV_QPS_RTS);',
        'if(access_profile){CHECK(q->qp_handle==44 && q->qp_state==IBV_QPS_INIT && q->port_num==1 && !q->pkey_index && '
        'q->attr_mask==(IBV_QP_STATE|IBV_QP_PORT|IBV_QP_PKEY_INDEX|IBV_QP_ACCESS_FLAGS) && '
        '(q->qp_access_flags==14 || q->qp_access_flags==6));}else '
        'CHECK(q->qp_handle==44 && q->attr_mask==IBV_QP_STATE && q->qp_state==IBV_QPS_RTS);')
    legacy.write_text(model)
    test=run/'tests/provider_atomic_commands.c';body=test.read_text()
    body=candidate.once(body,'immediate_profile=atoi(argv[1])!=0;',
        'access_profile=atoi(argv[1])==2;immediate_profile=atoi(argv[1])!=0;')
    body=candidate.once(body,'8192,VA,7);CHECK(mr);','8192,VA,access_profile ? 15:7);CHECK(mr);')
    body=candidate.once(body,'qp=ibv_create_qp(pd,&initial);CHECK(qp);',
        'qp=ibv_create_qp(pd,&initial);CHECK(qp);\n'
        '    if(access_profile){for(unsigned int i=0;i<2;i++){\n'
        '        struct ibv_qp_attr qa={.qp_state=IBV_QPS_INIT,.port_num=1,.qp_access_flags=i ? 6:14};\n'
        '        CHECK(!ibv_modify_qp(qp,&qa,IBV_QP_STATE|IBV_QP_PORT|IBV_QP_PKEY_INDEX|IBV_QP_ACCESS_FLAGS));}\n'
        '        CHECK(commands[IB_USER_VERBS_CMD_MODIFY_QP]==2);}')
    body=candidate.once(body,r'\"profile1023\":%s',r'\"profile1023\":%s,\"profile2047\":%s')
    body=candidate.once(body,'immediate_profile ? "true":"false");',
        '(immediate_profile && !access_profile) ? "true":"false",access_profile ? "true":"false");')
    test.write_text(body)
    upstream={str(p):digest(p)for p in [core/'libibverbs/cmd.c',core/'libibverbs/driver.h',core/'libibverbs/verbs.h',core/'build/include/config.h']}
    library=Path('/lib/x86_64-linux-gnu/libibverbs.so.1').resolve();libraries={str(library):digest(library)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        upstream_sha256=upstream,actual_installed_library_sha256=libraries,rdma_core_commit=old.PIN,provider_PABI=34,
        production_provider_changed=False,private_provider_cohort_generated=True,provider_installed=False,real_NIC_opened=False,kernel_loaded=False,
        syscall_boundary_modeled=True,hardware_verified=False,Atomic_cap_advertised=False,simulation_limit_seconds=10,tests={})
    try:
        command=['cc','-std=gnu11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-O1','-g',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
            '-isystem',str(core/'build/include'),'-isystem',str(core),str(run/'tests/provider_atomic_commands.c'),
            '-pthread','-Wl,-export-dynamic','-libverbs','-o',str(run/'cases')]
        report['compile_command']=command;start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
        report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('real provider Atomic compile failed: '+str(run/'compile.log'))
        report['ldd']=subprocess.check_output(['ldd',str(run/'cases')],text=True)
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        for profile in [0,1,2]:
            start=time.monotonic();r=subprocess.run([str(run/'cases'),str(profile)],capture_output=True,text=True,env=env,timeout=10)
            (run/(str(profile)+'.log')).write_text(r.stdout+r.stderr)
            result=dict(seconds=time.monotonic()-start,exit=r.returncode);report['tests'][str(profile)]=result
            if r.returncode:raise ValueError('provider Atomic runtime failed: '+str(run/(str(profile)+'.log')))
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_ATOMIC_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['profile1023']!=(profile==1)or rows[0]['profile2047']!=(profile==2):
                raise ValueError('actual public API assertions missing')
            result['summary']=rows[0]
            result['RNC_features']=[511,1023,2047][profile]
        for mapping,base in [(before,ROOT),(upstream,Path('/')),(libraries,Path('/'))]:
            if any(digest(base/n)!=h for n,h in mapping.items()):raise ValueError('consumed inputs changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],tests={n:v['seconds']for n,v in report['tests'].items()})))


if __name__=='__main__':main()
