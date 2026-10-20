/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include "rnic_io.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

static int status(struct as02_ctl *c, as02_u32 *s)
{
    int ret;
    if (c->detached)
        return -ENODEV;
    ret = c->io->read32(c->context, AS02_CTL_STATUS, s);
    if (ret)
        return ret;
    if ((*s & ~0xfffU) || (*s & (AS02_ST_FATAL | AS02_ST_MMIO_ERROR | AS02_ST_ENDPOINT_FAULT)))
        return -EIO;
    return 0;
}

int as02_ctl_init(struct as02_ctl *c, const struct as02_ctl_transport *io,
                   void *context, as02_u32 timeout)
{
    as02_u32 value, s;
    int ret;
    if (!c || !io || !io->read32 || !io->write32 || !io->time_us || !io->wait ||
        !timeout || timeout > 1000000)
        return -EINVAL;
    if (c->initialized)
        return c->detached ? -ENODEV : -EBUSY;
    memset(c, 0, sizeof(*c));
    c->io = io;
    c->context = context;
    c->timeout_us = timeout;
    ret = io->read32(context, AS02_CTL_ID, &value);
    if (ret || value != AS02_CTL_ID_VALUE)
        return ret ? ret : -ENODEV;
    ret = io->read32(context, AS02_CTL_ABI, &value);
    if (ret || value != AS02_CTL_ABI_VALUE)
        return ret ? ret : -EOPNOTSUPP;
    ret = io->read32(context, AS02_CTL_FEATURES, &value);
    if (ret || (value != 1 && value != (1|AS02_CTL_FEATURE_QP_TX) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND|AS02_CTL_FEATURE_RECV) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND|AS02_CTL_FEATURE_RECV|AS02_CTL_FEATURE_RNR) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND|AS02_CTL_FEATURE_RECV|AS02_CTL_FEATURE_RNR|AS02_CTL_FEATURE_RECV_RETIRE) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND|AS02_CTL_FEATURE_RECV|AS02_CTL_FEATURE_RNR|AS02_CTL_FEATURE_RECV_RETIRE|AS02_CTL_FEATURE_RECV_CQ) &&
                value != (1|AS02_CTL_FEATURE_QP_TX|AS02_CTL_FEATURE_SEND|AS02_CTL_FEATURE_RECV|AS02_CTL_FEATURE_RNR|AS02_CTL_FEATURE_RECV_RETIRE|AS02_CTL_FEATURE_RECV_CQ|AS02_CTL_FEATURE_REQUEST_CQ) &&
                value != (255U|AS02_CTL_FEATURE_SEPARATE_RQ) &&
                value != AS02_CTL_IMMEDIATE_NATIVE_FEATURES))
        return ret ? ret : -EOPNOTSUPP;
    c->features = value;
    ret = status(c, &s);
    if (ret)
        return ret;
    if ((s & (AS02_ST_READY | AS02_ST_PAUSED | AS02_ST_PARENT_DRAINED | AS02_ST_ENDPOINT_QUIET)) !=
        (AS02_ST_READY | AS02_ST_PAUSED | AS02_ST_PARENT_DRAINED | AS02_ST_ENDPOINT_QUIET) ||
        (s & (AS02_ST_BUSY | AS02_ST_REPLY | AS02_ST_EPOCH | AS02_ST_QP | AS02_ST_RUN)))
        return -EBUSY;
    /* Do not adopt an old driver's registrations, queues or reply sequence. */
    ret = io->read32(context, AS02_CTL_ENTRY_STATE, &value);
    if (ret || value)
        return ret ? ret : -EBUSY;
    ret = io->read32(context, AS02_CTL_LAST_QUEUED, &value);
    if (ret || value)
        return ret ? ret : -EBUSY;
    ret = io->read32(context, AS02_CTL_LAST_SEQUENCE, &value);
    if (ret || value)
        return ret ? ret : -EBUSY;
    c->initialized = 1;
    return 0;
}

