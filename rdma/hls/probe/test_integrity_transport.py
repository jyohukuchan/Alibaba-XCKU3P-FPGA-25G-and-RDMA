#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite generated-RTL integration test; no FPGA/network access."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "rdma/host"))
sys.path.insert(0, str(ROOT / "rdma/tests"))
from rocev2_wire import decode_ethernet, icrc_ipv4, internet_checksum, write_only_frame
from test_icrc_rtl import words
import test_wire as observed

TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0;
always #2 clk=~clk;
reg rst=0;
reg [127:0] sd=0;
reg [15:0] sk=0;
reg sv=0, sl=0, su=0;
wire sr;
wire [127:0] md;
wire [15:0] mk;
wire mv,ml;
reg mr=0;
reg qvalid=0,cvalid=0;
wire qready,cready;
wire [95:0] wc;
wire wcv;
reg wcr=0;
wire [511:0] wd;
wire [63:0] wk;
wire wv,wl;
reg wr=0;
wire [87:0] debug_data;
wire debug_valid;
reg debug_ready=0;
wire [31:0] rx_good,rx_bad,tx_good,tx_bad,overflows,rx_words,tx_words,psn_drop,retrans;
wire read_cmd_valid,ack_valid;
rocev2_integrity_transport dut (
 .clk(clk),.rst(rst),.s_axis_rx_tdata(sd),.s_axis_rx_tkeep(sk),.s_axis_rx_tvalid(sv),.s_axis_rx_tready(sr),.s_axis_rx_tlast(sl),.s_axis_rx_tuser(su),
 .m_axis_tx_tdata(md),.m_axis_tx_tkeep(mk),.m_axis_tx_tvalid(mv),.m_axis_tx_tready(mr),.m_axis_tx_tlast(ml),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h123456,24'h123456,24'd2,32'd3}),.s_axis_qp_tvalid(qvalid),.s_axis_qp_tready(qready),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(cvalid),.s_axis_conn_tready(cready),
 .s_axis_sq_tdata(240'd0),.s_axis_sq_tvalid(1'b0),.s_axis_sq_tready(),
 .m_axis_ack_tdata(),.m_axis_ack_tvalid(ack_valid),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(wc),.m_axis_mem_write_cmd_tvalid(wcv),.m_axis_mem_write_cmd_tready(wcr),
 .m_axis_mem_read_cmd_tdata(),.m_axis_mem_read_cmd_tvalid(read_cmd_valid),.m_axis_mem_read_cmd_tready(1'b1),
 .m_axis_mem_write_tdata(wd),.m_axis_mem_write_tkeep(wk),.m_axis_mem_write_tvalid(wv),.m_axis_mem_write_tready(wr),.m_axis_mem_write_tlast(wl),
 .s_axis_mem_read_tdata(512'd0),.s_axis_mem_read_tkeep(64'd0),.s_axis_mem_read_tvalid(1'b0),.s_axis_mem_read_tready(),.s_axis_mem_read_tlast(1'b0),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(debug_data),.m_axis_debug_tvalid(debug_valid),.m_axis_debug_tready(debug_ready),
 .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(rx_words),.core_tx_word_count(tx_words),
 .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),.tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflows));
reg [145:0] stimulus[0:INPUT_COUNT-1];
reg [31:0] rng=32'h1234abcd;
integer cycle=0,index=0,accepted=0,commands=0,data_frames=0,net_frames=0,quiet=0,b;
integer tx_stalls=0,cmd_stalls=0,data_stalls=0;
integer checked_beats=0,core_input_beats=0;
integer crc_removed=0,ip_parsed=0,ip_output=0,udp_output=0;
reg took_input=0,took_q=0,took_c=0,q_done=0,c_done=0;
reg net_stalled=0,cmd_stalled=0,data_stalled=0,dbg_stalled=0;
reg [144:0] saved_net;
reg [95:0] saved_cmd;
reg [576:0] saved_data;
reg [87:0] saved_debug;
initial begin
 // Drive an actual reset edge before the first clock. A declaration-time
 // constant alone does not reliably trigger generated always@* inversion.
 #1 rst=1;
 $readmemh("input.hex",stimulus);
 repeat(8) @(negedge clk);
 rst=0;qvalid=1;cvalid=1;
