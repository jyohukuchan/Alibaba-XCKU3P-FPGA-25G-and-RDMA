/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include "wqe.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

static void put_le(as02_byte *out, as02_u64 value, unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; i++)
        out[i] = (as02_byte)(value >> (8U * i));
}

static as02_u64 get_le(const as02_byte *in, unsigned int count)
{
    as02_u64 value = 0;
    unsigned int i;
    for (i = 0; i < count; i++)
        value |= (as02_u64)in[i] << (8U * i);
    return value;
}

int as02_wqe_validate_profile(const struct as02_wqe *w, as02_u32 profile)
{
    const as02_u64 max = ~(as02_u64)0;
    if (!w || !w->sequence || !w->epoch)
        return -EINVAL;
    if (profile & ~AS02_WQE_PROFILE_IMMEDIATE)
        return -EOPNOTSUPP;
    if (w->opcode != AS02_WQE_WRITE && w->opcode != AS02_WQE_READ &&
        w->opcode != AS02_WQE_SEND && w->opcode != AS02_WQE_RECV &&
        (!(profile & AS02_WQE_PROFILE_IMMEDIATE) ||
         (w->opcode != AS02_WQE_SEND_IMMEDIATE && w->opcode != AS02_WQE_WRITE_IMMEDIATE)))
        return -EOPNOTSUPP;
    if (w->immediate && (w->opcode != AS02_WQE_SEND_IMMEDIATE && w->opcode != AS02_WQE_WRITE_IMMEDIATE))
        return -EINVAL;
    /* SEND consumes a peer receive WQE and has no remote VA or rkey. */
    if ((w->opcode == AS02_WQE_SEND || w->opcode == AS02_WQE_RECV || w->opcode == AS02_WQE_SEND_IMMEDIATE) &&
        (w->remote_address || w->remote_key))
        return -EINVAL;
    if (w->opcode == AS02_WQE_RECV && w->flags != AS02_WQE_SIGNALED)
        return -EINVAL;
    if (w->flags & ~(as02_u32)AS02_WQE_SIGNALED)
        return -EOPNOTSUPP;
    if (!w->length || w->length > AS02_WQE_MAX_BYTES)
        return -EMSGSIZE;
    /* Last-byte checks allow exactly the top64-bit byte without an exclusive
     * end-address wrap. This does not replace MR/PD/access/range checking.
     */
    if (w->local_address > max - (w->length - 1U) ||
        w->remote_address > max - (w->length - 1U))
        return -EFAULT;
    return 0;
}

int as02_wqe_validate(const struct as02_wqe *w)
{ return as02_wqe_validate_profile(w, 0); }

int as02_wqe_encode_profile(as02_byte out[AS02_WQE_BYTES], const struct as02_wqe *input, as02_u32 profile)
{
    struct as02_wqe w;
    int ret;
    if (!out)
        return -EINVAL;
    if (!input) {
        memset(out, 0, AS02_WQE_BYTES);
        return -EINVAL;
    }
    w = *input;
    memset(out, 0, AS02_WQE_BYTES);
    ret = as02_wqe_validate_profile(&w, profile);
    if (ret)
        return ret;
    put_le(out, w.wr_id, 8);
    put_le(out + 8, w.sequence, 8);
    put_le(out + 16, w.local_address, 8);
    put_le(out + 24, w.remote_address, 8);
    put_le(out + 32, w.length, 4);
    put_le(out + 36, w.local_key, 4);
    put_le(out + 40, w.remote_key, 4);
    put_le(out + 44, w.opcode, 2);
    put_le(out + 46, w.flags, 2);
    put_le(out + 48, w.immediate, 4);
    put_le(out + 56, w.epoch, 8);
    return 0;
}

int as02_wqe_encode(as02_byte out[AS02_WQE_BYTES], const struct as02_wqe *input)
{ return as02_wqe_encode_profile(out, input, 0); }

int as02_wqe_decode_profile(struct as02_wqe *out, const as02_byte input[AS02_WQE_BYTES], as02_u32 profile)
{
    as02_byte bytes[AS02_WQE_BYTES];
    struct as02_wqe w;
    int ret;
    if (!out)
        return -EINVAL;
    if (!input) {
        memset(out, 0, sizeof(*out));
        return -EINVAL;
    }
    memcpy(bytes, input, sizeof(bytes));
    memset(out, 0, sizeof(*out));
    if (get_le(bytes + 52, 4) || (!(profile & AS02_WQE_PROFILE_IMMEDIATE) && get_le(bytes + 48, 4)))
        return -EINVAL;
    memset(&w, 0, sizeof(w));
    w.wr_id = get_le(bytes, 8);
    w.sequence = get_le(bytes + 8, 8);
    w.local_address = get_le(bytes + 16, 8);
    w.remote_address = get_le(bytes + 24, 8);
    w.length = (as02_u32)get_le(bytes + 32, 4);
    w.local_key = (as02_u32)get_le(bytes + 36, 4);
    w.remote_key = (as02_u32)get_le(bytes + 40, 4);
    w.opcode = (as02_u32)get_le(bytes + 44, 2);
    w.flags = (as02_u32)get_le(bytes + 46, 2);
    w.immediate = (as02_u32)get_le(bytes + 48, 4);
    w.epoch = get_le(bytes + 56, 8);
    ret = as02_wqe_validate_profile(&w, profile);
    if (ret)
        return ret;
    *out = w;
    return 0;
}

int as02_wqe_decode(struct as02_wqe *out, const as02_byte input[AS02_WQE_BYTES])
{ return as02_wqe_decode_profile(out, input, 0); }

#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_wqe_validate);
EXPORT_SYMBOL_GPL(as02_wqe_encode);
EXPORT_SYMBOL_GPL(as02_wqe_decode);
EXPORT_SYMBOL_GPL(as02_wqe_validate_profile);
EXPORT_SYMBOL_GPL(as02_wqe_encode_profile);
EXPORT_SYMBOL_GPL(as02_wqe_decode_profile);
#endif
