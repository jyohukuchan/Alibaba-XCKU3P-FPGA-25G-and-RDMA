# SPDX-License-Identifier: BSD-2-Clause-Views
"""Late-WRITE RQ with a non-authorizing posted-head observation port.

Do not feed a notice producer from the same notice's protocol-gated head
VALID: that makes a combinational cycle. The peek only exposes an existing
posted owner for independent validation. ALL actual take, notice, packet,
CQ and retirement gates remain byte-identical to the qualified parent.
"""
import derive_write_notice_queue as parent

ROOT=parent.ROOT;SOURCE=parent.SOURCE;once=parent.once
NAME='rocev2_write_notice_binding_queue'


def derive():
    t=once(parent.derive(),'module '+parent.NAME+' #(','module '+NAME+' #(')
    t=once(t,'    input wire clk,input wire rst,input wire parent_fault,',r'''
    // Observation only, NEVER a take, MR grant or completion certificate.
    // Independent of this same notice's combinational protocol_fault.
    output wire [619:0] m_notice_head_context,output wire m_notice_head_valid,
    input wire clk,input wire rst,input wire parent_fault,''')
    t=once(t,'assign held_context=owner;assign active=held;',r'''
assign held_context=owner;assign active=held;
assign m_notice_head_context=m_head_context;
assign m_notice_head_valid=query_ok && !cancel_target && !fault &&
    parent_fault===1'b0 && !rst && !held && count[query_qpn[2:0]]!=0;''')
    return t
