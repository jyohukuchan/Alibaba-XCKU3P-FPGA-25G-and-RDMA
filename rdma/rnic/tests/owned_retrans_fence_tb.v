// SPDX-License-Identifier: BSD-2-Clause-Views
// The actual production composition, WITHOUT the other bench's pool mux.
`timescale 1ns/1ps
module fence_tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [415:0] idata=0;reg iv=0;wire ir;
reg [223:0] udata=0;reg uv=0;wire ur;
reg [191:0] tdata=0,rdata=0;reg tv=0,rv=0;wire tr,rr;
wire [319:0] fdata;wire fv;reg fr=0;
integer which=0,queries=0,alloc_markers=0,release_markers=0,pool_queries=0;
wire [575:0] edata;wire ev;reg er=0;
wire [319:0] ddata;wire dv;reg dr=0;
wire [31:0] fault,inserted,released,partial;wire [7:0] phase;
wire pi,pf;wire [11:0] free_slots,active_slots;
rocev2_owned_retrans_fenced dut(.clk(clk),.rst(rst),
 .s_insert_data(idata),.s_insert_valid(iv),.s_insert_ready(ir),
 .s_update_data(udata),.s_update_valid(uv),.s_update_ready(ur),
 .s_retry_data(rdata),.s_retry_valid(rv),.s_retry_ready(rr),
 .s_timer_data(tdata),.s_timer_valid(tv),.s_timer_ready(tr),
 .m_event_data(edata),.m_event_valid(ev),.m_event_ready(er),
 .m_rdinit_data(ddata),.m_rdinit_valid(dv),.m_rdinit_ready(dr),
 .m_fence_data(fdata),.m_fence_valid(fv),.m_fence_ready(fr),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial),
 .pool_initialized(pi),.pool_fault(pf),.pool_free(free_slots),.pool_active(active_slots));
localparam [63:0] EP=64'hfedcba9876543210,SQ=64'he123456789abcdef;
localparam [63:0] LA=64'hfedcba9876543210,RA=64'h9123456789abcdef;
integer cycle=0,deadline;reg [247:0] lease;reg [575:0] expected;reg [247:0] lease2;reg [63:0] digest;
reg es=0,ds=0,fs=0;reg [575:0] eh;reg [319:0] dh;reg [319:0] fh;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"finite production-wrapper deadline");
 if(es && (!ev || edata!==eh))$fatal(1,"wrapper event unstable");
 if(ds && (!dv || ddata!==dh))$fatal(1,"wrapper RDinit unstable");
 es=ev&&!er;eh=edata;ds=dv&&!dr;dh=ddata;
 if(pf || (fault!=0 && which!=4 && which!=5))$fatal(1,"production-wrapper fault %h phase%0d",fault,phase);
 if(fs && (!fv || fdata!==fh))$fatal(1,"barrier response changed under stall");
 fs=fv&&!fr;fh=fdata;
 if(ev && edata[575])$fatal(1,"private event marker leaked to normal consumer");
 if(dv && ddata[319])$fatal(1,"private RDinit marker leaked to normal consumer");
 if(dut.arv&&dut.arr&&dut.ar[168])alloc_markers=alloc_markers+1;
 if(dut.rrv&&dut.rrr&&dut.rr[248])release_markers=release_markers+1;
 if(dut.pool_snapshot_valid&&dut.pool_snapshot_ready)pool_queries=pool_queries+1;
 if(fv&&fr)queries=queries+1;
end else begin es=0;ds=0;fs=0;end
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

function [167:0] owner;
 input [63:0] seq;begin owner={seq,EP,24'hffffff,16'd2};end
endfunction
function [63:0] record_digest;
 input [23:0] psn;input [31:0] op,len;input [63:0] la,ra;input [247:0] token;
 reg [575:0] flat;reg [63:0] value;integer j;
 begin
  flat=0;flat[32]=1;flat[33]=1;flat[57:34]=psn;flat[105:74]=op;
  flat[169:106]=la;flat[233:170]=ra;flat[265:234]=len;flat[266]=1;flat[270:267]=15;
  flat[271]=1;flat[272]=1;flat[520:273]=token;value=0;
  for(j=0;j<9;j=j+1)value=value^flat[j*64+:64];
  record_digest=value;
 end
endfunction
task mark;
 input integer source;input [167:0] token;input bad;
 begin
  @(negedge clk);
  case(source)
   0:begin
    udata=0;udata[15:0]=token[15:0];udata[39:16]=token[39:16];
    udata[135:72]=token[103:40];udata[199:136]=token[167:104];udata[200]=1;uv=1;
   end
   1:begin rdata={23'd0,1'b1,token};rv=1;end
   2:begin tdata={23'd0,1'b1,token};tv=1;end
   3:begin
    idata=0;idata[15:0]=token[15:0];idata[39:16]=token[39:16];
    idata[334:271]=token[103:40];idata[398:335]=token[167:104];idata[399]=1;
    if(bad)idata[40]=1;iv=1;
   end
  endcase
  @(posedge clk);
  while((source==0&&!ur)||(source==1&&!rr)||(source==2&&!tr)||(source==3&&!ir))@(posedge clk);
  @(negedge clk);uv=0;rv=0;tv=0;iv=0;
 end
endtask
task all_markers;
 input [63:0] seq;
 begin mark(3,owner(seq),0);mark(1,owner(seq),0);mark(0,owner(seq),0);mark(2,owner(seq),0);end
endtask
task expect_fence;
 input [63:0] seq;input [7:0] status;input [11:0] active;input [63:0] hash;
 begin
  deadline=cycle+10000;while(!fv)begin if(cycle>deadline)$fatal(1,"actual barrier join missing phase%0d",phase);@(negedge clk);end
  if((^fdata)===1'bx || fdata[167:0]!==owner(seq) || fdata[175:168]!==status ||
   fdata[179:176]!==15 || fdata[184:180]!==31 || !fdata[185] ||
   fdata[197:186]!==active || fdata[209:198]!==active ||
   fdata[221:210]!==(12'd2000-active) || fdata[285:222]!==hash ||
   fdata[297:286]!==2000 || fdata[300:298]!=={2'd0,status==2} || !fdata[301] || fdata[319:302]!==0)
   $fatal(1,"wrong REAL barrier response %h expected hash%h status%0d",fdata,hash,status);
  repeat(23)@(negedge clk);
 end
endtask
task accept_fence;
 begin @(negedge clk);fr=1;@(posedge clk);@(negedge clk);fr=0;end
endtask
task take_event;
 begin @(negedge clk);er=1;@(posedge clk);@(negedge clk);er=0;end
endtask
initial begin
 if(!$value$plusargs("CASE=%d",which))which=1;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;while(!pi)@(negedge clk);
 if(which==4 || which==5)begin
  mark(0,owner(SQ),0);mark(2,owner(SQ),0);mark(1,owner(SQ),0);
  repeat(500)@(negedge clk);
  if(fv || alloc_markers!=0 || release_markers!=0 || pool_queries!=0)$fatal(1,"missing input marker became success");
  if(which==4)mark(3,owner(SQ)^168'h10000000000000000000000000000000000,0);
  else mark(3,owner(SQ),1);
  deadline=cycle+1000;while(fault===0)begin if(cycle>deadline)$fatal(1,"bad marker not rejected");@(negedge clk);end
  repeat(127)@(negedge clk);
  if(fault!==11 || fv || inserted!==0 || pool_queries!=0)$fatal(1,"bad marker caused table/pool or false completion");
 end else if(which==2)begin
  insert(12,4161,SQ);while(inserted!==1)@(negedge clk);
  lease={SQ,EP,24'hffffff,16'd2,64'd1,16'd0};
  update(24'hffffff,13,SQ);while(partial!==1)@(negedge clk);
  timer(SQ);while(!ev || !dv)@(negedge clk);
  expected=event_word(0,12,65,LA+64'd4096,RA+64'd4096,lease);
  if(edata!==expected || ddata!=={7'd0,lease,1'b1,LA})$fatal(1,"READ normal event/immutable lease wrong");
  update(0,15,SQ);while(released!==1)@(negedge clk);
  all_markers(SQ);take_event();
  deadline=cycle+10000;while(pool_queries!=1)begin if(cycle>deadline)$fatal(1,"actual pool result missing");@(negedge clk);end
  repeat(127)@(negedge clk);
  if(fv || !dv || active_slots!==0 || alloc_markers!=1 || release_markers!=1 || pool_queries!=1)
   $fatal(1,"pool zero/event acceptance bypassed real held RDinit");
  @(negedge clk);dr=1;@(posedge clk);@(negedge clk);dr=0;
  digest=record_digest(0,12,65,LA+64'd4096,RA+64'd4096,lease);
  expect_fence(SQ,0,0,digest);accept_fence();
 end else if(which==3)begin
  insert(10,65,SQ);while(inserted!==1)@(negedge clk);
  lease={SQ,EP,24'hffffff,16'd2,64'd1,16'd0};
  digest=record_digest(24'hffffff,10,65,LA,RA,lease);
  all_markers(SQ);expect_fence(SQ,2,1,digest);accept_fence();
  if(released!==0 || active_slots!==1)$fatal(1,"BUSY response freed owner");
  update(24'hffffff,17,SQ);while(released!==1)@(negedge clk);
  all_markers(SQ);expect_fence(SQ,0,0,digest);accept_fence();
 end else begin
  insert(10,65,SQ);while(inserted!==1)@(negedge clk);
  lease={SQ,EP,24'hffffff,16'd2,64'd1,16'd0};
  timer(SQ);while(!ev)@(negedge clk);
  expected=event_word(24'hffffff,10,65,LA,RA,lease);if(edata!==expected)$fatal(1,"WRITE event wrong");
  update(24'hffffff,17,SQ);while(released!==1)@(negedge clk);
  all_markers(SQ);
  deadline=cycle+10000;while(pool_queries!=1)begin if(cycle>deadline)$fatal(1,"actual pool result missing");@(negedge clk);end
  repeat(127)@(negedge clk);
  if(fv || !ev || active_slots!==0 || alloc_markers!=1 || release_markers!=1 || pool_queries!=1)
   $fatal(1,"pool zero bypassed real held event");
  take_event();digest=record_digest(24'hffffff,10,65,LA,RA,lease);
  expect_fence(SQ,0,0,digest);
  // Queue actual later input behind the marker while response is held in
  // registered AXIS output. It MUST NOT execute before genuine acceptance.
  insert(10,65,SQ+64'd1);repeat(127)@(negedge clk);
  if(inserted!==1 || active_slots!==0 || !fv)$fatal(1,"buffered AXIS write reopened input fence early");
  accept_fence();while(inserted!==2)@(negedge clk);
  if(active_slots!==1 || released!==1)$fatal(1,"later WR not honestly retained after fence acceptance");
 end
 repeat(17)@(negedge clk);
 $display("OWNED_RETRANS_FENCE_RTL {\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"queries\":%0d,\"actual_alloc_markers\":%0d,\"actual_release_markers\":%0d,\"actual_pool_queries\":%0d,\"inserted\":%0d,\"released\":%0d,\"partial\":%0d,\"fault\":%0d,\"metadata_entries\":2000,\"actual_production_composition\":true,\"test_pool_mux\":false,\"whole_shared_core_drain\":false}",which,cycle,queries,alloc_markers,release_markers,pool_queries,inserted,released,partial,fault);
 $finish;
end
endmodule