end
always @(negedge clk) begin
 if(!rst) begin
  rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  if(took_q) begin qvalid=0;q_done=1;end
  if(took_c) begin cvalid=0;c_done=1;end
  mr=cycle>2000 && rng[2:0]!=0;
  wcr=cycle>1000 && rng[5:3]!=0;
  wr=cycle>1500 && rng[8:6]!=0;
  debug_ready=cycle>700 && rng[10:9]!=0;
  if(!sv || took_input) begin
   sv=0;
   if(q_done && c_done && cycle>128 && index<INPUT_COUNT && rng[13:11]!=0) begin
    {su,sl,sk,sd}=stimulus[index];sv=1;index=index+1;
   end
  end
 end
end
always @(posedge clk) begin
 if(!rst) begin
  cycle=cycle+1;took_input=sv && sr;took_q=qvalid && qready;took_c=cvalid && cready;
  if(took_input) accepted=accepted+1;
  if(dut.checked_valid && dut.checked_ready) checked_beats=checked_beats+1;
  if(dut.core_rx_valid && dut.core_rx_ready) core_input_beats=core_input_beats+1;
  if(dut.transport.rx_crc2ipFifo_U.if_empty_n && dut.transport.rx_crc2ipFifo_U.if_read) crc_removed=crc_removed+1;
  if(dut.transport.rx_process2dropFifo_U.if_empty_n && dut.transport.rx_process2dropFifo_U.if_read) ip_parsed=ip_parsed+1;
  if(dut.transport.rx_ip2udpFifo_U.if_empty_n && dut.transport.rx_ip2udpFifo_U.if_read) ip_output=ip_output+1;
  if(dut.transport.rx_udp2ibFifo_U.if_empty_n && dut.transport.rx_udp2ibFifo_U.if_read) udp_output=udp_output+1;
  if(net_stalled && (!mv || {ml,mk,md}!==saved_net)) $fatal(1,"network AXIS changed under stall");
  if(cmd_stalled && (!wcv || wc!==saved_cmd)) $fatal(1,"memory command changed under stall");
  if(data_stalled && (!wv || {wl,wk,wd}!==saved_data)) $fatal(1,"memory data changed under stall");
  if(dbg_stalled && (!debug_valid || debug_data!==saved_debug)) $fatal(1,"debug AXIS changed under stall");
  net_stalled=mv && !mr;cmd_stalled=wcv && !wcr;data_stalled=wv && !wr;dbg_stalled=debug_valid && !debug_ready;
  saved_net={ml,mk,md};saved_cmd=wc;saved_data={wl,wk,wd};saved_debug=debug_data;
  if(net_stalled) tx_stalls=tx_stalls+1;
  if(cmd_stalled) cmd_stalls=cmd_stalls+1;
  if(data_stalled) data_stalls=data_stalls+1;
  if(read_cmd_valid!==1'b0 || ack_valid!==1'b0) $fatal(1,"unexpected/unknown local read or initiator-completion event");
  if(wcv && wcr) begin
   if(commands>=2 || wc[47:0]!==48'h615eb7c6b000+commands*64 || wc[75:48]!==28'd64)
    $fatal(1,"unexpected memory write command %h index=%0d",wc,commands);
   commands=commands+1;
  end
  if(wv && wr) begin
   if(data_frames>=2 || wk!==64'hffffffffffffffff || !wl) $fatal(1,"memory data shape/error frame leaked");
   for(b=0;b<64;b=b+1)
    if(wd[b*8+:8]!==(((b*131)^(b>>8)^data_frames^8'h5a)&32'hff))
     $fatal(1,"memory payload mismatch frame=%0d byte=%0d",data_frames,b);
   data_frames=data_frames+1;
  end
  if(mv && mr) begin
   $display("OUT %032h %04h %b",md,mk,ml);
   if(ml) net_frames=net_frames+1;
  end
  if(overflows!==32'd0 || psn_drop!==32'd0 || retrans!==32'd0 || tx_bad!==32'd0) $fatal(1,"unexpected/unknown transport/integrity errors");
  if(accepted==INPUT_COUNT && commands==2 && data_frames==2 && net_frames==2 && rx_good==2 && rx_bad==1 && tx_good==2) quiet=quiet+1;
  else quiet=0;
  if(quiet==100) begin
   if(rx_words!==32'd4 || tx_words!==32'd2) $fatal(1,"unexpected core word counters %0d %0d",rx_words,tx_words);
   if(tx_stalls==0 || cmd_stalls==0 || data_stalls==0) $fatal(1,"backpressure not exercised");
   $display("RESULT {\"cycles\":%0d,\"verified_writes\":2,\"verified_bytes\":128,\"rx_rejected_crc_frames\":1,\"wire_acks\":2,\"network_stall_cycles\":%0d,\"command_stall_cycles\":%0d,\"data_stall_cycles\":%0d}",cycle,tx_stalls,cmd_stalls,data_stalls);
   $finish;
  end
  if(cycle>6000) begin
   $display("STAGES checked=%0d core_input=%0d qp_done=%b conn_done=%b",checked_beats,core_input_beats,q_done,c_done);
   $display("DATAFLOW crc_removed=%0d ip_parsed=%0d ip_output=%0d udp_output=%0d ip_meta_empty_n=%b udp_meta_empty_n=%b",crc_removed,ip_parsed,ip_output,udp_output,dut.transport.rx_ip2udpMetaFifo_empty_n,dut.transport.rx_ipUdpMetaFifo_empty_n);
   $display("CRC_INPUT empty_n=%b count=%0d read=%b output_write=%b state=%0d first_fsm=%b second_fsm=%b block0=%b block1=%b",
    dut.transport.s_axis_rx_data_internal_U.if_empty_n,dut.transport.s_axis_rx_data_internal_U.if_num_data_valid,
    dut.transport.s_axis_rx_data_internal_U.if_read,dut.transport.rx_crc2ipFifo_U.if_write,
    dut.transport.extract_icrc_512_0_U0.ei_state,dut.transport.extract_icrc_512_0_U0.ap_CS_iter0_fsm,
    dut.transport.extract_icrc_512_0_U0.ap_CS_iter1_fsm,
    dut.transport.extract_icrc_512_0_U0.ap_block_state1_pp0_stage0_iter0,
    dut.transport.extract_icrc_512_0_U0.ap_block_state2_pp0_stage0_iter1);
   $display("CONVERTER input_valid=%b input_ready=%b start=%b fsm0=%b fsm1=%b readfifo_write=%b rst=%b",
    dut.transport.s_axis_rx_data_TVALID,dut.transport.s_axis_rx_data_TREADY,
    dut.transport.convert_axis_to_net_axis_512_U0.ap_start,
    dut.transport.convert_axis_to_net_axis_512_U0.ap_CS_iter0_fsm,
    dut.transport.convert_axis_to_net_axis_512_U0.ap_CS_iter1_fsm,
    dut.transport.s_axis_rx_data_internal_U.if_write,dut.transport.ap_rst_n_inv);
   $fatal(1,"deadline inputs=%0d cmd=%0d data=%0d net=%0d good=%0d bad=%0d core_rx=%0d",accepted,commands,data_frames,net_frames,rx_good,rx_bad,rx_words);
  end
 end
end
endmodule
'''


TB_TX = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0;
always #2 clk=~clk;
reg rst=0;
reg [127:0] sd=0;
reg [15:0] sk=0;
reg sv=0,sl=0,su=0,mr=0,qvalid=0,cvalid=0,sqvalid=0;
wire sr,mv,ml,qready,cready,sqready;
wire [127:0] md;
wire [15:0] mk;
wire [95:0] rc;
wire rcv;
reg rcr=0;
reg [511:0] read_data=0;
reg read_valid=0;
wire read_ready;
wire [39:0] ack_data;
wire ack_valid;
wire unexpected_wcmd,unexpected_wdata;
wire [31:0] rx_good,rx_bad,tx_good,tx_bad,overflows,rx_words,tx_words,psn_drop,retrans;
wire [127:0] ip_rd,ip_td;
wire [15:0] ip_rk,ip_tk;
wire ip_rv,ip_rr,ip_rl,ip_ru,ip_tv,ip_tr,ip_tl;
wire [31:0] eth_guard_drop,eth_rx_frames;
generate if(ETHERNET_VALUE) begin : ethernet
 rocev2_ethernet_rx ingress (
  .clk(clk),.rst(rst),.enable(1'b1),.local_mac(48'h8af3fbb97531),.peer_mac(48'hb8830367c5d0),
  .local_ip(32'hc6120b02),.peer_ip(32'hc6120b01),.local_qpn(24'd2),
  .s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser({96'd0,su}),
  .m_axis_host_tdata(),.m_axis_host_tkeep(),.m_axis_host_tvalid(),.m_axis_host_tready(1'b1),.m_axis_host_tlast(),.m_axis_host_tuser(),
  .m_axis_roce_tdata(ip_rd),.m_axis_roce_tkeep(ip_rk),.m_axis_roce_tvalid(ip_rv),.m_axis_roce_tready(ip_rr),.m_axis_roce_tlast(ip_rl),.m_axis_roce_tuser(ip_ru),
  .host_frame_count(),.roce_frame_count(eth_rx_frames),.drop_frame_count(eth_guard_drop),.overflow_count());
 rocev2_ethernet_tx egress (
  .clk(clk),.rst(rst),.local_mac(48'h8af3fbb97531),.peer_mac(48'hb8830367c5d0),
  .s_axis_roce_tdata(ip_td),.s_axis_roce_tkeep(ip_tk),.s_axis_roce_tvalid(ip_tv),.s_axis_roce_tready(ip_tr),.s_axis_roce_tlast(ip_tl),
  .s_axis_host_tdata(128'd0),.s_axis_host_tkeep(16'd0),.s_axis_host_tvalid(1'b0),.s_axis_host_tready(),.s_axis_host_tlast(1'b0),.s_axis_host_tuser(17'd0),
  .m_axis_tdata(md),.m_axis_tkeep(mk),.m_axis_tvalid(mv),.m_axis_tready(mr),.m_axis_tlast(ml),.m_axis_tuser(),
  .s_axis_cpl_tag(16'd0),.s_axis_cpl_ts(96'd0),.s_axis_cpl_valid(1'b0),.s_axis_cpl_ready(),
  .m_axis_host_cpl_tag(),.m_axis_host_cpl_ts(),.m_axis_host_cpl_valid(),.m_axis_host_cpl_ready(1'b1),
  .roce_frame_count(),.roce_completion_count());
end else begin : ip_only
 assign ip_rd=sd; assign ip_rk=sk; assign ip_rv=sv; assign sr=ip_rr; assign ip_rl=sl; assign ip_ru=su;
 assign md=ip_td; assign mk=ip_tk; assign mv=ip_tv; assign ip_tr=mr; assign ml=ip_tl;
 assign eth_guard_drop=0; assign eth_rx_frames=0;
end endgenerate
rocev2_integrity_transport dut (
 .clk(clk),.rst(rst),.s_axis_rx_tdata(ip_rd),.s_axis_rx_tkeep(ip_rk),.s_axis_rx_tvalid(ip_rv),.s_axis_rx_tready(ip_rr),.s_axis_rx_tlast(ip_rl),.s_axis_rx_tuser(ip_ru),
 .m_axis_tx_tdata(ip_td),.m_axis_tx_tkeep(ip_tk),.m_axis_tx_tvalid(ip_tv),.m_axis_tx_tready(ip_tr),.m_axis_tx_tlast(ip_tl),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h123456,24'h123456,24'd2,32'd3}),.s_axis_qp_tvalid(qvalid),.s_axis_qp_tready(qready),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(cvalid),.s_axis_conn_tready(cready),
 .s_axis_sq_tdata({32'd0,32'd64,64'hfedcba9876543210,64'h4000,4'd0,1'b1,1'b0,10'd2,32'd10}),.s_axis_sq_tvalid(sqvalid),.s_axis_sq_tready(sqready),
 .m_axis_ack_tdata(ack_data),.m_axis_ack_tvalid(ack_valid),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(),.m_axis_mem_write_cmd_tvalid(unexpected_wcmd),.m_axis_mem_write_cmd_tready(1'b1),
 .m_axis_mem_read_cmd_tdata(rc),.m_axis_mem_read_cmd_tvalid(rcv),.m_axis_mem_read_cmd_tready(rcr),
 .m_axis_mem_write_tdata(),.m_axis_mem_write_tkeep(),.m_axis_mem_write_tvalid(unexpected_wdata),.m_axis_mem_write_tready(1'b1),.m_axis_mem_write_tlast(),
 .s_axis_mem_read_tdata(read_data),.s_axis_mem_read_tkeep(64'hffffffffffffffff),.s_axis_mem_read_tvalid(read_valid),.s_axis_mem_read_tready(read_ready),.s_axis_mem_read_tlast(1'b1),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(rx_words),.core_tx_word_count(tx_words),
 .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),.tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflows));
reg [145:0] stimulus[0:INPUT_COUNT-1];
reg [31:0] rng=32'h68ab2134;
integer cycle=0,index=0,accepted=0,commands=0,memory_beats=0,net_frames=0,ack_events=0,quiet=0,b,tx_end=0;
integer network_stalls=0,command_stalls=0;
reg took_input=0,took_q=0,took_c=0,took_sq=0,took_read=0;
reg q_done=0,c_done=0,sq_done=0,net_stalled=0,cmd_stalled=0;
reg [144:0] saved_net;
reg [95:0] saved_cmd;
initial begin
 #1 rst=1;
 $readmemh("input.hex",stimulus);
 for(b=0;b<64;b=b+1) read_data[b*8+:8]=((b*131)^(b>>8)^8'h5a)&32'hff;
 repeat(8) @(negedge clk);
 rst=0;qvalid=1;cvalid=1;
end
always @(negedge clk) begin
 if(!rst) begin
  rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  if(took_q) begin qvalid=0;q_done=1;end
  if(took_c) begin cvalid=0;c_done=1;end
  if(took_sq) begin sqvalid=0;sq_done=1;end
  if(q_done && c_done && cycle>2300 && !sq_done) sqvalid=1;
  mr=cycle>2800 && rng[2:0]!=0;
  rcr=cycle>2400 && rng[5:3]!=0;
  if(took_read) read_valid=0;
  else if(commands==1 && memory_beats==0) read_valid=1;
  if(!sv || took_input) begin
   sv=0;
   if(net_frames==1 && cycle>tx_end+20 && index<INPUT_COUNT && rng[8:6]!=0) begin
    {su,sl,sk,sd}=stimulus[index];sv=1;index=index+1;
   end
  end
 end
end
always @(posedge clk) begin
 if(!rst) begin
  cycle=cycle+1;took_input=sv && sr;took_q=qvalid && qready;took_c=cvalid && cready;took_sq=sqvalid && sqready;took_read=read_valid && read_ready;
  if(took_input) accepted=accepted+1;
  if(net_stalled && (!mv || {ml,mk,md}!==saved_net)) $fatal(1,"network data changed under stall");
  if(cmd_stalled && (!rcv || rc!==saved_cmd)) $fatal(1,"read command changed under stall");
  net_stalled=mv && !mr;cmd_stalled=rcv && !rcr;saved_net={ml,mk,md};saved_cmd=rc;
  if(net_stalled) network_stalls=network_stalls+1;
  if(cmd_stalled) command_stalls=command_stalls+1;
  if(rcv && rcr) begin
   if(commands!=0 || rc[47:0]!==48'h4000 || rc[75:48]!==28'd64) $fatal(1,"wrong memory read command %h",rc);
   commands=commands+1;
  end
  if(took_read) memory_beats=memory_beats+1;
  if(unexpected_wcmd || unexpected_wdata) $fatal(1,"unexpected memory write from ACK");
  if(mv && mr) begin
   $display("OUT %032h %04h %b",md,mk,ml);
   if(ml) begin net_frames=net_frames+1;tx_end=cycle;end
  end
  if(ack_valid) begin
   if(ack_data[0]!==1'b1 || ack_data[10:1]!==10'd2 || ack_data[34:11]!==24'h123456)
    $fatal(1,"wrong successful WRITE ACK metadata %h",ack_data);
   ack_events=ack_events+1;
  end
  if(overflows!==0 || psn_drop!==0 || retrans!==0 || tx_bad!==0 ||
     (^rx_bad)===1'bx || rx_bad>32'dETHERNET_VALUE) $fatal(1,"unexpected transport/integrity errors");
  if(sq_done && accepted==INPUT_COUNT && commands==1 && memory_beats==1 && net_frames==1 && ack_events==1 && rx_good==1 && tx_good==1) quiet=quiet+1;
  else quiet=0;
  if(quiet==100) begin
   if(network_stalls==0 || command_stalls==0) $fatal(1,"backpressure not exercised");
   if(rx_words!==1 || rx_bad!==32'dETHERNET_VALUE || eth_guard_drop!==32'dETHERNET_VALUE || eth_rx_frames!==32'dETHERNET_VALUE*2)
    $fatal(1,"guard/ICRC rejection did not isolate HLS input words=%0d guard=%0d routed=%0d",rx_words,eth_guard_drop,eth_rx_frames);
   $display("RESULT {\"cycles\":%0d,\"verified_transmit_writes\":1,\"verified_transmit_bytes\":64,\"consumed_success_ack\":1,\"network_stall_cycles\":%0d,\"command_stall_cycles\":%0d,\"core_rx_words\":%0d,\"peer_qp_rejected_frames\":%0d,\"icrc_rejected_frames\":%0d}",cycle,network_stalls,command_stalls,rx_words,eth_guard_drop,rx_bad);
   $finish;
  end
  if(cycle>6000) $fatal(1,"deadline sq=%b cmd=%0d memory=%0d net=%0d ack=%0d rx=%0d tx=%0d",sq_done,commands,memory_beats,net_frames,ack_events,rx_words,tx_words);
 end
end
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hls-build", type=pathlib.Path, required=True)
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument("--direction", choices=("rx", "tx"), default="rx")
    parser.add_argument("--ethernet", action="store_true", help="TX WRITE + peer/QP guarded Ethernet ACK path")
    args = parser.parse_args()
    if args.ethernet and args.direction != "tx":
        parser.error("Ethernet ingress currently permits ACKs only; use --direction tx")
    rtl = args.hls_build.resolve() / "solution1/syn/verilog"
    if not (rtl / "rocev2_top.v").is_file():
        parser.error("missing generated rocev2_top.v; run the pinned synthesis probe first")
    packets = []
    for sequence in range(2):
        p = write_only_frame(source_mac="02:00:00:00:00:01", destination_mac="02:00:00:00:00:02",
                             source_ip="198.18.11.1", destination_ip="198.18.11.2", udp_source_port=52484,
                             destination_qpn=2, psn=0x123456 + sequence, rkey=0xFEDCBA98,
                             remote_address=0x615EB7C6B000 + sequence*64,
                             payload=bytes(((i*131)^(i>>8)^sequence^0x5a)&255 for i in range(64)))[14:]
        packets.append(p)
    damaged = bytearray(packets[1]); damaged[60] ^= 1
    input_words = words(packets[0]) + words(bytes(damaged)) + words(packets[1])
    if args.direction=="tx":
        ack = bytearray(observed.CX_ACK[14:])
        ack[33:36] = (2).to_bytes(3,"big")
        ack[37:40] = (0x123456).to_bytes(3,"big")
        ack[40:44] = bytes.fromhex("1f000001")
        ack[-4:] = icrc_ipv4(bytes(ack))
        input_words = words(bytes(ack))
        if args.ethernet:
            header = observed.CX_ACK[:14]
            wrong_qp = bytearray(ack)
            wrong_qp[33:36] = (99).to_bytes(3, "big")
            wrong_qp[-4:] = icrc_ipv4(wrong_qp)
            corrupt = bytearray(ack); corrupt[-1] ^= 1
            input_words = words(header + wrong_qp) + words(header + corrupt) + words(header + ack)
    with tempfile.TemporaryDirectory(prefix="as02-integrity-transport-") as directory:
        path = pathlib.Path(directory)
        (path / "tb.v").write_text((TB if args.direction=="rx" else TB_TX)
                                  .replace("INPUT_COUNT", str(len(input_words)))
                                  .replace("ETHERNET_VALUE", str(int(args.ethernet))))
        (path / "input.hex").write_text("".join(f"{word:037x}\n" for word in input_words))
        for initial_data in rtl.glob("*.dat"):
            shutil.copy2(initial_data,path / initial_data.name)
        # HLS emits generic behavioral memories here, not a hardware image.
        sources = list(rtl.glob("*.v")) + [ROOT / "rdma/rtl/rocev2_ipv4_icrc.v",
                  ROOT / "rdma/rtl/rocev2_tx_padding.v",
                  ROOT / "rdma/rtl/rocev2_integrity_transport.v",
                  ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_adapter.v",
                  ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_fifo.v",
                  ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_register.v",
                  ROOT / "external/corundum/fpga/lib/eth/rtl/lfsr.v"]
        # Include both application blocks for TX's elaborated generate branch.
        sources += [ROOT / "rdma/rtl/rocev2_ethernet_rx.v", ROOT / "rdma/rtl/rocev2_ethernet_tx.v"]
        sources += [ROOT / "external/corundum/fpga/lib/eth/rtl" / name for name in ("eth_axis_rx.v", "eth_axis_tx.v")]
        sources += [ROOT / "external/corundum/fpga/lib/axis/rtl" / name for name in ("axis_arb_mux.v", "arbiter.v", "priority_encoder.v")]
        compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                   str(path / "tb.v"), *(str(source) for source in sources)],
                                  capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        simulated = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path,
                                   capture_output=True, text=True, timeout=120)
        print(simulated.stdout)
        if "ERROR:" in simulated.stdout:
            raise RuntimeError("RTL simulator emitted an error (including missing memory initialization)")
        if simulated.returncode:
            raise RuntimeError(simulated.stderr or "RTL simulation failed")
        acknowledgements, current = [], bytearray()
        for line in simulated.stdout.splitlines():
            if line.startswith("OUT "):
                _, data, keep, last = line.split()
                beat = int(data,16).to_bytes(16,"little")
                current.extend(beat[i] for i in range(16) if int(keep,16) & (1<<i))
                if last=="1":
                    acknowledgements.append(bytes(current));current.clear()
        if len(acknowledgements)!=(2 if args.direction=="rx" else 1) or current:
            raise ValueError("missing/extra complete ACK frames")
        for sequence, output in enumerate(acknowledgements):
            if args.ethernet:
                expected_header = bytes.fromhex("b8830367c5d08af3fbb975310800")
                if output[:14] != expected_header:
                    raise ValueError("incorrect Ethernet source/destination/type")
                ip = output[14:]
                decoded = decode_ethernet(output)
            else:
                ip = output
                decoded = decode_ethernet(bytes.fromhex("0200000000010200000000020800") + ip)
            if not decoded["icrc_valid"] or internet_checksum(ip[:20])!=0:
                raise ValueError(f"invalid wire checksums: {decoded}")
            if args.direction=="rx":
                if (decoded["opcode"]!=17 or decoded["destination_qpn"]!=196 or decoded["psn"]!=0x123456+sequence or
                    decoded["aeth_syndrome"] & 0xe0 or decoded["msn"]!=sequence+1):
                    raise ValueError(f"invalid wire ACK: {decoded}")
            else:
                expected_payload=bytes(((i*131)^(i>>8)^0x5a)&255 for i in range(64))
                if (decoded["opcode"]!=10 or decoded["destination_qpn"]!=196 or decoded["psn"]!=0x123456 or
                    decoded["rkey"]!="0xfedcba98" or decoded["remote_address"]!="0xfedcba9876543210" or
                    decoded["dma_length"]!=64 or decoded["payload_bytes"]!=64 or ip[56:120]!=expected_payload):
                    raise ValueError(f"invalid wire WRITE: {decoded}")
        records = [json.loads(line[7:]) for line in simulated.stdout.splitlines() if line.startswith("RESULT ")]
        if len(records)!=1:
            raise ValueError("missing RTL test completion record")
        report = dict(evidence_type="RTL simulation, not hardware", hls_build=args.hls_build.name,
                      direction=args.direction, ethernet_boundary=args.ethernet, **records[0], wire_ipv4_checksums_valid=True, wire_icrcs_valid=True,
                      whole_invalid_frame_rejected_before_hls=args.direction=="rx" or args.ethernet, hardware_verified=False)
        report["integrity_rtl_sha256"] = hashlib.sha256((ROOT/"rdma/rtl/rocev2_ipv4_icrc.v").read_bytes()).hexdigest()
        report["transport_rtl_sha256"] = hashlib.sha256((ROOT/"rdma/rtl/rocev2_integrity_transport.v").read_bytes()).hexdigest()
        report["padding_rtl_sha256"] = hashlib.sha256((ROOT/"rdma/rtl/rocev2_tx_padding.v").read_bytes()).hexdigest()
        report["test_sha256"] = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
        if args.ethernet:
            report["ethernet_rtl_sha256"] = {name: hashlib.sha256((ROOT / "rdma/rtl" / name).read_bytes()).hexdigest()
                                             for name in ("rocev2_ethernet_rx.v", "rocev2_ethernet_tx.v")}
        generated = hashlib.sha256()
        for source in sorted([*rtl.glob("*.v"),*rtl.glob("*.dat")]):
            generated.update(source.name.encode()+b"\0"+source.read_bytes())
        report["generated_rtl_sha256"] = generated.hexdigest()
        print(json.dumps(report,indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    main()
