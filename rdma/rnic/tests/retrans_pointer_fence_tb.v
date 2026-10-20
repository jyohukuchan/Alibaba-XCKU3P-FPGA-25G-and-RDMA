// SPDX-License-Identifier: BSD-2-Clause-Views
`timescale 1ns/1ps
module tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [223:0] data[0:1];reg [1:0] valid=0;wire [1:0] ready;
wire [39:0] ndata;wire nvalid;reg nready=0;
wire [287:0] fdata;wire fvalid;reg fready=0;
as02_pointer_fence_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_req_TDATA(data[0]),.s_req_TVALID(valid[0]),.s_req_TREADY(ready[0]),
 .s_upd_TDATA(data[1]),.s_upd_TVALID(valid[1]),.s_upd_TREADY(ready[1]),
 .m_normal_TDATA(ndata),.m_normal_TVALID(nvalid),.m_normal_TREADY(nready),
 .m_fence_TDATA(fdata),.m_fence_TVALID(fvalid),.m_fence_TREADY(fready));
integer cycle=0,queries=0,q;reg fs=0,ns=0;reg [287:0] held,last;reg [39:0] nheld;
reg [23:0] psn;reg [63:0] epoch,seq;
always @(posedge clk)begin
 if(rst)begin fs=0;ns=0;end else begin
  cycle=cycle+1;if(cycle>20000)$fatal(1,"finite pointer deadline");
  if(fs && (!fvalid || fdata!==held))$fatal(1,"fence changed under stall");
  if(ns && (!nvalid || ndata!==nheld))$fatal(1,"normal response changed under stall");
  fs=fvalid&&!fready;held=fdata;ns=nvalid&&!nready;nheld=ndata;
  if(fvalid&&fready)begin
   if((^fdata)===1'bx || fdata[287:263]!==0 || fdata[177:176]!==3)$fatal(1,"unknown/noncanonical pointer response");
   queries=queries+1;
  end
 end
end
function [223:0] request;
 input [15:0] qp;input lock;
 begin request=0;request[15:0]=qp;request[49]=lock;end
endfunction
function [223:0] update;
 input [15:0] qp,h,t;input v;
 begin update=request(qp,0);update[31:16]=h;update[47:32]=t;update[48]=v;end
endfunction
function [223:0] marker;
 input [15:0] qp;input [23:0] p;input [63:0] e,s;
 begin marker=request(qp,0);marker[50]=1;marker[74:51]=p;marker[138:75]=e;marker[202:139]=s;end
endfunction
task send;
 input integer source;input [223:0] word;integer deadline;
 begin
  @(negedge clk);data[source]=word;valid[source]=1;deadline=cycle+3000;
  @(posedge clk);while(!ready[source])begin if(cycle>deadline)$fatal(1,"producer deadline");@(posedge clk);end
  @(negedge clk);valid[source]=0;
 end
endtask
task simultaneous_update_and_request;
 reg [1:0] remaining;integer deadline;
 begin
  @(negedge clk);data[0]=request(0,1);data[1]=update(0,1999,1999,1);
  valid=2'b11;remaining=2'b11;deadline=cycle+3000;
  while(remaining!=0)begin
   @(posedge clk);if(cycle>deadline)$fatal(1,"simultaneous producer deadline");remaining=remaining&~ready;
   @(negedge clk);valid=remaining;
  end
 end
endtask
task receive;
 input [15:0] qp;input [23:0] p;input [63:0] e,s;input [7:0] status;integer deadline;
 begin
  deadline=cycle+3000;while(!fvalid)begin if(cycle>deadline)$fatal(1,"pointer response missing");@(negedge clk);end
  if(fdata[15:0]!==qp || fdata[39:16]!==p || fdata[103:40]!==e || fdata[167:104]!==s ||
   fdata[175:168]!==status || (^fdata)===1'bx)$fatal(1,"wrong pointer token/status %h expected%h",fdata,status);
  last=fdata;repeat(17)@(negedge clk);fready=1;@(posedge clk);@(negedge clk);fready=0;
 end
endtask
task query;
 input [15:0] qp;input [23:0] p;input [63:0] e,s;input [7:0] status;input rev;
 begin
  send(rev,marker(qp,p,e,s));repeat(17)begin @(negedge clk);if(fvalid)$fatal(1,"missing peer marker certified");end
  send(!rev,marker(qp,p,e,s));receive(qp,p,e,s,status);
 end
endtask
task entry;
 input [15:0] h,t;input v,locked;input [15:0] lockqp;
 begin
  if(!last[178] || last[194:179]!==h || last[210:195]!==t || last[211]!==v || last[212]!==locked ||
   last[213] || last[229:214]!==lockqp || last[245:230]!==0)$fatal(1,"wrong actual pointer/lock state");
 end
endtask
task normal_reply;
 input [15:0] h,t;input v;integer deadline;
 begin
  deadline=cycle+3000;while(!nvalid)begin if(cycle>deadline)$fatal(1,"normal response missing");@(negedge clk);end
  if(ndata!=={7'd0,v,t,h})$fatal(1,"wrong normal pointer response");
  repeat(17)@(negedge clk);nready=1;@(posedge clk);@(negedge clk);nready=0;
 end
endtask
initial begin
 data[0]=0;data[1]=0;@(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;
 query(7,24'hffffff,64'hffffffffffffffff,64'hffffffffffffffff,0,0);entry(0,0,0,0,0);
 for(q=0;q<8;q=q+1)begin
  psn=24'hfffffe+q;epoch=64'hf123456789abc001+q;seq=64'he123456789abc001+q;
  query(q,psn,epoch,seq,0,q&1);entry(0,0,0,0,0);
  if(q==0)simultaneous_update_and_request();
  else begin send(1,update(q,1999,1999-q,1));send(0,request(q,1));end
  normal_reply(1999,1999-q,1);
  query(q,psn,epoch,seq+64'h100,2,q&1);entry(1999,1999-q,1,1,q);
  send(1,update(q,1999,1999-q,0));query(q,psn,epoch,seq+64'h200,0,q&1);entry(1999,1999-q,0,0,0);
 end
 send(0,request(2,1));normal_reply(1999,1997,0);send(0,request(3,1));
 repeat(17)begin @(negedge clk);if(nvalid)$fatal(1,"waiting lock bypassed owner");end
 send(0,marker(3,24'hffffff,64'h9123456789abcdef,64'hf123456789abcdef));
 repeat(17)begin @(negedge clk);if(fvalid)$fatal(1,"marker overtook waiting lock");end
 send(1,update(2,1999,1997,0));send(1,marker(3,24'hffffff,64'h9123456789abcdef,64'hf123456789abcdef));
 receive(3,24'hffffff,64'h9123456789abcdef,64'hf123456789abcdef,2);entry(1999,1996,0,1,3);
 send(1,update(3,1999,1996,0));query(3,0,9,10,0,0);entry(1999,1996,0,0,0);
 repeat(37)begin @(negedge clk);if(!nvalid)$fatal(1,"pointer OK discarded held normal response");end
 normal_reply(1999,1996,0);send(0,request(2,0));query(2,0,9,11,0,1);normal_reply(1999,1997,0);
 query(16'hffff,0,9,12,1,0);if(last[178])$fatal(1,"range marker indexed table");
 query(2,0,0,13,3,1);query(2,0,9,0,3,0);
 send(1,update(2,2000,1999,1));query(2,1,9,14,4,0);entry(1999,1997,0,0,0);
 if(!last[246] || last[262:247]!==16'd2)$fatal(1,"metadata2000 range hidden");
 send(1,update(2,1999,2000,1));query(2,9,9,23,4,1);entry(1999,1997,0,0,0);
 if(!last[246] || last[262:247]!==16'd2)$fatal(1,"metadata tail2000 range hidden");
 send(0,request(16'hffff,0));query(2,2,9,15,4,1);
 if(last[246] || last[262:247]!==16'hffff)$fatal(1,"full request QPN truncated");
 send(1,update(16'h0102,1,1,1));query(2,8,9,22,4,0);entry(1999,1997,0,0,0);
 if(!last[246] || last[262:247]!==16'h0102)$fatal(1,"full update QPN aliased");
 send(0,marker(2,3,9,16));repeat(17)@(negedge clk);send(1,marker(2,3,9,64'h8000000000000010));receive(2,3,9,16,4);
 if(!last[246] || last[262:247]!==16'd2)$fatal(1,"high64-bit sequence mismatch hidden");
 send(0,marker(2,4,9,17)|(224'd1<<223));repeat(17)@(negedge clk);send(1,marker(2,4,9,17));receive(2,4,9,17,4);
 if(last[246] || last[262:247]!==16'd2)$fatal(1,"reserved marker hidden");
 // This is a simulated private-DUT reset, never a host/FPGA reset or a
 // certificate releasing an external owner. BRAM must really clear.
 send(1,update(7,1999,1999,1));query(7,5,9,18,4,0);entry(1999,1999,1,0,0);
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;
 query(7,6,64'hf123456789abcdef,64'he123456789abcdef,0,1);entry(0,0,0,0,0);
 $display("POINTER_FENCE_RTL {\"pass_test\":true,\"queries\":%0d,\"table_entries\":8,\"metadata_capacity\":2000,\"ordered_producers\":2,\"real_lock_wait_release\":true,\"normal_output_held_after_pointer_OK\":true,\"real_BRAM_cleared_after_simulated_reset\":true,\"whole_core_drain\":false,\"cycles\":%0d}",queries,cycle);
 $finish;
end
endmodule
