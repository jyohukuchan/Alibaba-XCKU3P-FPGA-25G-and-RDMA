# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private exact65535 provider binding, retaining every seven old identity.

Unchanged standard uverbs/libibverbs RECV and kernel-owned MR/RQ/CQ path.
No direct BAR/DMA/C128 bypass, payload copy, installation or physical claim.
"""
import derive_segmented_immediate_provider as base

SOURCE=base.SOURCE;once=base.once


def derive():
    t=once(base.derive(),'#define AS02_FW_SEGMENTED_IMMEDIATE (((uint64_t)0x10000<<32)|32767U)',
        '#define AS02_FW_SEGMENTED_IMMEDIATE (((uint64_t)0x10000<<32)|32767U)\n'
        '#define AS02_FW_SEGMENTED_RECEIVE (((uint64_t)0x10000<<32)|65535U)')
    return once(t,'response.base.fw_ver!=AS02_FW_SEGMENTED_IMMEDIATE)',
        'response.base.fw_ver!=AS02_FW_SEGMENTED_IMMEDIATE && response.base.fw_ver!=AS02_FW_SEGMENTED_RECEIVE)')
