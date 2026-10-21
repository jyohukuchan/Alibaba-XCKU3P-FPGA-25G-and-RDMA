# SPDX-License-Identifier: BSD-2-Clause-Views
"""Distinct private incoming-WRITE identity on the actual qualified native graph.

Only three CSR feature words change: RNC131071/CQC511/SQC13/RQC63. Payload,
owner, clocks, geometry, MR/DMA/HLS/ACK/PSN/CQ gates are byte-identical.
Old tuples/defaults stay immutable. Not installed or physical qualification.
"""
import derive_segmented_write_native as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
RNC=131071;CQC=511;SQC=13;RQC=63;PROFILE=8
CHANGED={'rocev2_control_regs.v','rocev2_cq_mmio.v','rocev2_sq_control_regs.v'}


def derive():
    out=parent.derive()
    p=RTL/'rocev2_control_regs.v'
    out[p]=once(out[p],' | 32768; // distinct private large SEND receive identity',
        ' | 32768 | 65536; // distinct private segmented WRITE receive identity')
    p=RTL/'rocev2_cq_mmio.v'
    out[p]=once(out[p],'8:rd=255; // separate large SEND receive cohort, source only until qualified',
        '8:rd=511; // distinct private segmented WRITE receive cohort')
    p=RTL/'rocev2_sq_control_regs.v'
    out[p]=once(out[p],"8:rd=(RECV_CANCEL_ENABLE ? 32'h13:32'h1) | 32'hc;",
        "8:rd=(RECV_CANCEL_ENABLE ? 32'h33:32'h1) | 32'hc;")
    return out
