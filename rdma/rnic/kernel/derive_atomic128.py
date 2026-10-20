# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked matched128 kernel SOURCE cohort, never the default installed driver.

Generate actual existing SQ/MR/verbs/CQ bodies with full Atomic owners, not
parallel queue/MR namespaces or model backends. Default files remain intact.
No atomic capability advertisement, load/install/MMIO/reboot/timing authority.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];KERNEL=Path(__file__).resolve().parent


def once(t,a,b):
    if t.count(a)!=1:raise ValueError('kernel derivation anchor changed: '+a)
    return t.replace(a,b)


def sq_io(t):
    t=once(t,'valid_words(const as02_u32 *w)','valid_words(const struct as02_sqc_io *c,const as02_u32 *w)')
    t=once(t,'(dma & 63)','(dma & (c->descriptor_bytes-1))')
    t=once(t,'bytes = 64ULL << w[10];','bytes = (as02_u64)c->descriptor_bytes << w[10];')
    t=once(t,'ret = valid_words(w);','ret = valid_words(c,w);')
    t=once(t,'!(expected_id == AS02_SQC_ID_VALUE && v == AS02_SQC_IMMEDIATE_FEATURE_VALUE)',
        '!(expected_id == AS02_SQC_ID_VALUE && (v == AS02_SQC_IMMEDIATE_FEATURE_VALUE || v == AS02_SQC_ATOMIC_FEATURE_VALUE))')
    t=once(t,'(v == 3 || v == AS02_RQC_IMMEDIATE_FEATURE_VALUE)',
        '(v == 3 || v == AS02_RQC_IMMEDIATE_FEATURE_VALUE || v == AS02_RQC_ATOMIC_FEATURE_VALUE)')
    return once(t,'    c->features=v;',r'''
    c->features=v;c->descriptor_bytes=AS02_WQE_BYTES;
    if(v==(expected_id==AS02_SQC_ID_VALUE ? AS02_SQC_ATOMIC_FEATURE_VALUE:AS02_RQC_ATOMIC_FEATURE_VALUE)){
        ret=io->read32(context,AS02_SQC_DESCRIPTOR_BYTES,&v);
        if(ret || v!=AS02_ATOMIC_WQE_BYTES)return ret ? ret:-EOPNOTSUPP;
        c->descriptor_bytes=v;
    }''')


def cq_header(t):
    t=once(t,'#include "wqe.h"','#include "atomic_profile.h"')
    t=once(t,'    as02_u32 context_extension, notification, notification_flags;',
        '    as02_u32 context_extension, notification, notification_flags;\n    as02_u64 compare,swap_add;')
    t=once(t,'    as02_u32 profile, notification, notification_flags;',
        '    as02_u32 profile, notification, notification_flags;\n    as02_u64 compare,swap_add;')
    return once(t,'(d->profile & ~AS02_WQE_PROFILE_IMMEDIATE)',
        '(d->profile!=0 && d->profile!=AS02_WQE_PROFILE_IMMEDIATE && d->profile!=AS02_WQE_PROFILE_ATOMIC128)')


def cq_io(t):
    t=once(t,'    struct as02_cq_decoded d={};','    struct as02_cq_decoded d={};struct as02_atomic_wqe aw;')
    t=once(t,'(profile & ~AS02_WQE_PROFILE_IMMEDIATE)',
        '(profile!=0 && profile!=AS02_WQE_PROFILE_IMMEDIATE && profile!=AS02_WQE_PROFILE_ATOMIC128) ||\n'
        '       (profile!=AS02_WQE_PROFILE_ATOMIC128 && (e->compare || e->swap_add))')
    t=once(t,'    if(d.qpn>=8 || !d.tag || as02_wqe_validate_profile(&d.work,profile) || !as02_cq_notification_valid(&d))return -EIO;',
        '    d.compare=e->compare;d.swap_add=e->swap_add;\n'
        '    aw=(struct as02_atomic_wqe){.base=d.work,.compare=d.compare,.swap_add=d.swap_add};\n'
        '    if(d.qpn>=8 || !d.tag || (profile==AS02_WQE_PROFILE_ATOMIC128 ? as02_atomic_wqe_validate(&aw):\n'
        '       as02_wqe_validate_profile(&d.work,profile)) || !as02_cq_notification_valid(&d))return -EIO;')
    t=once(t,'features!=AS02_CQC_IMMEDIATE_FEATURE_VALUE))',
        'features!=AS02_CQC_IMMEDIATE_FEATURE_VALUE && features!=AS02_CQC_ATOMIC_FEATURE_VALUE))')
    t=once(t,'    if(status || seq || ack)return -EBUSY;',r'''
    if(features==AS02_CQC_ATOMIC_FEATURE_VALUE){
        as02_u32 owner_bits,operand_base;
        ret=read_reg(h,AS02_CQC_OWNER_BITS,&owner_bits);if(ret)return ret;
        ret=read_reg(h,AS02_CQC_OPERAND_BASE,&operand_base);if(ret)return ret;
        if(owner_bits!=AS02_CQC_ATOMIC_OWNER_BITS || operand_base!=AS02_CQC_ATOMIC_OPERANDS)return -EOPNOTSUPP;
    }
    if(status || seq || ack)return -EBUSY;''')
    t=once(t,'    GET(AS02_CQC_SEQUENCE,seq);GET(AS02_CQC_STATUS,again);',r'''
    if(h->features==AS02_CQC_ATOMIC_FEATURE_VALUE){
        GET(AS02_CQC_ATOMIC_OPERANDS,lo);GET(AS02_CQC_ATOMIC_OPERANDS+4,hi);e.compare=lo|((as02_u64)hi<<32);
        GET(AS02_CQC_ATOMIC_OPERANDS+8,lo);GET(AS02_CQC_ATOMIC_OPERANDS+12,hi);e.swap_add=lo|((as02_u64)hi<<32);
    }
    GET(AS02_CQC_SEQUENCE,seq);GET(AS02_CQC_STATUS,again);''')
    return once(t,'(h->features&AS02_CQC_FEATURE_IMMEDIATE) ? AS02_WQE_PROFILE_IMMEDIATE:0',
        'h->features==AS02_CQC_ATOMIC_FEATURE_VALUE ? AS02_WQE_PROFILE_ATOMIC128:\n'
        '        (h->features&AS02_CQC_FEATURE_IMMEDIATE) ? AS02_WQE_PROFILE_IMMEDIATE:0')


