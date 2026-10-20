/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Zero-length normal WQEs have NO local MR/address or data DMA authority.
 * Full QP/PD/sequence/epoch ownership and real wire/CQ proof are still needed.
 * Remote VA/rkey are exact wire fields but not dereferenced for zero bytes.
 */
#include "wqe_zero.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

int as02_zero_wqe_validate(const struct as02_atomic_wqe *w)
{
    const struct as02_wqe *b;
    if(!w)return -EINVAL;
    b=&w->base;
    if(b->length)return as02_atomic_wqe_validate(w);
    if(b->opcode==7 || b->opcode==8)return -EMSGSIZE;
    if(b->opcode<1 || b->opcode>6)return -EOPNOTSUPP;
    if(!b->sequence || !b->epoch || b->local_address || b->local_key || w->compare || w->swap_add)return -EINVAL;
    if(b->flags&~AS02_WQE_SIGNALED)return -EOPNOTSUPP;
    if(b->opcode==AS02_WQE_RECV && b->flags!=AS02_WQE_SIGNALED)return -EINVAL;
    if(b->opcode!=AS02_WQE_SEND_IMMEDIATE && b->opcode!=AS02_WQE_WRITE_IMMEDIATE && b->immediate)return -EINVAL;
    if((b->opcode==AS02_WQE_SEND || b->opcode==AS02_WQE_RECV || b->opcode==AS02_WQE_SEND_IMMEDIATE) &&
       (b->remote_address || b->remote_key))return -EINVAL;
    return 0;
}
int as02_zero_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct as02_atomic_wqe *input)
{
    struct as02_atomic_wqe w;int ret;int zero;
    if(!out)return -EINVAL;
    if(!input){memset(out,0,AS02_ATOMIC_WQE_BYTES);return -EINVAL;}
    w=*input;memset(out,0,AS02_ATOMIC_WQE_BYTES);
    ret=as02_zero_wqe_validate(&w);if(ret)return ret;
    zero=!w.base.length;
    /* Reuse ONLY existing byte serialization after full zero-aware shape
     * validation. This local codec surrogate grants no MR/DMA permission. */
    if(zero)w.base.length=1;
    ret=as02_atomic_wqe_encode(out,&w);
    if(!ret && zero)memset(out+32,0,4);
    return ret;
}
int as02_zero_wqe_decode(struct as02_atomic_wqe *out,const as02_byte input[AS02_ATOMIC_WQE_BYTES])
{
    as02_byte bytes[AS02_ATOMIC_WQE_BYTES];struct as02_atomic_wqe w;int ret,zero;
    if(!out)return -EINVAL;
    if(!input){memset(out,0,sizeof(*out));return -EINVAL;}
    memcpy(bytes,input,sizeof(bytes));memset(out,0,sizeof(*out));
    zero=!(bytes[32]||bytes[33]||bytes[34]||bytes[35]);
    if(zero)bytes[32]=1;
    ret=as02_atomic_wqe_decode(&w,bytes);if(ret)return ret;
    if(zero)w.base.length=0;
    ret=as02_zero_wqe_validate(&w);if(ret)return ret;
    *out=w;return 0;
}
#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_zero_wqe_validate);
EXPORT_SYMBOL_GPL(as02_zero_wqe_encode);
EXPORT_SYMBOL_GPL(as02_zero_wqe_decode);
#endif
