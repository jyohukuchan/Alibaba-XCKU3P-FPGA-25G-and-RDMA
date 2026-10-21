# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual board TX queue + cut-through CDC, not a larger invented test FIFO.

Keep old small-packet fixtures immutable. Bind the real config/parameter
propagation and instantiate Corundum's unchanged tx_fifo and CDC modules.
The RNIC/host/PHY are not thereby hardware- or full-board-qualified.
"""
from pathlib import Path
import re
import atomic_mac_wire_fixture as old

ROOT = old.ROOT
COMMON = ROOT/'external/corundum/fpga/common/rtl'
SOURCES = [COMMON/'tx_fifo.v', *[old.AXIS/n for n in ['axis_fifo_adapter.v', 'axis_fifo.v', 'axis_demux.v']]]
INPUTS = [ROOT/'fpga/config_25g.tcl', ROOT/'fpga/fpga_as02mc04_25g_cdc.v',
          *[COMMON/n for n in ['mqnic_core_pcie_us.v', 'mqnic_core_pcie.v', 'mqnic_core.v',
                              'mqnic_interface.v', 'mqnic_port_tx.v']], *SOURCES]


def parameters():
    config = INPUTS[0].read_text()
    for name, value in [('TX_FIFO_DEPTH', 32768), ('MAX_TX_SIZE', 9214), ('PORTS_PER_IF', 1),
                        ('AXIS_ETH_TX_PIPELINE', 0), ('AXIS_ETH_TX_FIFO_PIPELINE', 2)]:
        if len(re.findall(r'dict set params '+name+r' "'+str(value)+'"', config)) != 1:
            raise ValueError('board configuration changed: '+name)
    wrapper = INPUTS[1].read_text()
    for text in ['parameter XGMII_DATA_WIDTH = 64;', 'parameter AXIS_ETH_SYNC_DATA_WIDTH_DOUBLE = 1,',
                 'parameter AXIS_ETH_DATA_WIDTH = XGMII_DATA_WIDTH;',
                 'parameter AXIS_ETH_SYNC_DATA_WIDTH = AXIS_ETH_DATA_WIDTH*(AXIS_ETH_SYNC_DATA_WIDTH_DOUBLE ? 2 : 1);',
                 '.TX_FIFO_DEPTH(TX_FIFO_DEPTH)', '.AXIS_ETH_SYNC_DATA_WIDTH(AXIS_ETH_SYNC_DATA_WIDTH)',
                 '.AXIS_ETH_TX_FIFO_PIPELINE(AXIS_ETH_TX_FIFO_PIPELINE)']:
        if text not in wrapper:
            raise ValueError('board width/config propagation changed: '+text)
    for name, tokens in {
        'mqnic_core_pcie_us.v': ['.TX_FIFO_DEPTH(TX_FIFO_DEPTH)', '.AXIS_SYNC_DATA_WIDTH(AXIS_ETH_SYNC_DATA_WIDTH)',
                                '.AXIS_IF_DATA_WIDTH(AXIS_ETH_IF_DATA_WIDTH)', '.AXIS_TX_FIFO_PIPELINE(AXIS_ETH_TX_FIFO_PIPELINE)',
                                'parameter AXIS_ETH_IF_DATA_WIDTH = AXIS_ETH_SYNC_DATA_WIDTH*2**$clog2(PORTS_PER_IF)'],
        'mqnic_core_pcie.v': ['.TX_FIFO_DEPTH(TX_FIFO_DEPTH)', '.AXIS_SYNC_DATA_WIDTH(AXIS_SYNC_DATA_WIDTH)',
                             '.AXIS_IF_DATA_WIDTH(AXIS_IF_DATA_WIDTH)', '.AXIS_TX_FIFO_PIPELINE(AXIS_TX_FIFO_PIPELINE)'],
        'mqnic_core.v': ['.TX_FIFO_DEPTH(TX_FIFO_DEPTH)', '.AXIS_SYNC_DATA_WIDTH(AXIS_SYNC_DATA_WIDTH)',
                        '.AXIS_IF_DATA_WIDTH(AXIS_IF_DATA_WIDTH)', '.AXIS_TX_FIFO_PIPELINE(AXIS_TX_FIFO_PIPELINE)'],
        'mqnic_interface.v': ['tx_fifo #(', '.FIFO_DEPTH(TX_FIFO_DEPTH)', '.PORTS(PORTS)',
                             '.S_DATA_WIDTH(AXIS_IF_DATA_WIDTH)', '.M_DATA_WIDTH(AXIS_SYNC_DATA_WIDTH)',
                             '.RAM_PIPELINE(AXIS_TX_FIFO_PIPELINE)'],
        'mqnic_port_tx.v': ['.DEPTH(AXIS_SYNC_KEEP_WIDTH*32)', '.S_DATA_WIDTH(AXIS_SYNC_DATA_WIDTH)',
                           '.M_DATA_WIDTH(AXIS_DATA_WIDTH)', '.RAM_PIPELINE(0)', '.FRAME_FIFO(1)',
                           '.DROP_OVERSIZE_FRAME(0)', '.DROP_BAD_FRAME(0)', '.DROP_WHEN_FULL(0)',
                           '.MARK_WHEN_FULL(0)', '.PAUSE_ENABLE(1)', '.FRAME_PAUSE(1)'],
        'tx_fifo.v': ['.DEPTH(FIFO_DEPTH)', '.RAM_PIPELINE(RAM_PIPELINE)', '.FRAME_FIFO(1)',
                      '.DROP_OVERSIZE_FRAME(1)', '.DROP_BAD_FRAME(USER_ENABLE)'],
    }.items():
        text = (COMMON/name).read_text()
        if any(token not in text for token in tokens):
            raise ValueError('actual board FIFO parameter trace changed: '+name)
    return dict(synchronous_FIFO_bytes=32768, synchronous_data_bits=128, synchronous_RAM_pipeline=2,
                CDC_FIFO_bytes=512, CDC_data_in_bits=128, CDC_data_out_bits=64, CDC_RAM_pipeline=0,
                CDC_drop_oversize=False, CDC_drop_bad_frame=False, board_MAX_TX_SIZE=9214,
                core_period_ns=4, MAC_period_ns=2.56, physical_endpoints_modeled=True)


def replace_link(text):
    parameters()
    start = text.index('axis_async_fifo_adapter #(.DEPTH(1024)')
    end = text.index('axis_xgmii_tx_64 #(', start)
    return text[:start]+BOARD_FIFO+text[end:]


BOARD_FIFO = r'''
// Board's real 32KiB synchronous frame queue BEFORE its small CDC FIFO.
wire [127:0] board_tx_data;wire [15:0] board_tx_keep;
wire board_tx_valid,board_tx_ready,board_tx_last;wire [16:0] board_tx_user;
wire board_tx_overflow,board_tx_bad_frame;
always @(posedge clk)if(!rst && (board_tx_overflow || board_tx_bad_frame))
 $fatal(1,"actual board synchronous TX FIFO error overflow%0d bad%0d",board_tx_overflow,board_tx_bad_frame);
tx_fifo #(.FIFO_DEPTH(32768),.PORTS(1),.S_DATA_WIDTH(128),.S_KEEP_ENABLE(1),.S_KEEP_WIDTH(16),
 .M_DATA_WIDTH(128),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(16),.ID_ENABLE(1),.ID_WIDTH(1),
 .S_DEST_WIDTH(1),.M_DEST_WIDTH(1),.USER_ENABLE(1),.USER_WIDTH(17),.RAM_PIPELINE(2)) actual_board_tx_fifo(
 .clk(clk),.rst(rst),.s_axis_tdata(link_s_data),.s_axis_tkeep(link_s_keep),
 .s_axis_tvalid(link_s_valid),.s_axis_tready(link_s_ready),.s_axis_tlast(link_s_last),
 .s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(link_s_user),
 .m_axis_tdata(board_tx_data),.m_axis_tkeep(board_tx_keep),.m_axis_tvalid(board_tx_valid),
 .m_axis_tready(board_tx_ready),.m_axis_tlast(board_tx_last),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(board_tx_user),
 .status_depth(),.status_depth_commit(),.status_overflow(board_tx_overflow),
 .status_bad_frame(board_tx_bad_frame),.status_good_frame());
// Exact mqnic_port_tx CDC policy: stream a frame through a 32-beat FIFO.
axis_async_fifo_adapter #(.DEPTH(16*32),.S_DATA_WIDTH(128),.S_KEEP_ENABLE(1),.S_KEEP_WIDTH(16),
 .M_DATA_WIDTH(64),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(8),.USER_ENABLE(1),.USER_WIDTH(17),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.RAM_PIPELINE(0),.FRAME_FIFO(1),
 .USER_BAD_FRAME_VALUE(17'd1),.USER_BAD_FRAME_MASK(17'd1),.DROP_OVERSIZE_FRAME(0),.DROP_BAD_FRAME(0),
 .DROP_WHEN_FULL(0),.MARK_WHEN_FULL(0),.PAUSE_ENABLE(1),.FRAME_PAUSE(1)) actual_tx_fifo(
 .s_clk(clk),.s_rst(rst),.s_axis_tdata(board_tx_data),.s_axis_tkeep(board_tx_keep),
 .s_axis_tvalid(board_tx_valid),.s_axis_tready(board_tx_ready),.s_axis_tlast(board_tx_last),
 .s_axis_tuser(board_tx_user),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),
 .m_clk(mac_clk),.m_rst(rst),.m_axis_tdata(mac_axis_data),.m_axis_tkeep(mac_axis_keep),
 .m_axis_tvalid(mac_axis_valid),.m_axis_tready(mac_axis_ready),.m_axis_tlast(mac_axis_last),
 .m_axis_tuser(mac_axis_user),.m_axis_tid(),.m_axis_tdest(),
 .s_pause_req(1'b0),.m_pause_req(1'b0),.s_pause_ack(),.m_pause_ack(),
 .s_status_depth(),.s_status_depth_commit(),.s_status_overflow(tx_overflow),.s_status_bad_frame(tx_bad_frame),.s_status_good_frame(),
 .m_status_depth(),.m_status_depth_commit(),.m_status_overflow(),.m_status_bad_frame(),.m_status_good_frame());
// Read-only peer observation: ACKs must not precede real XGMII TERM.
integer board_wire_eofs=0,board_wire_lane;
reg board_wire_in_frame=0;
always @(posedge mac_clk)begin
 if(rst)begin board_wire_eofs=0;board_wire_in_frame=0;end
 else for(board_wire_lane=0;board_wire_lane<8;board_wire_lane=board_wire_lane+1)begin
  if(xgmii_txc[board_wire_lane] && xgmii_txd[board_wire_lane*8+:8]==8'hfb)begin
   if(board_wire_in_frame)$fatal(1,"nested actual board MAC START");
   board_wire_in_frame=1;
  end
  if(xgmii_txc[board_wire_lane] && xgmii_txd[board_wire_lane*8+:8]==8'hfd)begin
   if(!board_wire_in_frame)$fatal(1,"actual board MAC TERM without START");
   board_wire_in_frame=0;board_wire_eofs=board_wire_eofs+1;
   $display("ACTUAL_BOARD_WIRE_EOF %0d",board_wire_eofs);
  end
 end
end
'''
