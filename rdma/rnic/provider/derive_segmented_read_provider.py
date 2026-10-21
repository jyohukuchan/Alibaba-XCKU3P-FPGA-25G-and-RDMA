# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private exact16383 provider identity, unchanged standard verbs/uverbs ABI.

Keep all five old identities and the kernel-owned MR/SQ/CQ path. No direct
user BAR/DMA/C128 bypass, payload copy, installation or physical/runtime claim.
"""
import derive_segmented_provider as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_SEGMENTED (((uint64_t)0x10000<<32)|8191U)',
        '#define AS02_FW_SEGMENTED (((uint64_t)0x10000<<32)|8191U)\n'
        '#define AS02_FW_SEGMENTED_READ (((uint64_t)0x10000<<32)|16383U)')
    return once(t,'response.base.fw_ver!=AS02_FW_SEGMENTED)',
        'response.base.fw_ver!=AS02_FW_SEGMENTED && response.base.fw_ver!=AS02_FW_SEGMENTED_READ)')
