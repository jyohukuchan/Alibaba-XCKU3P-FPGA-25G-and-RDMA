# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private Atomic128 kernel cohort for actual QP AND MR receive authority.

The new RNC2047 feature MUST negotiate the full128-byte SQ/RQ/CQ geometry.
Only that bound cohort accepts standard remote-Atomic MR/QP access flags.
QP access travels in the actual privileged snapshot and retained route owner;
TX-only commands preserve it and drained PD0 tombstones carry zero access.
Default/097 sources and both IB_ATOMIC_NONE declarations are unchanged.
"""
import derive_atomic128 as base

ROOT=base.ROOT;KERNEL=base.KERNEL;once=base.once

ENABLED=r'''
static bool atomic_access_enabled(const struct as02_verbs_device *d)
{
    return d && d->sq && d->sq->profile_bound &&
        d->sq->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 && d->qp_hw && d->qp_hw->control &&
        d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES;
}
'''


def derive():
    out=base.derive()
    for n in ['rnic_regs.h','rnic_io.c','qp_hw.h','qp_hw.c']:
        out[KERNEL/n]=(KERNEL/n).read_text()
    p=KERNEL/'rnic_regs.h'
    out[p]=once(out[p],'#define AS02_CTL_FEATURE_IMMEDIATE 512U',
        '#define AS02_CTL_FEATURE_IMMEDIATE 512U\n#define AS02_CTL_FEATURE_ATOMIC_ACCESS 1024U\n'
        '#define AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES 2047U')
    p=KERNEL/'rnic_io.c';t=out[p]
    t=once(t,'value != AS02_CTL_IMMEDIATE_NATIVE_FEATURES))',
        'value != AS02_CTL_IMMEDIATE_NATIVE_FEATURES && value != AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES))')
    t=once(t,'    if (op == AS02_CMD_QP_TX) {',r'''
    if(op==AS02_CMD_BEGIN && (access&8) && c->features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES)
        return -EOPNOTSUPP;
    if(op==AS02_CMD_QP){
        if(c->features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES){
            if(w[AS02_W_PD] ? (access!=6 && access!=14):access!=0)return -EINVAL;
        }else if(access)return -EOPNOTSUPP;
    }
    if (op == AS02_CMD_QP_TX) {''')
    out[p]=t
    p=KERNEL/'qp_hw.h'
    out[p]=once(out[p],'    u32 qpn, pd, peer_qpn, local_ip, peer_ip, rx_psn, tx_psn;',
        '    u32 qpn, pd, peer_qpn, local_ip, peer_ip, rx_psn, tx_psn;\n    u32 access;')
    p=KERNEL/'qp_hw.c';t=out[p]
    t=once(t,'        w[AS02_W_QP] = route->qpn;',
        '        w[AS02_W_ACCESS] = op==AS02_CMD_QP ? route->access:0;\n        w[AS02_W_QP] = route->qpn;')
    t=once(t,'    if (q->owned || q->uncertain) { ret = -EBUSY; goto out; }',
        '    if(q->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ?\n'
        '       (route->access!=6 && route->access!=14):route->access!=0){ret=-EOPNOTSUPP;goto out;}\n'
        '    if (q->owned || q->uncertain) { ret = -EBUSY; goto out; }')
    out[p]=t
    p=KERNEL/'verbs.c';t=out[p]
    t=once(t,'if(transport==AS02_CTL_IMMEDIATE_NATIVE_FEATURES && rq &&',
        'if((transport==AS02_CTL_IMMEDIATE_NATIVE_FEATURES || transport==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES) && rq &&')
    t=once(t,'static struct ib_mr *reg_user_mr(',ENABLED+'\nstatic struct ib_mr *reg_user_mr(')
    t=once(t,'IB_ACCESS_REMOTE_WRITE | IB_ACCESS_REMOTE_READ)))',
        'IB_ACCESS_REMOTE_WRITE | IB_ACCESS_REMOTE_READ | (atomic_access_enabled(d) ? IB_ACCESS_REMOTE_ATOMIC:0))))')
    t=once(t,'p->number, access, 7);', 'p->number, access, atomic_access_enabled(d) ? 15:7);')
    t=once(t,'attr->qp_access_flags != (IB_ACCESS_REMOTE_READ | IB_ACCESS_REMOTE_WRITE))',
        '(attr->qp_access_flags != (IB_ACCESS_REMOTE_READ | IB_ACCESS_REMOTE_WRITE) &&\n'
        '             !(atomic_access_enabled(d) && attr->qp_access_flags==\n'
        '               (IB_ACCESS_REMOTE_READ | IB_ACCESS_REMOTE_WRITE | IB_ACCESS_REMOTE_ATOMIC))))')
    t=once(t,'        route.qpn = ibqp->qp_num; route.pd = q->pd->number;',
        '        route.access=d->qp_hw->control->control.features==AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES ?\n'
        '            q->attributes.qp_access_flags:0;\n        route.qpn = ibqp->qp_num; route.pd = q->pd->number;')
    out[p]=t
    for name in ['device.c','native_graph.c']:
        p=KERNEL/name;t=out[p]
        owner='d->qp_hw->control->control'if name=='device.c'else'g->control.control'
        t=once(t,owner+'.features!=AS02_CTL_IMMEDIATE_NATIVE_FEATURES)',
            owner+'.features!=AS02_CTL_IMMEDIATE_NATIVE_FEATURES &&\n         '+owner+'.features!=AS02_CTL_ATOMIC_ACCESS_NATIVE_FEATURES)')
        out[p]=t
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:
        raise ValueError('no standard Atomic capability before full qualification')
    return out
