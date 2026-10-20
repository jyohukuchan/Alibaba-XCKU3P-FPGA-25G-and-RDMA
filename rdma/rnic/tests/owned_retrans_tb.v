// SPDX-License-Identifier: BSD-2-Clause-Views
// REAL generated FNS subsystem + REAL production allocator. Test-only input
// producers/diagnostic pool mux are not genuine whole-core producer fences.
`timescale 1ns/1ps
module tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [415:0] idata=0;reg iv=0;wire ir;
reg [223:0] udata=0;reg uv=0;wire ur;
reg [191:0] tdata=0,rdata=0;reg tv=0,rv=0;wire tr,rr;
wire [191:0] ca;wire cav,car;
wire [255:0] cg;wire cgv,cgr;
wire [255:0] cr;wire crv,crr;
wire [255:0] ck;wire ckv,ckr;
wire [575:0] edata;wire ev;reg er=0;
wire [319:0] ddata;wire dv;reg dr=0;
wire [31:0] fault,inserted,released,partial;wire [7:0] phase;
wire pf,pi;wire [11:0] free_slots,active_slots;
as02_owned_retrans_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_insert_TDATA(idata),.s_insert_TVALID(iv),.s_insert_TREADY(ir),
 .s_update_TDATA(udata),.s_update_TVALID(uv),.s_update_TREADY(ur),
 .s_retry_TDATA(rdata),.s_retry_TVALID(rv),.s_retry_TREADY(rr),
 .s_timer_TDATA(tdata),.s_timer_TVALID(tv),.s_timer_TREADY(tr),
 .m_pool_alloc_TDATA(ca),.m_pool_alloc_TVALID(cav),.m_pool_alloc_TREADY(car),
 .s_pool_alloc_TDATA(cg),.s_pool_alloc_TVALID(cgv),.s_pool_alloc_TREADY(cgr),
 .m_pool_release_TDATA(cr),.m_pool_release_TVALID(crv),.m_pool_release_TREADY(crr),
 .s_pool_release_TDATA(ck),.s_pool_release_TVALID(ckv),.s_pool_release_TREADY(ckr),
 .m_event_TDATA(edata),.m_event_TVALID(ev),.m_event_TREADY(er),
 .m_rdinit_TDATA(ddata),.m_rdinit_TVALID(dv),.m_rdinit_TREADY(dr),
 .pool_credit(free_slots),.pool_initialized(pi),.pool_fault_in(pf),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial));
reg direct=0;reg [191:0] da=0;reg dav=0;wire dar;
reg [255:0] dz=0;reg dzv=0;wire dzr;
wire [255:0] pa,pk;wire pav,pkv;reg par=0,pkr=0;
wire [223:0] fd;wire fv;reg fr=0;
rocev2_retrans_pool pool(.clk(clk),.rst(rst),
 .s_alloc_data(direct?da:ca),.s_alloc_valid(direct?dav:cav),.s_alloc_ready(dar),
 .s_release_data(direct?dz:cr),.s_release_valid(direct?dzv:crv),.s_release_ready(dzr),
 .m_alloc_data(pa),.m_alloc_valid(pav),.m_alloc_ready(direct?par:cgr),
 .m_release_data(pk),.m_release_valid(pkv),.m_release_ready(direct?pkr:ckr),
 .m_fence_data(fd),.m_fence_valid(fv),.m_fence_ready(fr),
 .pool_fault(pf),.initialized(pi),.free_slots(free_slots),.active_slots(active_slots));
assign car=!direct&&dar;assign crr=!direct&&dzr;
assign cg=pa;assign cgv=!direct&&pav;assign ck=pk;assign ckv=!direct&&pkv;
integer cycle=0,which=0,j,deadline,alloc_requests=0,grants=0,returns=0,events_taken=0;
reg [247:0] leases[0:7];
reg es=0,ds=0;reg [575:0] eh=0;reg [319:0] dh=0;
reg [167:0] own;reg [575:0] expected_event;
reg [63:0] epoch=64'hfedcba9876543210,seq=64'hf123456789abcdef;
localparam [63:0] LA=64'hfedcba9876543210,RA=64'h9123456789abcdef;
always @(posedge clk)begin
 if(rst)begin es=0;ds=0;end else begin
  cycle=cycle+1;if(cycle>200000)$fatal(1,"finite owned retransmission deadline");
  if(es && (!ev || edata!==eh))$fatal(1,"real event changed under stall");
  if(ds && (!dv || ddata!==dh))$fatal(1,"real RDinit changed under stall");
  es=ev&&!er;eh=edata;ds=dv&&!dr;dh=ddata;
  if(!direct && cav&&car)alloc_requests=alloc_requests+1;
  if(!direct && pav&&cgr)begin
   if(pa[255:248]!==0 || (^pa)===1'bx || grants>=8)$fatal(1,"bad actual pool grant");
   leases[grants]=pa[247:0];grants=grants+1;
  end
  if(!direct && pkv&&ckr)begin
   if(pk[255:248]!==0 || (^pk)===1'bx)$fatal(1,"bad actual pool return");returns=returns+1;
  end
  if(ev&&er)events_taken=events_taken+1;
  if(direct && (cav || crv))$fatal(1,"test pool mux stole a real producer request");
 end
end
function [167:0] owner;
 input [15:0] qp;input [23:0] psn;input [63:0] ep,sq;
 begin owner={sq,ep,psn,qp};end
endfunction
function [415:0] ins;
 input [15:0] qp;input [23:0] psn;input [31:0] op,len;input [63:0] ep,sq;
 begin
  ins=0;ins[15:0]=qp;ins[39:16]=psn;ins[71:40]=op;
  ins[103:72]=0;ins[104]=1;ins[105]=1;ins[169:106]=LA;ins[233:170]=RA;
  ins[265:234]=len;ins[266]=1;ins[270:267]=15;ins[334:271]=ep;ins[398:335]=sq;
 end
endfunction
function [223:0] upd;
 input [23:0] psn;input [31:0] op;input [63:0] sq;
 begin upd=0;upd[15:0]=2;upd[39:16]=psn;upd[71:40]=op;upd[135:72]=epoch;upd[199:136]=sq;end
endfunction
function [575:0] event_word;
 input [23:0] psn;input [31:0] op,len;input [63:0] la,ra;input [247:0] lease;
 begin
  event_word=0;event_word[23:0]=2;event_word[47:24]=psn;event_word[79:48]=op;
  event_word[112]=1;event_word[113]=1;event_word[177:114]=la;event_word[241:178]=ra;
  event_word[273:242]=len;event_word[274]=1;event_word[278:275]=15;event_word[279]=1;
  event_word[528:281]=lease;
 end
endfunction
task send_insert;
 input [415:0] word;integer endat;
 begin
  @(negedge clk);idata=word;iv=1;endat=cycle+10000;
  @(posedge clk);while(!ir)begin if(cycle>endat)$fatal(1,"insert input deadline");@(posedge clk);end
  @(negedge clk);iv=0;
 end
endtask
task send_update;
 input [223:0] word;integer endat;
 begin
  @(negedge clk);udata=word;uv=1;endat=cycle+10000;
  @(posedge clk);while(!ur)begin if(cycle>endat)$fatal(1,"update input deadline");@(posedge clk);end
  @(negedge clk);uv=0;
 end
endtask
task send_retry;
 input timer;input [167:0] word;integer endat;
 begin
  @(negedge clk);if(timer)begin tdata={24'd0,word};tv=1;end else begin rdata={24'd0,word};rv=1;end
  endat=cycle+10000;@(posedge clk);
  while(timer?!tr:!rr)begin if(cycle>endat)$fatal(1,"retry input deadline");@(posedge clk);end
  @(negedge clk);tv=0;rv=0;
 end
endtask
task wait_insert;
 input integer n;integer endat;
 begin endat=cycle+10000;while(inserted!==n)begin if(cycle>endat||fault!=0||pf)$fatal(1,"insert progress failure phase%0d fault%0d n%0d",phase,fault,inserted);@(negedge clk);end end
endtask
task wait_release;
 input integer n;integer endat;
 begin endat=cycle+10000;while(released!==n)begin if(cycle>endat||fault!=0||pf)$fatal(1,"release progress failure phase%0d fault%0d",phase,fault);@(negedge clk);end end
endtask
task check_event;
 input [575:0] expected;integer endat;
 begin
  endat=cycle+10000;while(!ev)begin if(cycle>endat||fault!=0||pf)$fatal(1,"real retransmission event missing");@(negedge clk);end
  if(edata!==expected)$fatal(1,"wrong REAL metadata event %h expected %h",edata,expected);
  repeat(23)@(negedge clk);
 end
endtask
task wait_fault;
 input [31:0] code;integer endat;
 begin
  endat=cycle+10000;while(fault===0)begin if(cycle>endat)$fatal(1,"missing fail-closed owner rejection");@(negedge clk);end
  if(fault!==code || pf)$fatal(1,"wrong rejection fault%0d pool%0d",fault,pf);
  repeat(64)@(negedge clk);
 end
endtask
task pool_alloc;
 input [167:0] word;input integer index;integer endat;
 begin
  @(negedge clk);da={24'd0,word};dav=1;endat=cycle+10000;
  @(posedge clk);while(!dar)begin if(cycle>endat)$fatal(1,"prefill request timeout");@(posedge clk);end
  @(negedge clk);dav=0;
  while(!pav)begin if(cycle>endat)$fatal(1,"prefill grant timeout");@(negedge clk);end
  if(pa!=={8'd0,word,64'(index+1),16'(index)})$fatal(1,"real fullpool prefill mismatch");
  par=1;@(posedge clk);@(negedge clk);par=0;
 end
endtask
task pool_snapshot;
 input [167:0] word;input [11:0] expected_global;integer endat;
 begin
  @(negedge clk);direct=1;da={23'd0,1'b1,word};dav=1;endat=cycle+10000;
  @(posedge clk);while(!dar)begin if(cycle>endat)$fatal(1,"diagnostic alloc marker timeout");@(posedge clk);end
  @(negedge clk);dav=0;dz={7'd0,1'b1,word,80'd0};dzv=1;
  @(posedge clk);while(!dzr)begin if(cycle>endat)$fatal(1,"diagnostic return marker timeout");@(posedge clk);end
  @(negedge clk);dzv=0;
  while(!fv)begin if(cycle>endat)$fatal(1,"real pool snapshot timeout");@(negedge clk);end
  if((^fd)===1'bx || fd[167:0]!==word || fd[179:168]!==0 || fd[191:180]!==expected_global ||
   fd[203:192]!==(12'd2000-expected_global) || fd[211:204]!==0 || !fd[212] || fd[223:213]!==0)
   $fatal(1,"wrong actual pool snapshot %h",fd);
  repeat(17)@(negedge clk);fr=1;@(posedge clk);@(negedge clk);fr=0;direct=0;
 end
endtask
initial begin
 if(!$value$plusargs("CASE=%d",which))which=1;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;
 deadline=cycle+10000;while(!pi)begin if(cycle>deadline)$fatal(1,"real pool not initialized");@(negedge clk);end
 if(free_slots!==2000 || active_slots!==0)$fatal(1,"wrong real capacity");
 if(which==3)begin
  // Test-only API prefill, not2000connections or an allocator model.
  direct=1;
  for(j=0;j<1999;j=j+1)pool_alloc(owner(7,0,2,100+j),j);
  direct=0;
 end
 if(which==5)begin
  send_insert(ins(16'hffff,0,10,65,epoch,seq));wait_fault(5);
  if(alloc_requests!=0 || grants!=0 || active_slots!==0)$fatal(1,"fullQPN aliased before allocation");
 end else if(which==6)begin
  // Two REAL linked records, same WR/context but distinct immutable lease
  // PSNs/indices/generations. Exercises append plus actual retry traversal.
  send_insert(ins(2,24'hffffff,10,65,epoch,seq));wait_insert(1);
  send_insert(ins(2,0,10,65,epoch,seq));wait_insert(2);
  if(leases[0]!=={owner(2,24'hffffff,epoch,seq),64'd1,16'd0} ||
     leases[1]!=={owner(2,0,epoch,seq),64'd2,16'd1})$fatal(1,"linked immutable leases wrong");
  send_retry(1,owner(2,24'hffffff,epoch,seq));
  check_event(event_word(24'hffffff,10,65,LA,RA,leases[0]));
  send_update(upd(24'hffffff,17,seq));wait_release(1);
  if(active_slots!==1)$fatal(1,"linked ACK freed wrong record count");
  @(negedge clk);er=1;@(posedge clk);@(negedge clk);er=0;
  expected_event=event_word(0,10,65,LA,RA,leases[1]);check_event(expected_event);
  send_update(upd(0,17,seq));wait_release(2);
  pool_snapshot(owner(2,24'hffffff,epoch,seq),0);
  if(!ev || edata!==expected_event || returns!=2)$fatal(1,"linked real output not retained after pool zero");
  @(negedge clk);er=1;@(posedge clk);@(negedge clk);er=0;
 end else if(which==2)begin
  send_insert(ins(2,24'hffffff,12,4161,epoch,seq));wait_insert(1);
  if(leases[0]!=={owner(2,24'hffffff,epoch,seq),64'd1,16'd0})$fatal(1,"READ original lease wrong");
  send_update(upd(24'hffffff,13,seq));deadline=cycle+10000;
  while(partial!==1)begin if(cycle>deadline||fault!=0)$fatal(1,"READ partial update failed");@(negedge clk);end
  while(!dv)begin if(cycle>deadline)$fatal(1,"real RDinit missing");@(negedge clk);end
  if(ddata!=={7'd0,leases[0],1'b1,LA})$fatal(1,"READ forwarding/lease mismatch");
  send_retry(1,owner(2,0,epoch,seq));
  expected_event=event_word(0,12,65,LA+64'd4096,RA+64'd4096,leases[0]);check_event(expected_event);
  if(edata[400:377]!==24'hffffff)$fatal(1,"immutable lease PSN changed with protocol PSN");
  send_update(upd(0,15,seq));wait_release(1);
  if(active_slots!==0 || returns!=1)$fatal(1,"mutable PSN incorrectly used for pool return");
  pool_snapshot(owner(2,24'hffffff,epoch,seq),0);
  if(!ev || !dv || edata!==expected_event)$fatal(1,"pool zero erased real held outputs");
  @(negedge clk);er=1;dr=1;@(posedge clk);@(negedge clk);er=0;dr=0;
 end else if(which==3)begin
  send_insert(ins(2,24'hffffff,10,65,epoch,seq));wait_insert(1);
  if(leases[0]!=={owner(2,24'hffffff,epoch,seq),64'd2000,16'd1999} || free_slots!==0)$fatal(1,"real full capacity missing");
  send_insert(ins(2,0,10,65,epoch,seq+64'd1));
  repeat(97)@(negedge clk);
  if(inserted!==1 || alloc_requests!=1 || grants!=1)$fatal(1,"unfillable insert hid releases");
  send_update(upd(24'hffffff,17,seq));wait_release(1);wait_insert(2);
  if(leases[1]!=={owner(2,0,epoch,seq+64'd1),64'd2001,16'd1999})$fatal(1,"real release/reuse generation mismatch");
  send_update(upd(0,17,seq+64'd1));wait_release(2);
  pool_snapshot(owner(2,0,epoch,seq+64'd1),1999);
  if(alloc_requests!=2 || grants!=2 || returns!=2 || active_slots!==1999)$fatal(1,"fullpool ACK progress incomplete");
 end else begin
  send_insert(ins(2,24'hffffff,10,65,epoch,seq));wait_insert(1);
  if(leases[0]!=={owner(2,24'hffffff,epoch,seq),64'd1,16'd0})$fatal(1,"WRITE original lease wrong");
  if(which==1)begin
   send_retry(1,owner(2,24'hffffff,epoch,seq));
   expected_event=event_word(24'hffffff,10,65,LA,RA,leases[0]);check_event(expected_event);
  end
  send_update(upd(24'hffffff,17,seq));wait_release(1);
  pool_snapshot(owner(2,24'hffffff,epoch,seq),0);
  if(which==1 && (!ev || edata!==expected_event))$fatal(1,"pool zero incorrectly drained actual event");
  send_insert(ins(2,24'hffffff,10,65,epoch,seq+64'd1));wait_insert(2);
  if(leases[1][79:16]!==2)$fatal(1,"global generation reused");
  if(which==1)begin
   send_retry(0,owner(2,24'hffffff,epoch,seq));wait_fault(9);
   @(negedge clk);er=1;@(posedge clk);@(negedge clk);er=0;
   repeat(64)@(negedge clk);if(ev || events_taken!=1)$fatal(1,"old retry replayed new WR");
  end else begin send_update(upd(24'hffffff,17,seq));wait_fault(7);end
  if(released!==1 || returns!=1 || active_slots!==1)$fatal(1,"old context freed a new WR");
 end
 if(pf || (which==2 && fault!=0) || (which==3 && fault!=0) || (which==6 && fault!=0))$fatal(1,"unexpected subsystem fault");
 $display("OWNED_RETRANS_RTL {\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"real_alloc_requests\":%0d,\"real_grants\":%0d,\"real_returns\":%0d,\"inserted\":%0d,\"released\":%0d,\"partial\":%0d,\"fault\":%0d,\"metadata_entries\":2000,\"pointer_entries\":8,\"whole_core_drain\":false}",which,cycle,alloc_requests,grants,returns,inserted,released,partial,fault);
 $finish;
end
endmodule
