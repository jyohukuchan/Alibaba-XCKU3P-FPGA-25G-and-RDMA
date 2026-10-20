# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE full owned HLS bridge for normal/Immediate AND native Atomic service.

Preserves RX/TX integrity, padding,280-bitSQ, commonPSN/MSN and request/receive
proofs. Unlike the isolated Atomic-only bridge, this bridge does NOT replace
ordinary protected admission with an Atomic-only guard. Native parents MUST
supply genuine owned Atomic admission/MR/exclusive-memory/MAC retirement.
Only the bridge is derived here; whole native graph selection is separate.
"""
import derive_immediate_bridge as base
once=base.once

PORTS=r'''
    input wire [143:0] s_atomic_owner,input wire s_atomic_owner_valid,output wire s_atomic_owner_ready,
    output wire [511:0] m_atomic_request,output wire m_atomic_request_valid,input wire m_atomic_request_ready,
    input wire [391:0] s_atomic_reply,input wire s_atomic_reply_valid,output wire s_atomic_reply_ready,
    output wire [223:0] m_atomic_done,output wire m_atomic_done_valid,input wire m_atomic_done_ready,
'''


def derive():
    t=base.derive()
    t=once(t,'module rocev2_immediate_integrity_transport #','module rocev2_atomic_native_integrity_transport #')
    t=once(t,'    input wire clk,',PORTS+'    input wire clk,')
    return once(t,'rocev2_native_immediate_top transport (',
        'rocev2_native_atomic_owned_top transport (\n'
        '    .s_axis_atomic_owner_TDATA(s_atomic_owner),.s_axis_atomic_owner_TVALID(s_atomic_owner_valid),.s_axis_atomic_owner_TREADY(s_atomic_owner_ready),\n'
        '    .m_axis_atomic_request_TDATA(m_atomic_request),.m_axis_atomic_request_TVALID(m_atomic_request_valid),.m_axis_atomic_request_TREADY(m_atomic_request_ready),\n'
        '    .s_axis_atomic_reply_TDATA(s_atomic_reply),.s_axis_atomic_reply_TVALID(s_atomic_reply_valid),.s_axis_atomic_reply_TREADY(s_atomic_reply_ready),\n'
        '    .m_axis_atomic_done_TDATA(m_atomic_done),.m_axis_atomic_done_TVALID(m_atomic_done_valid),.m_axis_atomic_done_TREADY(m_atomic_done_ready),')
