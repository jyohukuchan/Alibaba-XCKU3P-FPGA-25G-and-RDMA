#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual standard WRITE-notice provider marshalling and all8 old identities.

Real libibverbs/private provider, chained zero-capacity RQ/bad-WR/WC/BE
Immediate. ONLY syscall/WC replies modeled; not kernel/native/hardware proof.
Do not install or advertise this source candidate before matched gates pass.
"""
import ast
from pathlib import Path
import probe_provider_segmented_receive as parent
import derive_segmented_write_provider as candidate

ROOT=parent.ROOT;once=candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_receive_provider as candidate','import derive_segmented_write_provider as candidate')
    t=once(t,"prefix='provider-segmented-receive-'","prefix='provider-segmented-write-'")
    t=once(t,'segmented_immediate_profile,segmented_receive_profile;',
        'segmented_immediate_profile,segmented_receive_profile,segmented_write_profile;')
    t=once(t,'uint64_t profile=segmented_receive_profile ?',
        'uint64_t profile=segmented_write_profile ? AS02_FW_SEGMENTED_WRITE:segmented_receive_profile ?')
    t=once(t,'segmented_receive_profile=atoi(argv[1])==7;',
        'segmented_write_profile=atoi(argv[1])==8;segmented_receive_profile=atoi(argv[1])>=7;')
    files="'provider_segmented_receive_commands.h'"
    if t.count(files)!=2:raise ValueError('both actual provider input/copy inventories required')
    t=t.replace(files,files+",'provider_segmented_write_receive_commands.h'")
    t=once(t,r'#include "provider_segmented_receive_commands.h"\nstatic',
        r'#include "provider_segmented_receive_commands.h"\n#include "provider_segmented_write_receive_commands.h"\nstatic')
    t=once(t,'    if(segmented_receive_boundary)return segmented_receive_write(fd,buffer,bytes);',
        r'    if(write_receive_boundary)return write_receive_write(fd,buffer,bytes);\n    if(segmented_receive_boundary)return segmented_receive_write(fd,buffer,bytes);')
    t=once(t,'if(segmented_receive_profile)exercise_segmented_receive(pd,qp,rq);',
        r'if(segmented_receive_profile)exercise_segmented_receive(pd,qp,rq);\n    if(segmented_write_profile)exercise_write_receive(qp,rq);')
    t=once(t,r'\"profile65535\":%s',r'\"profile65535\":%s,\"profile131071\":%s')
    t=once(t,'segmented_receive_profile ? "true":"false");',
        '(segmented_receive_profile && !segmented_write_profile) ? "true":"false",segmented_write_profile ? "true":"false");')
    for old,new in [('for profile in range(8):','for profile in range(9):'),
        ('[511,1023,2047,4095,8191,16383,32767,65535][profile]','[511,1023,2047,4095,8191,16383,32767,65535,131071][profile]'),
        ('(7,65535)]','(7,65535),(8,131071)]'),('            if profile==7:','            if profile>=7:')]:t=once(t,old,new)
    marker='        for mapping,base in [(before,ROOT)'
    t=once(t,marker,"            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_WRITE_RECEIVE_RESULT ')]\n"
        "            if profile==8:\n"
        "                if len(rows)!=1 or not rows[0]['pass_test']or not rows[0]['zero_capacity_RQ']or rows[0]['WC_actual_bytes']!=[0,1,4096,4097,8193,1048576]or not rows[0]['network_order_Immediate']or rows[0]['posts_including_errors']!=12 or rows[0]['polls']!=6:raise ValueError('all new WRITE-notice/zeroRQ/bad-WR/WC cases required')\n"
        "                result['WRITE_receive_summary']=rows[0]\n"
        "            elif rows:raise ValueError('old provider identity mislabeled WRITE-qualified')\n"+marker)
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        read_header_source=parent.parent.base.read_header_source,immediate_header_source=parent.parent.immediate_header_source))
