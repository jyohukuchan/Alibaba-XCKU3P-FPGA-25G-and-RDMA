/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_RNIC_HW_H
#define AS02_RNIC_HW_H
#include <linux/io.h>
#include <linux/mutex.h>
#include "mr.h"
#include "rnic_io.h"
struct as02_rnic_hw {
    struct mutex lock;
    void __iomem *registers;
    struct as02_ctl control;
};
/* A future actual bus driver maps the NEW identified control region. This
 * does not map/probe/bind the old running ROC2 application or load a driver.
 */
int as02_rnic_hw_init(struct as02_rnic_hw *, void __iomem *, size_t, u32);
int as02_rnic_hw_reconcile(struct as02_rnic_hw *, struct as02_ctl_reply *);
/* Future bus removal must stop new users, serialize this detach BEFORE BAR
 * unmap, and RETAIN the hw/pool/context/page/device/module objects when DMA
 * ownership is unknown. This closes MMIO; it does NOT release/unpin anything.
 */
int as02_rnic_hw_detach(struct as02_rnic_hw *);
extern const struct as02_mr_hw_ops as02_rnic_mr_hw_ops;
#endif
