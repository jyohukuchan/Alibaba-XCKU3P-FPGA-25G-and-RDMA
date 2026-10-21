# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private exact RNC16383/CQC63/profile5 READ-aware kernel source cohort.

Preserve all old profiles/defaults, real MR/PD/ranges/refs/ring/replay/CQ and
failure lifetime checks. Only exact new tuple/geometry enables large READ.
No install/load/live Linux/physical/timing claim; IB_ATOMIC_NONE stays.
"""
import derive_segmented_kernel as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once
PROFILE='AS02_WQE_PROFILE_SEGMENTED_READ128'
RNC='AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES'
CQC='AS02_CQC_SEGMENTED_READ_FEATURE_VALUE'


def derive():
    out=base.derive()
    p=KERNEL/'rnic_regs.h'
    out[p]=once(out[p],'#define AS02_CTL_SEGMENTED_NATIVE_FEATURES 8191U',
        '#define AS02_CTL_SEGMENTED_NATIVE_FEATURES 8191U\n'
        '#define AS02_CTL_FEATURE_SEGMENTED_READ 8192U\n#define '+RNC+' 16383U')
    # Extend only the exact existing zero/segmented permission whitelists,
    # NOT the individual profile4 selectors or mixed-tuple refusals.
    for name,owners in [('rnic_io.c',['c->features']),('qp_hw.c',['q->control->control.features']),
        ('verbs.c',['d->qp_hw->control->control.features','transport']),
        ('device.c',['d->qp_hw->control->control.features']),('native_graph.c',['g->control.control.features'])]:
        p=KERNEL/name;t=out[p]
        for owner in owners:
            for op,join in [('==',' || '),('!=',' && ')]:
                old='('+owner+op+'AS02_CTL_ZERO_NATIVE_FEATURES'+join+owner+op+'AS02_CTL_SEGMENTED_NATIVE_FEATURES)'
                t=t.replace(old,old[:-1]+join+owner+op+RNC+')')
        out[p]=t
    p=KERNEL/'rnic_io.c'
    out[p]=once(out[p],'value != AS02_CTL_SEGMENTED_NATIVE_FEATURES))',
        'value != AS02_CTL_SEGMENTED_NATIVE_FEATURES && value != '+RNC+'))')
    p=KERNEL/'atomic_profile.h';t=out[p]
    t=once(t,'#include "verbs_segmented_wqe.h"','#include "verbs_segmented_wqe.h"\n#include "verbs_segmented_read_wqe.h"')
    t=once(t,'#define AS02_WQE_PROFILE_SEGMENTED128 4U',
        '#define AS02_WQE_PROFILE_SEGMENTED128 4U\n#define '+PROFILE+' 5U\n#define '+CQC+' 63U')
    out[p]=once(t,'p==AS02_WQE_PROFILE_SEGMENTED128;',
        'p==AS02_WQE_PROFILE_SEGMENTED128 || p=='+PROFILE+';')

    p=KERNEL/'verbs.c';t=out[p]
    out[p]=once(t,'    if(transport==AS02_CTL_SEGMENTED_NATIVE_FEATURES){',
        '    if(transport=='+RNC+') {\n'
        '        if(!rq || sq_features!=AS02_SQC_ATOMIC_FEATURE_VALUE || rq_features!=AS02_RQC_ATOMIC_FEATURE_VALUE ||\n'
        '           cq_features!='+CQC+'){ret=-EOPNOTSUPP;goto out;}\n'
        '        ret=atomic_geometry(h,rq,cq);if(ret)goto out;\n'
        '        profile='+PROFILE+';\n'
        '    }else if(transport==AS02_CTL_SEGMENTED_NATIVE_FEATURES){')

    p=KERNEL/'sq.c';t=out[p]
    t=once(t,'(p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?\n',
        '(p->wqe_profile=='+PROFILE+' ?\n'
        '             as02_segmented_read_wqe_from_ib_send_wr(encoded,wr,q->producer+1,owner->epoch):\n'
        '             p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?\n')
    t=once(t,'if(!ret)ret=p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?',
        'if(!ret)ret=p->wqe_profile=='+PROFILE+' ? as02_segmented_read_wqe_decode(&atomic_work,encoded):\n'
        '            p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?')
    for pair in ['expected,&a','observed,&b']:
        old='(p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_encode('+pair+'):'
        t=once(t,old,'(p->wqe_profile=='+PROFILE+' ? as02_segmented_read_wqe_encode('+pair+'):\n'
            '             p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_encode('+pair+'):')
    out[p]=t

    p=KERNEL/'cq_io.c';t=out[p]
    t=once(t,'(profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_validate(&aw):',
        '(profile=='+PROFILE+' ? as02_segmented_read_wqe_validate(&aw):\n'
        '        profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_validate(&aw):')
    t=once(t,'features!=AS02_CQC_SEGMENTED_FEATURE_VALUE))',
        'features!=AS02_CQC_SEGMENTED_FEATURE_VALUE && features!='+CQC+'))')
    for prefix in ['', 'h->']:
        old='if('+prefix+'features==AS02_CQC_ATOMIC_FEATURE_VALUE || '+prefix+'features==AS02_CQC_SEGMENTED_FEATURE_VALUE){'
        t=once(t,old,old[:-2]+' || '+prefix+'features=='+CQC+'){')
    t=once(t,'as02_cq_decode_profile(&d,&e,h->features==AS02_CQC_SEGMENTED_FEATURE_VALUE ?',
        'as02_cq_decode_profile(&d,&e,h->features=='+CQC+' ? '+PROFILE+':\n'
        '        h->features==AS02_CQC_SEGMENTED_FEATURE_VALUE ?')
    out[p]=t

    p=KERNEL/'device.c';t=out[p]
    t=once(t,'(d->qp_hw->control->control.features==AS02_CTL_SEGMENTED_NATIVE_FEATURES ?',
        '(d->qp_hw->control->control.features=='+RNC+' ? '+PROFILE+':\n'
        '             d->qp_hw->control->control.features==AS02_CTL_SEGMENTED_NATIVE_FEATURES ?')
    t=once(t,'(d->sq->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?',
        '(d->sq->wqe_profile=='+PROFILE+' ? '+CQC+':\n'
        '              d->sq->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?')
    t=once(t,'a->max_msg_sz = 4096;',
        'a->max_msg_sz = d->sq && d->sq->profile_bound && d->sq->wqe_profile=='+PROFILE+' ?\n'
        '        AS02_SEGMENTED_WQE_MAX_BYTES:4096;')
    out[p]=t

    p=KERNEL/'native_graph.c';t=out[p]
    marker='    if((g->control.control.features==AS02_CTL_SEGMENTED_NATIVE_FEATURES) !='
    t=once(t,marker,'    if((g->control.control.features=='+RNC+') !=\n'
        '       (readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)=='+CQC+')){\n'
        '        ret=-EOPNOTSUPP;goto failed;\n    }\n'+marker)
    out[p]=once(t,'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_SEGMENTED_FEATURE_VALUE):',
        'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_SEGMENTED_FEATURE_VALUE &&\n'
        '         readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+CQC+'):')
    p=KERNEL/'Makefile'
    out[p]=once(out[p],'wqe_segmented.o verbs_segmented_wqe.o',
        'wqe_segmented.o verbs_segmented_wqe.o wqe_segmented_read.o verbs_segmented_read_wqe.o')
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:
        raise ValueError('default Atomic advertisement must stay disabled')
    return out