def sq(t):
    t=once(t,'    struct as02_wqe work;\n    bool used;',
        '    struct as02_wqe work;\n    u64 compare,swap_add;\n    bool used;')
    for a,b in [('q->layout.depth * AS02_WQE_BYTES','q->layout.depth * as02_profile_descriptor_bytes(p->wqe_profile)'),
                ('receive->layout.depth*AS02_WQE_BYTES','receive->layout.depth*as02_profile_descriptor_bytes(p->wqe_profile)'),
                ('((u64)q->dma & 63)','((u64)q->dma & (as02_profile_descriptor_bytes(p->wqe_profile)-1))'),
                ('((u64)receive->dma&63)','((u64)receive->dma&(as02_profile_descriptor_bytes(p->wqe_profile)-1))'),
                ('    u8 encoded[AS02_WQE_BYTES];','    u8 encoded[AS02_ATOMIC_WQE_BYTES]={};\n    struct as02_atomic_wqe atomic_work={};'),
                ('    slot->work = work;','    slot->work = work;slot->compare=atomic_work.compare;slot->swap_add=atomic_work.swap_add;'),
                ('index*AS02_WQE_BYTES, encoded, AS02_WQE_BYTES',
                 'index*as02_profile_descriptor_bytes(p->wqe_profile), encoded, as02_profile_descriptor_bytes(p->wqe_profile)')]:
        t=once(t,a,b)
    a=t.index('    ret = receive ? as02_wqe_from_ib_recv_wr(');b=t.index('    mr = as02_user_mr_get_work',a)
    t=t[:a]+r'''    if(p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128){
        if(!p->profile_bound){ret=-EOPNOTSUPP;goto out;}
        ret=receive ? as02_atomic_wqe_from_ib_recv_wr(encoded,receive,q->producer+1,owner->epoch):
            as02_atomic_wqe_from_ib_send_wr(encoded,wr,q->producer+1,owner->epoch);
        if(!ret)ret=as02_atomic_wqe_decode(&atomic_work,encoded);
        work=atomic_work.base;
    }else{
        ret=receive ? as02_wqe_from_ib_recv_wr(encoded,receive,q->producer+1,owner->epoch):
            as02_wqe_from_ib_send_wr_profile(encoded,wr,q->producer+1,owner->epoch,p->wqe_profile);
        if(!ret)ret=as02_wqe_decode_profile(&work,encoded,p->wqe_profile);
    }
    if(ret)goto out;
'''+t[b:]
    t=once(t,'(work.opcode == AS02_WQE_READ || work.opcode == AS02_WQE_RECV) ? 1 : 0',
        '(work.opcode == AS02_WQE_READ || work.opcode == AS02_WQE_RECV || as02_is_atomic_opcode(work.opcode)) ? 1 : 0')
    t=once(t,'    /* A proof-only legacy completion cannot distinguish',
        '    if(p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 && !event){ret=-EOPNOTSUPP;goto out;}\n'
        '    /* A proof-only legacy completion cannot distinguish')
    t=once(t,'        as02_byte expected[AS02_WQE_BYTES], observed[AS02_WQE_BYTES];',
        '        as02_byte expected[AS02_ATOMIC_WQE_BYTES]={}, observed[AS02_ATOMIC_WQE_BYTES]={};\n'
        '        struct as02_atomic_wqe a={.base=slot->work,.compare=slot->compare,.swap_add=slot->swap_add};\n'
        '        struct as02_atomic_wqe b={.base=event->work,.compare=event->compare,.swap_add=event->swap_add};')
    t=once(t,'        if (event->proofs != AS02_CQC_COMPLETE_PROOFS',
        '        if ((p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 && (!p->profile_bound || event->profile!=p->wqe_profile)) ||\n'
        '            event->proofs != AS02_CQC_COMPLETE_PROOFS')
    t=once(t,'p->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE || event->profile!=p->wqe_profile',
        '(p->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE && p->wqe_profile!=AS02_WQE_PROFILE_ATOMIC128) || event->profile!=p->wqe_profile')
    t=once(t,'            as02_wqe_encode_profile(expected, &slot->work,event->profile) ||\n            as02_wqe_encode_profile(observed, &event->work,event->profile) ||',
        '            (p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 ? as02_atomic_wqe_encode(expected,&a):\n'
        '             as02_wqe_encode_profile(expected,&slot->work,event->profile)) ||\n'
        '            (p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 ? as02_atomic_wqe_encode(observed,&b):\n'
        '             as02_wqe_encode_profile(observed,&event->work,event->profile)) ||')
    # No ring exists with a caller-forged unbound new format.
    t=once(t,'    mutex_lock(&p->lock);\n    if (p->stopping || p->slots[qpn]',
        '    if(p->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 && !p->profile_bound)return -EOPNOTSUPP;\n'
        '    mutex_lock(&p->lock);\n    if (p->stopping || p->slots[qpn]')
    return t


