# SPDX-License-Identifier: BSD-2-Clause-Views
"""Add only the exact private131071 identity to the standard uverbs provider.

All8 old identities remain. Kernel-owned MR/queues/standard verbs serialization
are unchanged; no direct BAR/DMA, local payload copy or fake completion path.
"""
import derive_segmented_receive_provider as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_SEGMENTED_RECEIVE (((uint64_t)0x10000<<32)|65535U)',
        '#define AS02_FW_SEGMENTED_RECEIVE (((uint64_t)0x10000<<32)|65535U)\n'
        '#define AS02_FW_SEGMENTED_WRITE (((uint64_t)0x10000<<32)|131071U)')
    return once(t,'response.base.fw_ver!=AS02_FW_SEGMENTED_RECEIVE)',
        'response.base.fw_ver!=AS02_FW_SEGMENTED_RECEIVE && response.base.fw_ver!=AS02_FW_SEGMENTED_WRITE)')
