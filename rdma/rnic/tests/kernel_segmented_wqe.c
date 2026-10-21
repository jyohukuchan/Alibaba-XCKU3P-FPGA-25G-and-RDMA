/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real adapters/codecs, explicit modeled Linux WR types. Not actual posting. */
#include "kernel_atomic128_model.h"
#include "verbs_segmented_wqe.h"
#include "atomic_profile.h"

static void check_zero(const unsigned char *out)
{
    unsigned int i;
    for (i = 0; i < 128; i++) assert(!out[i]);
}

static void compare_expected(const unsigned char *out, const struct as02_atomic_wqe *w)
{
    /* Independent canonical C128 byte layout, not the encoder under test. */
    unsigned char expected[128] = {};
    unsigned int i;
    const u64 values[] = {w->base.wr_id, w->base.local_address, w->base.remote_address,
                          w->base.sequence, w->base.epoch, w->compare, w->swap_add};
    const unsigned int offsets[] = {0, 16, 24, 8, 56, 64, 72};
    for (i = 0; i < 7; i++) {
        unsigned int j;
        for (j = 0; j < 8; j++) expected[offsets[i]+j] = values[i] >> (j*8);
    }
    for (i = 0; i < 4; i++) {
        expected[32+i] = w->base.length >> (i*8);
        expected[36+i] = w->base.local_key >> (i*8);
        expected[40+i] = w->base.remote_key >> (i*8);
        expected[48+i] = w->base.immediate >> (i*8);
    }
    expected[44] = w->base.opcode; expected[45] = w->base.opcode >> 8;
    expected[46] = w->base.flags; expected[47] = w->base.flags >> 8;
    assert(!memcmp(out, expected, sizeof(expected)));
}

