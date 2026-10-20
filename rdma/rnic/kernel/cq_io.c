/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif
#include "cq_io.h"

static as02_u64 bits(const as02_u32 *v, unsigned int first, unsigned int width)
{
    as02_u64 result=0;
    unsigned int i;
    for(i=0;i<width;i++)
        result|=(as02_u64)((v[(first+i)/32]>>((first+i)%32))&1U)<<i;
    return result;
}
int as02_cq_decode_profile(struct as02_cq_decoded *out, const struct as02_cq_event *e, as02_u32 profile)
{
    struct as02_cq_decoded d={};
    as02_u32 context[AS02_CQC_CONTEXT_WORDS+1];
    if(!out)return -EINVAL;
    memset(out,0,sizeof(*out));
    if(!e || !e->sequence || !e->cookie || e->proofs!=AS02_CQC_COMPLETE_PROOFS || e->status ||
       (profile & ~AS02_WQE_PROFILE_IMMEDIATE) ||
       (profile ? (e->context_extension&0xfffff000U) :
        ((e->context[18]&0xfffff000U) || e->context_extension || e->notification || e->notification_flags)) ||
       bits(e->context,0,2)!=3 || bits(e->context,2,18))
        return -EIO;
    d.work.wr_id=bits(e->context,524,64);d.work.sequence=bits(e->context,460,64);
    d.work.epoch=bits(e->context,396,64);d.qpn=bits(e->context,372,24);
    d.pd=bits(e->context,356,16);d.tag=bits(e->context,340,16);
    d.work.opcode=bits(e->context,324,16);d.work.flags=bits(e->context,308,16);
    d.work.length=bits(e->context,276,32);d.work.local_key=bits(e->context,244,32);
    d.work.local_address=bits(e->context,180,64);d.local_offset=bits(e->context,116,64);
    d.work.remote_address=bits(e->context,52,64);d.work.remote_key=bits(e->context,20,32);
    d.cookie=e->cookie;d.event_sequence=e->sequence;d.proofs=e->proofs;d.status=e->status;
    d.received_bytes=e->received_bytes;
    d.profile=profile;d.notification=e->notification;d.notification_flags=e->notification_flags;
    memcpy(context,e->context,sizeof(e->context));context[AS02_CQC_CONTEXT_WORDS]=e->context_extension;
    if(profile)d.work.immediate=(as02_u32)bits(context,588,32);
    if(d.qpn>=8 || !d.tag || as02_wqe_validate_profile(&d.work,profile) || !as02_cq_notification_valid(&d))return -EIO;
    *out=d;return 0;
}
int as02_cq_decode(struct as02_cq_decoded *out,const struct as02_cq_event *e)
{ return as02_cq_decode_profile(out,e,0); }
static int read_reg(struct as02_cq_io *h,as02_u32 offset,as02_u32 *value)
{
    return h->io->read32(h->context,offset,value);
}
int as02_cq_io_init(struct as02_cq_io *h,const struct as02_cq_transport *io,void *context)
{
    as02_u32 id,abi,features,status,seq,ack;
    int ret;
    if(!h || !io || !io->read32 || !io->write32)return -EINVAL;
    if(h->initialized || h->detached)return -EBUSY;
    memset(h,0,sizeof(*h));h->io=io;h->context=context;
#define GET(offset,value) do {ret=read_reg(h,offset,&value);if(ret)return ret;}while(0)
    GET(AS02_CQC_ID,id);GET(AS02_CQC_ABI,abi);GET(AS02_CQC_FEATURES,features);
    GET(AS02_CQC_STATUS,status);GET(AS02_CQC_SEQUENCE,seq);GET(AS02_CQC_LAST_ACK,ack);
#undef GET
    if(id!=AS02_CQC_ID_VALUE || abi!=AS02_CQC_ABI_VALUE ||
       (features!=AS02_CQC_FEATURE_VALUE && features!=AS02_CQC_MESSAGE_FEATURE_VALUE &&
        features!=AS02_CQC_IMMEDIATE_FEATURE_VALUE))
        return -ENODEV;
    if(status || seq || ack)return -EBUSY;
    h->features=features;h->initialized=1;return 0;
}
static int finish_ack(struct as02_cq_io *h)
{
    as02_u32 ack;
    int ret=read_reg(h,AS02_CQC_LAST_ACK,&ack);
    if(ret)return ret;
    if(ack==h->held.sequence){
        h->acknowledged=ack;h->pending_ack=0;memset(&h->held,0,sizeof(h->held));return 1;
    }
    if(ack!=h->acknowledged){h->uncertain=1;return -EIO;}
    ret=h->io->write32(h->context,AS02_CQC_ACK,h->held.sequence);
    if(ret)return ret;
    ret=read_reg(h,AS02_CQC_LAST_ACK,&ack);
    if(ret)return ret;
    if(ack!=h->held.sequence)return -EAGAIN;
    h->acknowledged=ack;h->pending_ack=0;memset(&h->held,0,sizeof(h->held));return 1;
}
int as02_cq_io_poll(struct as02_cq_io *h,int (*deliver)(void *,const struct as02_cq_decoded *),void *ctx)
{
    struct as02_cq_event e={};struct as02_cq_decoded d;
    as02_u32 status,again,seq,lo,hi,ack;
    unsigned int i;
    int ret;
    if(!h || !h->initialized || !deliver)return -EINVAL;
    if(h->detached)return -ENODEV;
    if(h->uncertain)return -EIO;
    if(h->pending_ack)return finish_ack(h);
#define GET(offset,value) do {ret=read_reg(h,offset,&value);if(ret)return ret;}while(0)
    GET(AS02_CQC_STATUS,status);
    if(status&~15U || status&AS02_CQC_FAULT){h->uncertain=1;return -EIO;}
    if(!(status&AS02_CQC_VISIBLE))return 0;
    GET(AS02_CQC_SEQUENCE,e.sequence);GET(AS02_CQC_LAST_ACK,ack);
    if(h->acknowledged==0xffffffffU || e.sequence!=h->acknowledged+1 || ack!=h->acknowledged){
        h->uncertain=1;return -EIO;
    }
    GET(AS02_CQC_PROOFS,e.proofs);GET(AS02_CQC_WC_STATUS,e.status);
    GET(AS02_CQC_COOKIE_LO,lo);GET(AS02_CQC_COOKIE_HI,hi);e.cookie=lo|((as02_u64)hi<<32);
    if(h->features&AS02_CQC_FEATURE_MESSAGES)GET(AS02_CQC_RECEIVED_BYTES,e.received_bytes);
    for(i=0;i<AS02_CQC_CONTEXT_WORDS;i++)GET(AS02_CQC_CONTEXT+i*4,e.context[i]);
    if(h->features&AS02_CQC_FEATURE_IMMEDIATE){
        GET(AS02_CQC_CONTEXT_EXTENSION,e.context_extension);
        GET(AS02_CQC_NOTIFICATION,e.notification);GET(AS02_CQC_NOTIFICATION_FLAGS,e.notification_flags);
    }
    GET(AS02_CQC_SEQUENCE,seq);GET(AS02_CQC_STATUS,again);
#undef GET
    if(seq!=e.sequence || again!=status || !(status&AS02_CQC_BUSY) ||
       as02_cq_decode_profile(&d,&e,(h->features&AS02_CQC_FEATURE_IMMEDIATE) ? AS02_WQE_PROFILE_IMMEDIATE:0) ||
       (d.work.opcode==AS02_WQE_RECV && !(h->features&AS02_CQC_FEATURE_MESSAGES))){
        h->uncertain=1;return -EIO;
    }
    ret=deliver(ctx,&d);
    if(ret)return ret;
    h->held=e;h->pending_ack=1;
    return finish_ack(h);
}
int as02_cq_io_detach(struct as02_cq_io *h)
{
    as02_u32 status,seq,ack;
    int ret;
    if(!h || !h->initialized)return -EINVAL;
    if(h->pending_ack || h->uncertain)return -EBUSY;
    ret=read_reg(h,AS02_CQC_STATUS,&status);if(ret)return ret;
    ret=read_reg(h,AS02_CQC_SEQUENCE,&seq);if(ret)return ret;
    ret=read_reg(h,AS02_CQC_LAST_ACK,&ack);if(ret)return ret;
    if(status&~AS02_CQC_EXHAUSTED || seq!=ack || ack!=h->acknowledged)return -EBUSY;
    h->detached=1;return 0;
}
#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_cq_decode);
EXPORT_SYMBOL_GPL(as02_cq_decode_profile);
EXPORT_SYMBOL_GPL(as02_cq_io_init);
EXPORT_SYMBOL_GPL(as02_cq_io_poll);
EXPORT_SYMBOL_GPL(as02_cq_io_detach);
#endif
