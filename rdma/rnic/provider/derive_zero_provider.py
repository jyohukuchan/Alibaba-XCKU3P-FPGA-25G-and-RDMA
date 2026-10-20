# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private future4095 provider cohort, same standard uverbs serialization.

No direct user BAR/DMA/128-byte WQE ABI, local MR shortcut or completion
fabrication. Kernel source negotiates the actual full zero tuple separately.
Incoming zero/RQ/native/Linux qualification is unfinished; never install.
"""
import derive_atomic_access as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_ATOMIC_ACCESS (((uint64_t)0x10000<<32)|2047U)',
        '#define AS02_FW_ATOMIC_ACCESS (((uint64_t)0x10000<<32)|2047U)\n'
        '#define AS02_FW_ZERO_LENGTH (((uint64_t)0x10000<<32)|4095U)')
    return once(t,'response.base.fw_ver!=AS02_FW_ATOMIC_ACCESS)',
        'response.base.fw_ver!=AS02_FW_ATOMIC_ACCESS && response.base.fw_ver!=AS02_FW_ZERO_LENGTH)')
