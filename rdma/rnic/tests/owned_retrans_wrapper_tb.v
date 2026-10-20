// SPDX-License-Identifier: BSD-2-Clause-Views
// The actual production composition, WITHOUT the other bench's pool mux.
`timescale 1ns/1ps
module wrapper_tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [415:0] idata=0;reg iv=0;wire ir;
reg [223:0] udata=0;reg uv=0;wire ur;
reg [191:0] tdata=0;reg tv=0;wire tr;
wire [575:0] edata;wire ev;reg er=0;
wire [319:0] ddata;wire dv;reg dr=0;
wire [31:0] fault,inserted,released,partial;wire [7:0] phase;
wire pi,pf;wire [11:0] free_slots,active_slots;
rocev2_owned_retrans dut(.clk(clk),.rst(rst),
 .s_insert_data(idata),.s_insert_valid(iv),.s_insert_ready(ir),
 .s_update_data(udata),.s_update_valid(uv),.s_update_ready(ur),
 .s_retry_data(192'd0),.s_retry_valid(1'b0),.s_retry_ready(),
 .s_timer_data(tdata),.s_timer_valid(tv),.s_timer_ready(tr),
 .m_event_data(edata),.m_event_valid(ev),.m_event_ready(er),
 .m_rdinit_data(ddata),.m_rdinit_valid(dv),.m_rdinit_ready(dr),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial),
 .pool_initialized(pi),.pool_fault(pf),.pool_free(free_slots),.pool_active(active_slots));
localparam [63:0] EP=64'hfedcba9876543210,SQ=64'he123456789abcdef;
localparam [63:0] LA=64'hfedcba9876543210,RA=64'h9123456789abcdef;
integer cycle=0,deadline;reg [247:0] lease;reg [575:0] expected;
reg es=0,ds=0;reg [575:0] eh;reg [319:0] dh;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"finite production-wrapper deadline");
 if(es && (!ev || edata!==eh))$fatal(1,"wrapper event unstable");
 if(ds && (!dv || ddata!==dh))$fatal(1,"wrapper RDinit unstable");
 es=ev&&!er;eh=edata;ds=dv&&!dr;dh=ddata;
 if(pf || fault!=0)$fatal(1,"production-wrapper fault %h",fault);
end else begin es=0;ds=0;end
task insert;
 input [31:0] op,len;input [63:0] seq;
 begin
  @(negedge clk);idata=0;idata[15:0]=2;idata[39:16]=24'hffffff;idata[71:40]=op;
  idata[104]=1;idata[105]=1;idata[169:106]=LA;idata[233:170]=RA;idata[265:234]=len;
  idata[266]=1;idata[270:267]=15;idata[334:271]=EP;idata[398:335]=seq;iv=1;
  @(posedge clk);while(!ir)@(posedge clk);@(negedge clk);iv=0;
 end
endtask
task update;
 input [23:0] psn;input [31:0] op;input [63:0] seq;
 begin
  @(negedge clk);udata=0;udata[15:0]=2;udata[39:16]=psn;udata[71:40]=op;
  udata[135:72]=EP;udata[199:136]=seq;uv=1;
  @(posedge clk);while(!ur)@(posedge clk);@(negedge clk);uv=0;
 end
endtask
task timer;
 input [63:0] seq;
 begin
  @(negedge clk);tdata={24'd0,seq,EP,24'hffffff,16'd2};tv=1;
  @(posedge clk);while(!tr)@(posedge clk);@(negedge clk);tv=0;
 end
endtask
function [575:0] event_word;
 input [23:0] psn;input [31:0] op,len;input [63:0] la,ra;input [247:0] token;
 begin
  event_word=0;event_word[23:0]=2;event_word[47:24]=psn;event_word[79:48]=op;
  event_word[112]=1;event_word[113]=1;event_word[177:114]=la;event_word[241:178]=ra;
  event_word[273:242]=len;event_word[274]=1;event_word[278:275]=15;event_word[279]=1;
  event_word[528:281]=token;
 end
endfunction
initial begin
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;
 while(!pi)@(negedge clk);
 insert(10,65,SQ);while(inserted!==1)@(negedge clk);
 timer(SQ);while(!ev)@(negedge clk);
 lease={SQ,EP,24'hffffff,16'd2,64'd1,16'd0};expected=event_word(24'hffffff,10,65,LA,RA,lease);
 if(edata!==expected)$fatal(1,"production WRITE actual metadata mismatch");
 update(24'hffffff,17,SQ);while(released!==1)@(negedge clk);
 repeat(37)@(negedge clk);
 if(active_slots!==0 || free_slots!==2000 || !ev || edata!==expected)$fatal(1,"pool zero/held WRITE distinction lost");
 @(negedge clk);er=1;@(posedge clk);@(negedge clk);er=0;
 insert(12,4161,SQ+64'd1);while(inserted!==2)@(negedge clk);
 update(24'hffffff,13,SQ+64'd1);while(partial!==1)@(negedge clk);
 timer(SQ+64'd1);while(!ev || !dv)@(negedge clk);
 lease={SQ+64'd1,EP,24'hffffff,16'd2,64'd2,16'd1};
 expected=event_word(0,12,65,LA+64'd4096,RA+64'd4096,lease);
 if(edata!==expected || ddata!=={7'd0,lease,1'b1,LA})$fatal(1,"production READ mutated immutable lease");
 update(0,15,SQ+64'd1);while(released!==2)@(negedge clk);
 repeat(37)@(negedge clk);
 if(active_slots!==0 || free_slots!==2000 || !ev || !dv || edata!==expected)$fatal(1,"pool zero/held READ distinction lost");
 $display("OWNED_RETRANS_WRAPPER_RTL {\"pass_test\":true,\"cycles\":%0d,\"inserted\":%0d,\"released\":%0d,\"partial\":%0d,\"test_pool_mux\":false,\"actual_production_composition\":true,\"real_outputs_held_after_pool_zero\":true,\"whole_core_drain\":false}",cycle,inserted,released,partial);
 $finish;
end
endmodule
