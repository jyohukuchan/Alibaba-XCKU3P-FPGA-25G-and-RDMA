# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only Atomic route lookup on the actual existing SQC owner arrays.

Original CSR/ABI/table and CQ/retry lookups are untouched. New lookup refuses
full-width aliases/unknowns, busy/mailbox faults and the accepting doorbell
edge. Actual downstream Atomic guards MUST still block retirement/config.
Not a new QP table, memory authority, lease or native integration by itself.
"""
from pathlib import Path
import derive_shared_responder as base

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'rdma/rnic/rtl/rocev2_sq_control_regs.v'
once=base.once
PORTS=r'''
    input wire [23:0] atomic_query_qpn,
    output wire [63:0] atomic_query_cookie,
    output wire [63:0] atomic_query_epoch,
    output wire [15:0] atomic_query_pd,
    output wire atomic_query_valid,
'''
LOGIC=r'''
wire atomic_query_known=(^atomic_query_qpn)!==1'bx && atomic_query_qpn<MAX_QPS;
wire [2:0] atomic_query_index=atomic_query_qpn[2:0];
assign atomic_query_valid=atomic_query_known && state==IDLE && !doorbell &&
    owner_active[atomic_query_index] && !owner_tainted[atomic_query_index] &&
    !fatal && !endpoint_fault && !mmio_error && !rst;
assign atomic_query_cookie=atomic_query_valid ? owner_cookie[atomic_query_index]:64'd0;
assign atomic_query_epoch=atomic_query_valid ? owner_epoch[atomic_query_index]:64'd0;
assign atomic_query_pd=atomic_query_valid ? owner_pd[atomic_query_index]:16'd0;
'''


def derive():
    t=SOURCE.read_text()
    t=once(t,'    input wire [23:0] owner_query_qpn,',PORTS+'    input wire [23:0] owner_query_qpn,')
    return once(t,'wire sequence_ok=stage[0]==last_sequence+1\'b1 && stage[0]!=0 && wd==stage[0];',
        'wire sequence_ok=stage[0]==last_sequence+1\'b1 && stage[0]!=0 && wd==stage[0];\n'+LOGIC)
