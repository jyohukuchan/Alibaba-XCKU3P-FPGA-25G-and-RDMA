# SPDX-License-Identifier: BSD-2-Clause-Views
"""Atomic MAC branch with real downstream reservation before HLS ownership.

Keeps086 generators/RTL/evidence unchanged. Still not the ordinary/native
admission replacement. Gate NEW post-integrity packet admission on actual
MAC availability; admitted packet/owner drains under later disable. Finite
nonwrapping tag exhaustion cannot create another service side effect.
"""
import derive_atomic_mac_bridge as base
once=base.once

PORTS=r'''
    output wire atomic_mac_tags_exhausted,output wire atomic_mac_available,
    output wire atomic_reservation_guard,output wire atomic_reservation_fault,
    output wire [7:0] atomic_reservation_queue_guard,
    output wire [31:0] atomic_reservations,output wire [31:0] atomic_owner_deliveries,
'''

RESERVATION=r'''
wire atomic_mac_busy;
assign atomic_mac_available=!atomic_mac_busy && !atomic_mac_tags_exhausted &&
 !atomic_mac_fault && !atomic_reservation_guard && !atomic_reservation_fault &&
 atomic_parent_fault===1'b0;
wire [327:0] reserved_mac_owner;wire [143:0] reserved_hls_owner;
wire reserved_mac_valid,reserved_mac_ready,reserved_hls_valid,reserved_hls_ready;
rocev2_atomic_owner_reservation owner_reservation(
 .clk(clk),.rst(rst),
 .parent_fault(atomic_parent_fault || atomic_admission_fault || atomic_mac_fault || request_fault || recv_fault || rnr_fault),
 .s_owner({admitted_local_mac,admitted_peer_mac,admitted_local_ip,admitted_peer_ip,admitted_peer_qpn,m_atomic_owner_tag,m_atomic_owner_psn,m_atomic_owner_epoch,m_atomic_owner_qpn}),
 .s_valid(m_atomic_owner_valid),.s_ready(m_atomic_owner_ready),
 .m_mac_owner(reserved_mac_owner),.m_mac_valid(reserved_mac_valid),.m_mac_ready(reserved_mac_ready),
 .m_hls_owner(reserved_hls_owner),.m_hls_valid(reserved_hls_valid),.m_hls_ready(reserved_hls_ready),
 .configuration_guard(atomic_reservation_guard),.queue_guard(atomic_reservation_queue_guard),.fault(atomic_reservation_fault),
 .reserved_count(atomic_reservations),.delivered_count(atomic_owner_deliveries));
'''


def derive():
    t=base.derive()
    t=once(t,'module rocev2_atomic_mac_integrity_transport #',
        'module rocev2_atomic_reserved_mac_integrity_transport #')
    t=once(t,'parameter REQUEST_CQ_ENABLE = 0)(',
        'parameter REQUEST_CQ_ENABLE = 0,\n    parameter ATOMIC_MAC_TAG_SEQUENCE_WIDTH=13)(')
    t=once(t,'    input wire atomic_parent_fault,',PORTS+'    input wire atomic_parent_fault,')
    first=t.index('wire [655:0] owner_fanout_data;')
    last=t.index('axis_broadcast #(.M_COUNT(2),.DATA_WIDTH(392)',first)
    t=t[:first]+RESERVATION+'\nwire [783:0] reply_fanout_data;wire [1:0] reply_fanout_valid,reply_fanout_ready;\n'+t[last:]
    t=once(t,'.enable(atomic_admission_enable && !atomic_mac_fault),',
        '.enable(atomic_admission_enable && atomic_mac_available),')
    t=once(t,'rocev2_atomic_mac_tx mac_owner(',
        'rocev2_atomic_mac_tx #(.TAG_SEQUENCE_WIDTH(ATOMIC_MAC_TAG_SEQUENCE_WIDTH)) mac_owner(')
    # Enable controls NEW packet admission only. This owner has already been
    # accepted by the packet guard, so do not strand it under later disable.
    t=once(t,'.enable(atomic_admission_enable),',".enable(1'b1),")
    t=once(t,'atomic_parent_fault || atomic_admission_fault || request_fault || recv_fault || rnr_fault),\n .s_owner',
        'atomic_parent_fault || atomic_admission_fault || atomic_reservation_fault || request_fault || recv_fault || rnr_fault),\n .s_owner')
    replacements={
        'owner_fanout_data[471:328]':'reserved_mac_owner[143:0]',
        'owner_fanout_valid[1]':'reserved_mac_valid','owner_fanout_ready[1]':'reserved_mac_ready',
        'owner_fanout_data[655:608]':'reserved_mac_owner[327:280]',
        'owner_fanout_data[607:560]':'reserved_mac_owner[279:232]',
        'owner_fanout_data[559:528]':'reserved_mac_owner[231:200]',
        'owner_fanout_data[527:496]':'reserved_mac_owner[199:168]',
        'owner_fanout_data[495:472]':'reserved_mac_owner[167:144]',
        'owner_fanout_data[143:0]':'reserved_hls_owner',
        'owner_fanout_valid[0]':'reserved_hls_valid','owner_fanout_ready[0]':'reserved_hls_ready',
        '.configuration_guard(atomic_mac_guard),.busy()':'.configuration_guard(atomic_mac_guard),.busy(atomic_mac_busy)',
        '.tags_exhausted()':'.tags_exhausted(atomic_mac_tags_exhausted)',
    }
    for before,after in replacements.items():t=once(t,before,after)
    if 'owner_fanout_'in t:raise ValueError('unordered owner path remains')
    return t
