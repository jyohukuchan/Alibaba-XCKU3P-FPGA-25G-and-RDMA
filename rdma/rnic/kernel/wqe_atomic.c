/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include "wqe_atomic.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

static int atomic_opcode(as02_u32 op)
{ return op == AS02_WQE_COMPARE_SWAP || op == AS02_WQE_FETCH_ADD; }

static void put64(as02_byte *out, as02_u64 value)
{
    unsigned int i;
    for (i = 0; i < 8; i++) out[i] = (as02_byte)(value >> (8U * i));
}

static as02_u64 get64(const as02_byte *in)
{
    as02_u64 value = 0;
    unsigned int i;
    for (i = 0; i < 8; i++) value |= (as02_u64)in[i] << (8U * i);
    return value;
}

int as02_atomic_wqe_validate(const struct as02_atomic_wqe *w)
{
    struct as02_wqe base;
    if (!w) return -EINVAL;
    base = w->base;
    if (!atomic_opcode(base.opcode)) {
        if (w->compare || w->swap_add) return -EINVAL;
        return as02_wqe_validate_profile(&base, AS02_WQE_PROFILE_IMMEDIATE);
    }
    if (base.immediate || (base.opcode == AS02_WQE_FETCH_ADD && w->compare)) return -EINVAL;
    if (base.length != 8) return -EMSGSIZE;
    if (base.remote_address & 7U) return -EINVAL;
    /* Apply the exact existing full-width sequence/epoch/flags/range checks.
     * READ is only a validation surrogate; the emitted opcode is7/8 and the
     * OLD64-byte API never gains Atomic authorization from this code. */
    base.opcode = AS02_WQE_READ;
    return as02_wqe_validate_profile(&base, AS02_WQE_PROFILE_IMMEDIATE);
}

int as02_atomic_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES], const struct as02_atomic_wqe *input)
{
    struct as02_atomic_wqe w;
    struct as02_wqe base;
    int ret;
    if (!out) return -EINVAL;
    if (!input) { memset(out, 0, AS02_ATOMIC_WQE_BYTES); return -EINVAL; }
    w = *input;
    memset(out, 0, AS02_ATOMIC_WQE_BYTES);
    ret = as02_atomic_wqe_validate(&w);
    if (ret) return ret;
    base = w.base;
    if (atomic_opcode(base.opcode)) base.opcode = AS02_WQE_READ;
    ret = as02_wqe_encode_profile(out, &base, AS02_WQE_PROFILE_IMMEDIATE);
    if (ret) return ret;
    out[44] = (as02_byte)w.base.opcode;
    out[45] = (as02_byte)(w.base.opcode >> 8U);
    put64(out + 64, w.compare);
    put64(out + 72, w.swap_add);
    return 0;
}

int as02_atomic_wqe_decode(struct as02_atomic_wqe *out, const as02_byte input[AS02_ATOMIC_WQE_BYTES])
{
    as02_byte bytes[AS02_ATOMIC_WQE_BYTES];
    struct as02_atomic_wqe w;
    as02_u32 opcode;
    unsigned int i;
    int ret;
    if (!out) return -EINVAL;
    if (!input) { memset(out, 0, sizeof(*out)); return -EINVAL; }
    memcpy(bytes, input, sizeof(bytes));
    memset(out, 0, sizeof(*out));
    for (i = 80; i < sizeof(bytes); i++) if (bytes[i]) return -EINVAL;
    opcode = (as02_u32)bytes[44] | ((as02_u32)bytes[45] << 8U);
    if (atomic_opcode(opcode)) { bytes[44] = AS02_WQE_READ; bytes[45] = 0; }
    memset(&w, 0, sizeof(w));
    ret = as02_wqe_decode_profile(&w.base, bytes, AS02_WQE_PROFILE_IMMEDIATE);
    if (ret) return ret;
    w.base.opcode = opcode;
    w.compare = get64(bytes + 64);
    w.swap_add = get64(bytes + 72);
    ret = as02_atomic_wqe_validate(&w);
    if (ret) return ret;
    *out = w;
    return 0;
}

#ifdef __KERNEL__
EXPORT_SYMBOL_GPL(as02_atomic_wqe_validate);
EXPORT_SYMBOL_GPL(as02_atomic_wqe_encode);
EXPORT_SYMBOL_GPL(as02_atomic_wqe_decode);
#endif
