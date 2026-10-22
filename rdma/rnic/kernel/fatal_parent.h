/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_FATAL_PARENT_H
#define AS02_FATAL_PARENT_H
#include <linux/workqueue.h>
#include "fatal_verbs.h"

/* Explicit optional FEC-native graph only; never probe aliases/legacy BARs. */
#define AS02_NATIVE_FATAL_BASE 0x406000U
#define AS02_NATIVE_FATAL_BYTES 0x1000U
struct as02_fatal_parent {
    struct mutex lock;
    struct delayed_work poll_work;
    struct as02_fatal_verbs verbs;
    int last_error;
    bool initialized, started, stop_requested, stopped, terminal;
};
/* Read-only fresh FEC metadata preflight BEFORE the parent's epoch command.
 * Empty metadata is NOT a drain/cancellation/reset-generation certificate.
 */
int as02_fatal_parent_check(void __iomem *,size_t);
int as02_fatal_parent_bind(struct as02_fatal_parent *,struct as02_verbs_device *,void __iomem *,size_t);
/* Start only AFTER genuine device publication. One retained event per tick;
 * does not depend on userspace CQ polling/arming and never busy-waits.
 */
int as02_fatal_parent_start(struct as02_fatal_parent *);
/* Stop POLLING only. Self-stop from the event worker returns EDEADLK; callers
 * must not hold graph/device/lease locks while synchronously joining work.
 * Returns no hardware STOP/drain/unpin authority. Attachment/device/BAR/
 * storage ownership remains held, even on an empty or logically stopped graph.
 */
int as02_fatal_parent_stop(struct as02_fatal_parent *);
#endif
