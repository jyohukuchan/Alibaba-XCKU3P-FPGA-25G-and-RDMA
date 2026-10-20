# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual128->64 asynchronous frame FIFO/25G XGMII TX/SFD/receipt CDC RTL.

Core250MHz,MAC390.625MHz. Physical pins/PHY, clock source and PTP time input
are models; MAC frames/FCS/START/TERM/SFD-valid/tag are actual RTL outputs.
"""
from pathlib import Path
import binascii

ROOT=Path(__file__).resolve().parents[3]
AXIS=ROOT/'external/corundum/fpga/lib/axis/rtl';ETH=ROOT/'external/corundum/fpga/lib/eth/rtl'
SOURCES=[ETH/'axis_xgmii_tx_64.v',ETH/'lfsr.v',AXIS/'axis_async_fifo_adapter.v',AXIS/'axis_async_fifo.v',AXIS/'axis_adapter.v']

LINK=r'''
// ACTUAL MAC RTL and two real CDC FIFOs. No test-produced completion tag.
reg mac_clk=0;always #1.28 mac_clk=~mac_clk;
wire [127:0] link_s_data;wire [15:0] link_s_keep;wire link_s_valid,link_s_ready,link_s_last;wire [16:0] link_s_user;
wire [15:0] link_m_cpl_tag;wire [95:0] link_m_cpl_ts;wire link_m_cpl_valid,link_m_cpl_ready;
wire [63:0] mac_axis_data,xgmii_txd;wire [7:0] mac_axis_keep,xgmii_txc;
wire mac_axis_valid,mac_axis_ready,mac_axis_last;wire [16:0] mac_axis_user;
wire tx_overflow,tx_bad_frame,completion_overflow,mac_underflow;wire [1:0] mac_start;
wire [15:0] mac_stamp_tag;wire [95:0] mac_stamp;wire mac_stamp_valid,mac_stamp_ready;
reg [95:0] modeled_ptp_time=96'h012345678900000000000000;
integer actual_SFD_count=0,actual_Atomic_SFD_count=0,actual_native_SFD_count=0;
always @(posedge mac_clk)begin
 if(rst)modeled_ptp_time<=96'h012345678900000000000000;
 else begin
  modeled_ptp_time<=modeled_ptp_time+96'h28f5c;
  if(mac_underflow || tx_overflow || tx_bad_frame || completion_overflow)$fatal(1,"real MAC/FIFO error");
  if(xgmii_txc!=8'hff || xgmii_txd!=64'h0707070707070707)$display("XGMII_TX %016h %02h",xgmii_txd,xgmii_txc);
  if(mac_stamp_valid)begin
   if(!mac_stamp_ready)$fatal(1,"actual MAC timestamp FIFO overflow");
   actual_SFD_count=actual_SFD_count+1;
   if(mac_stamp_tag!=0 && mac_stamp_tag<8192)actual_Atomic_SFD_count=actual_Atomic_SFD_count+1;
   else actual_native_SFD_count=actual_native_SFD_count+1;
   $display("ACTUAL_MAC_SFD %04h %024h",mac_stamp_tag,mac_stamp);
  end
 end
end
axis_async_fifo_adapter #(.DEPTH(1024),.S_DATA_WIDTH(128),.S_KEEP_ENABLE(1),.S_KEEP_WIDTH(16),
 .M_DATA_WIDTH(64),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(8),.USER_ENABLE(1),.USER_WIDTH(17),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.FRAME_FIFO(1),.DROP_BAD_FRAME(1),
 .USER_BAD_FRAME_VALUE(17'd1),.USER_BAD_FRAME_MASK(17'd1)) actual_tx_fifo(
 .s_clk(clk),.s_rst(rst),.s_axis_tdata(link_s_data),.s_axis_tkeep(link_s_keep),.s_axis_tvalid(link_s_valid),.s_axis_tready(link_s_ready),
 .s_axis_tlast(link_s_last),.s_axis_tuser(link_s_user),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),
 .m_clk(mac_clk),.m_rst(rst),.m_axis_tdata(mac_axis_data),.m_axis_tkeep(mac_axis_keep),.m_axis_tvalid(mac_axis_valid),.m_axis_tready(mac_axis_ready),
 .m_axis_tlast(mac_axis_last),.m_axis_tuser(mac_axis_user),.m_axis_tid(),.m_axis_tdest(),
 .s_pause_req(1'b0),.m_pause_req(1'b0),.s_pause_ack(),.m_pause_ack(),
 .s_status_depth(),.s_status_depth_commit(),.s_status_overflow(tx_overflow),.s_status_bad_frame(tx_bad_frame),.s_status_good_frame(),
 .m_status_depth(),.m_status_depth_commit(),.m_status_overflow(),.m_status_bad_frame(),.m_status_good_frame());
axis_xgmii_tx_64 #(.PTP_TS_ENABLE(1),.PTP_TAG_ENABLE(1),.PTP_TAG_WIDTH(16),.PTP_TS_WIDTH(96),.USER_WIDTH(17),
 .PTP_PERIOD_NS(4'd2),.PTP_PERIOD_FNS(16'h8f5c)) actual_mac(
 .clk(mac_clk),.rst(rst),.s_axis_tdata(mac_axis_data),.s_axis_tkeep(mac_axis_keep),.s_axis_tvalid(mac_axis_valid),.s_axis_tready(mac_axis_ready),
 .s_axis_tlast(mac_axis_last),.s_axis_tuser(mac_axis_user),.xgmii_txd(xgmii_txd),.xgmii_txc(xgmii_txc),
 .ptp_ts(modeled_ptp_time),.m_axis_ptp_ts(mac_stamp),.m_axis_ptp_ts_tag(mac_stamp_tag),.m_axis_ptp_ts_valid(mac_stamp_valid),
 .cfg_ifg(8'd12),.cfg_tx_enable(1'b1),.start_packet(mac_start),.error_underflow(mac_underflow));
axis_async_fifo #(.DEPTH(16),.DATA_WIDTH(112),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.LAST_ENABLE(0),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1),.FRAME_FIFO(0)) actual_timestamp_fifo(
 .s_clk(mac_clk),.s_rst(rst),.s_axis_tdata({mac_stamp_tag,mac_stamp}),.s_axis_tkeep(1'b1),.s_axis_tvalid(mac_stamp_valid),.s_axis_tready(mac_stamp_ready),
 .s_axis_tlast(1'b1),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
 .m_clk(clk),.m_rst(rst),.m_axis_tdata({link_m_cpl_tag,link_m_cpl_ts}),.m_axis_tvalid(link_m_cpl_valid),.m_axis_tready(link_m_cpl_ready),
 .m_axis_tkeep(),.m_axis_tlast(),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(),
 .s_pause_req(1'b0),.m_pause_req(1'b0),.s_pause_ack(),.m_pause_ack(),
 .s_status_depth(),.s_status_depth_commit(),.s_status_overflow(completion_overflow),.s_status_bad_frame(),.s_status_good_frame(),
 .m_status_depth(),.m_status_depth_commit(),.m_status_overflow(),.m_status_bad_frame(),.m_status_good_frame());
'''


def frames(output):
    result=[];data=None;tags=[]
    for line in output.splitlines():
        if line.startswith('ACTUAL_MAC_SFD '):tags.append(int(line.split()[1],16))
        if not line.startswith('XGMII_TX '):continue
        _,word,ctrl=line.split();d=int(word,16).to_bytes(8,'little');c=int(ctrl,16)
        for i,b in enumerate(d):
            if (c>>i)&1:
                if b==0xfb:
                    if data is not None:raise ValueError('nested real MAC START')
                    data=bytearray()
                elif b==0xfd:
                    if data is None or data[:7]!=b'\x55'*6+b'\xd5':raise ValueError('real MAC preamble/SFD')
                    frame=bytes(data[7:]);data=None
                    if len(frame)<64 or binascii.crc32(frame[:-4]).to_bytes(4,'little')!=frame[-4:]:
                        raise ValueError('real MAC frame length/FCS')
                    result.append(frame[:-4])
                elif data is not None:raise ValueError('unexpected real MAC control/error within frame')
            elif data is not None:data.append(b)
    if data is not None:raise ValueError('truncated real MAC frame')
    if len(tags)!=len(result):raise ValueError('actual SFD receipt/frame count differs')
    return list(zip(tags,result))