def cq(t):
    t=once(t,'event->opcode!=AS02_WQE_SEND_IMMEDIATE && event->opcode!=AS02_WQE_WRITE_IMMEDIATE',
        'event->opcode!=AS02_WQE_SEND_IMMEDIATE && event->opcode!=AS02_WQE_WRITE_IMMEDIATE && !as02_is_atomic_opcode(event->opcode)')
    t=once(t,'    wc.opcode=event->opcode==AS02_WQE_READ ? IB_WC_RDMA_READ :',
        '    wc.opcode=event->opcode==AS02_WQE_COMPARE_SWAP ? IB_WC_COMP_SWAP:\n'
        '        event->opcode==AS02_WQE_FETCH_ADD ? IB_WC_FETCH_ADD:\n'
        '        event->opcode==AS02_WQE_READ ? IB_WC_RDMA_READ :')
    return once(t,'(event->opcode==AS02_WQE_READ || event->opcode==AS02_WQE_RECV) ? event->length : 0',
        '(event->opcode==AS02_WQE_READ || event->opcode==AS02_WQE_RECV || as02_is_atomic_opcode(event->opcode)) ? event->length : 0')


def verbs(t):
    t=once(t,'int as02_sq_bind_transport_profile(',GEOMETRY+'\nint as02_sq_bind_transport_profile(')
    t=once(t,'    if(transport&AS02_CTL_FEATURE_IMMEDIATE){',r'''
    if(transport==AS02_CTL_IMMEDIATE_NATIVE_FEATURES && rq &&
       sq_features==AS02_SQC_ATOMIC_FEATURE_VALUE && rq_features==AS02_RQC_ATOMIC_FEATURE_VALUE &&
       cq_features==AS02_CQC_ATOMIC_FEATURE_VALUE){
        ret=atomic_geometry(h,rq,cq);if(ret)goto out;
        profile=AS02_WQE_PROFILE_ATOMIC128;
    }else if(transport&AS02_CTL_FEATURE_IMMEDIATE){''')
    t=once(t,'        bool send=w->opcode==IB_WR_SEND || w->opcode==IB_WR_SEND_WITH_IMM;',
        '        bool atomic=w->opcode==IB_WR_ATOMIC_CMP_AND_SWP || w->opcode==IB_WR_ATOMIC_FETCH_AND_ADD;\n'
        '        bool send=w->opcode==IB_WR_SEND || w->opcode==IB_WR_SEND_WITH_IMM;')
    t=once(t,'d->sq->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE))',
        '(d->sq->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE && d->sq->wqe_profile!=AS02_WQE_PROFILE_ATOMIC128)))')
    t=once(t,'        if ((immediate &&','        if ((atomic && (!d->sq->profile_bound || d->sq->wqe_profile!=AS02_WQE_PROFILE_ATOMIC128)) ||\n            (immediate &&')
    t=once(t,'(!send && w->opcode!=IB_WR_RDMA_READ','(!send && !atomic && w->opcode!=IB_WR_RDMA_READ')
    return once(t,'        else if (q->signal_all) {\n            struct ib_rdma_wr copy',r'''
        else if(q->signal_all && atomic){
            struct ib_atomic_wr copy=*atomic_wr(w);
            copy.wr.send_flags|=IB_SEND_SIGNALED;
            ret=as02_sq_post(d->sq,&q->owner,&copy.wr);
        }
        else if (q->signal_all) {
            struct ib_rdma_wr copy''')


