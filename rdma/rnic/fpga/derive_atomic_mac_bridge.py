# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned Atomic-only branch with hardware MAC lifetime and automatic retirement.

Retains earlier owned branch as rollback. Not the full ordinary/Atomic native
admission/MR/QP integration. Existing native Ethernet frames pass the final
mux; private Atomic completions never enter the inner WQE native-tag policy.
"""
import derive_atomic_owned_bridge as base
once=base.once

PORTS=r'''
    input wire atomic_parent_fault,
    input wire [47:0] atomic_trusted_local_mac,input wire [47:0] atomic_trusted_peer_mac,
    input wire [23:0] atomic_trusted_peer_qpn,
    input wire [127:0] s_native_data,input wire [15:0] s_native_keep,
    input wire s_native_valid,output wire s_native_ready,input wire s_native_last,input wire [16:0] s_native_user,
    output wire [127:0] m_mac_data,output wire [15:0] m_mac_keep,
    output wire m_mac_valid,input wire m_mac_ready,output wire m_mac_last,output wire [16:0] m_mac_user,
    input wire [15:0] s_mac_cpl_tag,input wire [95:0] s_mac_cpl_ts,input wire s_mac_cpl_valid,output wire s_mac_cpl_ready,
    output wire [15:0] m_native_cpl_tag,output wire [95:0] m_native_cpl_ts,output wire m_native_cpl_valid,input wire m_native_cpl_ready,
    output wire atomic_mac_guard,output wire atomic_mac_fault,output wire [7:0] atomic_mac_queue_guard,
    output wire [31:0] atomic_mac_frames,output wire [31:0] atomic_mac_receipts,output wire [31:0] atomic_mac_retired,
'''

LOGIC=r'''
// Trusted MAC/peer sideband captured on EXACT SAME accepted post-integrity
// first beat as the real packet guard's QPN/epoch/IP snapshot.
reg atomic_in_frame=0;
reg [47:0] admitted_local_mac=0,admitted_peer_mac=0;
reg [31:0] admitted_local_ip=0,admitted_peer_ip=0;reg [23:0] admitted_peer_qpn=0;
always @(posedge clk)begin
 if(rst)begin atomic_in_frame<=0;admitted_local_mac<=0;admitted_peer_mac<=0;admitted_local_ip<=0;admitted_peer_ip<=0;admitted_peer_qpn<=0;end
 else if(checked_valid && checked_ready)begin
  if(!atomic_in_frame)begin
   admitted_local_mac<=atomic_trusted_local_mac;admitted_peer_mac<=atomic_trusted_peer_mac;
   admitted_local_ip<=atomic_trusted_local_ip;admitted_peer_ip<=atomic_trusted_peer_ip;admitted_peer_qpn<=atomic_trusted_peer_qpn;
  end
  atomic_in_frame<=!checked_last;
 end
end
wire [655:0] owner_fanout_data;wire [1:0] owner_fanout_valid,owner_fanout_ready;
wire [783:0] reply_fanout_data;wire [1:0] reply_fanout_valid,reply_fanout_ready;
axis_broadcast #(.M_COUNT(2),.DATA_WIDTH(328),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.LAST_ENABLE(0),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1)) owner_broadcast(
 .clk(clk),.rst(rst),
 .s_axis_tdata({admitted_local_mac,admitted_peer_mac,admitted_local_ip,admitted_peer_ip,admitted_peer_qpn,m_atomic_owner_tag,m_atomic_owner_psn,m_atomic_owner_epoch,m_atomic_owner_qpn}),
 .s_axis_tkeep(1'b1),.s_axis_tvalid(m_atomic_owner_valid),.s_axis_tready(m_atomic_owner_ready),.s_axis_tlast(1'b1),
 .s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
 .m_axis_tdata(owner_fanout_data),.m_axis_tvalid(owner_fanout_valid),.m_axis_tready(owner_fanout_ready),
 .m_axis_tkeep(),.m_axis_tlast(),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
axis_broadcast #(.M_COUNT(2),.DATA_WIDTH(392),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.LAST_ENABLE(0),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1)) reply_broadcast(
 .clk(clk),.rst(rst),.s_axis_tdata(s_atomic_reply_tdata),.s_axis_tkeep(1'b1),
 .s_axis_tvalid(s_atomic_reply_tvalid),.s_axis_tready(s_atomic_reply_tready),.s_axis_tlast(1'b1),
 .s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
 .m_axis_tdata(reply_fanout_data),.m_axis_tvalid(reply_fanout_valid),.m_axis_tready(reply_fanout_ready),
 .m_axis_tkeep(),.m_axis_tlast(),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
wire [143:0] mac_retire_owner;
assign {s_atomic_retire_tag,s_atomic_retire_psn,s_atomic_retire_epoch,s_atomic_retire_qpn}=mac_retire_owner;
rocev2_atomic_mac_tx mac_owner(
 .clk(clk),.rst(rst),.enable(atomic_admission_enable),
 .parent_fault(atomic_parent_fault || atomic_admission_fault || request_fault || recv_fault || rnr_fault),
 .s_owner(owner_fanout_data[471:328]),.s_owner_valid(owner_fanout_valid[1]),.s_owner_ready(owner_fanout_ready[1]),
 .s_owner_local_mac(owner_fanout_data[655:608]),.s_owner_peer_mac(owner_fanout_data[607:560]),
 .s_owner_local_ip(owner_fanout_data[559:528]),.s_owner_peer_ip(owner_fanout_data[527:496]),.s_owner_peer_qpn(owner_fanout_data[495:472]),
 .s_service_reply(reply_fanout_data[783:392]),.s_service_valid(reply_fanout_valid[1]),.s_service_ready(reply_fanout_ready[1]),
 .s_core_done(m_atomic_core_done_tdata),.s_core_valid(m_atomic_core_done_tvalid),.s_core_ready(m_atomic_core_done_tready),
 .s_axis_ip_tdata(m_axis_tx_tdata),.s_axis_ip_tkeep(m_axis_tx_tkeep),.s_axis_ip_tvalid(m_axis_tx_tvalid),.s_axis_ip_tready(m_axis_tx_tready),.s_axis_ip_tlast(m_axis_tx_tlast),
 .s_axis_native_tdata(s_native_data),.s_axis_native_tkeep(s_native_keep),.s_axis_native_tvalid(s_native_valid),.s_axis_native_tready(s_native_ready),.s_axis_native_tlast(s_native_last),.s_axis_native_tuser(s_native_user),
 .m_axis_mac_tdata(m_mac_data),.m_axis_mac_tkeep(m_mac_keep),.m_axis_mac_tvalid(m_mac_valid),.m_axis_mac_tready(m_mac_ready),.m_axis_mac_tlast(m_mac_last),.m_axis_mac_tuser(m_mac_user),
 .s_mac_cpl_tag(s_mac_cpl_tag),.s_mac_cpl_ts(s_mac_cpl_ts),.s_mac_cpl_valid(s_mac_cpl_valid),.s_mac_cpl_ready(s_mac_cpl_ready),
 .m_native_cpl_tag(m_native_cpl_tag),.m_native_cpl_ts(m_native_cpl_ts),.m_native_cpl_valid(m_native_cpl_valid),.m_native_cpl_ready(m_native_cpl_ready),
 .m_retire_owner(mac_retire_owner),.m_retire_core(),.m_retire_tag(),.m_retire_timestamp(),.m_retire_valid(s_atomic_retire_valid),.m_retire_ready(s_atomic_retire_ready),
 .queue_guard(atomic_mac_queue_guard),.configuration_guard(atomic_mac_guard),.busy(),.fault(atomic_mac_fault),.fault_code(),
 .active_tag(),.tags_exhausted(),.frame_count(atomic_mac_frames),.receipt_count(atomic_mac_receipts),.retired_count(atomic_mac_retired),.drop_retired_count());
'''


def derive():
    t=base.derive()
    t=once(t,'module rocev2_atomic_owned_integrity_transport #','module rocev2_atomic_mac_integrity_transport #')
    t=once(t,'    input wire rst,','    input wire rst,\n'+PORTS)
    for port in ['m_axis_tx_tready','m_atomic_core_done_tready']:
        t=once(t,'input wire '+port,'output wire '+port)
    for width,port in [('23:0','s_atomic_retire_qpn'),('63:0','s_atomic_retire_epoch'),
                       ('23:0','s_atomic_retire_psn'),('31:0','s_atomic_retire_tag')]:
        t=once(t,'input wire ['+width+'] '+port,'output wire ['+width+'] '+port)
    t=once(t,'input wire s_atomic_retire_valid','output wire s_atomic_retire_valid')
    t=once(t,'.enable(atomic_admission_enable),','.enable(atomic_admission_enable && !atomic_mac_fault),')
    t=once(t,'.s_axis_atomic_owner_TDATA({m_atomic_owner_tag,m_atomic_owner_psn,m_atomic_owner_epoch,m_atomic_owner_qpn}),',
        '.s_axis_atomic_owner_TDATA(owner_fanout_data[143:0]),')
    t=once(t,'.s_axis_atomic_owner_TVALID(m_atomic_owner_valid),.s_axis_atomic_owner_TREADY(m_atomic_owner_ready),',
        '.s_axis_atomic_owner_TVALID(owner_fanout_valid[0]),.s_axis_atomic_owner_TREADY(owner_fanout_ready[0]),')
    t=once(t,'.s_axis_atomic_reply_TDATA(s_atomic_reply_tdata),.s_axis_atomic_reply_TVALID(s_atomic_reply_tvalid),.s_axis_atomic_reply_TREADY(s_atomic_reply_tready),',
        '.s_axis_atomic_reply_TDATA(reply_fanout_data[391:0]),.s_axis_atomic_reply_TVALID(reply_fanout_valid[0]),.s_axis_atomic_reply_TREADY(reply_fanout_ready[0]),')
    return once(t,'wire [511:0] core_rx_data, core_tx_data;',LOGIC+'\nwire [511:0] core_rx_data, core_tx_data;')
