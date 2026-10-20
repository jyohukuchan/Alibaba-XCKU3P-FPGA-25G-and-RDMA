# SPDX-License-Identifier: BSD-2-Clause-Views
"""Atomic-only branch: actual guard owner -> full HLS -> owned service/done.

Not normal/native graph replacement. External retirement must join real core
done and, if response expected, operation-owned MAC SFD/EOF/tail, not ready.
"""
import derive_atomic_bridge as base
once=base.once


def derive():
    t=base.derive()
    t=once(t,'module rocev2_atomic_integrity_transport #',
        'module rocev2_atomic_owned_integrity_transport #')
    t=once(t,'output wire [367:0] m_atomic_request_tdata','output wire [511:0] m_atomic_request_tdata')
    t=once(t,'input wire [247:0] s_atomic_reply_tdata','input wire [391:0] s_atomic_reply_tdata')
    t=once(t,'output wire m_atomic_owner_valid, input wire m_atomic_owner_ready,',
        'output wire m_atomic_owner_valid, output wire m_atomic_owner_ready,\n'
        '    output wire [223:0] m_atomic_core_done_tdata, output wire m_atomic_core_done_tvalid, input wire m_atomic_core_done_tready,')
    return once(t,'rocev2_native_atomic_top transport (',
        'rocev2_native_atomic_owned_top transport (\n'
        '    .s_axis_atomic_owner_TDATA({m_atomic_owner_tag,m_atomic_owner_psn,m_atomic_owner_epoch,m_atomic_owner_qpn}),\n'
        '    .s_axis_atomic_owner_TVALID(m_atomic_owner_valid),.s_axis_atomic_owner_TREADY(m_atomic_owner_ready),\n'
        '    .m_axis_atomic_done_TDATA(m_atomic_core_done_tdata),.m_axis_atomic_done_TVALID(m_atomic_core_done_tvalid),.m_axis_atomic_done_TREADY(m_atomic_core_done_tready),')
