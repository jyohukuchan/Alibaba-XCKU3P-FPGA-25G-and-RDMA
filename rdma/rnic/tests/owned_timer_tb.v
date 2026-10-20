// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual timer producer FOUR-STATE reset/context/closure tests, no fake RAM.
`timescale 1ns/1ps
module timer_tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [255:0] td=0;reg tv=0;wire tr;
reg [543:0] cd=0;reg cv=0;wire cr;
reg [191:0] sd=0;reg sv=0;wire sr;
wire [191:0] rd;wire rv;reg rr=0;
wire [255:0] bd;wire bv;reg br=0;
wire [31:0] fd;wire fv;
as02_owned_timer_probe_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_tx_TDATA(td),.s_tx_TVALID(tv),.s_tx_TREADY(tr),
 .s_ctrl_TDATA(cd),.s_ctrl_TVALID(cv),.s_ctrl_TREADY(cr),
 .s_resume_TDATA(sd),.s_resume_TVALID(sv),.s_resume_TREADY(sr),
 .m_retry_TDATA(rd),.m_retry_TVALID(rv),.m_retry_TREADY(rr),
 .m_barrier_TDATA(bd),.m_barrier_TVALID(bv),.m_barrier_TREADY(br),
 .m_fault_TDATA(fd),.m_fault_TVALID(fv),.m_fault_TREADY(1'b1));
integer cycle=0,which=0,queries=0,deadline;
reg rs=0,bs=0;reg [191:0] rh;reg [255:0] bh;
reg [247:0] a,b,c;reg [255:0] word;reg [543:0] ctrl;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>10000)$fatal(1,"bounded owned timer producer test");
 if(rs && (!rv || rd!==rh))$fatal(1,"timer marker changed under output stall");
 if(bs && (!bv || bd!==bh))$fatal(1,"timer snapshot changed under output stall");
 rs=rv&&!rr;rh=rd;bs=bv&&!br;bh=bd;
 if(fv && which==1)$fatal(1,"valid owned timer context fault %0d",fd);
 if(bv&&br)queries=queries+1;
end else begin rs=0;bs=0;end
function [247:0] lease;
 input [63:0] seq;input [23:0] psn;input [63:0] gen;input [15:0] index;
 begin lease={seq,64'hfedcba9876543210,psn,16'd7,gen,index};end
endfunction
function [543:0] control;
 input [247:0] old,next;input valid,advance;
 begin control=0;control[247:0]=old;control[495:248]=next;control[496]=valid;control[497]=advance;end
endfunction
task tx;
 input [255:0] value;
 begin @(negedge clk);td=value;tv=1;@(posedge clk);while(!tr)@(posedge clk);@(negedge clk);tv=0;end
endtask
task update;
 input [543:0] value;
 begin @(negedge clk);cd=value;cv=1;@(posedge clk);while(!cr)@(posedge clk);@(negedge clk);cv=0;end
endtask
task resume;
 input [167:0] token;
 begin @(negedge clk);sd={24'd0,token};sv=1;@(posedge clk);while(!sr)@(posedge clk);@(negedge clk);sv=0;end
endtask
task query;
 input [247:0] l;input [7:0] status;input bound;input do_resume;
 reg [543:0] m;reg [255:0] t;integer endat;
 begin
  m=0;m[167:0]=l[247:80];m[498]=1;update(m);endat=cycle+1000;
  while(!rv)begin if(cycle>endat)$fatal(1,"actual timeout-producer marker missing");@(negedge clk);end
  if(rd!=={23'd0,1'b1,l[247:80]})$fatal(1,"wrong immutable timer producer token");
  repeat(17)@(negedge clk);rr=1;@(posedge clk);@(negedge clk);rr=0;
  repeat(37)@(negedge clk);if(bv)$fatal(1,"missing TX marker inferred from idle");
  t=0;t[167:0]=l[247:80];t[249]=1;tx(t);
  while(!bv)begin if(cycle>endat)$fatal(1,"actual timer table snapshot missing");@(negedge clk);end
  if((^bd)===1'bx || bd[167:0]!==l[247:80] || bd[175:168]!==status || !bd[176] ||
   bd[177]!==bound || bd[178]!==bound || bd[215]!==(status==2) || bd[255:216]!==0 ||
   (bound && bd[210:179]==0) || (!bound && bd[210:179]!==0) || bd[214:211]!==0)
   $fatal(1,"wrong real timer snapshot %h",bd);
  repeat(17)@(negedge clk);br=1;@(posedge clk);@(negedge clk);br=0;
  if(do_resume)resume(l[247:80]);
 end
endtask
initial begin
 if(!$value$plusargs("CASE=%d",which))which=1;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;
 a=lease(64'he123456789abc001,24'hffffff,1,0);
 b=lease(64'he123456789abc002,0,2,1);
 c=lease(64'he123456789abc003,24'hffffff,3,2);
 if(which==1)begin
  tx({8'd0,a});tx({8'd0,b});query(b,0,1,1); // oldest remains a, not latest TX b
  update(control(a,b,1,1));update(control(a,0,0,1));tx({8'd1,a});
  query(b,2,1,0);
  update(control(b,0,0,1));repeat(37)@(negedge clk);resume(b[247:80]);
  query(b,0,0,1);tx({8'd0,b});query(b,0,0,1);
  update(control(c,0,0,1));tx({8'd0,c});query(c,0,0,1);
 end else if(which==2)begin
  a[15:0]=16'hffff;tx({8'd0,a});deadline=cycle+1000;
  while(!fv)begin if(cycle>deadline)$fatal(1,"full index not rejected");@(negedge clk);end
  if(fd!==20 || bv)$fatal(1,"invalid full lease index aliased");
 end else begin
  ctrl=0;ctrl[167:0]=a[247:80];ctrl[498]=1;update(ctrl);
  word=0;word[167:0]=a[247:80]^168'h10000000000000000000000000000000000;word[249]=1;tx(word);
  deadline=cycle+1000;while(!fv)begin if(cycle>deadline)$fatal(1,"bad timer fence identity accepted");@(negedge clk);end
  if(fd!==11 || bv)$fatal(1,"wrong marker became success");
 end
 repeat(17)@(negedge clk);
 $display("OWNED_TIMER_PRODUCER_RTL {\"pass_test\":true,\"case\":%0d,\"queries\":%0d,\"cycles\":%0d,\"timer_entries\":8,\"actual_timer_array\":true,\"four_state\":true,\"whole_core_drain\":false}",which,queries,cycle);
 $finish;
end
endmodule
