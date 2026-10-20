#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual public4095 provider/zero verbs serialization, not Linux runtime.

Real installed libibverbs and reviewed pinned rdma-core headers; only fake-fd
syscall replies are modeled. Preserve all511/1023/2047 Atomic regressions,
add exact4095 context and six zero operations with both canonical user SGE
representations. Never install/load/open a real NIC or claim physical DMA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import probe_provider_commands as old
sys.path.insert(0,str(old.ROOT/'rdma/rnic/provider'))
import derive_zero_provider as candidate

ROOT=old.ROOT;digest=old.digest;once=candidate.once


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rdma-core',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    core=a.rdma_core.resolve()
    if subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()!=old.PIN:
        raise ValueError('reviewed pinned headers required')
    run=Path(tempfile.mkdtemp(prefix='provider-zero-',dir=ROOT/'rdma/rnic/build'))
    (run/'tests').mkdir();(run/'provider').mkdir()
    inputs=[Path(__file__).resolve(),Path(old.__file__).resolve(),candidate.SOURCE,
        Path(candidate.__file__).resolve(),Path(candidate.base.__file__).resolve(),
        *[ROOT/'rdma/rnic/tests'/n for n in ['provider_commands.c','provider_atomic_commands.c','provider_zero_commands.h']]]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
    for n in ['provider_commands.c','provider_atomic_commands.c','provider_zero_commands.h']:
        shutil.copy2(ROOT/'rdma/rnic/tests'/n,run/'tests'/n)
    legacy=run/'tests/provider_commands.c';t=legacy.read_text()
    if not t.endswith('\n}\n'):raise ValueError('legacy main shape changed')
    t=t[:-2]+'    return 0;\n}\n'
    t=once(t,'static bool immediate_profile,poll_immediate,poll_write_immediate;',
        'static bool access_profile,zero_profile;\nstatic bool immediate_profile,poll_immediate,poll_write_immediate;')
    t=once(t,'uint64_t profile=immediate_profile ? AS02_FW_IMMEDIATE:AS02_FW;',
        'uint64_t profile=zero_profile ? AS02_FW_ZERO_LENGTH:access_profile ? AS02_FW_ATOMIC_ACCESS:immediate_profile ? AS02_FW_IMMEDIATE:AS02_FW;')
    t=once(t,'q->access_flags==7','q->access_flags==(access_profile ? 15U:7U)')
    t=once(t,'CHECK(q->qp_handle==44 && q->attr_mask==IBV_QP_STATE && q->qp_state==IBV_QPS_RTS);',
        'if(access_profile){CHECK(q->qp_handle==44 && q->qp_state==IBV_QPS_INIT && q->port_num==1 && !q->pkey_index && '
        'q->attr_mask==(IBV_QP_STATE|IBV_QP_PORT|IBV_QP_PKEY_INDEX|IBV_QP_ACCESS_FLAGS) && '
        '(q->qp_access_flags==14 || q->qp_access_flags==6));}else '
        'CHECK(q->qp_handle==44 && q->attr_mask==IBV_QP_STATE && q->qp_state==IBV_QPS_RTS);')
    legacy.write_text(t);(run/'provider/as02.c').write_text(candidate.derive())
    test=run/'tests/provider_atomic_commands.c';t=test.read_text()
    t=once(t,'static struct ibv_send_wr expected_atomic[2];',
        '#include "provider_zero_commands.h"\nstatic struct ibv_send_wr expected_atomic[2];')
    t=once(t,'    const struct ib_uverbs_cmd_hdr *h=buffer;',
        '    if(zero_boundary)return zero_write(fd,buffer,bytes);\n    const struct ib_uverbs_cmd_hdr *h=buffer;')
    t=once(t,'immediate_profile=atoi(argv[1])!=0;',
        'zero_profile=atoi(argv[1])==3;access_profile=atoi(argv[1])>=2;immediate_profile=atoi(argv[1])!=0;')
    t=once(t,'8192,VA,7);CHECK(mr);','8192,VA,access_profile ? 15:7);CHECK(mr);')
    t=once(t,'qp=ibv_create_qp(pd,&initial);CHECK(qp);',
        'qp=ibv_create_qp(pd,&initial);CHECK(qp);\n'
        '    if(access_profile){for(unsigned int i=0;i<2;i++){\n'
        '        struct ibv_qp_attr qa={.qp_state=IBV_QPS_INIT,.port_num=1,.qp_access_flags=i ? 6:14};\n'
        '        CHECK(!ibv_modify_qp(qp,&qa,IBV_QP_STATE|IBV_QP_PORT|IBV_QP_PKEY_INDEX|IBV_QP_ACCESS_FLAGS));}\n'
        '        CHECK(commands[IB_USER_VERBS_CMD_MODIFY_QP]==2);}')
    t=once(t,'    CHECK(atomic_posts==6 && atomic_polls==3 && ioctls);',
        '    CHECK(atomic_posts==6 && atomic_polls==3 && ioctls);\n    if(zero_profile)exercise_zero(qp,cq);')
    t=once(t,r'\"profile1023\":%s',r'\"profile1023\":%s,\"profile2047\":%s,\"profile4095\":%s')
    t=once(t,'immediate_profile ? "true":"false");',
        '(immediate_profile && !access_profile) ? "true":"false",(access_profile && !zero_profile) ? "true":"false",zero_profile ? "true":"false");')
    test.write_text(t)
    upstream={str(p):digest(p)for p in [core/'libibverbs/cmd.c',core/'libibverbs/driver.h',core/'libibverbs/verbs.h',core/'build/include/config.h']}
    library=Path('/lib/x86_64-linux-gnu/libibverbs.so.1').resolve();libraries={str(library):digest(library)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        upstream_sha256=upstream,actual_installed_library_sha256=libraries,rdma_core_commit=old.PIN,provider_PABI=34,
        production_provider_changed=False,private_provider_cohort_generated=True,provider_installed=False,
        real_NIC_opened=False,kernel_loaded=False,syscall_boundary_modeled=True,hardware_verified=False,
        Atomic_cap_advertised=False,simulation_limit_seconds=10,tests={})
    try:
        command=['cc','-std=gnu11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-O1','-g',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
            '-isystem',str(core/'build/include'),'-isystem',str(core),str(test),'-pthread','-Wl,-export-dynamic','-libverbs','-o',str(run/'cases')]
        report['compile_command']=command;start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
        report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('provider zero compile failed: '+str(run/'compile.log'))
        report['ldd']=subprocess.check_output(['ldd',str(run/'cases')],text=True)
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        for profile in range(4):
            start=time.monotonic();r=subprocess.run([str(run/'cases'),str(profile)],capture_output=True,text=True,env=env,timeout=10)
            (run/(str(profile)+'.log')).write_text(r.stdout+r.stderr)
            result=dict(seconds=time.monotonic()-start,exit=r.returncode,RNC_features=[511,1023,2047,4095][profile]);report['tests'][str(profile)]=result
            if r.returncode:raise ValueError('provider zero runtime failed: '+str(run/(str(profile)+'.log')))
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_ATOMIC_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or any(rows[0]['profile'+str(f)]!=(profile==i)for i,f in [(1,1023),(2,2047),(3,4095)]):
                raise ValueError('exact standard API/profile evidence absent')
            result['atomic_summary']=rows[0]
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_ZERO_RESULT ')]
            if profile==3:
                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['zero_operations']!=6 or rows[0]['posts_including_errors']!=24 or rows[0]['polls']!=12:
                    raise ValueError('all zero standard verbs/SGE/bad-WR/WC cases required')
                result['zero_summary']=rows[0]
            elif rows:raise ValueError('legacy run mislabeled zero-qualified')
        for mapping,base in [(before,ROOT),(upstream,Path('/')),(libraries,Path('/'))]:
            if any(digest(base/n)!=h for n,h in mapping.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],tests={n:v['seconds']for n,v in report['tests'].items()})))


if __name__=='__main__':main()
