# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit private RNC16383/CQC63 READ-capable admission profile.

Extend the fully wired READ RX/MSN/memory/lifetime candidate. Only actual SQ
admission/HLS-SQ/CQ length gates and distinct identities change. No installed
kernel/provider/default selection; real native runtime/timing still required.
"""
import derive_segmented_read_lifetime as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA
RNC_FEATURES=16383;CQC_FEATURES=63


def derive():
    out=parent.derive()
    for name,length,op in [('rocev2_wqe_admission.v','length','opcode'),
        ('rocev2_wqe_hls_sq.v','in_length','in_opcode'),('rocev2_cq_mmio.v','s_ticket_context[307:276]','incoming_opcode')]:
        p=RTL/name;out[p]=parent.read_limit(out[p],length,op)
    p=RTL/'rocev2_control_regs.v'
    out[p]=once(out[p],'(IMMEDIATE_ENABLE ? 512 : 0) | 1024 | 2048 | 4096;',
        '(IMMEDIATE_ENABLE ? 512 : 0) | 1024 | 2048 | 4096 | 8192; // distinct private large READ identity')
    p=RTL/'rocev2_cq_mmio.v'
    out[p]=once(out[p],'    8:rd=31; // private matched large-WR owner/codec profile',
        '    8:rd=63; // private matched large READ owner/codec profile')
    return out
