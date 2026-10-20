/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_CQ_HW_H
#define AS02_CQ_HW_H
#include <linux/io.h>
#include <linux/spinlock.h>
#include <linux/atomic.h>
#include <linux/workqueue.h>
#include "cq_io.h"
#include "sq.h"

/* Actual CQC1 MMIO -> complete full native WR -> real CQ callback/MR refs.
 * Lock order: CQ-MMIO -> SQ-fast -> SQC-fast -> CQ-router -> software-CQ.
 * poll_cq must pump this transport BEFORE acquiring its CQ ring lock.
 * This code does not bind/probe/load a device or manufacture a drain proof.
 */
struct as02_cq_hw {
    spinlock_t lock;
    void __iomem *registers;
    struct as02_sq_pool *pool;
    struct as02_cq_io control;
    unsigned int cq_clients;
    atomic_t notify_users;
    struct delayed_work poll_work;
};
int as02_cq_hw_init(struct as02_cq_hw *, struct as02_sq_pool *, void __iomem *, size_t);
int as02_cq_hw_poll(void *);
/* Requires closed SQs and the caller's stable device/execution lifetime.
 * Busy/uncertain retains the client and context, never releases DMA/umem.
 */
int as02_cq_hw_detach(struct as02_cq_hw *);
int as02_cq_hw_get_client(struct as02_cq_hw *);
int as02_cq_hw_put_client(struct as02_cq_hw *);
/* One-shot CQ notification needs progress even when the application is not
 * polling. These are atomic/non-sleeping; called under the software CQ lock.
 * The work item polls one actual event per tick, not a busy-wait or fake IRQ.
 */
void as02_cq_hw_arm(struct as02_cq_hw *);
void as02_cq_hw_disarm(struct as02_cq_hw *);
#endif
