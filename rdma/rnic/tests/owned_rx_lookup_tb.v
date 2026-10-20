// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual same tables/timer/process and real pool. Packet/QP admission is still
// a test stimulus, not a native/wire RX/CQ/recovery proof. No test pool mux.
`timescale 1ns/1ps
module rx_lookup_tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [415:0] idata=0;reg iv=0;wire ir;
reg [223:0] udata=0;reg uv=0;wire ur;
reg [191:0] retry_data=0;reg retry_valid=0;wire retry_ready;
reg [319:0] query_data=0;reg query_valid=0;wire query_ready;
wire [447:0] binding_data;wire binding_valid;reg binding_ready=0;
wire [575:0] event_data;wire event_valid;
wire [319:0] rdinit_data,fence_data;wire rdinit_valid,fence_valid;reg fence_ready=0;
wire [31:0] fault,inserted,released,partial;wire [7:0] phase;
wire pool_initialized,pool_fault;wire [11:0] pool_free,pool_active;
integer which=1,cycle=0,deadline,i,bindings=0,fences=0,rdinits=0;
reg held=0,fheld=0;reg [447:0] prior;reg [319:0] prior_fence;
localparam [63:0] EP=64'hfedcba9876543210,SQ=64'h8765432100000001;
localparam [63:0] LA=64'hfedcba9876540000,RA=64'h123456789abc0000;
rocev2_owned_rx_lookup dut(.clk(clk),.rst(rst),
 .s_insert_data(idata),.s_insert_valid(iv),.s_insert_ready(ir),
 .s_update_data(udata),.s_update_valid(uv),.s_update_ready(ur),
 .s_retry_data(retry_data),.s_retry_valid(retry_valid),.s_retry_ready(retry_ready),
 .s_rx_query_data(query_data),.s_rx_query_valid(query_valid),.s_rx_query_ready(query_ready),
 .m_rx_binding_data(binding_data),.m_rx_binding_valid(binding_valid),.m_rx_binding_ready(binding_ready),
 .m_event_data(event_data),.m_event_valid(event_valid),.m_event_ready(1'b0),
 .m_rdinit_data(rdinit_data),.m_rdinit_valid(rdinit_valid),.m_rdinit_ready(1'b1),
 .m_fence_data(fence_data),.m_fence_valid(fence_valid),.m_fence_ready(fence_ready),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial),
 .pool_initialized(pool_initialized),.pool_fault(pool_fault),.pool_free(pool_free),.pool_active(pool_active));
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>400000)$fatal(1,"bounded actual RX lookup deadline");
 if(held && (binding_valid!==1'b1 || binding_data!==prior))$fatal(1,"lookup changed/lost held binding");
 held=binding_valid&&!binding_ready;prior=binding_data;
 if(fheld && (fence_valid!==1'b1 || fence_data!==prior_fence))$fatal(1,"lookup fence changed under stall");
 fheld=fence_valid&&!fence_ready;prior_fence=fence_data;
 if(binding_valid&&binding_ready)bindings=bindings+1;
 if(fence_valid&&fence_ready)fences=fences+1;
 if(rdinit_valid)rdinits=rdinits+1;
 if(pool_fault || (fault!==0 && which!=5))$fatal(1,"actual RX lookup fault%h phase%0d",fault,phase);
end else begin held=0;fheld=0;end
task insert_record(input [31:0] op,len,input [23:0] psn,input [63:0] seq);
begin
 @(negedge clk);idata=0;idata[15:0]=2;idata[39:16]=psn;idata[71:40]=op;
 idata[104]=1;idata[105]=1;idata[169:106]=LA;idata[233:170]=RA;idata[265:234]=len;
 idata[266]=1;idata[334:271]=EP;idata[398:335]=seq;iv=1;
 @(posedge clk);while(!ir)@(posedge clk);@(negedge clk);iv=0;
end endtask
task update_record(input [23:0] psn,input [31:0] op,input [63:0] seq);
begin
 @(negedge clk);udata=0;udata[15:0]=2;udata[39:16]=psn;udata[71:40]=op;
 udata[135:72]=EP;udata[199:136]=seq;uv=1;
 @(posedge clk);while(!ur)@(posedge clk);@(negedge clk);uv=0;
end endtask
task query(input [23:0] qpn,psn,input [7:0] op,syndrome,input aeth,input [63:0] epoch);
begin
 @(negedge clk);query_data=0;query_data[23:0]=qpn;query_data[47:24]=psn;query_data[55:48]=op;
 query_data[119:56]=epoch;query_data[127:120]=syndrome;query_data[128]=aeth;query_valid=1;
 @(posedge clk);while(!query_ready)@(posedge clk);@(negedge clk);query_valid=0;
end endtask
function [247:0] lease(input [15:0] index,input [63:0] generation,input [23:0] psn,input [63:0] seq);
begin lease={seq,EP,psn,16'd2,generation,index};end endfunction
task expect_binding(input [23:0] qpn,psn,input [7:0] op,syndrome,input aeth,input [63:0] epoch,
 input [7:0] status,input [11:0] walked,input head,input [23:0] delta,input [247:0] token);
reg [447:0] expected;
begin
 deadline=cycle+30000;while(!binding_valid)begin if(cycle>deadline)$fatal(1,"missing actual lookup result phase%0d",phase);@(negedge clk);end
 expected=0;expected[247:0]=token;expected[271:248]=qpn;expected[295:272]=psn;expected[303:296]=op;
 expected[367:304]=epoch;expected[391:368]=delta;expected[399:392]=status;expected[411:400]=walked;
 expected[419:412]=syndrome;expected[420]=aeth;expected[421]=head;expected[422]=1;
 if(binding_data!==expected)$fatal(1,"wrong actual table binding got%h expected%h",binding_data,expected);
 repeat(31)@(negedge clk);
end endtask
task accept_binding;
begin @(negedge clk);binding_ready=1;@(posedge clk);@(negedge clk);binding_ready=0;repeat(30)@(negedge clk);end endtask
task wait_inserted(input [31:0] count);
begin deadline=cycle+30000;while(inserted!==count)begin if(cycle>deadline)$fatal(1,"actual insert missing");@(negedge clk);end end endtask
task wait_released(input [31:0] count);
begin deadline=cycle+30000;while(released!==count)begin if(cycle>deadline)$fatal(1,"actual pool return missing");@(negedge clk);end end endtask
function [167:0] marker_owner;input [63:0] seq;begin marker_owner={seq,EP,24'hffffff,16'd2};end endfunction
task old_input_markers;
reg [167:0] token;
begin
 token=marker_owner(SQ);
 @(negedge clk);idata=0;idata[15:0]=2;idata[39:16]=24'hffffff;idata[334:271]=EP;idata[398:335]=SQ;idata[399]=1;iv=1;
 @(posedge clk);while(!ir)@(posedge clk);@(negedge clk);iv=0;
 retry_data={23'd0,1'b1,token};retry_valid=1;
 @(posedge clk);while(!retry_ready)@(posedge clk);@(negedge clk);retry_valid=0;
 udata=0;udata[15:0]=2;udata[39:16]=24'hffffff;udata[135:72]=EP;udata[199:136]=SQ;udata[200]=1;uv=1;
 @(posedge clk);while(!ur)@(posedge clk);@(negedge clk);uv=0;
end endtask
task query_marker;
begin @(negedge clk);query_data=0;query_data[129]=1;query_data[297:130]=marker_owner(SQ);query_valid=1;
 @(posedge clk);while(!query_ready)@(posedge clk);@(negedge clk);query_valid=0;end endtask
initial begin
 if(!$value$plusargs("CASE=%d",which))which=1;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;while(!pool_initialized)@(negedge clk);
 if(which==1)begin
  insert_record(10,65,24'hffffff,SQ);wait_inserted(1);insert_record(10,65,0,SQ+1);wait_inserted(2);
  query(2,0,17,0,1,EP);expect_binding(2,0,17,0,1,EP,0,2,0,0,lease(1,2,0,SQ+1));
  update_record(24'hffffff,17,SQ);repeat(127)@(negedge clk);
  if(released!==0 || pool_active!==2 || !binding_valid)$fatal(1,"buffered lookup reopened actual process/returned pool lease");
  accept_binding();wait_released(1);
  query(2,0,17,0,1,EP);expect_binding(2,0,17,0,1,EP,0,1,1,0,lease(1,2,0,SQ+1));accept_binding();
  update_record(0,17,SQ+1);wait_released(2);
  query(2,0,17,0,1,EP);expect_binding(2,0,17,0,1,EP,1,0,0,0,0);accept_binding();
  if(pool_active!==0 || released!==2)$fatal(1,"lookup is not metadata-valid/free ownership");
 end else if(which==2)begin
  insert_record(12,4161,24'hffffff,SQ);wait_inserted(1);
  query(2,24'hffffff,13,0,1,EP);expect_binding(2,24'hffffff,13,0,1,EP,0,1,1,0,lease(0,1,24'hffffff,SQ));accept_binding();
  if(partial!==0 || released!==0 || rdinits!=0)$fatal(1,"lookup mutated READ");
  update_record(24'hffffff,13,SQ);while(partial!==1)@(negedge clk);
  query(2,0,15,0,1,EP);expect_binding(2,0,15,0,1,EP,0,1,1,0,lease(0,1,24'hffffff,SQ));accept_binding();
  query(2,1,14,0,0,EP);expect_binding(2,1,14,0,0,EP,1,1,0,0,0);accept_binding();
  query(2,24'hffffff,15,0,1,EP);expect_binding(2,24'hffffff,15,0,1,EP,1,1,0,0,0);accept_binding();
  if(partial!==1 || released!==0 || pool_active!==1)$fatal(1,"READ lookup falsely completes/retags");
 end else if(which==3)begin
  insert_record(12,32'hffffffff,24'hfffffe,SQ);wait_inserted(1);
  query(2,24'h0ffffd,15,0,1,EP);expect_binding(2,24'h0ffffd,15,0,1,EP,0,1,1,24'h0fffff,lease(0,1,24'hfffffe,SQ));accept_binding();
  query(2,24'h0ffffe,15,0,1,EP);expect_binding(2,24'h0ffffe,15,0,1,EP,1,1,0,0,0);accept_binding();
  if(released!==0 || partial!==0 || pool_active!==1)$fatal(1,"full length lookup mutated metadata");
 end else if(which==4)begin
  insert_record(10,65,0,SQ);wait_inserted(1);insert_record(10,65,0,SQ+1);wait_inserted(2);
  query(2,0,17,0,1,EP);expect_binding(2,0,17,0,1,EP,2,2,0,0,0);accept_binding();
  query(2,0,17,0,1,EP-1);expect_binding(2,0,17,0,1,EP-1,3,1,0,0,0);accept_binding();
  if(released!==0 || pool_active!==2)$fatal(1,"ambiguous/stale epoch lookup freed owner");
 end else if(which==5)begin
  insert_record(10,65,0,SQ);wait_inserted(1);query(24'h010002,0,17,0,1,EP);
  deadline=cycle+1000;while(fault===0)begin if(cycle>deadline)$fatal(1,"full24QPN was truncated/accepted");@(negedge clk);end
  repeat(127)@(negedge clk);
  if(fault!==30 || binding_valid || released!==0 || pool_active!==1)$fatal(1,"malformed query side effect");
 end else if(which==6)begin
  insert_record(10,65,24'hffffff,SQ);wait_inserted(1);old_input_markers();repeat(500)@(negedge clk);
  if(fence_valid || dut.pool_snapshot_valid)$fatal(1,"missing fifth query marker became success");
  query_marker();deadline=cycle+20000;while(!fence_valid)begin if(cycle>deadline)$fatal(1,"actual fifth marker fence missing phase%0d",phase);@(negedge clk);end
  if(fence_data[167:0]!==marker_owner(SQ) || fence_data[175:168]!==8'd2 || fence_data[179:176]!==4'hf ||
     fence_data[184:180]!==5'h1f || fence_data[302]!==1'b1 || fence_data[310]!==1'b1 || fence_data[319:311]!==0)
   $fatal(1,"wrong actual lookup-boundary fence%h",fence_data);
  query(2,24'hffffff,17,0,1,EP);repeat(127)@(negedge clk);
  if(binding_valid || released!==0 || pool_active!==1)$fatal(1,"buffered fence reopened query window");
  @(negedge clk);fence_ready=1;@(posedge clk);@(negedge clk);fence_ready=0;
  expect_binding(2,24'hffffff,17,0,1,EP,0,1,1,0,lease(0,1,24'hffffff,SQ));accept_binding();
 end else if(which==7)begin
  insert_record(12,4161,24'hffffff,SQ);wait_inserted(1);
  query(2,24'hffffff,17,8'h20,1,EP);expect_binding(2,24'hffffff,17,8'h20,1,EP,0,1,1,0,lease(0,1,24'hffffff,SQ));accept_binding();
  query(2,24'hffffff,17,8'h60,1,EP);expect_binding(2,24'hffffff,17,8'h60,1,EP,0,1,1,0,lease(0,1,24'hffffff,SQ));accept_binding();
  query(2,24'hffffff,17,0,1,EP);expect_binding(2,24'hffffff,17,0,1,EP,1,1,0,0,0);accept_binding();
  if(released!==0 || partial!==0 || rdinits!=0 || pool_active!==1)$fatal(1,"control syndrome interpreted as completion");
 end else if(which==8)begin
  for(i=0;i<2000;i=i+1)begin insert_record(10,65,i,SQ+i);wait_inserted(i+1);end
  if(pool_free!==0 || pool_active!==2000)$fatal(1,"actual pool capacity reduced");
  query(2,1999,17,0,1,EP);expect_binding(2,1999,17,0,1,EP,0,2000,0,0,lease(1999,2000,1999,SQ+1999));accept_binding();
  if(released!==0 || pool_active!==2000)$fatal(1,"full-table query is not retirement");
 end else $fatal(1,"unknown case");
 repeat(23)@(negedge clk);
 $display("OWNED_RX_LOOKUP_RTL {\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"bindings\":%0d,\"fences\":%0d,\"inserted\":%0d,\"released\":%0d,\"partial\":%0d,\"fault\":%0d,\"metadata_entries\":2000,\"actual_same_table_lookup\":true,\"test_pool_mux\":false,\"native_CQ\":false}",which,cycle,bindings,fences,inserted,released,partial,fault);$finish;
end
endmodule
