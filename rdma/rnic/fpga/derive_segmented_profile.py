# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private explicit large-WR capability identity for the matched real graph.

RNC8191/CQC31, same128-byte SQ/RQ and748-bit owner; no new data bypass.
Old4095/15/default images and software are unchanged. Requires independent
matched kernel/provider/runtime/physical/timing qualification before use.
"""
import derive_segmented_padding as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA


def derive():
    out=parent.derive()
    p=RTL/'rocev2_control_regs.v'
    out[p]=once(out[p],'(IMMEDIATE_ENABLE ? 512 : 0) | 1024 | 2048;',
        '(IMMEDIATE_ENABLE ? 512 : 0) | 1024 | 2048 | 4096;')
    p=RTL/'rocev2_cq_mmio.v'
    out[p]=once(out[p],'    8:rd=15;','    8:rd=31; // private matched large-WR owner/codec profile')
    return out
