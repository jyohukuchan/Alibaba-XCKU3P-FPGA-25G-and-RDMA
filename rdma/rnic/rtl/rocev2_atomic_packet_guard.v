// SPDX-License-Identifier: BSD-2-Clause-Views
// Atomic branch ONLY, after the real whole-packet IPv4/ICRC checker. The
// existing native normal-operation branch must remain separately protected.
// No second PSN/MSN/MR table: snapshot TRUSTED peer/QPN/epoch, validate the
// complete72B packet, then give the shared HLS its unchanged wire bytes.
// Packet tag is distinct from protocol PSN, including duplicate retries.
// Explicit matching downstream retirement is mandatory. This input is not
// an application ACK/drain knob; native integration must use real ownership/
// MAC proof. Reset is NOT safe unpin, cancellation or epoch recovery proof.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_packet_guard (
    input wire clk, input wire rst, input wire enable,
    input wire trusted_valid, input wire [23:0] trusted_qpn,
    input wire [63:0] trusted_epoch,
    input wire [31:0] trusted_local_ip, input wire [31:0] trusted_peer_ip,
    input wire [127:0] s_axis_tdata, input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid, output wire s_axis_tready, input wire s_axis_tlast,
    output wire [127:0] m_axis_tdata, output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid, input wire m_axis_tready, output wire m_axis_tlast,
    output wire [23:0] m_owner_qpn, output wire [63:0] m_owner_epoch,
    output wire [23:0] m_owner_psn, output wire [31:0] m_owner_tag,
    output wire m_owner_valid, input wire m_owner_ready,
    input wire [23:0] s_retire_qpn, input wire [63:0] s_retire_epoch,
    input wire [23:0] s_retire_psn, input wire [31:0] s_retire_tag,
    input wire s_retire_valid, output wire s_retire_ready,
    output wire busy, output wire configuration_guard,
    output reg fault=0, output reg [7:0] fault_code=0,
    output reg [31:0] accepted_count=0, output reg [31:0] dropped_count=0
);
localparam COLLECT=0,CHECK=1,FORWARD=2,HELD=3;
reg [1:0] state=COLLECT;
reg [639:0] packet=0;
reg [6:0] bytes=0;reg [2:0] words=0,position=0;
reg bad=0,owner_taken=0,context_valid=0,tag_exhausted=0;
reg [23:0] qpn=0;reg [63:0] epoch=0;
reg [31:0] local_ip=0,peer_ip=0,tag=0,next_tag=1;
// Explicit data arguments are necessary for event-driven four-state
// sensitivity as well as synthesis; no hidden global header dependency.
function [15:0] be16;input [639:0] data;input integer p;begin be16={data[p*8+:8],data[(p+1)*8+:8]};end endfunction
function [31:0] be32;input [639:0] data;input integer p;begin be32={be16(data,p),be16(data,p+2)};end endfunction
wire [23:0] packet_qpn={packet[271:264],packet[279:272],packet[287:280]};
wire [23:0] packet_psn={packet[303:296],packet[311:304],packet[319:312]};
wire [7:0] opcode=packet[231:224];
wire tuple_known=(^{context_valid,qpn,epoch,local_ip,peer_ip})!==1'bx;
wire frame_ok=!bad && bytes==72 && words==5 && packet[7:0]==8'h45 && packet[79:72]==17 &&
    be16(packet,2)==72 && be16(packet,24)==52 && (be16(packet,6)&16'hbfff)==0 && be16(packet,22)==4791 && be16(packet,26)==0 &&
    (opcode==8'h13 || opcode==8'h14) && (packet[239:232]&8'hbf)==0 &&
    be16(packet,30)==16'hffff && (packet[263:256]&8'h3f)==0 && (packet[295:288]&8'h7f)==0;
wire peer_ok=tuple_known && context_valid && qpn<8 && epoch!=0 && packet_qpn==qpn &&
    be32(packet,12)==peer_ip && be32(packet,16)==local_ip;
assign s_axis_tready=state==COLLECT && !fault && !rst && (enable || words!=0);
assign m_axis_tdata=packet[position*128+:128];
assign m_axis_tkeep=position==4 ? 16'h00ff:16'hffff;
assign m_axis_tlast=position==4;
// Already-offered frame/owner transfers finish even after disable/fault.
// Fault still retains the lease and prevents all further input/retirement.
assign m_axis_tvalid=state==FORWARD && !rst;
assign m_owner_qpn=qpn;assign m_owner_epoch=epoch;
assign m_owner_psn=packet_psn;assign m_owner_tag=tag;
assign m_owner_valid=(state==FORWARD || state==HELD) && !owner_taken && !rst;
wire retire_known=(^{s_retire_qpn,s_retire_epoch,s_retire_psn,s_retire_tag})!==1'bx;
wire retire_match=retire_known && s_retire_qpn==qpn && s_retire_epoch==epoch &&
    s_retire_psn==packet_psn && s_retire_tag==tag;
assign s_retire_ready=state==HELD && owner_taken && retire_match && !fault && !rst;
assign busy=state!=COLLECT || words!=0 || fault;
assign configuration_guard=busy;
integer i;reg [4:0] count;
always @*begin count=0;for(i=0;i<16;i=i+1)count=count+{4'd0,s_axis_tkeep[i]};end
integer lane;
always @(posedge clk)begin
    if(rst)begin
        state<=COLLECT;packet<=0;bytes<=0;words<=0;position<=0;bad<=0;owner_taken<=0;
        context_valid<=0;qpn<=0;epoch<=0;local_ip<=0;peer_ip<=0;tag<=0;next_tag<=1;tag_exhausted<=0;
        fault<=0;fault_code<=0;accepted_count<=0;dropped_count<=0;
    end else begin
        if(s_axis_tvalid && s_axis_tready)begin
            if(words==0)begin
                context_valid<=trusted_valid;qpn<=trusted_qpn;epoch<=trusted_epoch;
                local_ip<=trusted_local_ip;peer_ip<=trusted_peer_ip;
            end
            if(words<5)begin
                for(lane=0;lane<16;lane=lane+1)
                    packet[words*128+lane*8+:8]<=s_axis_tkeep[lane] ? s_axis_tdata[lane*8+:8]:8'd0;
                words<=words+1'b1;
            end else bad<=1;
            if(bytes<80)bytes<=bytes+{2'd0,count};else bad<=1;
            if((^{s_axis_tkeep,s_axis_tlast})===1'bx || s_axis_tkeep==0 ||
               (s_axis_tkeep&(s_axis_tkeep+16'd1))!=0 || (!s_axis_tlast && s_axis_tkeep!=16'hffff))bad<=1;
            for(lane=0;lane<16;lane=lane+1)
                if(s_axis_tkeep[lane] && (^s_axis_tdata[lane*8+:8])===1'bx)bad<=1;
            if(s_axis_tlast)state<=CHECK;
        end
        if(state==CHECK && !fault)begin
            if(!frame_ok || !peer_ok)begin
                dropped_count<=dropped_count+1;state<=COLLECT;packet<=0;bytes<=0;words<=0;bad<=0;
            end else if(tag_exhausted)begin fault<=1;fault_code<=8'h91;end
            else begin
                tag<=next_tag;if(next_tag==32'hffffffff)tag_exhausted<=1;else next_tag<=next_tag+1'b1;
                position<=0;owner_taken<=0;state<=FORWARD;accepted_count<=accepted_count+1;
            end
        end
        if(m_axis_tvalid && m_axis_tready)begin
            if(m_axis_tlast)state<=HELD;else position<=position+1'b1;
        end
        if(m_owner_valid && m_owner_ready)owner_taken<=1;
        if(s_retire_valid && s_retire_ready)begin
            state<=COLLECT;packet<=0;bytes<=0;words<=0;bad<=0;position<=0;owner_taken<=0;
        end
        if(!fault && ((s_retire_valid!==1'b0 && s_retire_valid!==1'b1) ||
          (s_retire_valid && (state!=HELD || !owner_taken || !retire_match))))begin fault<=1;fault_code<=8'h92;end
    end
end
endmodule
`resetall
