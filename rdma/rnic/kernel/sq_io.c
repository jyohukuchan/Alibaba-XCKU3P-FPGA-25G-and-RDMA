/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include "sq_io.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

static as02_u64 pair(const as02_u32 *w)
{
    return w[0] | ((as02_u64)w[1] << 32);
}
static int status(struct as02_sqc_io *c, as02_u32 *value)
{
    int ret;
    if (c->detached)
        return -ENODEV;
    ret = c->io->read32(c->context, AS02_SQC_STATUS, value);
    if (ret)
        return ret;
    if ((*value & ~0x3fU) || (*value & (AS02_SQC_FATAL|AS02_SQC_MMIO_ERROR|AS02_SQC_ENDPOINT_FAULT)))
        return -EIO;
    return 0;
}
static int valid_words(const as02_u32 *w)
{
    as02_u64 dma = pair(w+8), producer = pair(w+11), nonce = pair(w+13), bytes;
    if (w[1] < 1 || w[1] > 4 || w[2] >= 8 || w[3] > 65535 ||
        !pair(w+4) || !pair(w+6) || w[10] < 1 || w[10] > 8 || (dma & 63))
        return -EINVAL;
    bytes = 64ULL << w[10];
    if (bytes-1 > ~(as02_u64)0-dma)
        return -ERANGE;
    if ((w[1] == 1 && (producer || nonce)) || (w[1] == 2 && (!producer || nonce)) ||
        (w[1] >= 3 && !nonce))
        return -EINVAL;
    return 0;
}
int as02_sqc_io_init_id(struct as02_sqc_io *c, const struct as02_sqc_transport *io,
                     void *context, as02_u32 timeout_us, as02_u32 expected_id)
{
    as02_u32 v;
    int ret;
    if (!c || !io || !io->read32 || !io->write32 || !io->time_us || !io->relax ||
        !timeout_us || timeout_us > AS02_SQC_MAX_TIMEOUT_US ||
        (expected_id != AS02_SQC_ID_VALUE && expected_id != AS02_RQC_ID_VALUE))
        return -EINVAL;
    if (c->initialized || c->detached)
        return c->detached ? -ENODEV : -EBUSY;
    memset(c, 0, sizeof(*c));
    c->io = io;c->context = context;c->timeout_us = timeout_us;
    ret = io->read32(context, AS02_SQC_ID, &v);
    if (ret || v != expected_id)
        return ret ? ret : -ENODEV;
    ret = io->read32(context, AS02_SQC_ABI, &v);
    if (ret || v != AS02_SQC_ABI_VALUE)
        return ret ? ret : -EOPNOTSUPP;
    ret = io->read32(context, AS02_SQC_FEATURES, &v);
    if (ret || (v != 1 && !(expected_id == AS02_SQC_ID_VALUE && v == AS02_SQC_IMMEDIATE_FEATURE_VALUE) &&
        !(expected_id == AS02_RQC_ID_VALUE && (v == 3 || v == AS02_RQC_IMMEDIATE_FEATURE_VALUE))))
        return ret ? ret : -EOPNOTSUPP;
    c->features=v;
    ret = status(c, &v);
    if (ret || v != AS02_SQC_AVAILABLE)
        return ret ? ret : -EBUSY;
    ret = io->read32(context, AS02_SQC_LAST_SEQUENCE, &v);
    if (ret || v)
        return ret ? ret : -EBUSY;
    c->initialized = 1;
    return 0;
}
int as02_sqc_io_init(struct as02_sqc_io *c, const struct as02_sqc_transport *io,
                     void *context, as02_u32 timeout_us)
{ return as02_sqc_io_init_id(c, io, context, timeout_us, AS02_SQC_ID_VALUE); }