static int valid_words(const struct as02_ctl *c, const as02_u32 *w)
{
    as02_u64 va = ((as02_u64)w[AS02_W_VA_HI] << 32) | w[AS02_W_VA_LO];
    as02_u32 op = w[AS02_W_OP], access = w[AS02_W_ACCESS];
    if (op < AS02_CMD_EPOCH || op > AS02_CMD_QP_TX ||
        !(w[AS02_W_COOKIE_LO] | w[AS02_W_COOKIE_HI]) || w[AS02_W_SLOT] >= 8 ||
        w[AS02_W_PD] > 65535 || access > 15 || w[AS02_W_FIRST] > 4095 ||
        w[AS02_W_PAGE_INDEX] > 255 || w[AS02_W_QP] > 7 || w[AS02_W_PEER_QP] > 0xffffff ||
        w[AS02_W_RX_PSN] > 0xffffff || w[AS02_W_TX_PSN] > 0xffffff)
        return -EINVAL;
    if (op == AS02_CMD_QP_TX) {
        if (!(c->features & AS02_CTL_FEATURE_QP_TX)) return -EOPNOTSUPP;
        if (!w[AS02_W_PD] || w[AS02_W_SLOT] || w[AS02_W_KEY] ||
            w[AS02_W_ACCESS] || w[AS02_W_VA_LO] || w[AS02_W_VA_HI] ||
            w[AS02_W_LENGTH] || w[AS02_W_FIRST] || w[AS02_W_PAGE_INDEX] ||
            w[AS02_W_DMA_LO] || w[AS02_W_DMA_HI] || w[AS02_W_PEER_QP] ||
            w[AS02_W_LOCAL_IP] || w[AS02_W_PEER_IP] || w[AS02_W_RX_PSN]) return -EINVAL;
    }
    if (op == AS02_CMD_BEGIN && (!w[AS02_W_LENGTH] ||
        w[AS02_W_LENGTH] > 1048576U-w[AS02_W_FIRST] || w[AS02_W_KEY] ||
        w[AS02_W_LENGTH]-1 > ~(as02_u64)0-va || ((access & 10) && !(access & 1))))
        return -EINVAL;
    if (op == AS02_CMD_PAGE && (w[AS02_W_DMA_LO] & 4095))
        return -EINVAL;
    if (op == AS02_CMD_EPOCH && w[AS02_W_KEY] >= AS02_MR_MAX_GENERATION)
        return -EINVAL;
    return 0;
}

static int check_reply(struct as02_ctl *c, struct as02_ctl_reply *r)
{
    as02_u32 values[8], i, key = c->expected[AS02_W_KEY], flags;
    const as02_u32 *w = c->expected;
    int ret;
    for (i = 0; i < 8; i++) {
        ret = c->io->read32(c->context, AS02_CTL_REPLY_SEQ+4*i, &values[i]);
        if (ret)
            return ret;
    }
    if (values[0] != w[AS02_W_SEQUENCE] || values[1] != w[AS02_W_OP] ||
        values[2] != w[AS02_W_COOKIE_LO] || values[3] != w[AS02_W_COOKIE_HI] ||
        values[4] != w[AS02_W_SLOT] || values[6] > 255 || values[7] > 31)
        return -EPROTO;
    if (values[6]) {
        if (values[7])
            return -EPROTO; /* Error is NEVER a release/publication proof. */
    } else {
        switch (w[AS02_W_OP]) {
        case AS02_CMD_EPOCH: flags = 14; break;
        case AS02_CMD_SEAL: flags = AS02_PROOF_PUBLISHED; break;
        case AS02_CMD_INVALIDATE: flags = 3; break;
        case AS02_CMD_STOP: flags = AS02_PROOF_DMA_DRAINED; key = 0; break;
        case AS02_CMD_QP:
        case AS02_CMD_QP_TX:
        case AS02_CMD_RUN: flags = 0; key = 0; break;
        default: flags = 0; break;
        }
        if (values[7] != flags)
            return -EPROTO;
        if (w[AS02_W_OP] == AS02_CMD_BEGIN) {
            if ((values[5] & 7) != w[AS02_W_SLOT] || !(values[5] >> 3))
                return -EPROTO;
        } else if (w[AS02_W_OP] == AS02_CMD_INVALIDATE) {
            if ((values[5] & 7) != w[AS02_W_SLOT] || (key && values[5] != key))
                return -EPROTO;
        } else if (values[5] != key) {
            return -EPROTO;
        }
    }
    r->sequence = values[0];r->command = values[1];r->cookie = ((as02_u64)values[3]<<32)|values[2];
    r->slot = values[4];r->key = values[5];r->error = values[6];r->flags = values[7];
    return 0;
}

