// SPDX-License-Identifier: BSD-2-Clause-Views
// Lossless two-consumer ready/valid fanout. Each receiver accepts ONCE;
// the actual upstream certificate remains leased until BOTH have accepted.
// Source must hold data+valid until s_ready, as for an ordinary stream.
// No event/proof/drain/reset/recovery authority is created by this adapter.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_fatal_event_fanout(
    input wire clk,input wire rst,
    input wire [999:0] s_data,input wire s_valid,output wire s_ready,
    output wire [999:0] m_observer_data,output wire m_observer_valid,input wire m_observer_ready,
    output wire [999:0] m_mailbox_data,output wire m_mailbox_valid,input wire m_mailbox_ready
);
reg observer_taken=0,mailbox_taken=0;
assign m_observer_data=s_data;assign m_mailbox_data=s_data;
assign m_observer_valid=s_valid && !observer_taken && !rst;
assign m_mailbox_valid=s_valid && !mailbox_taken && !rst;
assign s_ready=(observer_taken || m_observer_ready) && (mailbox_taken || m_mailbox_ready) && !rst;
always @(posedge clk)begin
    if(rst)begin observer_taken<=0;mailbox_taken<=0;end
    else if(s_valid && s_ready)begin observer_taken<=0;mailbox_taken<=0;end
    else begin
        if(m_observer_valid && m_observer_ready)observer_taken<=1;
        if(m_mailbox_valid && m_mailbox_ready)mailbox_taken<=1;
    end
end
endmodule
`resetall
