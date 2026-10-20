// SPDX-License-Identifier: BSD-2-Clause-Views
// Fair whole-packet merge of already protected requests and responses. A
// packet keeps its input until real EOF; never interleave beats or drop data.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_duplex_rx_mux(
    input wire clk,input wire rst,
    input wire [127:0] s_local_data,input wire [15:0] s_local_keep,
    input wire s_local_valid,output wire s_local_ready,input wire s_local_last,input wire s_local_user,
    input wire [127:0] s_remote_data,input wire [15:0] s_remote_keep,
    input wire s_remote_valid,output wire s_remote_ready,input wire s_remote_last,input wire s_remote_user,
    output wire [127:0] m_data,output wire [15:0] m_keep,
    output wire m_valid,input wire m_ready,output wire m_last,output wire m_user,
    output wire busy
);
reg held=0,held_local=0,last_local=1;
wire select_local=held ? held_local:(s_local_valid && (!s_remote_valid || !last_local));
assign m_data=select_local ? s_local_data:s_remote_data;
assign m_keep=select_local ? s_local_keep:s_remote_keep;
assign m_valid=(select_local ? s_local_valid:s_remote_valid) && !rst;
assign m_last=select_local ? s_local_last:s_remote_last;
assign m_user=select_local ? s_local_user:s_remote_user;
assign s_local_ready=select_local && m_ready && !rst;
assign s_remote_ready=!select_local && m_ready && !rst;
assign busy=held || s_local_valid || s_remote_valid;
always @(posedge clk)begin
    if(rst)begin held<=0;held_local<=0;last_local<=1;end
    else if(m_valid)begin
        // Latch an offered SOP even under output backpressure. A new other
        // input must never change the already-offered AXI beat/route.
        held<=1;held_local<=select_local;
        if(m_ready && m_last)begin held<=0;last_local<=select_local;end
    end
end
endmodule
`resetall
