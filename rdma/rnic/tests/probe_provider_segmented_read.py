#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual standard provider READ serialization, all five old identities kept.

Real libibverbs/provider/C marshalling; only fake-fd syscalls and WC replies
are models. New exact16383 identity,4097/8193/1MiB READ+SEND chains, full64
addresses/keys/SGEs, exact bad-WR and READ WC length. Never install/load/open.
"""
import ast
from pathlib import Path
import probe_provider_segmented as parent
import derive_segmented_read_provider as candidate

ROOT=Path(__file__).resolve().parents[3];once=candidate.once


def read_header_source():
    t=(ROOT/'rdma/rnic/tests/provider_segmented_commands.h').read_text()
    t=t.replace('segmented_','segmented_read_').replace('exercise_segmented(','exercise_segmented_read(')
    t=t.replace('IBV_WR_RDMA_WRITE','IBV_WR_RDMA_READ').replace('IBV_WC_RDMA_WRITE','IBV_WC_RDMA_READ')
    t=t.replace('0xa1234567','0xc1234567').replace('0xb1234567','0xd1234567')
    for old,new in [('r->mr_handle=19','r->mr_handle=20'),('q->mr_handle==19','q->mr_handle==20'),
                    ('mr->handle==19','mr->handle==20')]:t=once(t,old,new)
    t=once(t,'r->wc[i].opcode=i ? IBV_WC_SEND:IBV_WC_RDMA_READ;',
        'r->wc[i].opcode=i ? IBV_WC_SEND:IBV_WC_RDMA_READ;\n'
        '            r->wc[i].byte_len=i ? 0:segmented_read_expected[i].sg_list->length;')
    t=once(t,'!wc[i].byte_len && wc[i].status==IBV_WC_SUCCESS',
        'wc[i].byte_len==(i ? 0:lengths[n]) && wc[i].status==IBV_WC_SUCCESS')
    t=t.replace('PROVIDER_SEGMENTED_RESULT','PROVIDER_SEGMENTED_READ_RESULT').replace('WRITE_SEND_lengths','READ_SEND_lengths')
    return once(t,r'\"send_WC_zero_bytes\":true',r'\"send_WC_zero_bytes\":true,\"READ_WC_full_bytes\":true')


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_provider as candidate','import derive_segmented_read_provider as candidate')
    t=once(t,"prefix='provider-segmented-'","prefix='provider-segmented-read-'")
    t=once(t,'static bool access_profile,zero_profile,segmented_profile;',
        'static bool access_profile,zero_profile,segmented_profile,segmented_read_profile;')
    t=once(t,'uint64_t profile=segmented_profile ? AS02_FW_SEGMENTED:',
        'uint64_t profile=segmented_read_profile ? AS02_FW_SEGMENTED_READ:segmented_profile ? AS02_FW_SEGMENTED:')
    t=once(t,'segmented_profile=atoi(argv[1])==4;',
        'segmented_read_profile=atoi(argv[1])==5;segmented_profile=atoi(argv[1])>=4;')
    t=once(t,"    legacy=run/'tests/provider_commands.c';",
        "    (run/'tests/provider_segmented_read_commands.h').write_text(read_header_source())\n"
        "    legacy=run/'tests/provider_commands.c';")
    t=once(t,r'#include "provider_segmented_commands.h"\nstatic',
        r'#include "provider_segmented_commands.h"\n#include "provider_segmented_read_commands.h"\nstatic')
    t=once(t,'    if(segmented_boundary)return segmented_write(fd,buffer,bytes);',
        r'    if(segmented_read_boundary)return segmented_read_write(fd,buffer,bytes);\n    if(segmented_boundary)return segmented_write(fd,buffer,bytes);')
    t=once(t,'if(segmented_profile)exercise_segmented(pd,qp,cq);',
        r'if(segmented_profile)exercise_segmented(pd,qp,cq);\n    if(segmented_read_profile)exercise_segmented_read(pd,qp,cq);')
    t=once(t,r'\"profile8191\":%s',r'\"profile8191\":%s,\"profile16383\":%s')
    t=once(t,'segmented_profile ? "true":"false");',
        '(segmented_profile && !segmented_read_profile) ? "true":"false",segmented_read_profile ? "true":"false");')
    t=once(t,'for profile in range(5):','for profile in range(6):')
    t=once(t,'RNC_features=[511,1023,2047,4095,8191][profile]',
        'RNC_features=[511,1023,2047,4095,8191,16383][profile]')
    t=once(t,'(4,8191)]','(4,8191),(5,16383)]')
    t=once(t,'            if profile==4:','            if profile>=4:')
    marker='        for mapping,base in [(before,ROOT)'
    t=once(t,marker,"            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_SEGMENTED_READ_RESULT ')]\n"
        "            if profile==5:\n"
        "                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['READ_SEND_lengths']!=[4097,8193,1048576]or not rows[0]['READ_WC_full_bytes']or rows[0]['posts_including_errors']!=6 or rows[0]['polls']!=3:\n"
        "                    raise ValueError('all new standard READ chain/MR/bad-WR/byte-count cases required')\n"
        "                result['segmented_READ_summary']=rows[0]\n"
        "            elif rows:raise ValueError('old profile mislabeled READ-qualified')\n"+marker)
    t=once(t,"    upstream={str(p):digest(p)",
        "    frozen_before={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()}\n"
        "    upstream={str(p):digest(p)")
    t=once(t,'upstream_sha256=upstream,actual_installed_library_sha256=libraries,',
        'upstream_sha256=upstream,frozen_input_sha256=frozen_before,actual_installed_library_sha256=libraries,')
    t=once(t,'[(before,ROOT),(upstream,Path', '[(before,ROOT),(frozen_before,ROOT),(upstream,Path')
    t=once(t,'Path(old.__file__).resolve(),ROOT/"rdma/rnic/tests/probe_provider_zero.py",candidate.SOURCE,',
        'Path(old.__file__).resolve(),ROOT/"rdma/rnic/tests/probe_provider_segmented.py",ROOT/"rdma/rnic/tests/probe_provider_zero.py",candidate.SOURCE,')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
        dict(__name__='__main__',__file__=str(Path(__file__).resolve()),read_header_source=read_header_source))


if __name__=='__main__':main()