int main(void)
{
    const u32 lengths[] = {4097, 8193, 65537, 1048576};
    const u32 keys[] = {0, 0x80000008U, 0xffffffffU};
    struct ib_send_wr *send = malloc(sizeof(*send)); /* ASan guards true base-only SEND. */
    struct ib_sge sge = {.addr = 0xfedcba9876543210ULL};
    struct ib_rdma_wr rdma = {.remote_addr = 0xe23456789abcdef0ULL, .rkey = 0xffffffffU};
    struct ib_atomic_wr atomic = {.remote_addr = 0xe23456789abcdef0ULL, .rkey = 0x81234567,
                                  .compare_add = 0x8000000000000001ULL, .swap = 0xffffffffffffffffULL};
    struct as02_atomic_wqe expected = {};
    unsigned char out[128], legacy[128];
    unsigned int op, len, key, signaled, cases = 0, negative = 0;
    assert(send);
    for (op = 0; op < 2; op++) for (len = 0; len < 4; len++)
    for (key = 0; key < 3; key++) for (signaled = 0; signaled < 2; signaled++) {
        struct ib_send_wr *wr = op ? &rdma.wr : send;
        *wr = (struct ib_send_wr){.wr_id = 0xf123456789abc001ULL, .sg_list = &sge, .num_sge = 1,
                                  .opcode = op ? IB_WR_RDMA_WRITE : IB_WR_SEND,
                                  .send_flags = signaled ? IB_SEND_SIGNALED : 0};
        sge.length = lengths[len]; sge.lkey = keys[key];
        expected.base = (struct as02_wqe){.wr_id = wr->wr_id, .sequence = 0xfedcba9876543210ULL,
            .epoch = 0x9123456700000001ULL, .local_address = sge.addr, .local_key = sge.lkey,
            .length = sge.length, .remote_address = op ? rdma.remote_addr : 0,
            .remote_key = op ? rdma.rkey : 0, .opcode = op ? AS02_WQE_WRITE : AS02_WQE_SEND,
            .flags = signaled ? AS02_WQE_SIGNALED : 0};
        memset(out, 0xa5, sizeof(out));
        assert(!as02_segmented_wqe_from_ib_send_wr(out, wr, expected.base.sequence, expected.base.epoch));
        compare_expected(out, &expected);
        memset(legacy, 0xa5, sizeof(legacy));
        assert(as02_zero_wqe_from_ib_send_wr(legacy, wr, expected.base.sequence, expected.base.epoch) == -EMSGSIZE);
        check_zero(legacy); cases++;
    }
    for (len = 0; len < 2; len++) {
        sge.length = 8193; sge.addr = len ? ~0ULL-8191 : ~0ULL-8192;
        rdma.wr = (struct ib_send_wr){.sg_list = &sge, .num_sge = 1, .opcode = IB_WR_RDMA_WRITE};
        assert(as02_segmented_wqe_from_ib_send_wr(out, &rdma.wr, 1, 1) == (len ? -EFAULT : 0));
        if (len) {check_zero(out); negative++;}
    }
    sge.addr = 0x1000;
    for (len = 0; len < 2; len++) {
        rdma.remote_addr = len ? ~0ULL-8191 : ~0ULL-8192;
        assert(as02_segmented_wqe_from_ib_send_wr(out, &rdma.wr, 1, 1) == (len ? -EFAULT : 0));
        if (len) {check_zero(out); negative++;}
    }
    rdma.remote_addr = 0x2000;
    for (op = 0; op < 8; op++) {
        int error;
        rdma.wr = (struct ib_send_wr){.sg_list = &sge, .num_sge = 1, .opcode = IB_WR_RDMA_WRITE};
        sge.length = 8193;
        switch (op) {
        case 0: sge.length = 1048577; error = -EMSGSIZE; break;
        case 1: rdma.wr.send_flags = IB_SEND_SIGNALED | 0x80000000U; error = -EOPNOTSUPP; break;
        case 2: rdma.wr.num_sge = 2; error = -EOPNOTSUPP; break;
        case 3: rdma.wr.num_sge = -1; error = -EOPNOTSUPP; break;
        case 4: rdma.wr.sg_list = NULL; error = -EOPNOTSUPP; break;
        case 5: rdma.wr.opcode = IB_WR_RDMA_READ; error = -EMSGSIZE; break;
        case 6: rdma.wr.opcode = IB_WR_RDMA_WRITE_WITH_IMM; error = -EMSGSIZE; break;
        default: rdma.wr.opcode = IB_WR_SEND_WITH_IMM; error = -EMSGSIZE; break;
        }
        memset(out, 0xa5, sizeof(out));
        assert(as02_segmented_wqe_from_ib_send_wr(out, &rdma.wr, 1, 1) == error);
        check_zero(out); negative++;
    }
    *send = (struct ib_send_wr){.sg_list = &sge, .num_sge = 1, .opcode = IB_WR_SEND};
    sge.length = 8193;
    assert(as02_segmented_wqe_from_ib_send_wr(out, send, 0, 1) == -EINVAL); check_zero(out); negative++;
    assert(as02_segmented_wqe_from_ib_send_wr(out, send, 1, 0) == -EINVAL); check_zero(out); negative++;
    assert(as02_segmented_wqe_from_ib_send_wr(out, NULL, 1, 1) == -EINVAL); check_zero(out); negative++;
    assert(as02_segmented_wqe_from_ib_send_wr(NULL, send, 1, 1) == -EINVAL); negative++;
    /* Zero num_sge ignores an invalid unused SGE pointer; old semantics stay. */
    send->num_sge = 0; send->sg_list = (void *)1;
    assert(!as02_segmented_wqe_from_ib_send_wr(out, send, 1, 1));
    assert(!as02_zero_wqe_from_ib_send_wr(legacy, send, 1, 1)); assert(!memcmp(out, legacy, 128)); cases++;
    send->num_sge = 1; send->sg_list = &sge;
    for (len = 0; len < 3; len++) {
        sge.length = len == 0 ? 0 : len == 1 ? 65 : 4096;
        assert(!as02_segmented_wqe_from_ib_send_wr(out, send, 1, 1));
        assert(!as02_zero_wqe_from_ib_send_wr(legacy, send, 1, 1)); assert(!memcmp(out, legacy, 128)); cases++;
    }
    atomic.wr = (struct ib_send_wr){.sg_list = &sge, .num_sge = 1, .opcode = IB_WR_ATOMIC_CMP_AND_SWP};
    sge.length = 8; sge.addr = 0x1000;
    for (op = 0; op < 2; op++) {
        atomic.wr.opcode = op ? IB_WR_ATOMIC_FETCH_AND_ADD : IB_WR_ATOMIC_CMP_AND_SWP;
        assert(!as02_segmented_wqe_from_ib_send_wr(out, &atomic.wr, 1, 1));
        assert(!as02_zero_wqe_from_ib_send_wr(legacy, &atomic.wr, 1, 1)); assert(!memcmp(out, legacy, 128)); cases++;
    }
    free(send);
    printf("SEGMENTED_VERBS_ADAPTER {\"pass_test\":true,\"positive_cases\":%u,\"negative_cases\":%u,\"base_SEND_ASan_guarded\":true,\"Linux_WR_types_modeled\":true,\"actual_posting\":false}\n", cases, negative);
    return 0;
}
