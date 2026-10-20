// SPDX-License-Identifier: BSD-2-Clause-Views
// New per-WR HLS SQ ABI adapter. NOT selected by the frozen board profiles.
// params[191:160] occupies old SQ bits[239:208]; bit240 is key validity.
// Mode is static, not guessed from rkey==0 or from QP/host/address bits.
`timescale 1ns / 1ps
`default_nettype none
module rocev2_wrkey_sq_adapter #(
    parameter LEGACY_QP_KEY = 1
) (
    input  wire [239:0] s_axis_sq_tdata,
    input  wire [31:0]  s_axis_rkey,
    input  wire        s_axis_sq_tvalid,
    output wire        s_axis_sq_tready,
    output wire [247:0] m_axis_sq_tdata,
    output wire        m_axis_sq_tvalid,
    input  wire        m_axis_sq_tready
);
    assign m_axis_sq_tdata = LEGACY_QP_KEY ?
        {8'd0, s_axis_sq_tdata} :
        {7'd0, 1'b1, s_axis_rkey, s_axis_sq_tdata[207:0]};
    assign m_axis_sq_tvalid = s_axis_sq_tvalid;
    assign s_axis_sq_tready = m_axis_sq_tready;

    // Upstream must obey AXI stream stability while stalled, as for any
    // combinational width adapter. No accepted requests or ownership vanish.
    initial begin
        if (LEGACY_QP_KEY != 0 && LEGACY_QP_KEY != 1)
            $fatal(1, "LEGACY_QP_KEY must be exactly zero or one");
    end
endmodule
`default_nettype wire