GEOMETRY=r'''
static int atomic_geometry(struct as02_sq_hw *s,struct as02_sq_hw *r,struct as02_cq_hw *c)
{
    unsigned long flags;as02_u32 sb,rb,bits,base;int ret;
    spin_lock_irqsave(&s->lock,flags);
    ret=s->control.io->read32(s->control.context,AS02_SQC_DESCRIPTOR_BYTES,&sb);
    spin_unlock_irqrestore(&s->lock,flags);if(ret)return ret;
    spin_lock_irqsave(&r->lock,flags);
    ret=r->control.io->read32(r->control.context,AS02_SQC_DESCRIPTOR_BYTES,&rb);
    spin_unlock_irqrestore(&r->lock,flags);if(ret)return ret;
    spin_lock_irqsave(&c->lock,flags);
    ret=c->control.io->read32(c->control.context,AS02_CQC_OWNER_BITS,&bits);
    if(!ret)ret=c->control.io->read32(c->control.context,AS02_CQC_OPERAND_BASE,&base);
    spin_unlock_irqrestore(&c->lock,flags);if(ret)return ret;
    return sb==128 && rb==128 && s->control.descriptor_bytes==128 && r->control.descriptor_bytes==128 &&
        bits==748 && base==AS02_CQC_ATOMIC_OPERANDS ? 0:-EOPNOTSUPP;
}
'''


def derive():
    names=['sq_io.h','sq_io.c','sq.h','sq.c','cq_io.h','cq_io.c','cq.c','verbs.c','device.c','native_graph.c','Makefile']
    out={KERNEL/n:(KERNEL/n).read_text()for n in names}
    out[KERNEL/'sq.h']=once(out[KERNEL/'sq.h'],'#include "wqe.h"','#include "atomic_profile.h"')
    out[KERNEL/'sq_io.h']=once(out[KERNEL/'sq_io.h'],'#include "sq_regs.h"','#include "atomic_profile.h"')
    out[KERNEL/'sq_io.h']=once(out[KERNEL/'sq_io.h'],'timeout_us, sequence, features, expected',
        'timeout_us, sequence, features, descriptor_bytes, expected')
    for n,f in [('sq_io.c',sq_io),('sq.c',sq),('cq_io.h',cq_header),('cq_io.c',cq_io),('cq.c',cq),('verbs.c',verbs)]:
        out[KERNEL/n]=f(out[KERNEL/n])
    p=KERNEL/'Makefile';out[p]=once(out[p],'rnic_hw.o wqe.o verbs_wqe.o','rnic_hw.o wqe.o wqe_atomic.o verbs_wqe.o verbs_atomic_wqe.o')
    p=KERNEL/'device.c'
    out[p]=once(out[p],'? AS02_WQE_PROFILE_IMMEDIATE:0)',
        '? (d->cq_hw->control.features==AS02_CQC_ATOMIC_FEATURE_VALUE ? AS02_WQE_PROFILE_ATOMIC128:AS02_WQE_PROFILE_IMMEDIATE):0)')
    out[p]=once(out[p],'AS02_CQC_IMMEDIATE_FEATURE_VALUE:AS02_CQC_MESSAGE_FEATURE_VALUE)',
        '(d->sq->wqe_profile==AS02_WQE_PROFILE_ATOMIC128 ? AS02_CQC_ATOMIC_FEATURE_VALUE:AS02_CQC_IMMEDIATE_FEATURE_VALUE):AS02_CQC_MESSAGE_FEATURE_VALUE)')
    p=KERNEL/'native_graph.c'
    a=out[p].index('    if(readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ID)')
    b=out[p].index('    g->device=as02_device_alloc()',a)
    out[p]=out[p][:a]+r'''    if(readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ID)!=AS02_CQC_ID_VALUE ||
       readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ABI)!=AS02_CQC_ABI_VALUE ||
       ((g->control.control.features&AS02_CTL_FEATURE_IMMEDIATE) ?
        (readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_IMMEDIATE_FEATURE_VALUE &&
         readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_ATOMIC_FEATURE_VALUE):
        readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=AS02_CQC_MESSAGE_FEATURE_VALUE)){ret=-ENODEV;goto failed;}
'''+out[p][b:]
    if 'a->atomic_cap = IB_ATOMIC_NONE;'not in out[KERNEL/'device.c']:raise ValueError('Atomic advertisement changed')
    return out

