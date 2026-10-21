# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private exact32767 provider binding, retaining all six old FW identities.

Unchanged standard libibverbs/uverbs ABI and kernel-owned MR/SQ/CQ path;
no direct user BAR/DMA/C128 bypass, payload copy, installation or runtime claim.
"""
import derive_segmented_read_provider as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_SEGMENTED_READ (((uint64_t)0x10000<<32)|16383U)',
        '#define AS02_FW_SEGMENTED_READ (((uint64_t)0x10000<<32)|16383U)\n'
        '#define AS02_FW_SEGMENTED_IMMEDIATE (((uint64_t)0x10000<<32)|32767U)')
    return once(t,'response.base.fw_ver!=AS02_FW_SEGMENTED_READ)',
        'response.base.fw_ver!=AS02_FW_SEGMENTED_READ && response.base.fw_ver!=AS02_FW_SEGMENTED_IMMEDIATE)')
