# SPDX-License-Identifier: BSD-2-Clause-Views
"""Separate exact65535/255/13/31/profile7 large-RECV kernel source cohort.

Real full-range local-write MR references, independent RQ, whole owner and
actual received-byte CQ validation are retained. Old profiles/defaults and
IB_ATOMIC_NONE stay unchanged. No install/load/live API/physical/timing claim.
"""
import derive_segmented_immediate_kernel as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once
PROFILE='AS02_WQE_PROFILE_SEGMENTED_RECEIVE128'
RNC='AS02_CTL_SEGMENTED_RECEIVE_NATIVE_FEATURES'
CQC='AS02_CQC_SEGMENTED_RECEIVE_FEATURE_VALUE'
RQC='AS02_RQC_SEGMENTED_RECEIVE_FEATURE_VALUE'


def derive():
    out=base.derive();p=KERNEL/'rnic_regs.h'
    out[p]=once(out[p],'#define '+base.RNC+' 32767U',
        '#define '+base.RNC+' 32767U\n#define AS02_CTL_FEATURE_SEGMENTED_RECEIVE 32768U\n#define '+RNC+' 65535U')
    for name,owners in [('rnic_io.c',['c->features']),('qp_hw.c',['q->control->control.features']),
        ('verbs.c',['d->qp_hw->control->control.features','transport']),
        ('device.c',['d->qp_hw->control->control.features']),('native_graph.c',['g->control.control.features'])]:
        p=KERNEL/name;t=out[p]
        for owner in owners:
            for op,join in [('==',' || '),('!=',' && ')]:
                old='('+owner+op+'AS02_CTL_ZERO_NATIVE_FEATURES'+join+owner+op+'AS02_CTL_SEGMENTED_NATIVE_FEATURES'+join+owner+op+'AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES'+join+owner+op+base.RNC+')'
                t=t.replace(old,old[:-1]+join+owner+op+RNC+')')
        out[p]=t
    p=KERNEL/'rnic_io.c';out[p]=once(out[p],'value != '+base.RNC+'))','value != '+base.RNC+' && value != '+RNC+'))')
    p=KERNEL/'atomic_profile.h';t=out[p]
    t=once(t,'#include "verbs_segmented_immediate_wqe.h"',
        '#include "verbs_segmented_immediate_wqe.h"\n#include "verbs_segmented_receive_wqe.h"')
    t=once(t,'#define '+base.PROFILE+' 6U',
        '#define '+base.PROFILE+' 6U\n#define '+PROFILE+' 7U\n#define '+CQC+' 255U\n#define '+RQC+' 31U')
    out[p]=once(t,'p=='+base.PROFILE+';','p=='+base.PROFILE+' || p=='+PROFILE+';')
    # RQC31 is not a legal SQ identity; both new rings still require128 bytes.
    p=KERNEL/'sq_io.c';t=out[p]
    t=once(t,'v == AS02_RQC_ATOMIC_FEATURE_VALUE))))',
        'v == AS02_RQC_ATOMIC_FEATURE_VALUE || v == '+RQC+'))))')
    out[p]=once(t,'if(v==(expected_id==AS02_SQC_ID_VALUE ? AS02_SQC_ATOMIC_FEATURE_VALUE:AS02_RQC_ATOMIC_FEATURE_VALUE)){',
        'if(v==(expected_id==AS02_SQC_ID_VALUE ? AS02_SQC_ATOMIC_FEATURE_VALUE:AS02_RQC_ATOMIC_FEATURE_VALUE) ||\n'
        '       (expected_id==AS02_RQC_ID_VALUE && v=='+RQC+')){')
    p=KERNEL/'verbs.c';t=out[p]
    out[p]=once(t,'    if(transport=='+base.RNC+') {',
        '    if(transport=='+RNC+') {\n'
        '        if(!rq || sq_features!=AS02_SQC_ATOMIC_FEATURE_VALUE || rq_features!='+RQC+' ||\n'
        '           cq_features!='+CQC+'){ret=-EOPNOTSUPP;goto out;}\n'
        '        ret=atomic_geometry(h,rq,cq);if(ret)goto out;\n'
        '        profile='+PROFILE+';\n'
        '    }else if(transport=='+base.RNC+') {')
    p=KERNEL/'sq.c';t=out[p]
    t=once(t,'ret=receive ? as02_zero_wqe_from_ib_recv_wr(encoded,receive,q->producer+1,owner->epoch):',
        'ret=receive ? (p->wqe_profile=='+PROFILE+' ?\n'
        '            as02_segmented_receive_wqe_from_ib_recv_wr(encoded,receive,q->producer+1,owner->epoch):\n'
        '            as02_zero_wqe_from_ib_recv_wr(encoded,receive,q->producer+1,owner->epoch)):')
    t=once(t,'(p->wqe_profile=='+base.PROFILE+' ?\n',
        '((p->wqe_profile=='+base.PROFILE+' || p->wqe_profile=='+PROFILE+') ?\n')
    t=once(t,'if(!ret)ret=p->wqe_profile=='+base.PROFILE+' ?',
        'if(!ret)ret=p->wqe_profile=='+PROFILE+' ? as02_segmented_receive_wqe_decode(&atomic_work,encoded):\n'
        '            p->wqe_profile=='+base.PROFILE+' ?')
    for pair in ['expected,&a','observed,&b']:
        old='(p->wqe_profile=='+base.PROFILE+' ? as02_segmented_immediate_wqe_encode('+pair+'):'
        t=once(t,old,'(p->wqe_profile=='+PROFILE+' ? as02_segmented_receive_wqe_encode('+pair+'):\n'
            '             p->wqe_profile=='+base.PROFILE+' ? as02_segmented_immediate_wqe_encode('+pair+'):')
    out[p]=t
    p=KERNEL/'cq_io.c';t=out[p]
    t=once(t,'(profile=='+base.PROFILE+' ? as02_segmented_immediate_wqe_validate(&aw):',
        '(profile=='+PROFILE+' ? as02_segmented_receive_wqe_validate(&aw):\n'
        '        profile=='+base.PROFILE+' ? as02_segmented_immediate_wqe_validate(&aw):')
    t=once(t,'features!='+base.CQC+'))','features!='+base.CQC+' && features!='+CQC+'))')
    for prefix in ['','h->']:
        old='if('+prefix+'features==AS02_CQC_ATOMIC_FEATURE_VALUE || '+prefix+'features==AS02_CQC_SEGMENTED_FEATURE_VALUE || '+prefix+'features==AS02_CQC_SEGMENTED_READ_FEATURE_VALUE || '+prefix+'features=='+base.CQC+'){'
        t=once(t,old,old[:-2]+' || '+prefix+'features=='+CQC+'){')
    out[p]=once(t,'as02_cq_decode_profile(&d,&e,h->features=='+base.CQC+' ?',
        'as02_cq_decode_profile(&d,&e,h->features=='+CQC+' ? '+PROFILE+':\n'
        '        h->features=='+base.CQC+' ?')
    p=KERNEL/'cq_io.h';out[p]=once(out[p],
        'd->received_bytes>AS02_WQE_MAX_BYTES)return 0;',
        'd->received_bytes>((d->profile=='+PROFILE+' && flags!=3) ?\n'
        '        AS02_SEGMENTED_WQE_MAX_BYTES:AS02_WQE_MAX_BYTES))return 0;')
    p=KERNEL/'device.c';t=out[p]
    t=once(t,'(d->qp_hw->control->control.features=='+base.RNC+' ?',
        '(d->qp_hw->control->control.features=='+RNC+' ? '+PROFILE+':\n'
        '             d->qp_hw->control->control.features=='+base.RNC+' ?')
    t=once(t,'(d->sq->wqe_profile=='+base.PROFILE+' ?',
        '(d->sq->wqe_profile=='+PROFILE+' ? '+CQC+':\n'
        '              d->sq->wqe_profile=='+base.PROFILE+' ?')
    out[p]=once(t,'(d->sq->wqe_profile==AS02_WQE_PROFILE_SEGMENTED_READ128 || d->sq->wqe_profile=='+base.PROFILE+') ?',
        '(d->sq->wqe_profile==AS02_WQE_PROFILE_SEGMENTED_READ128 || d->sq->wqe_profile=='+base.PROFILE+' || d->sq->wqe_profile=='+PROFILE+') ?')
    p=KERNEL/'native_graph.c';t=out[p]
    marker='    if((g->control.control.features=='+base.RNC+') !='
    t=once(t,marker,'    if((g->control.control.features=='+RNC+') !=\n'
        '       (readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)=='+CQC+')){\n'
        '        ret=-EOPNOTSUPP;goto failed;\n    }\n'+marker)
    out[p]=once(t,'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+base.CQC+'):',
        'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+base.CQC+' &&\n'
        '         readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+CQC+'):')
    p=KERNEL/'Makefile';out[p]=once(out[p],'wqe_segmented_immediate.o verbs_segmented_immediate_wqe.o',
        'wqe_segmented_immediate.o verbs_segmented_immediate_wqe.o wqe_segmented_receive.o verbs_segmented_receive_wqe.o')
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:raise ValueError('Atomic advertisement stays disabled')
    return out
