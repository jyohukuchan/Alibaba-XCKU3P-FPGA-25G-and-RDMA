/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Private full-range codec. No installed/default capability is changed. */
#include "wqe_segmented.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

int as02_segmented_wqe_validate(const struct as02_atomic_wqe *input)
{
    const as02_u64 max=~(as02_u64)0;
    struct as02_atomic_wqe w;
    if(!input)return -EINVAL;
    w=*input;
    if(w.base.length<=AS02_WQE_MAX_BYTES)return as02_zero_wqe_validate(&w);
    if(w.base.opcode!=AS02_WQE_WRITE && w.base.opcode!=AS02_WQE_SEND)return -EMSGSIZE;
    if(w.base.length>AS02_SEGMENTED_WQE_MAX_BYTES)return -EMSGSIZE;
    /* Check the REAL full range before any local serialization surrogate.
     * This does not manufacture an MR grant, offset, PD or DMA mapping. */
    if(w.base.local_address>max-(w.base.length-1U) ||
       w.base.remote_address>max-(w.base.length-1U))return -EFAULT;
    w.base.length=1;
    return as02_zero_wqe_validate(&w);
}

int as02_segmented_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct as02_atomic_wqe *input)
{
    struct as02_atomic_wqe w;
    as02_u32 length;
    unsigned int i;
    int ret;
    if(!out)return -EINVAL;
    if(!input){memset(out,0,AS02_ATOMIC_WQE_BYTES);return -EINVAL;}
    w=*input;memset(out,0,AS02_ATOMIC_WQE_BYTES);
    ret=as02_segmented_wqe_validate(&w);if(ret)return ret;
    length=w.base.length;
    if(length>AS02_WQE_MAX_BYTES)w.base.length=1;
    /* Reuse byte serialization ONLY after actual whole-range validation. */
    ret=as02_zero_wqe_encode(out,&w);if(ret)return ret;
    for(i=0;i<4;i++)out[32+i]=(as02_byte)(length>>(8U*i));
    return 0;
}

int as02_segmented_wqe_decode(struct as02_atomic_wqe *out,const as02_byte input[AS02_ATOMIC_WQE_BYTES])
{
    as02_byte bytes[AS02_ATOMIC_WQE_BYTES];
    struct as02_atomic_wqe w;
    as02_u32 length=0;
    unsigned int i;
    int ret;
    if(!out)return -EINVAL;
    if(!input){memset(out,0,sizeof(*out));return -EINVAL;}
    memcpy(bytes,input,sizeof(bytes));memset(out,0,sizeof(*out));
    for(i=0;i<4;i++)length|=(as02_u32)bytes[32+i]<<(8U*i);
    if(length>AS02_WQE_MAX_BYTES){memset(bytes+32,0,4);bytes[32]=1;}
    ret=as02_zero_wqe_decode(&w,bytes);if(ret)return ret;
    w.base.length=length;
    ret=as02_segmented_wqe_validate(&w);if(ret)return ret;
    *out=w;return 0;
}
