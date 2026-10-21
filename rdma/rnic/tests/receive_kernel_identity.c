/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual IO C and CQ metadata validator; CSR reads are explicit models. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "sq_io.h"
#include "cq_io.h"
static unsigned int id,feature,descriptor,owner_bits,operand_base;
static int sq_read(void *ctx,as02_u32 off,as02_u32 *v)
{
    (void)ctx;*v=0;
    switch(off){
    case AS02_SQC_ID:*v=id;break;case AS02_SQC_ABI:*v=AS02_SQC_ABI_VALUE;break;
    case AS02_SQC_FEATURES:*v=feature;break;case AS02_SQC_DESCRIPTOR_BYTES:*v=descriptor;break;
    case AS02_SQC_STATUS:*v=AS02_SQC_AVAILABLE;break;case AS02_SQC_LAST_SEQUENCE:break;
    default:assert(0);
    }
    return 0;
}
static int cq_read(void *ctx,as02_u32 off,as02_u32 *v)
{
    (void)ctx;*v=0;
    switch(off){
    case AS02_CQC_ID:*v=AS02_CQC_ID_VALUE;break;case AS02_CQC_ABI:*v=AS02_CQC_ABI_VALUE;break;
    case AS02_CQC_FEATURES:*v=feature;break;case AS02_CQC_OWNER_BITS:*v=owner_bits;break;
    case AS02_CQC_OPERAND_BASE:*v=operand_base;break;
    case AS02_CQC_STATUS:case AS02_CQC_SEQUENCE:case AS02_CQC_LAST_ACK:break;
    default:assert(0);
    }
    return 0;
}
static int write_reg(void *c,as02_u32 o,as02_u32 v){(void)c;(void)o;(void)v;assert(0);return -EIO;}
static as02_u64 now(void *c){(void)c;return 0;}
static void relax(void *c){(void)c;assert(0);}
int main(void)
{
    const struct as02_sqc_transport sqio={.read32=sq_read,.write32=write_reg,.time_us=now,.relax=relax};
    const struct as02_cq_transport cqio={.read32=cq_read,.write32=write_reg};
    unsigned int direction,g,extra,cases=0;
    for(direction=0;direction<2;direction++)for(feature=0;feature<64;feature++)for(g=0;g<3;g++){
        struct as02_sqc_io io={};int allowed,wide,expected;
        id=direction ? AS02_RQC_ID_VALUE:AS02_SQC_ID_VALUE;descriptor=g==0 ? 64:g==1 ? 128:256;
        allowed=direction ? feature==1 || feature==3 || feature==7 || feature==15 || feature==31:
            feature==1 || feature==5 || feature==13;
        wide=direction ? feature==15 || feature==31:feature==13;
        expected=allowed && (!wide || descriptor==128) ? 0:-EOPNOTSUPP;
        assert(as02_sqc_io_init_id(&io,&sqio,NULL,30,id)==expected);
        if(!expected)assert(io.features==feature && io.descriptor_bytes==(wide ? 128:64));
        cases++;
    }
    for(feature=0;feature<512;feature++)for(g=0;g<2;g++)for(extra=0;extra<2;extra++){
        struct as02_cq_io io={};int allowed,wide,expected;
        owner_bits=g ? 620:748;operand_base=extra ? 0xa4:0xa0;
        allowed=feature==1 || feature==3 || feature==7 || feature==15 || feature==31 || feature==63 || feature==127 || feature==255;
        wide=feature==15 || feature==31 || feature==63 || feature==127 || feature==255;
        expected=!allowed ? -ENODEV:wide && (g || extra) ? -EOPNOTSUPP:0;
        assert(as02_cq_io_init(&io,&cqio,NULL)==expected);
        if(!expected)assert(io.features==feature);
        cases++;
    }
    for(direction=0;direction<2;direction++){
        struct as02_cq_decoded d={.profile=direction ? 7:6,.work={.opcode=4,.length=8194},.received_bytes=8193};
        assert(as02_cq_notification_valid(&d)==(int)direction);cases++;
        d.notification_flags=1;d.notification=0x89abcdefU;
        assert(as02_cq_notification_valid(&d)==(int)direction);cases++;
        d.notification_flags=3;assert(!as02_cq_notification_valid(&d));cases++;
        d.received_bytes=4096;assert(as02_cq_notification_valid(&d));cases++;
        d.notification_flags=0;d.notification=0;d.received_bytes=8195;
        assert(!as02_cq_notification_valid(&d));cases++;
    }
    printf("RECEIVE_KERNEL_IDENTITY {\"pass_test\":true,\"cases\":%u,\"actual_IO_C\":true,\"CSR_reads_modeled\":true,\"no_native_or_Linux_or_physical_proof\":true}\n",cases);
    return 0;
}
