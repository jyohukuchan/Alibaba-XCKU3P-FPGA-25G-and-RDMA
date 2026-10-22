/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_FATAL_VERBS_H
#define AS02_FATAL_VERBS_H
#include <linux/mutex.h>
#include "fatal_io.h"

struct as02_verbs_device;
struct as02_verbs_qp;
/* Explicit parent-owned optional attachment, never probed or enabled by the
 * default driver. Storage/BAR/device lifetime must outlive this object.
 * The derived verbs destroy/progress/unbind guards are MANDATORY, not an
 * optional callback contract or a substitute IB-core usecnt increment.
 */
struct as02_fatal_verbs {
    struct mutex lock;
    struct as02_fatal_io reader;
    struct as02_verbs_device *device;
    struct as02_verbs_qp *notification_qp;
    void __iomem *registers;
    bool initialized, polling, detached;
};
/* Exclusive initialization of a zeroed object, before QP creation. Only the
 * already-bound exact private profile8 graph is accepted. No BAR mapping,
 * registration, capability advertisement, reset or background poll starts.
 */
int as02_fatal_verbs_bind(struct as02_fatal_verbs *,struct as02_verbs_device *,
                         void __iomem *,size_t);
/* Sleepable, serialized, bounded one-event polling. Actual live QP/SQC owner
 * is matched under the device lock, then ERR/posting closure and a retained
 * record are committed before notification ACK. The QP-specific handler is
 * invoked once OUTSIDE all driver locks, with real destruction exclusion.
 * ACK failure cannot repeat the accepted callback or certify drain/unpin.
 */
int as02_fatal_verbs_poll(struct as02_fatal_verbs *);
/* Terminal logical detach: no MMIO/ACK or reference release. It stops new
 * posting and deliberately RETAINS d->fatal/device/BAR/storage ownership.
 * There is no invented safe-unbind API without actual whole-device proofs.
 */
int as02_fatal_verbs_detach(struct as02_fatal_verbs *);
#endif