static int poll(struct as02_sqc_io *c, int reply, as02_u64 start)
{
    as02_u32 n, v;
    int ret;
    for (n = 0; n < AS02_SQC_MAX_POLLS; n++) {
        ret = status(c, &v);
        if (ret)
            return ret;
        if (reply ? !!(v & AS02_SQC_RESPONSE) :
            (!(v & AS02_SQC_RESPONSE) && !!(v & (AS02_SQC_AVAILABLE|AS02_SQC_EXHAUSTED))))
            return 0;
        if (c->io->time_us(c->context)-start >= c->timeout_us)
            return -ETIMEDOUT;
        c->io->relax(c->context);
    }
    return -ETIMEDOUT;
}
static int known_error(as02_u32 error)
{
    switch (error) {
    case 0:case 16:case 17:case 18:case 19:case 20:case 21:case 22:
    case 32:case 33:case 34:case 35:case 36:
        return 1;
    default:
        return 0;
    }
}
static int check_reply(struct as02_sqc_io *c, struct as02_sqc_reply *r)
{
    as02_u32 n, v, lo, hi, wanted;
    int ret;
    for (n = 0; n < AS02_SQC_WORDS; n++) {
        ret = c->io->read32(c->context, AS02_SQC_REPLY+n*4, &v);
        if (ret || v != c->expected[n])
            return ret ? ret : -EPROTO;
        r->words[n] = v;
    }
    ret = c->io->read32(c->context, AS02_SQC_REPLY_ERROR, &r->error);
    if (ret || !known_error(r->error))
        return ret ? ret : -EPROTO;
    ret = c->io->read32(c->context, AS02_SQC_REPLY_FLAGS, &r->flags);
    if (ret)
        return ret;
    ret = c->io->read32(c->context, AS02_SQC_REPLY_CONSUMER_LO, &lo);
    if (ret)
        return ret;
    ret = c->io->read32(c->context, AS02_SQC_REPLY_CONSUMER_HI, &hi);
    if (ret)
        return ret;
    r->consumer = lo | ((as02_u64)hi << 32);
    wanted = r->error ? 0 : (r->words[1] == 1 ? AS02_SQC_ALLOC_FLAGS :
                            r->words[1] == 3 ? AS02_SQC_RETIRE_FLAGS :
                            r->words[1] == 4 ? AS02_RQC_CANCEL_FLAGS : 0);
    if (r->flags != wanted)
        return -EPROTO;
    if (!r->error && ((r->words[1] == 1 && r->consumer) ||
        (r->words[1] == 2 && r->consumer > pair(r->words+11)) ||
        (r->words[1] >= 3 && r->consumer != pair(r->words+11))))
        return -EPROTO;
    return 0;
}
int as02_sqc_io_reconcile(struct as02_sqc_io *c, struct as02_sqc_reply *out)
{
    struct as02_sqc_reply r = {0};
    as02_u64 start;
    as02_u32 v;
    int ret;
    if (!out)
        return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!c || !c->initialized)
        return -EINVAL;
    if (c->detached)
        return -ENODEV;
    if (!c->pending)
        return -EINVAL;
    c->uncertain = 1;
    start = c->io->time_us(c->context);
    ret = poll(c, 1, start);
    if (ret)
        return ret;
    ret = check_reply(c, &r);
    if (ret)
        return ret;
    ret = status(c, &v);
    if (ret || !(v & AS02_SQC_RESPONSE))
        return ret ? ret : -EPROTO;
    ret = c->io->read32(c->context, AS02_SQC_REPLY, &v);
    if (ret || v != c->expected[0])
        return ret ? ret : -EPROTO;
    ret = c->io->read32(c->context, AS02_SQC_LAST_SEQUENCE, &v);
    if (ret || v != c->expected[0])
        return ret ? ret : -EPROTO;
    ret = c->io->write32(c->context, AS02_SQC_REPLY_ACK, c->expected[0]);
    if (ret)
        return ret;
    ret = poll(c, 0, start);
    if (ret)
        return ret;
    ret = c->io->read32(c->context, AS02_SQC_LAST_SEQUENCE, &v);
    if (ret || v != c->expected[0])
        return ret ? ret : -EPROTO;
    c->pending = 0;c->uncertain = 0;*out = r;
    return 0;
}
int as02_sqc_io_execute(struct as02_sqc_io *c, const as02_u32 words[AS02_SQC_WORDS], struct as02_sqc_reply *out)
{
    as02_u32 w[AS02_SQC_WORDS], n, v;
    int ret;
    if (!out)
        return -EINVAL;
    /* Copy before output clearing for explicitly overlapping metadata buffers. */
    if (words)
        memcpy(w, words, sizeof(w));
    memset(out, 0, sizeof(*out));
    if (!c || !c->initialized || !words)
        return -EINVAL;
    if (c->detached)
        return -ENODEV;
    if (c->pending || c->uncertain)
        return -EBUSY;
    ret = valid_words(w);
    if (ret)
        return ret;
    if(w[1]==4 && !(c->features&AS02_RQC_CANCEL_FEATURE))return -EOPNOTSUPP;
    if (c->sequence == 0xffffffffU)
        return -ENOSPC;
    ret = status(c, &v);
    if (ret)
        return ret;
    if (v != AS02_SQC_AVAILABLE)
        return -EBUSY;
    ret = c->io->read32(c->context, AS02_SQC_LAST_SEQUENCE, &v);
    if (ret || v != c->sequence) {
        c->uncertain = 1;
        return ret ? ret : -EPROTO;
    }
    w[0] = c->sequence+1;
    for (n = 0; n < AS02_SQC_WORDS; n++) {
        ret = c->io->write32(c->context, AS02_SQC_STAGE+n*4, w[n]);
        if (ret)
            return ret;
    }
    for (n = 0; n < AS02_SQC_WORDS; n++) {
        ret = c->io->read32(c->context, AS02_SQC_STAGE+n*4, &v);
        if (ret || v != w[n])
            return ret ? ret : -EIO;
    }
    memcpy(c->expected, w, sizeof(w));
    c->sequence = w[0];c->pending = 1;c->uncertain = 1;
    ret = c->io->write32(c->context, AS02_SQC_DOORBELL, w[0]);
    if (ret)
        return ret;
    return as02_sqc_io_reconcile(c, out);
}
int as02_sqc_io_detach(struct as02_sqc_io *c)
{
    if (!c || !c->initialized)
        return -EINVAL;
    c->detached = 1;
    return 0;
}
