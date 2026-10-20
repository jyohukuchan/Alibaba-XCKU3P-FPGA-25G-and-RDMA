// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual BTH/EXH bytes and full-syndrome parser joined to same tables/pool.
// No effectful RX FSM, native auth, memory placement/CQ or whole-core drain.
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
module rocev2_owned_wire_rx(
 input wire clk,input wire rst,
 input wire [319:0] s_rx_descriptor_data,input wire s_rx_descriptor_valid,output wire s_rx_descriptor_ready,
 input wire [79:0] s_rx_packet_data,input wire s_rx_packet_valid,output wire s_rx_packet_ready,
 output wire [1023:0] m_rx_meta_data,output wire m_rx_meta_valid,input wire m_rx_meta_ready,
 output wire [79:0] m_rx_body_data,output wire m_rx_body_valid,input wire m_rx_body_ready,
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

wire [1023:0] raw_meta;wire raw_meta_valid,raw_meta_ready,meta_ack_ready,body_ack_ready;
wire [79:0] raw_body;wire raw_body_valid,raw_body_ready;
reg [1023:0] meta_ack=0,body_ack=0,body_owner=0;
reg meta_ack_valid=0,body_ack_valid=0,body_active=0;
wire rx_resume_ready;reg rx_resume_valid=0;reg [191:0] rx_resume=0;
wire [31:0] rx_ingress_fault,rx_front_fault,rx_frame_fault,rx_parser_words;
wire [7:0] rx_op=raw_meta[303:296];
wire [15:0] rx_length=raw_meta[799:784];
wire rx_no_body=rx_op==17 || ((rx_op==6 || rx_op==10 || rx_op==12) && rx_length==28);
wire rx_discard=!raw_meta[695] && (raw_meta[399:392]!=0 || (raw_meta[420] && raw_meta[419:417]!=0));
assign m_rx_meta_data=raw_meta;
assign m_rx_meta_valid=raw_meta_valid && !meta_ack_valid && !body_active;
assign raw_meta_ready=m_rx_meta_ready && !meta_ack_valid && !body_active;
assign m_rx_body_data=raw_body;
assign m_rx_body_valid=raw_body_valid && body_active && !body_ack_valid;
assign raw_body_ready=m_rx_body_ready && body_active && !body_ack_valid;
assign fault=process_fault!=0?process_fault:
 (rx_ingress_fault!=0?(32'h1000|rx_ingress_fault):
 (rx_front_fault!=0?(32'h2000|rx_front_fault):
 (rx_frame_fault!=0?(32'h3000|rx_frame_fault):(receipt_fault?32'h100:32'd0))));
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
assign m_fence_valid=raw_fence_valid&&!fence_ack_valid&&!rx_resume_valid;
assign raw_fence_ready=m_fence_ready&&!fence_ack_valid&&!rx_resume_valid;
always @(posedge clk)begin
 if(rst)begin
  meta_ack_valid<=0;body_ack_valid<=0;body_active<=0;rx_resume_valid<=0;
  meta_ack<=0;body_ack<=0;body_owner<=0;rx_resume<=0;
  event_ack_valid<=0;rdinit_ack_valid<=0;fence_ack_valid<=0;receipt_fault<=0;
  event_ack<=0;rdinit_ack<=0;fence_ack<=0;
 end else begin
  if(meta_ack_valid && meta_ack_ready)meta_ack_valid<=0;
  if(body_ack_valid && body_ack_ready)body_ack_valid<=0;
  if(rx_resume_valid && rx_resume_ready)rx_resume_valid<=0;
  if(m_rx_meta_valid && m_rx_meta_ready)begin
   meta_ack<=m_rx_meta_data;meta_ack_valid<=1;body_owner<=m_rx_meta_data;
   body_active<=!rx_no_body && !rx_discard;
   if(m_rx_meta_data[1023:1016]!==8'd0)receipt_fault<=1;
  end
  if(m_rx_body_valid && m_rx_body_ready && m_rx_body_data[72])begin
   body_ack<=body_owner;body_ack_valid<=1;body_active<=0;
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
   rx_resume<={24'd0,raw_fence[167:0]};rx_resume_valid<=1;
   if(raw_fence[319:311]!==9'd0 || raw_fence[310]!==1'b1)receipt_fault<=1;
  end
 end
end
as02_owned_wire_rx_top process_and_tables(
 .s_rx_descriptor_TDATA(s_rx_descriptor_data),.s_rx_descriptor_TVALID(s_rx_descriptor_valid),.s_rx_descriptor_TREADY(s_rx_descriptor_ready),
 .s_rx_packet_TDATA(s_rx_packet_data),.s_rx_packet_TVALID(s_rx_packet_valid),.s_rx_packet_TREADY(s_rx_packet_ready),
 .m_rx_meta_TDATA(raw_meta),.m_rx_meta_TVALID(raw_meta_valid),.m_rx_meta_TREADY(raw_meta_ready),
 .m_rx_body_TDATA(raw_body),.m_rx_body_TVALID(raw_body_valid),.m_rx_body_TREADY(raw_body_ready),
 .s_meta_accept_TDATA(meta_ack),.s_meta_accept_TVALID(meta_ack_valid),.s_meta_accept_TREADY(meta_ack_ready),
 .s_body_accept_TDATA(body_ack),.s_body_accept_TVALID(body_ack_valid),.s_body_accept_TREADY(body_ack_ready),
 .s_rx_resume_TDATA(rx_resume),.s_rx_resume_TVALID(rx_resume_valid),.s_rx_resume_TREADY(rx_resume_ready),
 .rx_ingress_fault(rx_ingress_fault),.rx_front_fault(rx_front_fault),.rx_frame_fault(rx_frame_fault),.rx_parser_words(rx_parser_words),
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
 .pool_credit(pool_free),.pool_initialized(pool_initialized),.pool_fault_in(pool_fault|receipt_fault|(rx_ingress_fault!=0)|(rx_front_fault!=0)|(rx_frame_fault!=0)),
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
