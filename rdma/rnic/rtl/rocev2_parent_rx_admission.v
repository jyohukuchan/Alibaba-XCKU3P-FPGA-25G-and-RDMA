// SPDX-License-Identifier: BSD-2-Clause-Views
// Retain an already OFFERED first beat and its entire frame across fatal.
// The data/keep/user/last paths remain direct, owned by the upstream AXIS.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_parent_rx_admission (
    input wire clk,
    input wire rst,
    input wire parent_fault,
    input wire s_valid,
    output wire s_ready,
    input wire s_last,
    output wire m_valid,
    input wire m_ready
);
reg frame_owned=0;
wire admit=frame_owned || !parent_fault;
assign m_valid=s_valid && admit;
assign s_ready=m_ready && admit;
always @(posedge clk) begin
    if(rst) frame_owned<=0;
    else if(s_valid && admit) begin
        // Ownership starts on an offer, not only on ready/valid acceptance.
        // A newly asserted fault must not withdraw a stalled valid beat.
        frame_owned<=!(m_ready && s_last);
    end
end
endmodule
`resetall
