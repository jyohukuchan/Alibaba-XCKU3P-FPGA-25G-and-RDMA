# SPDX-License-Identifier: BSD-2-Clause-Views
"""PRIVATE source cohort: zero-length work has no MR/data-DMA reference.

RNC4095/new bit2048 + exact Atomic128 geometry is mandatory. Genuine SQ/RQ
slots, producer/MMIO ownership, full-owner CQ comparison and actual retirement
remain required. No default source, prior proof or Atomic capability change.
Native/HLS/physical qualification is separate; this cohort is never installed.
"""
import derive_atomic_access as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once


def derive():
    out=base.derive()
    p=KERNEL/'rnic_regs.h';out[p]=once(out[p],'#define AS02_CTL_FEATURE_ATOMIC_ACCESS 1024U',
        '#define AS02_CTL_FEATURE_ATOMIC_ACCESS 1024U\n#define AS02_CTL_FEATURE_ZERO_LENGTH 2048U\n'
        '#define AS02_CTL_ZERO_NATIVE_FEATURES 4095U')
    p=KERNEL/'rnic_io.c';t=out[p]
    t=once(t,'value != AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES))',
        'value != AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES && value != AS02_CTL_ZERO_NATIVE_FEATURES))')
    t=once(t,'(access&8) && c->features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES)',
        '(access&8) && c->features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES && c->features!=AS02_CTL_ZERO_NATIVE_FEATURES)')
    t=once(t,'if(c->features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES){',
        'if(c->features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES || c->features==AS02_CTL_ZERO_NATIVE_FEATURES){')
    out[p]=t
    p=KERNEL/'qp_hw.c';out[p]=once(out[p],'q->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ?',
        '(q->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES || q->control->control.features==AS02_CTL_ZERO_NATIVE_FEATURES) ?')
    p=KERNEL/'atomic_profile.h';out[p]=once(p.read_text(),'#include "wqe_atomic.h"','#include "wqe_atomic.h"\n#include "wqe_zero.h"')
    p=KERNEL/'sq.h';out[p]=once(out[p],'    bool profile_bound;', '    bool profile_bound;\n    bool zero_length_enabled;')
    p=KERNEL/'verbs.c';t=out[p]
    t=once(t,'transport==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES) && rq &&',
        'transport==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES || transport==AS02_CTL_ZERO_NATIVE_FEATURES) && rq &&')
    t=once(t,'d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;',
        '(d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ||\n'
        '         d->qp_hw->control->control.features==AS02_CTL_ZERO_NATIVE_FEATURES);')
    t=once(t,'route.access=d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ?',
        'route.access=(d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ||\n'
        '            d->qp_hw->control->control.features==AS02_CTL_ZERO_NATIVE_FEATURES) ?')
    t=once(t,'if(p->profile_bound && p->wqe_profile!=profile)',
        'if(p->profile_bound && (p->wqe_profile!=profile || p->zero_length_enabled!=(transport==AS02_CTL_ZERO_NATIVE_FEATURES)))')
    t=once(t,'else{p->wqe_profile=profile;p->profile_bound=true;ret=0;}',
        'else{p->zero_length_enabled=transport==AS02_CTL_ZERO_NATIVE_FEATURES;p->wqe_profile=profile;p->profile_bound=true;ret=0;}')
    out[p]=t
    p=KERNEL/'sq.c';t=out[p]
    for a,b in [('as02_atomic_wqe_from_ib_recv_wr(','as02_zero_wqe_from_ib_recv_wr('),
                ('as02_atomic_wqe_from_ib_send_wr(','as02_zero_wqe_from_ib_send_wr('),
                ('as02_atomic_wqe_decode(','as02_zero_wqe_decode('),
                ('as02_atomic_wqe_encode(','as02_zero_wqe_encode(')]:
        if a not in t:raise ValueError('full zero SQ codec path missing '+a)
        t=t.replace(a,b)
    t=once(t,'    mr = as02_user_mr_get_work(',
        '    if(!work.length && (!p->zero_length_enabled || p->wqe_profile!=AS02_WQE_PROFILE_ATOMIC128)){ret=-EOPNOTSUPP;goto out;}\n'
        '    mr = !work.length ? NULL:as02_user_mr_get_work(')
    t=once(t,'        as02_user_mr_put_work(mr);','        if(mr)as02_user_mr_put_work(mr);')
    t=once(t,'        if ((p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128',
        '        if ((!slot->work.length && (!p->zero_length_enabled || slot->mr || event->local_offset)) ||\n'
        '            (slot->work.length && !slot->mr) ||\n'
        '            (event->work.opcode==AS02_WQE_RECV && !event->received_bytes && !p->zero_length_enabled) ||\n'
        '            (p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128')
    t=once(t,'slot->work.local_address-slot->mr->layout.iova',
        '(slot->mr ? slot->work.local_address-slot->mr->layout.iova:0)')
    t=once(t,'ret = as02_user_mr_put_work(slot->mr);','ret = slot->mr ? as02_user_mr_put_work(slot->mr):0;')
    t=once(t,'ret=as02_user_mr_put_work(slot->mr);','ret=slot->mr ? as02_user_mr_put_work(slot->mr):0;')
    out[p]=t
    p=KERNEL/'cq_io.c';out[p]=once(out[p],'as02_atomic_wqe_validate(&aw)', 'as02_zero_wqe_validate(&aw)')
    p=KERNEL/'cq_io.h';out[p]=once(out[p],'if(!d->received_bytes || d->received_bytes>AS02_WQE_MAX_BYTES)',
        'if((!d->received_bytes && d->profile!=AS02_WQE_PROFILE_ATOMIC128) || d->received_bytes>AS02_WQE_MAX_BYTES)')
    for name in ['device.c','native_graph.c']:
        p=KERNEL/name;t=out[p]
        owner='d->qp_hw->control->control'if name=='device.c'else'g->control.control'
        t=once(t,owner+'.features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES)',
            owner+'.features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES && '+owner+'.features!=AS02_CTL_ZERO_NATIVE_FEATURES)')
        out[p]=t
    p=KERNEL/'Makefile';out[p]=once(out[p],'wqe_atomic.o verbs_wqe.o verbs_atomic_wqe.o',
        'wqe_atomic.o wqe_zero.o verbs_wqe.o verbs_atomic_wqe.o verbs_zero_wqe.o')
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:raise ValueError('capability changed')
    return out
