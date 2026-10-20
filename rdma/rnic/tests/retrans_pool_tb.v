// SPDX-License-Identifier: BSD-2-Clause-Views
`timescale 1ns/1ps
module tb;
parameter [63:0] GENSTART=64'd1;
reg clk=0,rst=0;always #2 clk=~clk;
reg [191:0] adata=0;reg av=0;wire ar;
reg [255:0] rdata=0;reg rv=0;wire rr;
wire [255:0] ag,rg;wire agv,rgv;reg agr=0,rgr=0;
wire [223:0] fg;wire fgv;reg fgr=0;wire fault,init_done;wire [11:0] free_n,active_n;
rocev2_retrans_pool #(.GENERATION_START(GENSTART)) dut(.clk(clk),.rst(rst),
 .s_alloc_data(adata),.s_alloc_valid(av),.s_alloc_ready(ar),
 .s_release_data(rdata),.s_release_valid(rv),.s_release_ready(rr),
 .m_alloc_data(ag),.m_alloc_valid(agv),.m_alloc_ready(agr),
 .m_release_data(rg),.m_release_valid(rgv),.m_release_ready(rgr),
 .m_fence_data(fg),.m_fence_valid(fgv),.m_fence_ready(fgr),
 .pool_fault(fault),.initialized(init_done),.free_slots(free_n),.active_slots(active_n));
integer mode=0,cycle=0,allocations=0,releases=0,fences=0,resets=0,i;
reg ah=0,rh=0,fh=0;reg [255:0] held_a,held_r,last_a,last_r;reg [223:0] held_f,last_f;
reg [247:0] tokens[0:1999];reg [1999:0] unique_slots=0;
reg [247:0] first,second,replacement,bad;reg [191:0] aframe;reg [255:0] rframe;
reg [167:0] o2,o3,o4,other;
always @(posedge clk)begin
 if(rst)begin ah=0;rh=0;fh=0;end else begin
  cycle=cycle+1;if(cycle>500000)$fatal(1,"finite allocator deadline");
  if(ah && (!agv || ag!==held_a))$fatal(1,"allocation offer changed while stalled");
  if(rh && (!rgv || rg!==held_r))$fatal(1,"release acknowledgement changed while stalled");
  if(fh && (!fgv || fg!==held_f))$fatal(1,"pool snapshot changed while stalled");
  ah=agv&&!agr;held_a=ag;rh=rgv&&!rgr;held_r=rg;fh=fgv&&!fgr;held_f=fg;
  if(agv)begin if((^ag)===1'bx)$fatal(1,"unknown allocation result");end
  if(rgv)begin if((^rg)===1'bx)$fatal(1,"unknown release result");end
  if(fgv)begin if((^fg)===1'bx || fg[223:213]!==0)$fatal(1,"unknown/noncanonical fence result");end
  if(agv&&agr&&ag[255:248]==0)allocations=allocations+1;
  if(rgv&&rgr&&rg[255:248]==0)releases=releases+1;
  if(fgv&&fgr)fences=fences+1;
 end
end
always @(negedge clk)if(!rst && init_done)
 if({1'b0,free_n}+{1'b0,active_n}!==13'd2000)$fatal(1,"pool capacity invariant lost");
function [167:0] owner;
 input [15:0] qp;input [23:0] psn;input [63:0] e,s;
 begin owner={s,e,psn,qp};end
endfunction
task wait_init;
 integer limit;
 begin limit=cycle+10000;while(!init_done)begin if(cycle>limit)$fatal(1,"allocator rebuild missing");@(negedge clk);end end
endtask
task reset_local;
 begin
  @(negedge clk);av=0;rv=0;agr=0;rgr=0;fgr=0;rst=1;resets=resets+1;
  repeat(8)@(negedge clk);rst=0;@(negedge clk);wait_init();
 end
endtask
task send_alloc;
 input [191:0] word;integer limit;
 begin
  @(negedge clk);adata=word;av=1;limit=cycle+20000;
  @(posedge clk);while(!ar)begin if(cycle>limit)$fatal(1,"allocation input deadline");@(posedge clk);end
  @(negedge clk);av=0;
 end
endtask
task send_release;
 input [255:0] word;integer limit;
 begin
  @(negedge clk);rdata=word;rv=1;limit=cycle+20000;
  @(posedge clk);while(!rr)begin if(cycle>limit)$fatal(1,"release input deadline");@(posedge clk);end
  @(negedge clk);rv=0;
 end
endtask
task take_alloc;
 input [167:0] own;input [7:0] status;input integer hold_n;integer limit;
 begin
  limit=cycle+20000;while(!agv)begin if(cycle>limit)$fatal(1,"allocation result missing");@(negedge clk);end
  if(ag[255:248]!==status || ag[247:80]!==own)$fatal(1,"wrong allocation tuple/status %h expected%h",ag,status);
  if(status==0 && (ag[15:0]>=2000 || ag[79:16]==0))$fatal(1,"invalid successful lease");
  last_a=ag;repeat(hold_n)@(negedge clk);agr=1;@(posedge clk);@(negedge clk);agr=0;
 end
endtask
task allocate;
 input [167:0] own;input [7:0] status;input integer hold_n;
 begin send_alloc({24'd0,own});take_alloc(own,status,hold_n);end
endtask
task take_release;
 input [247:0] lease;input [7:0] status;input integer hold_n;integer limit;
 begin
  limit=cycle+20000;while(!rgv)begin if(cycle>limit)$fatal(1,"release result missing");@(negedge clk);end
  if(rg!=={status,lease})$fatal(1,"wrong release tuple/status %h expected%h",rg,status);
  last_r=rg;repeat(hold_n)@(negedge clk);rgr=1;@(posedge clk);@(negedge clk);rgr=0;
 end
endtask
task release_token;
 input [247:0] lease;input [7:0] status;input integer hold_n;
 begin send_release({8'd0,lease});take_release(lease,status,hold_n);end
endtask
task take_fence;
 input [167:0] own;input [7:0] status;input [11:0] own_n,global_n,free_expected;input integer hold_n;integer limit;
 begin
  limit=cycle+20000;while(!fgv)begin if(cycle>limit)$fatal(1,"pool rendezvous missing");@(negedge clk);end
  if(fg[167:0]!==own || fg[179:168]!==own_n || fg[191:180]!==global_n || fg[203:192]!==free_expected ||
   fg[211:204]!==status || fg[212]!==((status==0)||(status==2)))$fatal(1,"wrong real pool snapshot %h status%h owner%0d global%0d free%0d",fg,status,own_n,global_n,free_expected);
  last_f=fg;repeat(hold_n)@(negedge clk);fgr=1;@(posedge clk);@(negedge clk);fgr=0;
 end
endtask
task query;
 input [167:0] own;input [7:0] status;input [11:0] own_n,global_n,free_expected;
 begin
  send_alloc({23'd0,1'b1,own});repeat(17)begin @(negedge clk);if(fgv)$fatal(1,"single marker falsely certified");end
  send_release({7'd0,1'b1,own,80'd0});take_fence(own,status,own_n,global_n,free_expected,17);
 end
endtask
initial begin
 if(!$value$plusargs("CASE=%d",mode))mode=0;
 o2=owner(2,24'hfffffe,64'hfedcba9876543210,64'he123456789abcdef);
 o3=owner(3,24'hffffff,64'h9123456789abcdef,64'hf123456789abcdef);
 o4=owner(4,0,64'hffffffffffffffff,64'hffffffffffffffff);
 reset_local();
 case(mode)
 0:begin
  for(i=0;i<2000;i=i+1)begin
   allocate(owner(2,24'hfffffe+i,o2[103:40],o2[167:104]),0,i==0?17:0);
   if(last_a[15:0]!==i || last_a[79:16]!==i+64'd1 || unique_slots[last_a[15:0]])$fatal(1,"full capacity index/generation duplicate");
   unique_slots[last_a[15:0]]=1;tokens[i]=last_a[247:0];
  end
  if(unique_slots!=={2000{1'b1}})$fatal(1,"not all2000indices actually granted");
  query(o2,2,2000,2000,0);
  fork
   begin allocate(o3,0,17);replacement=last_a[247:0];end
   begin repeat(37)@(negedge clk);if(ar)$fatal(1,"exhaustion did not backpressure");release_token(tokens[17],0,17);end
  join
  if(replacement[15:0]!==16'd17 || replacement[79:16]!==64'd2001)$fatal(1,"wrong exhausted-pool reuse");
  tokens[17]=replacement;query(o2,2,1999,2000,0);query(o3,2,1,2000,0);
  for(i=0;i<2000;i=i+1)release_token(tokens[i],0,i==0?17:0);
  query(o2,0,0,0,2000);query(o3,0,0,0,2000);
  reset_local();allocate(o4,0,17);
  if(last_a[15:0]!==0 || last_a[79:16]!==64'd2002)$fatal(1,"reset reused generation or lost FIFO rebuild");
  release_token(last_a[247:0],0,0);query(o4,0,0,0,2000);
 end
 1:begin
  allocate(o2,0,0);first=last_a[247:0];
  allocate(owner(2,0,o2[103:40],o2[167:104]),0,0);second=last_a[247:0];
  reset_local();query(o2,2,2,2,1998);query(o4,0,0,2,1998);
  allocate(o3,0,0);if(last_a[15:0]!==16'd2 || last_a[79:16]!==64'd3)$fatal(1,"owned slots redistributed after reset");replacement=last_a[247:0];
  release_token(first,0,0);release_token(second,0,0);release_token(replacement,0,0);query(o2,0,0,0,2000);
 end
 2:begin
  send_alloc({24'd0,o2});while(!agv)@(negedge clk);first=ag[247:0];
  repeat(37)begin @(negedge clk);if(ar || rr || free_n!=1999 || active_n!=1)$fatal(1,"unconsumed offer not reserved");end
  reset_local();query(o2,2,1,1,1999);release_token(first,8,17);
  if(free_n!=1999 || active_n!=1)$fatal(1,"unconsumed pre-reset offer released");
  reset_local();query(o2,4,1,1,1999);
 end
 3:begin
  allocate(o2,0,0);first=last_a[247:0];release_token(first,0,0);release_token(first,5,17);
  query(o2,4,0,0,2000);reset_local();query(o2,4,0,0,2000);allocate(o3,4,17);
 end
 4:begin
  allocate(o2,0,0);first=last_a[247:0];bad=first^(248'd1<<247);release_token(bad,7,17);
  // Protocol metadata PSN may advance during READ. Lease PSN is immutable;
  // the real process binding must retain it, not substitute current PSN.
  bad=first^(248'd1<<96);release_token(bad,7,17);
  query(o2,4,1,1,1999);release_token(first,0,0);query(o2,4,0,0,2000);
 end
 5:begin
  for(i=0;i<2000;i=i+1)begin allocate(o2,0,0);tokens[i]=last_a[247:0];end
  first=tokens[0];release_token(first,0,0);allocate(o3,0,0);
  if(last_a[15:0]!==0 || last_a[79:16]!==64'd2001)$fatal(1,"stale-generation setup wrong");
  release_token(first,6,17);query(o3,4,1,2000,0);reset_local();query(o3,4,1,2000,0);allocate(o4,4,17);
 end
 6:begin
  allocate(o2,0,0);first=last_a[247:0];bad=first;bad[15:0]=16'hffff;release_token(bad,1,17);
  query(o2,4,1,1,1999);release_token(first,0,0);
  rframe={8'h80,first};send_release(rframe);take_release(first,3,17);query(o2,4,0,0,2000);
 end
 7:begin
  other=owner(16'h0102,0,o2[103:40],o2[167:104]);allocate(other,1,17);
  if(last_a[79:0]!==0 || free_n!=2000 || active_n!=0)$fatal(1,"high QPN allocated/aliased");query(o2,4,0,0,2000);
 end
 8:begin
  allocate(o2,0,0);first=last_a[247:0];send_alloc({23'd0,1'b1,o2});
  @(negedge clk);adata={24'd0,o3};av=1;
  repeat(37)begin @(negedge clk);if(ar || fgv)$fatal(1,"later allocation/single marker overtook fence");end
  release_token(first,0,17);send_release({7'd0,1'b1,o2,80'd0});
  while(!fgv)begin @(negedge clk);if(ar)$fatal(1,"allocation accepted during real owner scan");end
  if(fg[211:204]!==0 || fg[179:168]!==0 || fg[203:192]!==12'd2000)$fatal(1,"ordered prior release not reflected");
  repeat(37)begin @(negedge clk);if(ar || rr)$fatal(1,"closed producers reopened under stalled snapshot");end
  av=0;take_fence(o2,0,0,0,2000,17);allocate(o3,0,0);if(last_a[79:16]!==64'd2)$fatal(1,"later work leaked through marker");
  release_token(last_a[247:0],0,0);query(o3,0,0,0,2000);
 end
 9:begin
  send_alloc({23'd0,1'b1,o2});other=o2^(168'd1<<167);send_release({7'd0,1'b1,other,80'd0});
  take_fence(o2,4,0,0,2000,17);query(o2,4,0,0,2000);
 end
 10:begin
  aframe={24'd0,o2};aframe[140]=1'bx;send_alloc(aframe);take_alloc(0,3,17);
  rframe=0;rframe[200]=1'bz;send_release(rframe);take_release(0,3,17);query(o2,4,0,0,2000);
 end
 11:begin
  allocate(o2,0,0);first=last_a[247:0];if(first[79:16]!==64'hfffffffffffffffe)$fatal(1,"generation seed test wrong");
  release_token(first,0,0);reset_local();query(o2,0,0,0,2000);allocate(o3,8,17);
  if(last_a[79:0]!==0 || free_n!=2000 || active_n!=0)$fatal(1,"generation wrapped/allocated");
  reset_local();query(o3,4,0,0,2000);allocate(o4,4,17);
 end
 default:$fatal(1,"unknown pool case");
 endcase
 $display("POOL_RTL {\"pass_test\":true,\"case\":%0d,\"capacity\":2000,\"allocations\":%0d,\"releases\":%0d,\"fences\":%0d,\"simulated_local_resets\":%0d,\"cycles\":%0d,\"actual_FNS_process_integrated\":false,\"whole_core_drain\":false}",mode,allocations,releases,fences,resets,cycle);
 $finish;
end
endmodule
