/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_NATIVE_ATTACH_H
#define AS02_NATIVE_ATTACH_H
#include "mr_contract.h"
#include "native_regs.h"

#define AS02_NATIVE_APP_ID 0x41534e31U
#define AS02_NATIVE_AUX_NAME "mqnic.app_41534e31"
#define AS02_NATIVE_BAR_BYTES 0x1000000ULL

/* Full-width parent metadata, checked BEFORE any native CSR access. Does
 * not claim the parent's private C layout matches a loaded mqnic module.
 * That exact header/parent-module compatibility is a separate load gate.
 */
struct as02_native_parent {
    as02_u32 vendor, device, subvendor, subdevice, app_id, mapped;
    as02_u64 bar_bytes;
};
int as02_native_parent_validate(const struct as02_native_parent *);
#endif
