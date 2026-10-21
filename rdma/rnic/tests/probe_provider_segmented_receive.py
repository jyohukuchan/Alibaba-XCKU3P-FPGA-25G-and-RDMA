#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual standard RECV serializer/new65535 identity and all7 old modes.

Real installed libibverbs/private provider, MR/RQ/SGE/bad-WR/WC marshalling.
ONLY fake-fd syscalls/WC replies are modeled. Not kernel callbacks, native
payload execution, installed capability or physical proof. Never install.
"""
import ast
from pathlib import Path
import probe_provider_segmented_immediate as parent
import derive_segmented_receive_provider as candidate

ROOT=parent.ROOT;once=candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_immediate_provider as candidate','import derive_segmented_receive_provider as candidate')
    t=once(t,"prefix='provider-segmented-immediate-'","prefix='provider-segmented-receive-'")
    t=once(t,'static bool access_profile,zero_profile,segmented_profile,segmented_read_profile,segmented_immediate_profile;',
        'static bool access_profile,zero_profile,segmented_profile,segmented_read_profile,segmented_immediate_profile,segmented_receive_profile;')
    t=once(t,'uint64_t profile=segmented_immediate_profile ? AS02_FW_SEGMENTED_IMMEDIATE:',
        'uint64_t profile=segmented_receive_profile ? AS02_FW_SEGMENTED_RECEIVE:segmented_immediate_profile ? AS02_FW_SEGMENTED_IMMEDIATE:')
    t=once(t,'segmented_immediate_profile=atoi(argv[1])==6;',
        'segmented_receive_profile=atoi(argv[1])==7;segmented_immediate_profile=atoi(argv[1])>=6;')
    files="'provider_atomic_commands.c','provider_zero_commands.h','provider_segmented_commands.h'"
    if t.count(files)!=2:raise ValueError('both input and frozen copy inventories required')
    t=t.replace(files,files+",'provider_segmented_receive_commands.h'")
    t=once(t,r'#include "provider_segmented_immediate_commands.h"\nstatic',
        r'#include "provider_segmented_immediate_commands.h"\n#include "provider_segmented_receive_commands.h"\nstatic')
    t=once(t,'    if(segmented_immediate_boundary)return segmented_immediate_write(fd,buffer,bytes);',
        r'    if(segmented_receive_boundary)return segmented_receive_write(fd,buffer,bytes);\n    if(segmented_immediate_boundary)return segmented_immediate_write(fd,buffer,bytes);')
    t=once(t,'if(segmented_immediate_profile)exercise_segmented_immediate(pd,qp,cq);',
        r'if(segmented_immediate_profile)exercise_segmented_immediate(pd,qp,cq);\n    if(segmented_receive_profile)exercise_segmented_receive(pd,qp,rq);')
    t=once(t,r'\"profile32767\":%s',r'\"profile32767\":%s,\"profile65535\":%s')
    t=once(t,'segmented_immediate_profile ? "true":"false");',
        '(segmented_immediate_profile && !segmented_receive_profile) ? "true":"false",segmented_receive_profile ? "true":"false");')
    for old,new in [('for profile in range(7):','for profile in range(8):'),
        ('RNC_features=[511,1023,2047,4095,8191,16383,32767][profile]','RNC_features=[511,1023,2047,4095,8191,16383,32767,65535][profile]'),
        ('(6,32767)]','(6,32767),(7,65535)]'),('            if profile==6:','            if profile>=6:')]:t=once(t,old,new)
    marker='        for mapping,base in [(before,ROOT)'
    t=once(t,marker,"            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_SEGMENTED_RECEIVE_RESULT ')]\n"
        "            if profile==7:\n"
        "                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['RECV_capacities']!=[4097,8194,1048576]or rows[0]['WC_actual_bytes']!=[4096,8193,1048575]or not rows[0]['network_order_Immediate']or rows[0]['posts_including_errors']!=6 or rows[0]['polls']!=3:raise ValueError('all new RECV capacity/actual-count/MR/chain/bad-WR/WC cases required')\n"
        "                result['segmented_RECEIVE_summary']=rows[0]\n"
        "            elif rows:raise ValueError('old profile mislabeled new RECEIVE-qualified')\n"+marker)
    t=once(t,'ROOT/"rdma/rnic/tests/probe_provider_segmented_read.py",',
        'ROOT/"rdma/rnic/tests/probe_provider_segmented_read.py",ROOT/"rdma/rnic/tests/probe_provider_segmented_immediate.py",')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        read_header_source=parent.base.read_header_source,immediate_header_source=parent.immediate_header_source))
