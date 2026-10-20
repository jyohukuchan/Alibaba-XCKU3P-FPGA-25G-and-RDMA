// SPDX-License-Identifier: BSD-2-Clause-Views
// Opt-in REAL generated FNS process/tables + REAL2000-slot pool binding.
// Not selected in the board/native parent. Raw context must come from trusted
// WR/QP owners; native producer admission/fences and core retirement remain TODO.
// No diagnostic allocator mux, bare-index free, idle/drain or CQ-success input.
module rocev2_owned_retrans(
 input wire clk,input wire rst,
 input wire [415:0] s_insert_data,input wire s_insert_valid,output wire s_insert_ready,
 input wire [223:0] s_update_data,input wire s_update_valid,output wire s_update_ready,
 input wire [191:0] s_retry_data,input wire s_retry_valid,output wire s_retry_ready,
 input wire [191:0] s_timer_data,input wire s_timer_valid,output wire s_timer_ready,
 output wire [575:0] m_event_data,output wire m_event_valid,input wire m_event_ready,
 output wire [319:0] m_rdinit_data,output wire m_rdinit_valid,input wire m_rdinit_ready,
 output wire [31:0] fault,output wire [7:0] phase,
 output wire [31:0] inserted,output wire [31:0] released,output wire [31:0] partial,
 // Diagnostics only, NEVER whole-core/WR/MR/CQ retirement authority.
 output wire pool_initialized,output wire pool_fault,
 output wire [11:0] pool_free,output wire [11:0] pool_active
);
wire [191:0] ar;wire arv,arr;
wire [255:0] ag,rr,rg;wire agv,agr,rrv,rrr,rgv,rgr;
wire [223:0] unused_pool_snapshot;wire unused_pool_snapshot_valid;
as02_owned_retrans_top process_and_tables(
 .ap_clk(clk),.ap_rst_n(!rst),
 .s_insert_TDATA(s_insert_data),.s_insert_TVALID(s_insert_valid),.s_insert_TREADY(s_insert_ready),
 .s_update_TDATA(s_update_data),.s_update_TVALID(s_update_valid),.s_update_TREADY(s_update_ready),
 .s_retry_TDATA(s_retry_data),.s_retry_TVALID(s_retry_valid),.s_retry_TREADY(s_retry_ready),
 .s_timer_TDATA(s_timer_data),.s_timer_TVALID(s_timer_valid),.s_timer_TREADY(s_timer_ready),
 .m_pool_alloc_TDATA(ar),.m_pool_alloc_TVALID(arv),.m_pool_alloc_TREADY(arr),
 .s_pool_alloc_TDATA(ag),.s_pool_alloc_TVALID(agv),.s_pool_alloc_TREADY(agr),
 .m_pool_release_TDATA(rr),.m_pool_release_TVALID(rrv),.m_pool_release_TREADY(rrr),
 .s_pool_release_TDATA(rg),.s_pool_release_TVALID(rgv),.s_pool_release_TREADY(rgr),
 .m_event_TDATA(m_event_data),.m_event_TVALID(m_event_valid),.m_event_TREADY(m_event_ready),
 .m_rdinit_TDATA(m_rdinit_data),.m_rdinit_TVALID(m_rdinit_valid),.m_rdinit_TREADY(m_rdinit_ready),
 .pool_credit(pool_free),.pool_initialized(pool_initialized),.pool_fault_in(pool_fault),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial));
rocev2_retrans_pool pool(
 .clk(clk),.rst(rst),
 .s_alloc_data(ar),.s_alloc_valid(arv),.s_alloc_ready(arr),
 .s_release_data(rr),.s_release_valid(rrv),.s_release_ready(rrr),
 .m_alloc_data(ag),.m_alloc_valid(agv),.m_alloc_ready(agr),
 .m_release_data(rg),.m_release_valid(rgv),.m_release_ready(rgr),
 // The real upstream marker injection/join is intentionally NOT claimed.
 // No normal process request sets a marker. Never silently discard one.
 .m_fence_data(unused_pool_snapshot),.m_fence_valid(unused_pool_snapshot_valid),.m_fence_ready(1'b0),
 .pool_fault(pool_fault),.initialized(pool_initialized),.free_slots(pool_free),.active_slots(pool_active));
endmodule
