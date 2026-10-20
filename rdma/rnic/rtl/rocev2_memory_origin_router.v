// SPDX-License-Identifier: BSD-2-Clause-Views
// Matched duplex HLS only. Real producer's origin[95:94] selects a protected
// memory client; lower94 bits are unchanged. An ordered credit retains that
// origin and exact byte count until real data EOF, independently of the other
// active client. This does NOT authorize addresses or certify any core drain.
// Reset is whole-NIC reset, never an operation cancellation/unpin certificate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_memory_origin_router #(
    parameter READ_RETURN=0,
    parameter DEPTH=8,
    parameter PTR_WIDTH=$clog2(DEPTH)
)(
    input wire clk,input wire rst,
    input wire local_owned,input wire remote_owned,
    input wire [95:0] s_command,input wire s_command_valid,output wire s_command_ready,
    output wire [95:0] m_local_command,output wire m_local_command_valid,input wire m_local_command_ready,
    output wire [95:0] m_remote_command,output wire m_remote_command_valid,input wire m_remote_command_ready,
    input wire [511:0] s_data,input wire [63:0] s_keep,input wire s_valid,output wire s_ready,input wire s_last,
    output wire [511:0] m_local_data,output wire [63:0] m_local_keep,output wire m_local_valid,
    input wire m_local_ready,output wire m_local_last,
    output wire [511:0] m_remote_data,output wire [63:0] m_remote_keep,output wire m_remote_valid,
    input wire m_remote_ready,output wire m_remote_last,
    input wire [511:0] s_local_data,input wire [63:0] s_local_keep,input wire s_local_valid,
    output wire s_local_ready,input wire s_local_last,
    input wire [511:0] s_remote_data,input wire [63:0] s_remote_keep,input wire s_remote_valid,
    output wire s_remote_ready,input wire s_remote_last,
    output wire [511:0] m_data,output wire [63:0] m_keep,output wire m_valid,
    input wire m_ready,output wire m_last,
    output wire busy,output wire local_busy,output wire remote_busy,
    output reg fault=0,output reg [7:0] fault_code=0
);
initial if(DEPTH<2 || DEPTH!=(1<<PTR_WIDTH) || (READ_RETURN!=0 && READ_RETURN!=1))
    $fatal(1,"unsupported origin credit geometry");
reg origins[0:DEPTH-1];
reg [27:0] lengths[0:DEPTH-1];
reg [PTR_WIDTH-1:0] wr=0,rd=0;
reg [PTR_WIDTH:0] count=0;
reg [PTR_WIDTH:0] local_count=0,remote_count=0;
wire [1:0] origin=s_command[95:94];
wire local_command=origin==2;
wire command_shape=(^s_command)!==1'bx && (origin==1 || origin==2) &&
    s_command[75:48]!=0 && s_command[75:48]<=4096 &&
    (local_command ? local_owned===1'b1:remote_owned===1'b1);
wire bad_command=(s_command_valid!==1'b0 && s_command_valid!==1'b1) ||
    (s_command_valid && !command_shape);
wire token=count!=0;
wire local_data=origins[rd];
wire [27:0] remaining=lengths[rd];
wire [511:0] selected_data=READ_RETURN ? (local_data ? s_local_data:s_remote_data):s_data;
wire [63:0] selected_keep=READ_RETURN ? (local_data ? s_local_keep:s_remote_keep):s_keep;
wire selected_valid=READ_RETURN ? (local_data ? s_local_valid:s_remote_valid):s_valid;
wire selected_last=READ_RETURN ? (local_data ? s_local_last:s_remote_last):s_last;
wire selected_ready=READ_RETURN ? m_ready:(local_data ? m_local_ready:m_remote_ready);
wire [6:0] bytes=remaining>64 ? 7'd64:remaining[6:0];
wire [63:0] expected_keep=bytes==64 ? 64'hffffffffffffffff:(64'h1<<bytes)-1;
wire data_shape=(^{selected_keep,selected_last})!==1'bx && remaining!=0 &&
    selected_keep==expected_keep && selected_last==(remaining<=64);
// A read client may pre-offer its next data before its command wins. It is
// neither consumed nor mistaken for the other client's current transfer.
wire bad_data=token && ((selected_valid!==1'b0 && selected_valid!==1'b1) ||
    (selected_valid && !data_shape));
wire stopped=rst || fault || bad_command || bad_data;
assign m_local_command={2'd0,s_command[93:0]};
assign m_remote_command={2'd0,s_command[93:0]};
assign m_local_command_valid=s_command_valid && command_shape && local_command && count<DEPTH && !stopped;
assign m_remote_command_valid=s_command_valid && command_shape && !local_command && count<DEPTH && !stopped;
assign s_command_ready=command_shape && count<DEPTH && !stopped &&
    (local_command ? m_local_command_ready:m_remote_command_ready);
wire push=s_command_valid && s_command_ready;
wire data_valid=token && selected_valid && data_shape && !stopped;
wire transfer=data_valid && selected_ready;
wire pop=transfer && selected_last;
assign m_local_data=selected_data;assign m_remote_data=selected_data;
assign m_local_keep=selected_keep;assign m_remote_keep=selected_keep;
assign m_local_last=selected_last;assign m_remote_last=selected_last;
assign m_local_valid=!READ_RETURN && data_valid && local_data;
assign m_remote_valid=!READ_RETURN && data_valid && !local_data;
assign s_ready=!READ_RETURN && token && data_shape && selected_ready && !stopped;
assign m_data=selected_data;assign m_keep=selected_keep;assign m_last=selected_last;
assign m_valid=READ_RETURN && data_valid;
assign s_local_ready=READ_RETURN && token && local_data && data_shape && selected_ready && !stopped;
assign s_remote_ready=READ_RETURN && token && !local_data && data_shape && selected_ready && !stopped;
assign busy=token || s_command_valid || fault;
assign local_busy=local_count!=0 || (s_command_valid && origin==2) || fault;
assign remote_busy=remote_count!=0 || (s_command_valid && origin==1) || fault;
always @(posedge clk)begin
    if(rst)begin wr<=0;rd<=0;count<=0;local_count<=0;remote_count<=0;fault<=0;fault_code<=0;end
    else begin
        if(!fault && (bad_command || bad_data))begin fault<=1;fault_code<=bad_command ? 8'hc1:8'hc2;end
        if(push)begin origins[wr]<=local_command;lengths[wr]<=s_command[75:48];wr<=wr+1'b1;end
        if(transfer)begin
            if(pop)rd<=rd+1'b1;
            else lengths[rd]<=remaining-bytes;
        end
        case({push,pop})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:begin end endcase
        case({push && local_command,pop && local_data})
            2'b10:local_count<=local_count+1'b1;2'b01:local_count<=local_count-1'b1;default:begin end endcase
        case({push && !local_command,pop && !local_data})
            2'b10:remote_count<=remote_count+1'b1;2'b01:remote_count<=remote_count-1'b1;default:begin end endcase
    end
end
endmodule
`resetall
