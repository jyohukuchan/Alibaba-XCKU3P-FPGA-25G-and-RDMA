/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include "native_attach.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

int as02_native_parent_validate(const struct as02_native_parent *p)
{
    if (!p)
        return -EINVAL;
    if (p->vendor != 0x1234 || p->device != 0x1001 ||
        p->subvendor != 0x1ce4 || p->subdevice != 0x0009 ||
        p->app_id != AS02_NATIVE_APP_ID)
        return -ENODEV;
    /* Exact reviewed native BAR geometry, not a guessed lower-bit alias. */
    if (p->mapped != 1 || p->bar_bytes != AS02_NATIVE_BAR_BYTES ||
        p->bar_bytes < (as02_u64)AS02_NATIVE_CONTROL_BASE+AS02_NATIVE_CONTROL_BYTES)
        return -ENXIO;
    return 0;
}
