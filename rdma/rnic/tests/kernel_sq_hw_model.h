/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* EXPLICIT userspace MMIO/time/CQ kernel-primitive MODEL, not native Linux IO. */
#ifndef AS02_KERNEL_SQ_HW_MODEL_H
#define AS02_KERNEL_SQ_HW_MODEL_H
#include "kernel_queue_model.h"
#define __iomem
#define lockdep_assert_held(s) do { (void)(s);assert(km_spin_depth); } while(0)
typedef u64 ktime_t;
u32 readl(const volatile void *);
void writel(u32,volatile void *);
ktime_t ktime_get(void);
static inline u64 ktime_to_us(ktime_t n) { return n; }
void cpu_relax(void);
#endif
