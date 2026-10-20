// SPDX-License-Identifier: BSD-2-Clause-Views
// Exact actual TX graph; independent field/wire oracle. External QP-state/MSN
// responders are test models, NOT native pins/MAC/DMA/timer/CQ integration.
`timescale 1ns/1ps
module as02_axis_hold_check #(parameter WIDTH=1)(
 input wire clk,rst_n,valid,ready,input wire [WIDTH-1:0] data);
reg held=0;reg [WIDTH-1:0] prior;
always @(posedge clk)begin
 if(!rst_n)held<=0;
 else begin
  if(held && (valid!==1'b1 || data!==prior))$fatal(1,"AXIS changed/lost held token %m");
  held<=valid && !ready;if(valid && !ready)prior<=data;
 end
end
endmodule
module tb;
reg clk=0,rst_n=1;
always #2 clk=~clk; // ORIGINAL4ns, never relaxed to the HLS estimate
integer test_case=1,cycles=0;
reg uninitialized;
tri undriven;
reg [247:0] sq=0;reg sq_valid=0;wire sq_ready;
reg [191:0] context_data=0;reg context_valid=0;wire context_ready;
reg [95:0] remote_ack_data=0;reg remote_ack_valid=0;wire remote_ack_ready;
wire [15:0] conn,msn_req,len;
wire conn_valid,msn_req_valid,len_valid;
wire [95:0] state_req,bth;
wire state_req_valid,bth_valid;
wire [191:0] mem;
wire mem_valid;
wire [511:0] insert_data;wire insert_valid;
wire [767:0] start_data;wire start_valid;
wire [127:0] exh;wire exh_valid;
wire [23:0] info;wire info_valid;
wire [31:0] af,lf,bf,ef,jf,retrans;
integer nconn=0,nquery=0,nupdate=0,nmsn=0,nlen=0,nmem=0,ninsert=0,nstart=0,nbth=0,nexh=0,ninfo=0;
integer ndst=0,nstate=0,nmsnrsp=0;
wire dst_valid=ndst<nconn,state_valid=nstate<nquery,msn_valid=nmsnrsp<nmsn;
wire dst_ready,state_ready,msn_ready;
wire conn_ready=cycles%3!=0,state_req_ready=cycles%4!=0,msn_req_ready=cycles%5!=0;
wire insert_ready=cycles>200 && cycles%7!=0,start_ready=cycles%11!=0;
wire bth_ready=cycles%13!=0,exh_ready=cycles%6!=0,mem_ready=cycles%9!=0;
wire len_ready=cycles%8!=0,info_ready=cycles%10!=0;
function [15:0] qpn(input integer i);begin qpn=i==3?0:7;end endfunction
function [31:0] opcode(input integer i);begin opcode=(i==1 || i==2)?12:10;end endfunction
function [31:0] key(input integer i);begin key=i%2?32'hffffffff:0;end endfunction
function [31:0] length_value(input integer i);begin length_value=i==2?4161:65;end endfunction
function [23:0] psn(input integer i);begin psn=i==2?24'hffffff:24'habcdef+i;end endfunction
function [23:0] rev24(input [23:0] r);begin rev24={r[7:0],r[15:8],r[23:16]};end endfunction
function [31:0] rev32(input [31:0] r);begin rev32={r[7:0],r[15:8],r[23:16],r[31:24]};end endfunction
function [247:0] sq_value(input integer i);
begin sq_value=0;sq_value[31:0]=opcode(i);sq_value[41:32]=qpn(i);sq_value[42]=1;sq_value[43]=1;
 sq_value[47:44]=9;sq_value[111:48]=64'hfedcba9876540000;sq_value[175:112]=64'h123456789abc0000;
 sq_value[207:176]=length_value(i);sq_value[239:208]=key(i);sq_value[240]=1;end endfunction
function [191:0] context_value(input integer i);
begin context_value=0;context_value[15:0]=qpn(i);context_value[79:16]=64'hfedcba9876543210;
 context_value[143:80]=64'h8765432100000001+i;end endfunction
function [191:0] state_value(input integer i);begin state_value=0;state_value[87:64]=psn(i);end endfunction
function [511:0] expected_insert(input integer i);
begin expected_insert=0;expected_insert[31:0]=key(i);expected_insert[32]=1;expected_insert[40]=1;
 expected_insert[63:48]=qpn(i);expected_insert[87:64]=psn(i);expected_insert[127:96]=opcode(i);
 expected_insert[191:128]=64'hfedcba9876540000;expected_insert[255:192]=64'h123456789abc0000;
 expected_insert[287:256]=length_value(i);expected_insert[288]=1;expected_insert[303:296]=9;
 expected_insert[383:320]=64'hfedcba9876543210;expected_insert[447:384]=64'h8765432100000001+i;end endfunction
function [767:0] expected_start(input integer i);
begin expected_start=0;expected_start[15:0]=qpn(i);expected_start[127:64]=64'hfedcba9876543210;
 expected_start[191:128]=64'h8765432100000001+i;expected_start[512]=1;end endfunction
function [95:0] expected_bth(input integer i);
begin expected_bth=0;expected_bth[7:0]=opcode(i);expected_bth[14]=1;expected_bth[31:16]=16'hffff;
 expected_bth[63:40]=rev24(24'hdeadbe);expected_bth[71]=1;expected_bth[95:72]=rev24(psn(i));end endfunction
function [127:0] expected_exh(input integer beat);
integer i;begin i=beat/2;expected_exh=0;expected_exh[71:64]=8'hff;expected_exh[72]=beat%2;
 if(beat%2==0)expected_exh[63:0]=64'h0000bc9a78563412;
 else expected_exh[63:0]={rev32(length_value(i)),rev32(key(i))};end endfunction
function [191:0] expected_mem(input integer i);
begin expected_mem=0;expected_mem[31:0]=10;expected_mem[47:32]=qpn(i);
 expected_mem[127:64]=64'hfedcba9876540000;expected_mem[159:128]=65;expected_mem[160]=1;end endfunction

as02_owned_wire_tx_top dut(
 .ap_clk(clk),.ap_rst_n(rst_n),.s_sq_TDATA(sq),.s_sq_TVALID(sq_valid),.s_sq_TREADY(sq_ready),
 .s_trusted_context_TDATA(context_data),.s_trusted_context_TVALID(context_valid),.s_trusted_context_TREADY(context_ready),
 .s_replay_TDATA(1280'd0),.s_replay_TVALID(1'b0),.s_replay_TREADY(),
 .s_remote_ack_TDATA(remote_ack_data),.s_remote_ack_TVALID(remote_ack_valid),.s_remote_ack_TREADY(remote_ack_ready),
 .s_remote_read_TDATA(1280'd0),.s_remote_read_TVALID(1'b0),.s_remote_read_TREADY(),
 .s_destination_TDATA(24'hdeadbe),.s_destination_TVALID(dst_valid),.s_destination_TREADY(dst_ready),
 .s_state_TDATA(state_value(nstate)),.s_state_TVALID(state_valid),.s_state_TREADY(state_ready),
 .s_msn_TDATA({32'h13579bdf,8'd0,24'habcdef}),.s_msn_TVALID(msn_valid),.s_msn_TREADY(msn_ready),
 .m_connection_TDATA(conn),.m_connection_TVALID(conn_valid),.m_connection_TREADY(conn_ready),
 .m_state_TDATA(state_req),.m_state_TVALID(state_req_valid),.m_state_TREADY(state_req_ready),
 .m_msn_TDATA(msn_req),.m_msn_TVALID(msn_req_valid),.m_msn_TREADY(msn_req_ready),
 .m_memory_TDATA(mem),.m_memory_TVALID(mem_valid),.m_memory_TREADY(mem_ready),
 .m_insert_TDATA(insert_data),.m_insert_TVALID(insert_valid),.m_insert_TREADY(insert_ready),
 .m_tx_start_TDATA(start_data),.m_tx_start_TVALID(start_valid),.m_tx_start_TREADY(start_ready),
 .m_bth_TDATA(bth),.m_bth_TVALID(bth_valid),.m_bth_TREADY(bth_ready),
 .m_exh_TDATA(exh),.m_exh_TVALID(exh_valid),.m_exh_TREADY(exh_ready),
 .m_length_TDATA(len),.m_length_TVALID(len_valid),.m_length_TREADY(len_ready),
 .m_packet_info_TDATA(info),.m_packet_info_TVALID(info_valid),.m_packet_info_TREADY(info_ready),
 .admission_fault(af),.local_fault(lf),.ibh_fault(bf),.exh_fault(ef),.merge_fault(jf),.retransmissions(retrans)
);
as02_axis_hold_check #(16) hc(clk,rst_n,conn_valid,conn_ready,conn);
as02_axis_hold_check #(96) hs(clk,rst_n,state_req_valid,state_req_ready,state_req);
as02_axis_hold_check #(16) hm(clk,rst_n,msn_req_valid,msn_req_ready,msn_req);
as02_axis_hold_check #(192) hmem(clk,rst_n,mem_valid,mem_ready,mem);
as02_axis_hold_check #(512) hi(clk,rst_n,insert_valid,insert_ready,insert_data);
as02_axis_hold_check #(768) hstart(clk,rst_n,start_valid,start_ready,start_data);
as02_axis_hold_check #(96) hb(clk,rst_n,bth_valid,bth_ready,bth);
as02_axis_hold_check #(128) he(clk,rst_n,exh_valid,exh_ready,exh);
as02_axis_hold_check #(16) hl(clk,rst_n,len_valid,len_ready,len);
as02_axis_hold_check #(24) hp(clk,rst_n,info_valid,info_ready,info);
as02_axis_hold_check #(248) hsq(clk,rst_n,sq_valid,sq_ready,sq);
as02_axis_hold_check #(192) hctx(clk,rst_n,context_valid,context_ready,context_data);
always @(posedge clk) if(rst_n)begin
 cycles<=cycles+1;
 if(cycles>3000)$fatal(1,"bounded actual TX graph cycle deadline");
 if(dst_valid && dst_ready)ndst<=ndst+1;
 if(state_valid && state_ready)nstate<=nstate+1;
 if(msn_valid && msn_ready)nmsnrsp<=nmsnrsp+1;
 if(conn_valid && conn_ready)begin if(conn!==qpn(nconn))$fatal(1,"connection owner");nconn<=nconn+1;end
 if(msn_req_valid && msn_req_ready)begin if(msn_req!==qpn(nmsn))$fatal(1,"MSN owner");nmsn<=nmsn+1;end
 if(state_req_valid && state_req_ready)begin
  if(state_req[64]===1'b0)begin if(state_req[15:0]!==qpn(nquery))$fatal(1,"PSN query owner");nquery<=nquery+1;end
  else if(state_req[64]===1'b1)begin
   if(state_req[15:0]!==qpn(nupdate) || state_req[55:32]!==((psn(nupdate)+(length_value(nupdate)+4095)/4096)&24'hffffff))
    $fatal(1,"PSN update/wrap");nupdate<=nupdate+1;end
  else $fatal(1,"unknown state request");end
 if(mem_valid && mem_ready)begin if(mem!==expected_mem(nmem==0?0:3))$fatal(1,"actual local memory command");nmem<=nmem+1;end
 if(insert_valid && insert_ready)begin if(insert_data!==expected_insert(ninsert))$fatal(1,"full WR PSN/address join %0d got%h expected%h",ninsert,insert_data,expected_insert(ninsert));ninsert<=ninsert+1;end
 if(start_valid && start_ready)begin if(start_data!==expected_start(nstart))$fatal(1,"actual EXH full WR start");nstart<=nstart+1;end
 if(bth_valid && bth_ready)begin
  if(test_case==5)begin
   // ACK uses an already-valid PSN, no requester ACK bit or new state update.
   if(bth!=={rev24(24'habcdef),8'd0,rev24(24'hdeadbe),8'd0,16'hffff,8'h40,8'h11})$fatal(1,"actual ACK BTH");
  end else if(bth!==expected_bth(nbth))$fatal(1,"actual wire BTH/PSN");nbth<=nbth+1;end
 if(exh_valid && exh_ready)begin
  if(test_case==5)begin
   // AETH has four VALID bytes; other data lanes are not part of the packet.
   if(exh[31:0]!==32'hefcdab00 || exh[71:64]!==8'h0f || exh[72]!==1'b1)$fatal(1,"actual ACK AETH/keep/last");
  end else if(exh!==expected_exh(nexh))$fatal(1,"actual wire RETH/key %0d got%h expected%h",nexh,exh,expected_exh(nexh));nexh<=nexh+1;end
 if(len_valid && len_ready)begin if(len!==(test_case==5?16'd20:(opcode(nlen)==12?16'd32:16'd97)))$fatal(1,"actual wire length");nlen<=nlen+1;end
 if(info_valid && info_ready)begin if(info!==(test_case==5?24'h000101:(opcode(ninfo)==12?24'h000100:24'h010100)))$fatal(1,"actual packet info");ninfo<=ninfo+1;end
end
task send_sq(input [247:0] value);begin @(negedge clk);sq=value;sq_valid=1;
 @(posedge clk);while(sq_ready!==1'b1)@(posedge clk);@(negedge clk);sq_valid=0;end endtask
task send_context(input [191:0] value);begin @(negedge clk);context_data=value;context_valid=1;
 @(posedge clk);while(context_ready!==1'b1)@(posedge clk);@(negedge clk);context_valid=0;end endtask
task send_ack;begin @(negedge clk);remote_ack_data=0;remote_ack_data[23:0]=7;
 remote_ack_data[55:32]=24'habcdef;remote_ack_data[64]=1;remote_ack_valid=1;
 @(posedge clk);while(remote_ack_ready!==1'b1)@(posedge clk);@(negedge clk);remote_ack_valid=0;end endtask
integer i;reg [191:0] bad_context;reg [247:0] bad_sq;
initial begin
 if(!$value$plusargs("CASE=%d",test_case))test_case=1;
 #0;if(uninitialized!==1'bx || undriven!==1'bz)$fatal(1,"four-state calibration");
 #1;rst_n=0;repeat(5)@(negedge clk);rst_n=1;
 if(test_case==1)begin
  for(i=0;i<4;i=i+1)begin
   send_sq(sq_value(i));repeat(6)@(negedge clk);
   if(i==0 && (nconn!=0 || ninsert!=0))$fatal(1,"unpaired SQ consumed without trusted context");
   send_context(context_value(i));end
  repeat(1000)@(negedge clk);
  if({af,lf,bf,ef,jf,retrans}!==192'd0)$fatal(1,"unexpected producer fault");
  if(nconn!=4 || nquery!=4 || nupdate!=4 || nmsn!=4 || nmem!=2 || ninsert!=4 || nstart!=4 || nbth!=4 || nexh!=8 || nlen!=4 || ninfo!=4)
   $fatal(1,"missing/duplicate actual output conn%0d query%0d update%0d msn%0d mem%0d insert%0d start%0d bth%0d exh%0d length%0d info%0d",nconn,nquery,nupdate,nmsn,nmem,ninsert,nstart,nbth,nexh,nlen,ninfo);
 end else if(test_case==5)begin
  send_ack();repeat(800)@(negedge clk);
  if({af,lf,bf,ef,jf,retrans}!==192'd0)$fatal(1,"unexpected ACK producer fault");
  if(nconn!=1 || nquery!=0 || nupdate!=0 || nmsn!=1 || nmem!=0 || ninsert!=0 || nstart!=0 || nbth!=1 || nexh!=1 || nlen!=1 || ninfo!=1)
   $fatal(1,"ACK requester-owner contamination or missing/duplicate output");
 end else begin
  bad_context=context_value(0);bad_sq=sq_value(0);
  if(test_case==2)bad_context[191]=1;else if(test_case==3)bad_context[15:0]=6;else if(test_case==4)bad_sq[247]=1;else $fatal(1,"invalid CASE");
  send_sq(bad_sq);send_context(bad_context);repeat(500)@(negedge clk);
  if(af!==32'd1 || {lf,bf,ef,jf,retrans}!==160'd0)$fatal(1,"invalid admission did not quarantine");
  if(nconn!=0 || nquery!=0 || nupdate!=0 || nmsn!=0 || nmem!=0 || ninsert!=0 || nstart!=0 || nbth!=0 || nexh!=0 || nlen!=0 || ninfo!=0)
   $fatal(1,"side effect after denied context");end
 $display("{\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"actual_insertions\":%0d,\"wire_BTHs\":%0d,\"wire_EXH_words\":%0d,\"wire_RETH_words\":%0d,\"wire_AETH_words\":%0d,\"AXIS_hold_monitors\":12,\"four_state\":true,\"native_CQ\":false}",test_case,cycles,ninsert,nbth,nexh,test_case==5?0:nexh,test_case==5?nexh:0);$finish;
end
endmodule
