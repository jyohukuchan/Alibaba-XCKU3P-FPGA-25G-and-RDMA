// SPDX-License-Identifier: BSD-2-Clause-Views
// Same real tables/pool with RX lookup. Only real binding-output acceptance
// creates a private receipt; lookup/unlock is NOT WR/MR/CQ retirement.
// Native packet/QP admission and complete wire RX producers remain unconnected.
// Opt-in REAL generated FNS process/tables + REAL2000-slot pool binding.
// Not selected in the board/native parent. Raw context must come from trusted
// WR/QP owners; native producer admission/fences and core retirement remain TODO.
// Actual timer is driven by real metadata insert/ACK/head/replay controls;
// there is NO externally injectable timer request port. Private receipts
// require real boundary handshakes. This is
// still NOT whole shared-core/MAC/DMA/CQ retirement or upstream closure.
module rocev2_owned_rx_lookup(
 input wire clk,input wire rst,
 input wire [319:0] s_rx_query_data,input wire s_rx_query_valid,output wire s_rx_query_ready,
 output wire [447:0] m_rx_binding_data,output wire m_rx_binding_valid,input wire m_rx_binding_ready,
 input wire [415:0] s_insert_data,input wire s_insert_valid,output wire s_insert_ready,
 input wire [223:0] s_update_data,input wire s_update_valid,output wire s_update_ready,
 input wire [191:0] s_retry_data,input wire s_retry_valid,output wire s_retry_ready,
 output wire [575:0] m_event_data,output wire m_event_valid,input wire m_event_ready,
 output wire [319:0] m_rdinit_data,output wire m_rdinit_valid,input wire m_rdinit_ready,
 output wire [319:0] m_fence_data,output wire m_fence_valid,input wire m_fence_ready,
 output wire [31:0] fault,output wire [7:0] phase,
 output wire [31:0] inserted,output wire [31:0] released,output wire [31:0] partial,
 // Diagnostics only, NEVER whole-core/WR/MR/CQ retirement authority.
 output wire pool_initialized,output wire pool_fault,
 output wire [11:0] pool_free,output wire [11:0] pool_active
);
wire [191:0] ar;wire arv,arr;
wire [255:0] ag,rr,rg;wire agv,agr,rrv,rrr,rgv,rgr;
wire [223:0] pool_snapshot;wire pool_snapshot_valid,pool_snapshot_ready;
wire [575:0] raw_event;wire raw_event_valid,raw_event_ready;
wire [319:0] raw_rdinit,raw_fence;wire raw_rdinit_valid,raw_rdinit_ready,raw_fence_valid,raw_fence_ready;
wire event_ack_ready,rdinit_ack_ready,fence_ack_ready;
reg event_ack_valid=0,rdinit_ack_valid=0,fence_ack_valid=0,receipt_fault=0;
reg [191:0] event_ack=0,rdinit_ack=0,fence_ack=0;
wire [31:0] process_fault;
wire [447:0] raw_binding;wire raw_binding_valid,raw_binding_ready,lookup_ack_ready;
reg [447:0] lookup_ack=0;reg lookup_ack_valid=0;
wire lookup_room=!lookup_ack_valid || lookup_ack_ready;
assign m_rx_binding_data=raw_binding;
assign m_rx_binding_valid=raw_binding_valid && lookup_room;
assign raw_binding_ready=m_rx_binding_ready && lookup_room;
assign fault=process_fault!=0?process_fault:(receipt_fault?32'h100:32'd0);
// Output markers are removed ONLY at the real raw AXIS head, after every
// earlier normal transfer. A private one-entry receipt register holds the
// exact token until the actual HLS consumer accepts it.
assign m_event_data=raw_event;
assign m_event_valid=raw_event_valid&&!raw_event[575];
assign raw_event_ready=raw_event[575]?!event_ack_valid:m_event_ready;
assign m_rdinit_data=raw_rdinit;
assign m_rdinit_valid=raw_rdinit_valid&&!raw_rdinit[319];
assign raw_rdinit_ready=raw_rdinit[319]?!rdinit_ack_valid:m_rdinit_ready;
assign m_fence_data=raw_fence;
assign m_fence_valid=raw_fence_valid&&!fence_ack_valid;
assign raw_fence_ready=m_fence_ready&&!fence_ack_valid;
always @(posedge clk)begin
 if(rst)begin
  lookup_ack_valid<=0;lookup_ack<=0;
  event_ack_valid<=0;rdinit_ack_valid<=0;fence_ack_valid<=0;receipt_fault<=0;
  event_ack<=0;rdinit_ack<=0;fence_ack<=0;
 end else begin
  if(lookup_ack_valid && lookup_ack_ready)lookup_ack_valid<=0;
  if(m_rx_binding_valid && m_rx_binding_ready)begin
   lookup_ack<=m_rx_binding_data;lookup_ack_valid<=1;
  end
  if(event_ack_valid&&event_ack_ready)event_ack_valid<=0;
  if(rdinit_ack_valid&&rdinit_ack_ready)rdinit_ack_valid<=0;
  if(fence_ack_valid&&fence_ack_ready)fence_ack_valid<=0;
  if(raw_event_valid&&raw_event_ready&&raw_event[575])begin
   event_ack<={24'd0,raw_event[167:0]};event_ack_valid<=1;
   if(raw_event[574:168]!==407'd0)receipt_fault<=1;
  end
  if(raw_rdinit_valid&&raw_rdinit_ready&&raw_rdinit[319])begin
   rdinit_ack<={24'd0,raw_rdinit[167:0]};rdinit_ack_valid<=1;
   if(raw_rdinit[318:168]!==151'd0)receipt_fault<=1;
  end
  // An AXIS buffered write is NOT external acceptance. ONLY this genuine
  // external response handshake releases the process's closed input window.
  if(raw_fence_valid&&raw_fence_ready)begin
   fence_ack<={24'd0,raw_fence[167:0]};fence_ack_valid<=1;
   if(raw_fence[319:311]!==9'd0 || raw_fence[310]!==1'b1)receipt_fault<=1;
  end
 end
end
as02_owned_rx_lookup_top process_and_tables(
 .s_rx_query_TDATA(s_rx_query_data),.s_rx_query_TVALID(s_rx_query_valid),.s_rx_query_TREADY(s_rx_query_ready),
 .m_rx_binding_TDATA(raw_binding),.m_rx_binding_TVALID(raw_binding_valid),.m_rx_binding_TREADY(raw_binding_ready),
 .s_rx_accept_TDATA(lookup_ack),.s_rx_accept_TVALID(lookup_ack_valid),.s_rx_accept_TREADY(lookup_ack_ready),
 .ap_clk(clk),.ap_rst_n(!rst),
 .s_insert_TDATA(s_insert_data),.s_insert_TVALID(s_insert_valid),.s_insert_TREADY(s_insert_ready),
 .s_update_TDATA(s_update_data),.s_update_TVALID(s_update_valid),.s_update_TREADY(s_update_ready),
 .s_retry_TDATA(s_retry_data),.s_retry_TVALID(s_retry_valid),.s_retry_TREADY(s_retry_ready),
 .m_pool_alloc_TDATA(ar),.m_pool_alloc_TVALID(arv),.m_pool_alloc_TREADY(arr),
 .s_pool_alloc_TDATA(ag),.s_pool_alloc_TVALID(agv),.s_pool_alloc_TREADY(agr),
 .m_pool_release_TDATA(rr),.m_pool_release_TVALID(rrv),.m_pool_release_TREADY(rrr),
 .s_pool_release_TDATA(rg),.s_pool_release_TVALID(rgv),.s_pool_release_TREADY(rgr),
 .m_event_TDATA(raw_event),.m_event_TVALID(raw_event_valid),.m_event_TREADY(raw_event_ready),
 .m_rdinit_TDATA(raw_rdinit),.m_rdinit_TVALID(raw_rdinit_valid),.m_rdinit_TREADY(raw_rdinit_ready),
 .s_pool_fence_TDATA(pool_snapshot),.s_pool_fence_TVALID(pool_snapshot_valid),.s_pool_fence_TREADY(pool_snapshot_ready),
 .s_event_accept_TDATA(event_ack),.s_event_accept_TVALID(event_ack_valid),.s_event_accept_TREADY(event_ack_ready),
 .s_rdinit_accept_TDATA(rdinit_ack),.s_rdinit_accept_TVALID(rdinit_ack_valid),.s_rdinit_accept_TREADY(rdinit_ack_ready),
 .s_fence_accept_TDATA(fence_ack),.s_fence_accept_TVALID(fence_ack_valid),.s_fence_accept_TREADY(fence_ack_ready),
 .m_fence_TDATA(raw_fence),.m_fence_TVALID(raw_fence_valid),.m_fence_TREADY(raw_fence_ready),
 .pool_credit(pool_free),.pool_initialized(pool_initialized),.pool_fault_in(pool_fault|receipt_fault),
 .fault(process_fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial));
rocev2_retrans_pool pool(
 .clk(clk),.rst(rst),
 .s_alloc_data(ar),.s_alloc_valid(arv),.s_alloc_ready(arr),
 .s_release_data(rr),.s_release_valid(rrv),.s_release_ready(rrr),
 .m_alloc_data(ag),.m_alloc_valid(agv),.m_alloc_ready(agr),
 .m_release_data(rg),.m_release_valid(rgv),.m_release_ready(rgr),
 // These markers come from the actual process producer FSM. No test mux.
 .m_fence_data(pool_snapshot),.m_fence_valid(pool_snapshot_valid),.m_fence_ready(pool_snapshot_ready),
 .pool_fault(pool_fault),.initialized(pool_initialized),.free_slots(pool_free),.active_slots(pool_active));
endmodule
