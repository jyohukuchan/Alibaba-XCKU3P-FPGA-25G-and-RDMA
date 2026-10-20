/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif
#include "retry_io.h"
static int read_reg(struct as02_retry_io *h, as02_u32 a, as02_u32 *v)
{
    return h->io->read32(h->context, a, v);
}
int as02_retry_io_init(struct as02_retry_io *h, const struct as02_sqc_transport *io,
                       void *context, as02_u32 timeout_us)
{
    as02_u32 id, abi, feature, status, seq, clock;
    int ret;
    if (!h || !io || !io->read32 || !io->write32 || !io->time_us || !io->relax ||
        !timeout_us || timeout_us > AS02_SQC_MAX_TIMEOUT_US) return -EINVAL;
    if (h->initialized || h->pending || h->uncertain) return -EBUSY;
    h->io=io; h->context=context;
#define GET(a,v) do {ret=read_reg(h,a,&v);if(ret)return ret;} while(0)
    GET(0,id); GET(4,abi); GET(8,feature); GET(12,status); GET(24,seq); GET(28,clock);
#undef GET
    if (id!=AS02_RRP_ID || abi!=AS02_RRP_ABI || feature!=1 || clock!=4000) return -ENODEV;
    if (status!=1 || seq) return -EBUSY;
    h->sequence=0; h->timeout_us=timeout_us; h->clock_period_ps=clock; h->initialized=1;
    return 0;
}
int as02_retry_io_configure(struct as02_retry_io *h, const struct as02_retry_policy *p)
{
    as02_u32 words[8], status, seq, v, lo, hi;
    as02_u64 start;
    unsigned int i, polls;
    int ret;
    if (!h || !h->initialized || !p || !p->cookie || !p->epoch || p->qpn>=8 ||
        !p->pd || p->pd>65535 || p->timeout>31 || p->retry>7 || p->rnr_retry>7) return -EINVAL;
    if (h->pending || h->uncertain) return -EBUSY;
    if (h->sequence==0xffffffffU) return -ENOSPC;
    ret=read_reg(h,12,&status); if(ret)return ret;
    ret=read_reg(h,24,&seq); if(ret)return ret;
    if (status!=1 || seq!=h->sequence) {h->uncertain=1;return -EIO;}
    words[0]=h->sequence+1; words[1]=p->qpn; words[2]=p->pd;
    words[3]=p->timeout; words[4]=p->retry; words[5]=p->rnr_retry;
    words[6]=p->cookie; words[7]=p->cookie>>32;
    for(i=0;i<8;i++) {
        ret=h->io->write32(h->context,0x40+i*4,words[i]);
        if(ret)return ret; /* No bell, no ownership transfer yet. */
    }
    h->held=*p; h->pending=1; h->sequence=words[0];
    ret=h->io->write32(h->context,0x10,words[0]); if(ret)goto uncertain;
    start=h->io->time_us(h->context);
    for(polls=0;polls<AS02_SQC_MAX_POLLS;polls++) {
        ret=read_reg(h,12,&status); if(ret)goto uncertain;
        if(status&~15U || status&8U) {ret=-EIO;goto uncertain;}
        if(status&4U)break;
        if(h->io->time_us(h->context)-start>=h->timeout_us)break;
        h->io->relax(h->context);
    }
    if(status!=6) {ret=-ETIMEDOUT;goto uncertain;}
    for(i=0;i<8;i++) {
        ret=read_reg(h,0x80+i*4,&v); if(ret)goto uncertain;
        if(v!=words[i]) {ret=-EIO;goto uncertain;}
    }
    ret=read_reg(h,0xa0,&lo); if(ret)goto uncertain;
    ret=read_reg(h,0xa4,&hi); if(ret)goto uncertain;
    ret=read_reg(h,0xa8,&v); if(ret)goto uncertain;
    ret=read_reg(h,24,&seq); if(ret)goto uncertain;
    if((lo|((as02_u64)hi<<32))!=p->epoch || v || seq!=words[0]) {ret=-EIO;goto uncertain;}
    ret=h->io->write32(h->context,0x14,words[0]); if(ret)goto uncertain;
    ret=read_reg(h,12,&status); if(ret)goto uncertain;
    ret=read_reg(h,24,&seq); if(ret)goto uncertain;
    if(status!=1 || seq!=words[0]) {ret=-EIO;goto uncertain;}
    h->pending=0; memset(&h->held,0,sizeof(h->held)); return 0;
uncertain:
    h->uncertain=1; return ret;
}
#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_retry_io_init);
EXPORT_SYMBOL_GPL(as02_retry_io_configure);
#endif
