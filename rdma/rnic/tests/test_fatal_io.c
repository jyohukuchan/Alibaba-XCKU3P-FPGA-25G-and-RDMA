/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real C reader/decoder; MMIO/failure delivery/lifetime callbacks are MODELS. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "fatal_io.h"

static unsigned checks,deliveries;
#define CHECK(x) do {++checks;assert(x);}while(0)
struct model {
    struct as02_fatal_record r;
    unsigned visible,ack,fault,reads,writes,fail_read,ack_mode,callback_busy;
    struct as02_fatal_identity owner;
};
static int rd(void *context,as02_u32 off,as02_u32 *v)
{
    struct model *m=context;++m->reads;
    if(m->fail_read==m->reads)return -EIO;
    *v=0;
    if(off==AS02_FEC_ID)*v=AS02_FEC_ID_VALUE;
    else if(off==AS02_FEC_ABI)*v=AS02_FEC_ABI_VALUE;
    else if(off==AS02_FEC_FEATURES)*v=AS02_FEC_FEATURE_VALUE;
    else if(off==AS02_FEC_STATUS)*v=m->visible | (m->fault ? AS02_FEC_FAULT:0) | (m->r.sequence==0xffffffffU ? AS02_FEC_EXHAUSTED:0);
    else if(off==AS02_FEC_LAST_ACK)*v=m->ack;
    else if(off==AS02_FEC_SEQUENCE)*v=m->r.sequence;
    else if(off>=AS02_FEC_RECORD && off<AS02_FEC_BYTES && !(off&3))*v=m->visible ? m->r.word[(off-AS02_FEC_RECORD)/4]:0;
    else return -EIO;
    return 0;
}
static int wr(void *context,as02_u32 off,as02_u32 v)
{
    struct model *m=context;++m->writes;CHECK(off==AS02_FEC_ACK);
    if(m->ack_mode==1)return -EIO;
    if(m->ack_mode==2)return 0;
    CHECK(v==m->r.sequence && m->visible);m->ack=v;m->visible=0;
    return m->ack_mode==3 ? -EIO:0;
}
static int delivered(void *context,const struct as02_fatal_decoded *d)
{
    struct model *m=context;
    if(m->callback_busy)return -EAGAIN;
    if(!as02_fatal_identity_matches(d,&m->owner))return -ESTALE;
    /* Model: error is now recorded, ALL references remain held. */
    ++deliveries;return 0;
}
static const struct as02_fatal_transport io={rd,wr};
static void setbits(struct as02_fatal_record *r,unsigned bit,unsigned width,as02_u64 value)
{
    for(unsigned i=0;i<width;i++) {
        as02_u32 mask=1U<<((bit+i)%32);
        if((value>>i)&1)r->word[(bit+i)/32]|=mask;else r->word[(bit+i)/32]&=~mask;
    }
}
static struct as02_fatal_record load(const char *name)
{
    struct as02_fatal_record r={.sequence=1};FILE *f=fopen(name,"r");CHECK(f);
    for(unsigned i=0;i<AS02_FEC_WORDS;i++)CHECK(fscanf(f,"%x",&r.word[i])==1);
    CHECK(fclose(f)==0);return r;
}
static void malformed(struct as02_fatal_record r,unsigned first,unsigned width,as02_u64 value)
{
    struct as02_fatal_decoded d;setbits(&r,first,width,value);memset(&d,0x5a,sizeof(d));
    CHECK(as02_fatal_decode(&d,&r)==-EIO);
    struct as02_fatal_decoded zero={};CHECK(!memcmp(&d,&zero,sizeof(d)));
}
static void setup(struct model *m,struct as02_fatal_io *h,const struct as02_fatal_record *r)
{
    memset(m,0,sizeof(*m));memset(h,0,sizeof(*h));
    m->owner=(struct as02_fatal_identity){.cookie=0xfedcba9889abcdefULL,.epoch=0x9123456700000001ULL,.pd=17,.qpn=2};
    CHECK(as02_fatal_io_init(h,&io,m)==0);m->r=*r;m->visible=1;
}
int main(int argc,char **argv)
{
    CHECK(argc==3);
    struct as02_fatal_record records[2]={load(argv[1]),load(argv[2])};
    for(unsigned partial=0;partial<2;partial++) {
        struct as02_fatal_decoded d;struct as02_fatal_record r=records[partial];
        CHECK(as02_fatal_decode(&d,&r)==0 && d.qpn==2 && d.pd==17 && d.serial==1 && d.partial==partial*15);
        CHECK(d.syndrome==(partial ? 0x61:0x62) && d.received_psn==0x987654+partial && d.msn==0);
        CHECK(d.cookie==0xfedcba9889abcdefULL && d.epoch==0x9123456700000001ULL);
        CHECK(d.peer_qpn==196 && d.peer_ip==0xc6120b01 && d.local_ip==0xc6120b02 && d.access==14);
        CHECK(d.peer_mac==0xb8830367c5d0ULL && d.local_mac==0x8af3fbb97531ULL && !memcmp(d.raw.word,r.word,sizeof(r.word)));
        if(partial)CHECK(d.message_cookie==1 && d.packet_bytes==4096 && d.total_bytes==8193 && d.offset==0 && d.tag==1 && d.mac_tag==0x6001);
        if(partial)CHECK(d.address==0xfedcba9876543210ULL && d.key==8 && d.first_psn==0x987654 && d.packet_psn==0x987654);
        malformed(r,1000,1,1);malformed(r,992,8,3);malformed(r,984,8,1);malformed(r,960,24,1);
        malformed(r,952,8,1);malformed(r,900,4,1);malformed(r,892,8,0x60);malformed(r,780,64,0);
        malformed(r,528,64,0);malformed(r,464,64,0);malformed(r,448,16,0);malformed(r,424,24,8);
        if(!partial){malformed(r,0,1,1);malformed(r,928,16,0x6001);}
        else {
            malformed(r,944,8,14);malformed(r,928,16,0x6000);malformed(r,0,16,0);
            malformed(r,40,32,4080);malformed(r,72,32,1);malformed(r,128,32,4096);
            malformed(r,160,64,~(as02_u64)0);malformed(r,224,32,0);malformed(r,256,64,0);
            malformed(r,320,64,1);malformed(r,384,16,18);malformed(r,400,24,3);
        }
        struct model m;struct as02_fatal_io h;
        for(unsigned mode=0;mode<4;mode++) {
            setup(&m,&h,&r);m.ack_mode=mode;unsigned n=deliveries;
            int ret=as02_fatal_io_poll(&h,delivered,&m);
            CHECK(deliveries==n+1 && m.writes==1 && m.reads<100);
            if(mode==0)CHECK(ret==1 && !h.pending_ack && h.last_serial==d.serial);
            else {
                CHECK(h.pending_ack && (ret==-EIO || ret==-EAGAIN));m.ack_mode=0;
                CHECK(as02_fatal_io_poll(&h,delivered,&m)==1 && deliveries==n+1 && !h.pending_ack);
            }
            CHECK(as02_fatal_io_poll(&h,delivered,&m)==0);
            CHECK(as02_fatal_io_init(&h,&io,&m)==-EBUSY);
        }
        setup(&m,&h,&r);m.callback_busy=1;unsigned n=deliveries;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EAGAIN && deliveries==n && !m.writes && m.visible);
        m.callback_busy=0;m.owner.cookie=1;CHECK(as02_fatal_io_poll(&h,delivered,&m)==-ESTALE && !m.writes);
        m.owner.cookie=d.cookie;m.owner.epoch++;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-ESTALE && !m.writes);
        m.owner.epoch=d.epoch;CHECK(as02_fatal_io_poll(&h,delivered,&m)==1 && deliveries==n+1);
        /* A replayed CONTROL serial in a new synthetic mailbox event cannot
         * be silently adopted. This successor is not a live native proof. */
        m.r=r;m.r.sequence=2;m.visible=1;n=deliveries;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EIO && h.uncertain && deliveries==n);
        setup(&m,&h,&r);m.fail_read=m.reads+5;n=deliveries;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EIO && deliveries==n && !m.writes);
        m.fail_read=0;CHECK(as02_fatal_io_poll(&h,delivered,&m)==1);
        setup(&m,&h,&r);m.ack_mode=1;CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EIO && h.pending_ack);
        m.r.word[17]^=1;n=deliveries;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EIO && h.uncertain && deliveries==n);
        unsigned calls=m.reads+m.writes;CHECK(as02_fatal_io_detach(&h)==0 && h.pending_ack && h.uncertain);
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-ENODEV && calls==m.reads+m.writes);
        CHECK(as02_fatal_io_init(&h,&io,&m)==-EBUSY);
        setup(&m,&h,&r);m.r.sequence=2;n=deliveries;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==-EIO && h.uncertain && deliveries==n && !m.writes);
        /* Synthetic software/MMIO model boundary, NOT a narrowed or forced
         * hardware counter test: accept the final32-bit event, never wrap. */
        setup(&m,&h,&r);h.acknowledged=0xfffffffeU;m.ack=0xfffffffeU;m.r.sequence=0xffffffffU;
        CHECK(as02_fatal_io_poll(&h,delivered,&m)==1 && h.acknowledged==0xffffffffU);
        n=deliveries;CHECK(as02_fatal_io_poll(&h,delivered,&m)==-ENOSPC && deliveries==n);
    }
    printf("{\"pass_test\":true,\"assertions\":%u,\"accepted_callbacks\":%u,\"actual_recorded_native_seeds\":2,"
        "\"MMIO_is_model\":true,\"native_wiring_or_standard_verbs\":false,\"drain_unpin_or_reference_release\":false}\n",checks,deliveries);
    return 0;
}
