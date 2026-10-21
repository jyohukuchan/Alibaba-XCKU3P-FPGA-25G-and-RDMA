#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual public8191 provider/large verbs serialization, not Linux runtime.

Retain every511/1023/2047/4095 test, add exact8191 plus zero/Atomic regressions
and4097/8193/1MiB standard WRITE/SEND chains, registered MR and exact bad WR.
Real installed libibverbs; fake-fd syscalls/WCs only modeled. Never install.
"""
import ast
from pathlib import Path
import probe_provider_zero as parent
import derive_segmented_provider as candidate


def runner_source():
    t=Path(parent.__file__).read_text();once=candidate.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_zero_provider as candidate','import derive_segmented_provider as candidate')
    t=once(t,"prefix='provider-zero-'","prefix='provider-segmented-'")
    t=once(t,'Path(old.__file__).resolve(),candidate.SOURCE,',
        'Path(old.__file__).resolve(),ROOT/"rdma/rnic/tests/probe_provider_zero.py",candidate.SOURCE,')
    # Both input/copy inventories bind the new test; bind the entire actual
    # provider helper chain as well, not only the nearest parent.
    t=t.replace("'provider_atomic_commands.c','provider_zero_commands.h'",
        "'provider_atomic_commands.c','provider_zero_commands.h','provider_segmented_commands.h'")
    t=once(t,'    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}',
        '    inputs.extend(Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,"__file__",None)and\n'
        '        Path(m.__file__).resolve().is_relative_to(ROOT/"rdma/rnic/provider"))\n'
        '    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}')
    t=once(t,'static bool access_profile,zero_profile;',
        'static bool access_profile,zero_profile,segmented_profile;')
    t=once(t,'uint64_t profile=zero_profile ? AS02_FW_ZERO_LENGTH:',
        'uint64_t profile=segmented_profile ? AS02_FW_SEGMENTED:zero_profile ? AS02_FW_ZERO_LENGTH:')
    t=once(t,"'#include \"provider_zero_commands.h\"\\nstatic struct ibv_send_wr expected_atomic[2];'",
        "'#include \"provider_zero_commands.h\"\\n#include \"provider_segmented_commands.h\"\\nstatic struct ibv_send_wr expected_atomic[2];'")
    t=once(t,"'    if(zero_boundary)return zero_write(fd,buffer,bytes);\\n    const struct ib_uverbs_cmd_hdr *h=buffer;'",
        "'    if(segmented_boundary)return segmented_write(fd,buffer,bytes);\\n    if(zero_boundary)return zero_write(fd,buffer,bytes);\\n    const struct ib_uverbs_cmd_hdr *h=buffer;'")
    t=once(t,'zero_profile=atoi(argv[1])==3;access_profile=',
        'segmented_profile=atoi(argv[1])==4;zero_profile=atoi(argv[1])>=3;access_profile=')
    marker="    t=once(t,'8192,VA,7);CHECK(mr);'"
    t=once(t,marker,"    t=once(t,'v=as02_device_ops.alloc_context(&d->device,MODEL_FD,NULL);CHECK(v);c=&v->context;',\n"
        "        'wrong_profile=true;errno=0;CHECK(!as02_device_ops.alloc_context(&d->device,MODEL_FD,NULL) && errno==EPROTONOSUPPORT);'\n"
        "        'wrong_profile=false;v=as02_device_ops.alloc_context(&d->device,MODEL_FD,NULL);CHECK(v);c=&v->context;')\n"+marker)
    t=once(t,"    if(zero_profile)exercise_zero(qp,cq);'",
        "    if(zero_profile)exercise_zero(qp,cq);\\n    if(segmented_profile)exercise_segmented(pd,qp,cq);'")
    t=once(t,r'\"profile4095\":%s',r'\"profile4095\":%s,\"profile8191\":%s')
    t=once(t,'zero_profile ? "true":"false");',
        '(zero_profile && !segmented_profile) ? "true":"false",segmented_profile ? "true":"false");')
    t=once(t,'        for profile in range(4):','        for profile in range(5):')
    t=once(t,'RNC_features=[511,1023,2047,4095][profile]',
        'RNC_features=[511,1023,2047,4095,8191][profile]')
    t=once(t,'[(1,1023),(2,2047),(3,4095)]','[(1,1023),(2,2047),(3,4095),(4,8191)]')
    t=once(t,'            if profile==3:','            if profile>=3:')
    marker='        for mapping,base in [(before,ROOT)'
    t=once(t,marker,"            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_SEGMENTED_RESULT ')]\n"
        "            if profile==4:\n"
        "                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['WRITE_SEND_lengths']!=[4097,8193,1048576]or rows[0]['posts_including_errors']!=6 or rows[0]['polls']!=3:\n"
        "                    raise ValueError('all large standard chains/MR/SGE/bad-WR/WC cases required')\n"
        "                result['segmented_summary']=rows[0]\n"
        "            elif rows:raise ValueError('old profile mislabeled large-qualified')\n"+marker)
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
         dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