int as02_ctl_reconcile(struct as02_ctl *c, struct as02_ctl_reply *out)
{
    as02_u64 start;
    as02_u32 s, seq;
    struct as02_ctl_reply r = {0};
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
    start = c->io->time_us(c->context);
    for (;;) {
        ret = status(c, &s);
        if (ret)
            return ret;
        if (s & AS02_ST_REPLY)
            break;
        if (c->io->time_us(c->context)-start >= c->timeout_us)
            return -ETIMEDOUT;
        c->io->wait(c->context);
    }
    ret = check_reply(c, &r);
    if (ret)
        return ret;
    /* Reply must still be owned and the device not faulted before ACK. */
    ret = status(c, &s);
    if (ret || !(s & AS02_ST_REPLY))
        return ret ? ret : -EPROTO;
    ret = c->io->read32(c->context, AS02_CTL_REPLY_SEQ, &seq);
    if (ret || seq != c->expected[AS02_W_SEQUENCE])
        return ret ? ret : -EPROTO;
    ret = c->io->write32(c->context, AS02_CTL_REPLY_ACK, seq);
    if (ret)
        return ret;
    start = c->io->time_us(c->context);
    for (;;) {
        ret = status(c, &s);
        if (ret)
            return ret;
        if ((s & AS02_ST_READY) && !(s & (AS02_ST_REPLY | AS02_ST_BUSY)))
            break;
        if (c->io->time_us(c->context)-start >= c->timeout_us)
            return -ETIMEDOUT;
        c->io->wait(c->context);
    }
    c->pending = 0;c->uncertain = 0;*out = r;
    return 0;
}

int as02_ctl_execute(struct as02_ctl *c, const as02_u32 *words, struct as02_ctl_reply *out)
{
    as02_u32 w[AS02_CTL_STAGE_WORDS], i, value, s;
    int ret;
    if (!out)
        return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!c || !c->initialized || !words)
        return -EINVAL;
    if (c->detached)
        return -ENODEV;
    if (c->pending || c->uncertain)
        return -EBUSY;
    ret = valid_words(c, words);
    if (ret)
        return ret;
    if (c->sequence == 0xffffffffU)
        return -ENOSPC;
    ret = status(c, &s);
    if (ret)
        return ret;
    if (!(s & AS02_ST_READY) || (s & (AS02_ST_REPLY | AS02_ST_BUSY)))
        return -EBUSY;
    memcpy(w, words, sizeof(w));w[AS02_W_SEQUENCE] = ++c->sequence;
    for (i = 0; i < AS02_CTL_STAGE_WORDS; i++) {
        ret = c->io->write32(c->context, AS02_CTL_STAGE+i*4, w[i]);
        if (ret)
            return ret; /* Staging cannot execute without the doorbell. */
    }
    for (i = 0; i < AS02_CTL_STAGE_WORDS; i++) {
        ret = c->io->read32(c->context, AS02_CTL_STAGE+i*4, &value);
        if (ret || value != w[i])
            return ret ? ret : -EIO;
    }
    memcpy(c->expected, w, sizeof(w));
    c->pending = 1;c->uncertain = 1; /* BEFORE an ambiguous posted doorbell. */
    ret = c->io->write32(c->context, AS02_CTL_DOORBELL, 1);
    if (ret)
        return ret;
    return as02_ctl_reconcile(c, out);
}

int as02_ctl_detach(struct as02_ctl *c)
{
    if (!c || !c->initialized)
        return -EINVAL;
    /* Preserve pending, uncertain, sequence and full expected owner. Do not
     * fabricate a drain/ACK or erase ambiguity when the device disappears.
     */
    c->detached = 1;
    return 0;
}
