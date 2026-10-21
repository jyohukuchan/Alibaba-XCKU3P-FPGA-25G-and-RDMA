#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual standard Immediate serializer/new32767 identity and all6 old modes.

Real installed libibverbs/private provider, standard uverbs MR/WR/SGE/bad-WR
and WC marshalling. ONLY fake-fd syscalls/WC replies are modeled, not actual
kernel callbacks, DMA, payload/CQ execution or installed/physical support.
"""
import ast
from pathlib import Path
import probe_provider_segmented_read as base
import derive_segmented_immediate_provider as candidate

ROOT=base.ROOT;once=candidate.once


def immediate_header_source():
    t=(ROOT/'rdma/rnic/tests/provider_segmented_commands.h').read_text()
    t=t.replace('segmented_','segmented_immediate_').replace('exercise_segmented(','exercise_segmented_immediate(')
    t=t.replace('IBV_WR_RDMA_WRITE','IBV_WR_RDMA_WRITE_WITH_IMM').replace('IBV_WR_SEND','IBV_WR_SEND_WITH_IMM')
    t=t.replace('0xa1234567','0xe1234567').replace('0xb1234567','0xf1234567')
    for old,new in [('r->mr_handle=19','r->mr_handle=21'),('q->mr_handle==19','q->mr_handle==21'),('mr->handle==19','mr->handle==21')]:t=once(t,old,new)
    t=once(t,'w[i].num_sge==1 && w[i].send_flags==IBV_SEND_SIGNALED &&',
        'w[i].num_sge==1 && w[i].send_flags==IBV_SEND_SIGNALED && w[i].ex.imm_data==e->imm_data &&')
    t=once(t,'const unsigned int lengths[]={4097,8193,1048576};',
        'const unsigned int lengths[]={4097,8193,1048576},values[]={0,0x89abcdefU,0xffffffffU};')
    t=once(t,'.send_flags=IBV_SEND_SIGNALED};',
        '.send_flags=IBV_SEND_SIGNALED,.imm_data=htonl(values[n]^(i ? 0x13579bdfU:0))};')
    t=t.replace('PROVIDER_SEGMENTED_RESULT','PROVIDER_SEGMENTED_IMMEDIATE_RESULT').replace('WRITE_SEND_lengths','WRITE_SEND_Immediate_lengths')
    return once(t,r'\"send_WC_zero_bytes\":true',r'\"send_WC_zero_bytes\":true,\"network_order_Immediate\":true')


def runner_source():
    t=base.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_read_provider as candidate','import derive_segmented_immediate_provider as candidate')
    t=once(t,"prefix='provider-segmented-read-'","prefix='provider-segmented-immediate-'")
    t=once(t,'static bool access_profile,zero_profile,segmented_profile,segmented_read_profile;',
        'static bool access_profile,zero_profile,segmented_profile,segmented_read_profile,segmented_immediate_profile;')
    t=once(t,'uint64_t profile=segmented_read_profile ? AS02_FW_SEGMENTED_READ:',
        'uint64_t profile=segmented_immediate_profile ? AS02_FW_SEGMENTED_IMMEDIATE:segmented_read_profile ? AS02_FW_SEGMENTED_READ:')
    t=once(t,'segmented_read_profile=atoi(argv[1])==5;',
        'segmented_immediate_profile=atoi(argv[1])==6;segmented_read_profile=atoi(argv[1])>=5;')
    t=once(t,"    legacy=run/'tests/provider_commands.c';",
        "    (run/'tests/provider_segmented_immediate_commands.h').write_text(immediate_header_source())\n"
        "    legacy=run/'tests/provider_commands.c';")
    t=once(t,r'#include "provider_segmented_read_commands.h"\nstatic',
        r'#include "provider_segmented_read_commands.h"\n#include "provider_segmented_immediate_commands.h"\nstatic')
    t=once(t,'    if(segmented_read_boundary)return segmented_read_write(fd,buffer,bytes);',
        r'    if(segmented_immediate_boundary)return segmented_immediate_write(fd,buffer,bytes);\n    if(segmented_read_boundary)return segmented_read_write(fd,buffer,bytes);')
    t=once(t,'if(segmented_read_profile)exercise_segmented_read(pd,qp,cq);',
        r'if(segmented_read_profile)exercise_segmented_read(pd,qp,cq);\n    if(segmented_immediate_profile)exercise_segmented_immediate(pd,qp,cq);')
    t=once(t,r'\"profile16383\":%s',r'\"profile16383\":%s,\"profile32767\":%s')
    t=once(t,'segmented_read_profile ? "true":"false");',
        '(segmented_read_profile && !segmented_immediate_profile) ? "true":"false",segmented_immediate_profile ? "true":"false");')
    for old,new in [('for profile in range(6):','for profile in range(7):'),
        ('RNC_features=[511,1023,2047,4095,8191,16383][profile]','RNC_features=[511,1023,2047,4095,8191,16383,32767][profile]'),
        ('(5,16383)]','(5,16383),(6,32767)]'),('            if profile==5:','            if profile>=5:')]:t=once(t,old,new)
    marker='        for mapping,base in [(before,ROOT)'
    t=once(t,marker,"            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_SEGMENTED_IMMEDIATE_RESULT ')]\n"
        "            if profile==6:\n"
        "                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['WRITE_SEND_Immediate_lengths']!=[4097,8193,1048576]or not rows[0]['network_order_Immediate']or rows[0]['posts_including_errors']!=6 or rows[0]['polls']!=3:raise ValueError('all new Immediate values/MR/chain/bad-WR/WC cases required')\n"
        "                result['segmented_Immediate_summary']=rows[0]\n"
        "            elif rows:raise ValueError('old profile mislabeled Immediate-qualified')\n"+marker)
    t=once(t,'ROOT/"rdma/rnic/tests/probe_provider_segmented.py",',
        'ROOT/"rdma/rnic/tests/probe_provider_segmented.py",ROOT/"rdma/rnic/tests/probe_provider_segmented_read.py",')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        read_header_source=base.read_header_source,immediate_header_source=immediate_header_source))
