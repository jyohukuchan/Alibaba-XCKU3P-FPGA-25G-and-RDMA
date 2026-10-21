# SPDX-License-Identifier: BSD-2-Clause-Views
"""Distinct profile8/RNC131071/CQC511/SQC13/RQC63 WRITE-notice source cohort.

Reuse the actual standard RECV/zero/large codec and MR/QP/RQ/CQ lifetime
paths. Only the NEW exact capability tuple permits flags3 received bytes
through1MiB. Profile7's4096 WRITE limit and every older/default path remain.
No installation, live API, physical or timing qualification is implied.
"""
import derive_segmented_receive_kernel as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once
PROFILE='AS02_WQE_PROFILE_SEGMENTED_WRITE128'
RNC='AS02_CTL_SEGMENTED_WRITE_NATIVE_FEATURES'
CQC='AS02_CQC_SEGMENTED_WRITE_FEATURE_VALUE'
RQC='AS02_RQC_SEGMENTED_WRITE_FEATURE_VALUE'


def derive():
    out=base.derive();p=KERNEL/'rnic_regs.h'
    out[p]=once(out[p],'#define '+base.RNC+' 65535U',
        '#define '+base.RNC+' 65535U\n#define AS02_CTL_FEATURE_SEGMENTED_WRITE 65536U\n#define '+RNC+' 131071U')
    names=['AS02_CTL_ZERO_NATIVE_FEATURES','AS02_CTL_SEGMENTED_NATIVE_FEATURES','AS02_CTL_SEGMENTED_READ_NATIVE_FEATURES',base.base.RNC,base.RNC]
    extensions=0
    for name,owners in [('rnic_io.c',['c->features']),('qp_hw.c',['q->control->control.features']),
        ('verbs.c',['d->qp_hw->control->control.features','transport']),('device.c',['d->qp_hw->control->control.features']),
        ('native_graph.c',['g->control.control.features'])]:
        p=KERNEL/name;t=out[p]
        for owner in owners:
            for op,join in [('==',' || '),('!=',' && ')]:
                old='('+join.join(owner+op+n for n in names)+')';extensions+=t.count(old)
                t=t.replace(old,old[:-1]+join+owner+op+RNC+')')
        out[p]=t
    if extensions<8:raise ValueError('all actual native feature-identity groups must be extended')
    p=KERNEL/'rnic_io.c';out[p]=once(out[p],'value != '+base.RNC+'))','value != '+base.RNC+' && value != '+RNC+'))')
    p=KERNEL/'atomic_profile.h';t=out[p]
    t=once(t,'#define '+base.PROFILE+' 7U',
        '#define '+base.PROFILE+' 7U\n#define '+PROFILE+' 8U\n#define '+CQC+' 511U\n#define '+RQC+' 63U')
    out[p]=once(t,'p=='+base.PROFILE+';','p=='+base.PROFILE+' || p=='+PROFILE+';')
    p=KERNEL/'sq_io.c';t=out[p]
    t=once(t,'v == '+base.RQC+'))))','v == '+base.RQC+' || v == '+RQC+'))))')
    out[p]=once(t,'(expected_id==AS02_RQC_ID_VALUE && v=='+base.RQC+')){',
        '(expected_id==AS02_RQC_ID_VALUE && (v=='+base.RQC+' || v=='+RQC+'))){')
    p=KERNEL/'verbs.c';t=out[p]
    out[p]=once(t,'    if(transport=='+base.RNC+') {',
        '    if(transport=='+RNC+') {\n'
        '        if(!rq || sq_features!=AS02_SQC_ATOMIC_FEATURE_VALUE || rq_features!='+RQC+' ||\n'
        '           cq_features!='+CQC+'){ret=-EOPNOTSUPP;goto out;}\n'
        '        ret=atomic_geometry(h,rq,cq);if(ret)goto out;\n'
        '        profile='+PROFILE+';\n'
        '    }else if(transport=='+base.RNC+') {')
    # Identical C128 encoding and owner replay for profiles7/8. No new user
    # DMA address path, direct BAR access, payload copy or fake CQ release.
    p=KERNEL/'sq.c';t=out[p];needle='p->wqe_profile=='+base.PROFILE
    if t.count(needle)!=5:raise ValueError('all actual RECV/send/decode/replay codec selections required')
    out[p]=t.replace(needle,'(p->wqe_profile=='+base.PROFILE+' || p->wqe_profile=='+PROFILE+')')
    p=KERNEL/'cq_io.c';t=out[p]
    t=once(t,'(profile=='+base.PROFILE+' ? as02_segmented_receive_wqe_validate(&aw):',
        '((profile=='+base.PROFILE+' || profile=='+PROFILE+') ? as02_segmented_receive_wqe_validate(&aw):')
    t=once(t,'features!='+base.CQC+'))','features!='+base.CQC+' && features!='+CQC+'))')
    for prefix in ['','h->']:
        needle=' || '+prefix+'features=='+base.CQC+'){'
        t=once(t,needle,' || '+prefix+'features=='+base.CQC+' || '+prefix+'features=='+CQC+'){')
    out[p]=once(t,'as02_cq_decode_profile(&d,&e,h->features=='+base.CQC+' ? '+base.PROFILE+':',
        'as02_cq_decode_profile(&d,&e,h->features=='+CQC+' ? '+PROFILE+':\n'
        '        h->features=='+base.CQC+' ? '+base.PROFILE+':')
    p=KERNEL/'cq_io.h';out[p]=once(out[p],
        '(d->profile=='+base.PROFILE+' && flags!=3)',
        '(d->profile=='+PROFILE+' || (d->profile=='+base.PROFILE+' && flags!=3))')
    p=KERNEL/'device.c';t=out[p]
    t=once(t,'(d->qp_hw->control->control.features=='+base.RNC+' ? '+base.PROFILE+':',
        '(d->qp_hw->control->control.features=='+RNC+' ? '+PROFILE+':\n'
        '             d->qp_hw->control->control.features=='+base.RNC+' ? '+base.PROFILE+':')
    t=once(t,'(d->sq->wqe_profile=='+base.PROFILE+' ? '+base.CQC+':',
        '(d->sq->wqe_profile=='+PROFILE+' ? '+CQC+':\n'
        '              d->sq->wqe_profile=='+base.PROFILE+' ? '+base.CQC+':')
    needle=' || d->sq->wqe_profile=='+base.PROFILE+') ?'
    out[p]=once(t,needle,' || d->sq->wqe_profile=='+base.PROFILE+' || d->sq->wqe_profile=='+PROFILE+') ?')
    p=KERNEL/'native_graph.c';t=out[p]
    marker='    if((g->control.control.features=='+base.RNC+') !='
    t=once(t,marker,'    if((g->control.control.features=='+RNC+') !=\n'
        '       (readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)=='+CQC+')){\n'
        '        ret=-EOPNOTSUPP;goto failed;\n    }\n'+marker)
    out[p]=once(t,'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+base.CQC+'):',
        'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+base.CQC+' &&\n'
        '         readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!='+CQC+'):')
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:raise ValueError('Atomic advertisement remains disabled')
    return out
