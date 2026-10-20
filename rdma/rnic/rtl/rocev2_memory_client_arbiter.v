// SPDX-License-Identifier: BSD-2-Clause-Views
// Two AUTHORIZED memory clients share ONE sealed-page/payload backend.
// This is not MR authorization or RDMA/CQ completion. Full key/offset/length/
// tag and all data/status ownership are retained; identical client tags do
// not alias. The caller retains its real MR/QP/WR lease beyond memory status.
// Fault/reset are not cancellation, safe drain, unpin or recovery evidence.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_memory_client_arbiter (
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [1:0] s_command_write,
    input wire [127:0] s_command_offset,
    input wire [63:0] s_command_length,
    input wire [63:0] s_command_key,
    input wire [31:0] s_command_tag,
    input wire [1:0] s_command_valid,
    output wire [1:0] s_command_ready,
    input wire [1023:0] s_axis_write_tdata,
    input wire [127:0] s_axis_write_tkeep,
    input wire [1:0] s_axis_write_tlast,
    input wire [1:0] s_axis_write_tvalid,
    output wire [1:0] s_axis_write_tready,
    output wire [1023:0] m_axis_read_tdata,
    output wire [127:0] m_axis_read_tkeep,
    output wire [1:0] m_axis_read_tlast,
    output wire [1:0] m_axis_read_tvalid,
    input wire [1:0] m_axis_read_tready,
    output wire [31:0] m_status_tag,
    output wire [15:0] m_status_error,
    output wire [1:0] m_status_valid,
    input wire [1:0] m_status_ready,
    output reg m_command_write=0,
    output reg [63:0] m_command_offset=0,
    output reg [31:0] m_command_length=0,
    output reg [31:0] m_command_key=0,
    output reg [15:0] m_command_tag=0,
    output reg m_command_valid=0,
    input wire m_command_ready,
    output wire [511:0] m_axis_write_tdata,
    output wire [63:0] m_axis_write_tkeep,
    output wire m_axis_write_tlast,
    output wire m_axis_write_tvalid,
    input wire m_axis_write_tready,
    input wire [511:0] s_axis_read_tdata,
    input wire [63:0] s_axis_read_tkeep,
    input wire s_axis_read_tlast,
    input wire s_axis_read_tvalid,
    output wire s_axis_read_tready,
    input wire [15:0] s_status_tag,
    input wire [7:0] s_status_error,
    input wire s_status_valid,
    output wire s_status_ready,
    output wire [1:0] client_guard,
    output wire busy,
    output wire configuration_guard,
    output reg fault=0,
    output reg [7:0] fault_code=0
);
reg active=0,owner=0,next_owner=0,issued=0,data_done=0;
reg [31:0] remaining=0;
reg [511:0] beat_data=0;
reg [63:0] beat_keep=0;
reg beat_last=0,beat_valid=0;
reg [15:0] result_tag=0;
reg [7:0] result_error=0;
reg result_valid=0;
wire selected=s_command_valid[next_owner] ? next_owner : !next_owner;
wire valid_known=(^s_command_valid)!==1'bx;
wire [63:0] selected_offset=s_command_offset[selected*64+:64];
wire [31:0] selected_length=s_command_length[selected*32+:32];
wire [31:0] selected_key=s_command_key[selected*32+:32];
wire [15:0] selected_tag=s_command_tag[selected*16+:16];
wire selected_write=s_command_write[selected];
wire [64:0] selected_end={1'b0,selected_offset}+{33'd0,selected_length};
wire tuple_known=(^{selected_write,selected_offset,selected_length,selected_key,selected_tag})!==1'bx;
wire tuple_ok=tuple_known && selected_length!=0 && selected_length<=4096 &&
    (selected_end[64]==0 || selected_end==65'h10000000000000000);
wire accept_new=!active && !fault && enable && !rst && valid_known &&
    s_command_valid[selected] && tuple_ok;
assign s_command_ready=accept_new ? (2'b01<<selected) : 2'b00;
assign busy=active || fault;
assign configuration_guard=busy || (enable && (|s_command_valid));
assign client_guard=fault ? 2'b11 : active ? (2'b01<<owner) : 2'b00;
function [63:0] mask64;
    input [31:0] n;integer lane;
    begin for(lane=0;lane<64;lane=lane+1)mask64[lane]=n>lane;end
endfunction
wire [511:0] input_data=m_command_write ? s_axis_write_tdata[owner*512+:512] : s_axis_read_tdata;
wire [63:0] input_keep=m_command_write ? s_axis_write_tkeep[owner*64+:64] : s_axis_read_tkeep;
wire input_last=m_command_write ? s_axis_write_tlast[owner] : s_axis_read_tlast;
wire input_valid=m_command_write ? s_axis_write_tvalid[owner] : s_axis_read_tvalid;
wire shape_known=(^{input_keep,input_last})!==1'bx;
reg data_known;
integer known_lane;
always @* begin
    data_known=1;
    for(known_lane=0;known_lane<64;known_lane=known_lane+1)
        if(input_keep[known_lane] && (^input_data[known_lane*8+:8])===1'bx)data_known=0;
end
wire shape_ok=shape_known && data_known && input_keep==mask64(remaining) && input_last==(remaining<=64);
wire status_known=(^{s_status_tag,s_status_error})!==1'bx;
wire status_error_offer=s_status_valid && status_known && s_status_error!=0;
wire take_data=active && issued && !data_done && remaining!=0 && !beat_valid &&
    !result_valid && !fault && !status_error_offer && !rst && shape_ok;
assign s_axis_write_tready=take_data && m_command_write ? (2'b01<<owner) : 2'b00;
assign s_axis_read_tready=take_data && !m_command_write;
// Registered output beats never disappear on disable/fault. No payload from
// a non-owner or an unvalidated input is combinationally exposed downstream.
assign m_axis_write_tdata=beat_data;
assign m_axis_write_tkeep=beat_keep;
assign m_axis_write_tlast=beat_last;
assign m_axis_write_tvalid=beat_valid && m_command_write;
assign m_axis_read_tdata=owner ? {beat_data,512'd0} : {512'd0,beat_data};
assign m_axis_read_tkeep=owner ? {beat_keep,64'd0} : {64'd0,beat_keep};
assign m_axis_read_tlast=beat_valid && !m_command_write ? (beat_last ? (2'b01<<owner) : 2'b00) : 2'b00;
assign m_axis_read_tvalid=beat_valid && !m_command_write ? (2'b01<<owner) : 2'b00;
wire beat_transfer=beat_valid && (m_command_write ? m_axis_write_tready : m_axis_read_tready[owner]);
assign s_status_ready=active && issued && !result_valid && !beat_valid &&
    status_known && s_status_tag==m_command_tag && (data_done || s_status_error!=0) && !fault && !rst;
assign m_status_tag=owner ? {result_tag,16'd0} : {16'd0,result_tag};
assign m_status_error=owner ? {result_error,8'd0} : {8'd0,result_error};
assign m_status_valid=result_valid ? (2'b01<<owner) : 2'b00;
integer byte_lane;
always @(posedge clk)begin
    if(rst)begin
        active<=0;owner<=0;next_owner<=0;issued<=0;data_done<=0;remaining<=0;
        m_command_write<=0;m_command_offset<=0;m_command_length<=0;m_command_key<=0;
        m_command_tag<=0;m_command_valid<=0;beat_data<=0;beat_keep<=0;beat_last<=0;beat_valid<=0;
        result_tag<=0;result_error<=0;result_valid<=0;fault<=0;fault_code<=0;
    end else begin
        if(accept_new)begin
            active<=1;owner<=selected;next_owner<=!selected;issued<=0;data_done<=0;
            remaining<=selected_length;m_command_write<=selected_write;m_command_offset<=selected_offset;
            m_command_length<=selected_length;m_command_key<=selected_key;
            m_command_tag<=selected_tag;m_command_valid<=1;
        end
        if(m_command_valid && m_command_ready)begin m_command_valid<=0;issued<=1;end
        if(take_data && input_valid)begin
            for(byte_lane=0;byte_lane<64;byte_lane=byte_lane+1)
                beat_data[byte_lane*8+:8]<=input_keep[byte_lane] ? input_data[byte_lane*8+:8] : 8'd0;
            beat_keep<=input_keep;beat_last<=input_last;beat_valid<=1;
            remaining<=remaining<=64 ? 0 : remaining-64;
        end
        if(beat_transfer)begin beat_valid<=0;if(beat_last)data_done<=1;end
        if(s_status_valid && s_status_ready)begin
            result_tag<=s_status_tag;result_error<=s_status_error;result_valid<=1;
            if(s_status_error!=0)begin fault<=1;fault_code<=8'h65;end
        end
        if(result_valid && m_status_ready[owner])begin
            result_valid<=0;
            // Known DMA error is delivered, NOT safe lifetime release.
            if(!fault && result_error==0)begin active<=0;issued<=0;data_done<=0;end
        end
        if(!fault)begin
            if(!valid_known || (!active && enable && s_command_valid[selected] && !tuple_ok))begin
                fault<=1;fault_code<=8'h61;
            end
            if((s_status_valid!==1'b0 && s_status_valid!==1'b1) ||
                (s_status_valid && (!active || !issued || result_valid || !status_known || s_status_tag!=m_command_tag)))begin
                fault<=1;fault_code<=8'h62;
            end
            if(active && issued && !data_done && remaining!=0 && !beat_valid && input_valid && !shape_ok)begin
                fault<=1;fault_code<=8'h63;
            end
            if(active && issued && input_valid && (data_done || remaining==0) && !result_valid)begin
                fault<=1;fault_code<=8'h64;
            end
        end
    end
end
endmodule
`resetall
