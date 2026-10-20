// SPDX-License-Identifier: BSD-2-Clause-Views
// Candidate atomic transaction domain: ONE existing arbiter/backend, not a
// second memory namespace. Reserve across read/status/write/fence/response.
// Every competing DMA client in the atomicity domain MUST use normal_*.
// This does not exclude CPUs/other PCIe devices; it is NOT IB_ATOMIC_GLOB.
// Default native graph does not instantiate this candidate yet.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_memory_bridge (
    input wire clk, input wire rst, input wire enable,
    input wire atomic_lock_request, output wire atomic_lock_granted,
    input wire [1:0] s_command_write,
    input wire [127:0] s_command_offset,
    input wire [63:0] s_command_length,
    input wire [63:0] s_command_key,
    input wire [31:0] s_command_tag,
    input wire [1:0] s_command_valid, output wire [1:0] s_command_ready,
    input wire [1023:0] s_axis_write_tdata,
    input wire [127:0] s_axis_write_tkeep,
    input wire [1:0] s_axis_write_tlast, input wire [1:0] s_axis_write_tvalid,
    output wire [1:0] s_axis_write_tready,
    output wire [1023:0] m_axis_read_tdata,
    output wire [127:0] m_axis_read_tkeep,
    output wire [1:0] m_axis_read_tlast, output wire [1:0] m_axis_read_tvalid,
    input wire [1:0] m_axis_read_tready,
    output wire [31:0] m_status_tag, output wire [15:0] m_status_error,
    output wire [1:0] m_status_valid, input wire [1:0] m_status_ready,
    output wire m_command_write, output wire [63:0] m_command_offset,
    output wire [31:0] m_command_length, output wire [31:0] m_command_key,
    output wire [15:0] m_command_tag, output wire m_command_valid,
    input wire m_command_ready,
    output wire [511:0] m_axis_write_tdata,
    output wire [63:0] m_axis_write_tkeep,
    output wire m_axis_write_tlast, output wire m_axis_write_tvalid,
    input wire m_axis_write_tready,
    input wire [511:0] s_axis_read_tdata,
    input wire [63:0] s_axis_read_tkeep,
    input wire s_axis_read_tlast, input wire s_axis_read_tvalid,
    output wire s_axis_read_tready,
    input wire [15:0] s_status_tag, input wire [7:0] s_status_error,
    input wire s_status_valid, output wire s_status_ready,
    output wire [1:0] client_guard, output wire configuration_guard,
    output wire busy, output wire fault, output wire [7:0] fault_code
);
reg reserved=0,lock_fault=0;
wire arbiter_busy,arbiter_guard,arbiter_fault;
wire [7:0] arbiter_fault_code;
wire [1:0] arbiter_client_guard,ready;
wire lock_known=atomic_lock_request===1'b0 || atomic_lock_request===1'b1;
wire normal_allowed=!reserved && atomic_lock_request===1'b0 && !lock_fault;
wire [1:0] valid={s_command_valid[1] && reserved && !lock_fault,
    s_command_valid[0] && normal_allowed};
assign s_command_ready={ready[1] && reserved && !lock_fault,ready[0] && normal_allowed};
assign atomic_lock_granted=reserved && !fault && !rst;
assign fault=lock_fault || arbiter_fault;
assign fault_code=lock_fault ? 8'h6a:arbiter_fault_code;
assign client_guard=fault ? 2'b11:arbiter_client_guard | (reserved ? 2'b10:2'b00);
assign busy=reserved || arbiter_busy || fault;
assign configuration_guard=busy || arbiter_guard || atomic_lock_request!==1'b0;
always @(posedge clk)begin
    if(rst)begin reserved<=0;lock_fault<=0;end
    else begin
        if(!lock_known || (s_command_valid[1] && !reserved))lock_fault<=1;
        if(!reserved && !arbiter_busy && enable && atomic_lock_request===1'b1 && !fault)
            reserved<=1;
        // A fault retains the reservation. Disable is not cancellation.
        if(reserved && atomic_lock_request===1'b0 && !arbiter_busy && !fault)reserved<=0;
    end
end
rocev2_memory_client_arbiter arbiter (
    .clk(clk),.rst(rst),.enable(enable),
    .s_command_write(s_command_write),.s_command_offset(s_command_offset),
    .s_command_length(s_command_length),.s_command_key(s_command_key),
    .s_command_tag(s_command_tag),.s_command_valid(valid),.s_command_ready(ready),
    .s_axis_write_tdata(s_axis_write_tdata),.s_axis_write_tkeep(s_axis_write_tkeep),
    .s_axis_write_tlast(s_axis_write_tlast),.s_axis_write_tvalid(s_axis_write_tvalid),
    .s_axis_write_tready(s_axis_write_tready),.m_axis_read_tdata(m_axis_read_tdata),
    .m_axis_read_tkeep(m_axis_read_tkeep),.m_axis_read_tlast(m_axis_read_tlast),
    .m_axis_read_tvalid(m_axis_read_tvalid),.m_axis_read_tready(m_axis_read_tready),
    .m_status_tag(m_status_tag),.m_status_error(m_status_error),
    .m_status_valid(m_status_valid),.m_status_ready(m_status_ready),
    .m_command_write(m_command_write),.m_command_offset(m_command_offset),
    .m_command_length(m_command_length),.m_command_key(m_command_key),
    .m_command_tag(m_command_tag),.m_command_valid(m_command_valid),
    .m_command_ready(m_command_ready),.m_axis_write_tdata(m_axis_write_tdata),
    .m_axis_write_tkeep(m_axis_write_tkeep),.m_axis_write_tlast(m_axis_write_tlast),
    .m_axis_write_tvalid(m_axis_write_tvalid),.m_axis_write_tready(m_axis_write_tready),
    .s_axis_read_tdata(s_axis_read_tdata),.s_axis_read_tkeep(s_axis_read_tkeep),
    .s_axis_read_tlast(s_axis_read_tlast),.s_axis_read_tvalid(s_axis_read_tvalid),
    .s_axis_read_tready(s_axis_read_tready),.s_status_tag(s_status_tag),
    .s_status_error(s_status_error),.s_status_valid(s_status_valid),.s_status_ready(s_status_ready),
    .client_guard(arbiter_client_guard),.configuration_guard(arbiter_guard),
    .busy(arbiter_busy),.fault(arbiter_fault),.fault_code(arbiter_fault_code)
);
endmodule
`resetall
