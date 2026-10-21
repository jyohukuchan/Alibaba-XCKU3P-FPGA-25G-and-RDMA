# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private matched8191 provider, unchanged standard libibverbs/uverbs ABI.

Accept the exact new kernel FW identity plus all four reviewed old profiles.
No user BAR/DMA/C128 ABI, MR bypass, payload copy or fabricated completion.
Kernel still owns full tuple/geometry/range/lifetimes. Never install before
matched native/kernel/standard API/physical/timing qualification.
"""
import derive_zero_provider as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_ZERO_LENGTH (((uint64_t)0x10000<<32)|4095U)',
        '#define AS02_FW_ZERO_LENGTH (((uint64_t)0x10000<<32)|4095U)\n'
        '#define AS02_FW_SEGMENTED (((uint64_t)0x10000<<32)|8191U)')
    return once(t,'response.base.fw_ver!=AS02_FW_ZERO_LENGTH)',
        'response.base.fw_ver!=AS02_FW_ZERO_LENGTH && response.base.fw_ver!=AS02_FW_SEGMENTED)')
