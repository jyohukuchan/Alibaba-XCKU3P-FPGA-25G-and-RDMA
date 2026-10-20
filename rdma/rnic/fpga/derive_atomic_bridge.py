# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched Atomic-service full HLS integrity bridge, original bridge untouched.

Expose typed368/248 service words and place the actual new Atomic branch
packet guard AFTER whole-packet RX integrity and BEFORE the real HLS width
adapter. This guarded branch is not a replacement for native normal-operation
admission, native MAC ownership or actual kernel/provider integration.
"""
import derive_immediate_bridge as base

once=base.once


def derive():
    text=base.derive()
    text=once(text,'module rocev2_immediate_integrity_transport #',
        'module rocev2_atomic_integrity_transport #')
    text=once(text,'parameter REQUEST_CQ_ENABLE = 0) (','parameter REQUEST_CQ_ENABLE = 0)(\n')
    text=once(text,'    input wire rst,','    input wire rst,\n'+PORTS)
    text=once(text,'rocev2_native_immediate_top transport (',
        'rocev2_native_atomic_top transport (\n'
        '    .m_axis_atomic_request_TDATA(m_atomic_request_tdata),.m_axis_atomic_request_TVALID(m_atomic_request_tvalid),.m_axis_atomic_request_TREADY(m_atomic_request_tready),\n'
        '    .s_axis_atomic_reply_TDATA(s_atomic_reply_tdata),.s_axis_atomic_reply_TVALID(s_atomic_reply_tvalid),.s_axis_atomic_reply_TREADY(s_atomic_reply_tready),')
    anchor='wire [511:0] core_rx_data, core_tx_data;'
    guard=r'''
wire [127:0] guarded_data;wire [15:0] guarded_keep;wire guarded_valid,guarded_ready,guarded_last;
rocev2_atomic_packet_guard atomic_admission(
 .clk(clk),.rst(rst),.enable(atomic_admission_enable),
 .trusted_valid(atomic_trusted_valid),.trusted_qpn(atomic_trusted_qpn),.trusted_epoch(atomic_trusted_epoch),
 .trusted_local_ip(atomic_trusted_local_ip),.trusted_peer_ip(atomic_trusted_peer_ip),
 .s_axis_tdata(checked_data),.s_axis_tkeep(checked_keep),.s_axis_tvalid(checked_valid),.s_axis_tready(checked_ready),.s_axis_tlast(checked_last),
 .m_axis_tdata(guarded_data),.m_axis_tkeep(guarded_keep),.m_axis_tvalid(guarded_valid),.m_axis_tready(guarded_ready),.m_axis_tlast(guarded_last),
 .m_owner_qpn(m_atomic_owner_qpn),.m_owner_epoch(m_atomic_owner_epoch),.m_owner_psn(m_atomic_owner_psn),.m_owner_tag(m_atomic_owner_tag),
 .m_owner_valid(m_atomic_owner_valid),.m_owner_ready(m_atomic_owner_ready),
 .s_retire_qpn(s_atomic_retire_qpn),.s_retire_epoch(s_atomic_retire_epoch),.s_retire_psn(s_atomic_retire_psn),.s_retire_tag(s_atomic_retire_tag),
 .s_retire_valid(s_atomic_retire_valid),.s_retire_ready(s_atomic_retire_ready),
 .busy(),.configuration_guard(atomic_admission_guard),.fault(atomic_admission_fault),.fault_code(),
 .accepted_count(atomic_admission_accepted),.dropped_count(atomic_admission_dropped)
);
'''
    text=once(text,anchor,guard+anchor)
    text=once(text,'.s_axis_tdata(checked_data), .s_axis_tkeep(checked_keep),\n    .s_axis_tvalid(checked_valid), .s_axis_tready(checked_ready), .s_axis_tlast(checked_last),',
        '.s_axis_tdata(guarded_data), .s_axis_tkeep(guarded_keep),\n'
        '    .s_axis_tvalid(guarded_valid), .s_axis_tready(guarded_ready), .s_axis_tlast(guarded_last),')
    return text


PORTS=r'''
    input wire atomic_admission_enable, input wire atomic_trusted_valid,
    input wire [23:0] atomic_trusted_qpn, input wire [63:0] atomic_trusted_epoch,
    input wire [31:0] atomic_trusted_local_ip, input wire [31:0] atomic_trusted_peer_ip,
    output wire [367:0] m_atomic_request_tdata, output wire m_atomic_request_tvalid, input wire m_atomic_request_tready,
    input wire [247:0] s_atomic_reply_tdata, input wire s_atomic_reply_tvalid, output wire s_atomic_reply_tready,
    output wire [23:0] m_atomic_owner_qpn, output wire [63:0] m_atomic_owner_epoch,
    output wire [23:0] m_atomic_owner_psn, output wire [31:0] m_atomic_owner_tag,
    output wire m_atomic_owner_valid, input wire m_atomic_owner_ready,
    input wire [23:0] s_atomic_retire_qpn, input wire [63:0] s_atomic_retire_epoch,
    input wire [23:0] s_atomic_retire_psn, input wire [31:0] s_atomic_retire_tag,
    input wire s_atomic_retire_valid, output wire s_atomic_retire_ready,
    output wire atomic_admission_guard, output wire atomic_admission_fault,
    output wire [31:0] atomic_admission_accepted, output wire [31:0] atomic_admission_dropped,
'''
