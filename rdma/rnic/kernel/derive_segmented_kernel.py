# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private matched RNC8191/CQC31 large WRITE/SEND kernel source cohort.

New software profile4 still uses real128-byte SQ/RQ and full748-bit CQ.
Only exact privileged hardware negotiation enables it. Preserve every
MR/PD/range/ref, ring/producer/CQ/backpressure/failure-lifetime check.
Old profiles, defaults, IB_ATOMIC_NONE and <=4096 READ/RQ/Immediate remain.
No install/load or actual Linux/hardware-runtime qualification is implied.
"""
import re
import derive_zero_kernel as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once


def profiles(t):
    operand=r'([A-Za-z_]\w*(?:(?:->|\.)[A-Za-z_]\w*)*)'
    t=re.sub(operand+r'\s*==\s*AS02_WQE_PROFILE_ATOMIC128\b',r'as02_profile_is128(\1)',t)
    return re.sub(operand+r'\s*!=\s*AS02_WQE_PROFILE_ATOMIC128\b',r'!as02_profile_is128(\1)',t)


def derive():
    out=base.derive()
    p=KERNEL/'rnic_regs.h'
    out[p]=once(out[p],'#define AS02_CTL_ZERO_NATIVE_FEATURES 4095U',
        '#define AS02_CTL_ZERO_NATIVE_FEATURES 4095U\n#define AS02_CTL_FEATURE_SEGMENTED 4096U\n'
        '#define AS02_CTL_SEGMENTED_NATIVE_FEATURES 8191U')
    # Exact existing Atomic-access policy, additionally bound to new tuple.
    for name,owner in [('rnic_io.c','c->features'),('qp_hw.c','q->control->control.features'),
                       ('verbs.c','d->qp_hw->control->control.features'),
                       ('device.c','d->qp_hw->control->control.features'),('native_graph.c','g->control.control.features')]:
        p=KERNEL/name;t=out[p]
        for op,join in [('==',' || '),('!=',' && ')]:
            anchor=owner+op+'AS02_CTL_ZERO_NATIVE_FEATURES'
            t=t.replace(anchor,'('+anchor+join+owner+op+'AS02_CTL_SEGMENTED_NATIVE_FEATURES)')
        out[p]=t
    p=KERNEL/'rnic_io.c';out[p]=once(out[p],'value != AS02_CTL_ZERO_NATIVE_FEATURES))',
        'value != AS02_CTL_ZERO_NATIVE_FEATURES && value != AS02_CTL_SEGMENTED_NATIVE_FEATURES))')
    p=KERNEL/'atomic_profile.h';t=out[p]
    t=once(t,'#include "wqe_zero.h"','#include "wqe_zero.h"\n#include "verbs_segmented_wqe.h"')
    t=once(t,'#define AS02_WQE_PROFILE_ATOMIC128 3U',
        '#define AS02_WQE_PROFILE_ATOMIC128 3U\n#define AS02_WQE_PROFILE_SEGMENTED128 4U\n'
        '#define AS02_CQC_SEGMENTED_FEATURE_VALUE 31U\n'
        'static inline int as02_profile_is128(as02_u32 p)\n'
        '{ return p==AS02_WQE_PROFILE_ATOMIC128 || p==AS02_WQE_PROFILE_SEGMENTED128; }')
    out[p]=once(t,'profile==AS02_WQE_PROFILE_ATOMIC128 ?','as02_profile_is128(profile) ?')

    p=KERNEL/'verbs.c';t=out[p]
    marker='    if((transport==AS02_CTL_IMMEDIATE_NATIVE_FEATURES'
    t=once(t,marker,'''    if(transport==AS02_CTL_SEGMENTED_NATIVE_FEATURES){
        if(!rq || sq_features!=AS02_SQC_ATOMIC_FEATURE_VALUE || rq_features!=AS02_RQC_ATOMIC_FEATURE_VALUE ||
           cq_features!=AS02_CQC_SEGMENTED_FEATURE_VALUE){ret=-EOPNOTSUPP;goto out;}
        ret=atomic_geometry(h,rq,cq);if(ret)goto out;
        profile=AS02_WQE_PROFILE_SEGMENTED128;
    }else if((transport==AS02_CTL_IMMEDIATE_NATIVE_FEATURES''')
    t=t.replace('transport==AS02_CTL_ZERO_NATIVE_FEATURES',
        '(transport==AS02_CTL_ZERO_NATIVE_FEATURES || transport==AS02_CTL_SEGMENTED_NATIVE_FEATURES)')
    out[p]=t

    p=KERNEL/'sq.c';t=out[p]
    t=once(t,'as02_zero_wqe_from_ib_send_wr(encoded,wr,q->producer+1,owner->epoch);',
        '(p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?\n'
        '             as02_segmented_wqe_from_ib_send_wr(encoded,wr,q->producer+1,owner->epoch):\n'
        '             as02_zero_wqe_from_ib_send_wr(encoded,wr,q->producer+1,owner->epoch));')
    t=once(t,'if(!ret)ret=as02_zero_wqe_decode(&atomic_work,encoded);',
        'if(!ret)ret=p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ?\n'
        '            as02_segmented_wqe_decode(&atomic_work,encoded):as02_zero_wqe_decode(&atomic_work,encoded);')
    for name in ['expected,&a','observed,&b']:
        t=once(t,'as02_zero_wqe_encode('+name+')',
            '(p->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_encode('+name+'):\n'
            '             as02_zero_wqe_encode('+name+'))')
    out[p]=t

    p=KERNEL/'cq_io.c';t=out[p]
    t=once(t,'? as02_zero_wqe_validate(&aw):',
        '? (profile==AS02_WQE_PROFILE_SEGMENTED128 ? as02_segmented_wqe_validate(&aw):as02_zero_wqe_validate(&aw)):')
    t=once(t,'features!=AS02_CQC_ATOMIC_FEATURE_VALUE))',
        'features!=AS02_CQC_ATOMIC_FEATURE_VALUE && features!=AS02_CQC_SEGMENTED_FEATURE_VALUE))')
    t=once(t,'if(features==AS02_CQC_ATOMIC_FEATURE_VALUE){',
        'if(features==AS02_CQC_ATOMIC_FEATURE_VALUE || features==AS02_CQC_SEGMENTED_FEATURE_VALUE){')
    t=once(t,'if(h->features==AS02_CQC_ATOMIC_FEATURE_VALUE){',
        'if(h->features==AS02_CQC_ATOMIC_FEATURE_VALUE || h->features==AS02_CQC_SEGMENTED_FEATURE_VALUE){')
    t=once(t,'as02_cq_decode_profile(&d,&e,h->features==AS02_CQC_ATOMIC_FEATURE_VALUE ?',
        'as02_cq_decode_profile(&d,&e,h->features==AS02_CQC_SEGMENTED_FEATURE_VALUE ? AS02_WQE_PROFILE_SEGMENTED128:\n'
        '        h->features==AS02_CQC_ATOMIC_FEATURE_VALUE ?')
    out[p]=t

    p=KERNEL/'device.c';t=out[p]
    t=once(t,'(d->cq_hw->control.features==AS02_CQC_ATOMIC_FEATURE_VALUE ? AS02_WQE_PROFILE_ATOMIC128:AS02_WQE_PROFILE_IMMEDIATE)',
        '(d->qp_hw->control->control.features==AS02_CTL_SEGMENTED_NATIVE_FEATURES ? AS02_WQE_PROFILE_SEGMENTED128:\n'
        '             d->cq_hw->control.features==AS02_CQC_ATOMIC_FEATURE_VALUE ? AS02_WQE_PROFILE_ATOMIC128:AS02_WQE_PROFILE_IMMEDIATE)')
    t=once(t,'(d->sq->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 ? AS02_CQC_ATOMIC_FEATURE_VALUE:AS02_CQC_IMMEDIATE_FEATURE_VALUE)',
        '(d->sq->wqe_profile==AS02_WQE_PROFILE_SEGMENTED128 ? AS02_CQC_SEGMENTED_FEATURE_VALUE:\n'
        '              d->sq->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 ? AS02_CQC_ATOMIC_FEATURE_VALUE:AS02_CQC_IMMEDIATE_FEATURE_VALUE)')
    out[p]=t
    p=KERNEL/'native_graph.c';t=out[p]
    t=once(t,'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_ATOMIC_FEATURE_VALUE):',
        'readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_ATOMIC_FEATURE_VALUE &&\n'
        '         readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_SEGMENTED_FEATURE_VALUE):')
    marker='    if(g->control.control.features!=AS02_CTL_FULL_NATIVE_FEATURES'
    t=once(t,marker,'''    if((g->control.control.features==AS02_CTL_SEGMENTED_NATIVE_FEATURES) !=
       (readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)==AS02_CQC_SEGMENTED_FEATURE_VALUE)){
        ret=-EOPNOTSUPP;goto failed;
    }
'''+marker)
    out[p]=t
    for name in ['sq.c','verbs.c','cq_io.c','cq_io.h','device.c']:
        p=KERNEL/name;out[p]=profiles(out[p])
    p=KERNEL/'Makefile';out[p]=once(out[p],'wqe_atomic.o wqe_zero.o',
        'wqe_atomic.o wqe_zero.o wqe_segmented.o verbs_segmented_wqe.o')
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:
        raise ValueError('default Atomic advertisement must remain disabled')
    return out
