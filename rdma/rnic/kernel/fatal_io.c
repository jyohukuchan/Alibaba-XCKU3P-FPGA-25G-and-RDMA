/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif
#include "fatal_io.h"

static as02_u64 bits(const as02_u32 *v,unsigned int first,unsigned int width)
{
    as02_u64 r=0;unsigned int i;
    for(i=0;i<width;i++)r|=(as02_u64)((v[(first+i)/32]>>((first+i)%32))&1U)<<i;
    return r;
}
int as02_fatal_decode(struct as02_fatal_decoded *out,const struct as02_fatal_record *r)
{
    struct as02_fatal_decoded d={};as02_u64 end;unsigned int i;
    if(!out)return -EINVAL;
    memset(out,0,sizeof(*out));
    if(!r || !r->sequence || r->word[31]!=7 || bits(r->word,984,8) ||
       bits(r->word,952,8) || bits(r->word,900,4) ||
       bits(r->word,960,24)!=bits(r->word,904,24))return -EIO;
    d.raw=*r;d.serial=bits(r->word,780,64);d.cookie=bits(r->word,528,64);
    d.epoch=bits(r->word,464,64);d.qpn=bits(r->word,424,24);d.pd=bits(r->word,448,16);
    d.peer_qpn=bits(r->word,592,24);d.local_ip=bits(r->word,616,32);d.peer_ip=bits(r->word,648,32);
    d.local_mac=bits(r->word,680,48);d.peer_mac=bits(r->word,728,48);d.access=bits(r->word,776,4);
    d.syndrome=bits(r->word,892,8);d.received_psn=bits(r->word,868,24);
    d.response_psn=bits(r->word,844,24);d.msn=bits(r->word,904,24);
    d.partial=bits(r->word,944,8);d.mac_tag=bits(r->word,928,16);
    if(!d.serial || !d.cookie || !d.epoch || !d.pd || d.qpn>=8 ||
       d.syndrome<0x61 || d.syndrome>0x63 || d.received_psn!=d.response_psn)return -EIO;
    if(!d.partial) {
        for(i=0;i<13;i++)if(r->word[i])return -EIO;
        if((r->word[13]&0xffU) || d.mac_tag)return -EIO;
    } else {
        d.message_cookie=bits(r->word,256,64);d.key=bits(r->word,224,32);
        d.address=bits(r->word,160,64);d.total_bytes=bits(r->word,128,32);
        d.first_psn=bits(r->word,104,24);d.offset=bits(r->word,72,32);
        d.packet_bytes=bits(r->word,40,32);d.packet_psn=bits(r->word,16,24);d.tag=bits(r->word,0,16);
        end=(as02_u64)d.offset+d.packet_bytes;
        if(d.partial!=15 || (d.mac_tag>>13)!=3 || !(d.mac_tag&8191) ||
           bits(r->word,400,24)!=d.qpn || bits(r->word,384,16)!=d.pd || bits(r->word,320,64)!=d.epoch ||
           !d.message_cookie || !d.key || !d.tag || d.total_bytes<=4096 || d.total_bytes>1048576 ||
           d.address>(~(as02_u64)0)-(d.total_bytes-1) || d.offset&4095 || d.packet_bytes!=4096 ||
           end>=d.total_bytes || d.packet_psn!=((d.first_psn+(d.offset>>12))&0xffffff) ||
           ((d.packet_psn+1)&0xffffff)!=d.response_psn)return -EIO;
    }
    *out=d;return 0;
}
int as02_fatal_identity_matches(const struct as02_fatal_decoded *d,const struct as02_fatal_identity *o)
{
    return d && o && o->cookie && o->epoch && o->pd && o->pd<=65535 && o->qpn<8 &&
        d->qpn==o->qpn && d->pd==o->pd && d->cookie==o->cookie && d->epoch==o->epoch;
}
static int read_reg(struct as02_fatal_io *h,as02_u32 off,as02_u32 *v)
{ return h->io->read32(h->context,off,v); }
int as02_fatal_io_init(struct as02_fatal_io *h,const struct as02_fatal_transport *io,void *context)
{
    as02_u32 id,abi,features,status,seq,ack;int ret;
    if(!h || !io || !io->read32 || !io->write32)return -EINVAL;
    if(h->initialized || h->detached || h->pending_ack || h->uncertain)return -EBUSY;
#define GET(o,v) do {ret=io->read32(context,o,&v);if(ret)return ret;}while(0)
    GET(AS02_FEC_ID,id);GET(AS02_FEC_ABI,abi);GET(AS02_FEC_FEATURES,features);
    GET(AS02_FEC_STATUS,status);GET(AS02_FEC_SEQUENCE,seq);GET(AS02_FEC_LAST_ACK,ack);
#undef GET
    if(id!=AS02_FEC_ID_VALUE || abi!=AS02_FEC_ABI_VALUE || features!=AS02_FEC_FEATURE_VALUE)return -ENODEV;
    if(status || seq || ack)return -EBUSY;
    memset(h,0,sizeof(*h));h->io=io;h->context=context;h->initialized=1;return 0;
}
static int bad(struct as02_fatal_io *h) {h->uncertain=1;return -EIO;}
static int finish_ack(struct as02_fatal_io *h)
{
    as02_u32 ack,status,seq,v;unsigned int i;int ret;
#define GET(o,v) do {ret=read_reg(h,o,&v);if(ret)return ret;}while(0)
    GET(AS02_FEC_LAST_ACK,ack);
    if(ack==h->held.sequence)goto done;
    if(ack!=h->acknowledged)return bad(h);
    GET(AS02_FEC_STATUS,status);GET(AS02_FEC_SEQUENCE,seq);
    if(status&~7U || status&AS02_FEC_FAULT || !(status&AS02_FEC_VISIBLE) || seq!=h->held.sequence)return bad(h);
    for(i=0;i<AS02_FEC_WORDS;i++) {
        GET(AS02_FEC_RECORD+i*4,v);if(v!=h->held.word[i])return bad(h);
    }
    GET(AS02_FEC_SEQUENCE,v);if(v!=seq)return bad(h);
    GET(AS02_FEC_STATUS,v);if(v!=status)return bad(h);
    ret=h->io->write32(h->context,AS02_FEC_ACK,h->held.sequence);if(ret)return ret;
    GET(AS02_FEC_LAST_ACK,ack);if(ack!=h->held.sequence)return ack==h->acknowledged ? -EAGAIN:bad(h);
#undef GET
done:
    h->acknowledged=h->held.sequence;h->last_serial=h->held_serial;h->pending_ack=0;
    h->held_serial=0;memset(&h->held,0,sizeof(h->held));return 1;
}
int as02_fatal_io_poll(struct as02_fatal_io *h,int (*deliver)(void *,const struct as02_fatal_decoded *),void *context)
{
    struct as02_fatal_record r={};struct as02_fatal_decoded d;
    as02_u32 status,seq,ack,again;unsigned int i;int ret;
    if(!h || !h->initialized || !deliver)return -EINVAL;
    if(h->detached)return -ENODEV;
    if(h->uncertain)return -EIO;
    if(h->pending_ack)return finish_ack(h);
#define GET(o,v) do {ret=read_reg(h,o,&v);if(ret)return ret;}while(0)
    GET(AS02_FEC_STATUS,status);
    if(status&~7U || status&AS02_FEC_FAULT)return bad(h);
    GET(AS02_FEC_SEQUENCE,r.sequence);GET(AS02_FEC_LAST_ACK,ack);
    if(!(status&AS02_FEC_VISIBLE)) {
        if(r.sequence!=ack || ack!=h->acknowledged)return bad(h);
        return status&AS02_FEC_EXHAUSTED ? -ENOSPC:0;
    }
    if(h->acknowledged==0xffffffffU || r.sequence!=h->acknowledged+1 || ack!=h->acknowledged)return bad(h);
    for(i=0;i<AS02_FEC_WORDS;i++)GET(AS02_FEC_RECORD+i*4,r.word[i]);
    GET(AS02_FEC_SEQUENCE,seq);GET(AS02_FEC_STATUS,again);
#undef GET
    if(seq!=r.sequence || again!=status || as02_fatal_decode(&d,&r) || d.serial<=h->last_serial)return bad(h);
    ret=deliver(context,&d);if(ret)return ret;
    h->held=r;h->held_serial=d.serial;h->pending_ack=1;return finish_ack(h);
}
int as02_fatal_io_detach(struct as02_fatal_io *h)
{
    if(!h || !h->initialized)return -EINVAL;
    h->detached=1;return 0;
}
#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_fatal_decode);
EXPORT_SYMBOL_GPL(as02_fatal_identity_matches);
EXPORT_SYMBOL_GPL(as02_fatal_io_init);
EXPORT_SYMBOL_GPL(as02_fatal_io_poll);
EXPORT_SYMBOL_GPL(as02_fatal_io_detach);
#endif
