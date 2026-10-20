// SPDX-License-Identifier: BSD-2-Clause-Views
`timescale 1ns/1ps
module tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [479:0] idata=0;reg ivalid=0;wire iready;
wire [287:0] ndata;wire nvalid;reg nready=0;
wire [511:0] fdata;wire fvalid;reg fready=0;
as02_meta_fence_top dut(.ap_clk(clk),.ap_rst_n(!rst),
 .s_meta_TDATA(idata),.s_meta_TVALID(ivalid),.s_meta_TREADY(iready),
 .m_normal_TDATA(ndata),.m_normal_TVALID(nvalid),.m_normal_TREADY(nready),
 .m_fence_TDATA(fdata),.m_fence_TVALID(fvalid),.m_fence_TREADY(fready));
integer cycle=0,queries=0,reads=0,idx,j,reset_start;
reg fs=0,ns=0;reg [511:0] held,last;reg [287:0] nheld;
reg [272:0] d,a,b,bad,expected,link;reg [63:0] epoch,seq;
always @(posedge clk)begin
 if(rst)begin fs=0;ns=0;end else begin
  cycle=cycle+1;if(cycle>300000)$fatal(1,"finite metadata deadline");
  if(fs && (!fvalid || fdata!==held))$fatal(1,"metadata fence changed under stall");
  if(ns && (!nvalid || ndata!==nheld))$fatal(1,"normal metadata changed under stall");
  fs=fvalid&&!fready;held=fdata;ns=nvalid&&!nready;nheld=ndata;
  if(fvalid&&fready)begin
   if((^fdata)===1'bx || fdata[511:482]!==0)$fatal(1,"unknown/noncanonical metadata response");
   queries=queries+1;
  end
  if(nvalid&&nready)begin if((^ndata)===1'bx || ndata[287:273]!==0)$fatal(1,"unknown normal metadata");reads=reads+1;end
 end
end
function [272:0] pattern;
 input integer index;reg [272:0] v;
 begin
  v=0;v[31:0]=index==0?0:(32'hfedcba98^index);v[32]=1;v[33]=1;
  v[57:34]=24'hfffffe+index;v[73:58]=(index+1)%2000;v[105:74]=32'd10;
  v[169:106]=64'hfedcba9876543210+index;v[233:170]=64'h9123456789abcdef+index;
  v[265:234]=32'hf1234567+index;v[266]=index&1;v[270:267]=index&15;v[271]=1;v[272]=1;pattern=v;
 end
endfunction
function [479:0] request;
 input [15:0] index;input wr,append;input [272:0] v;
 begin request=0;request[15:0]=index;request[16]=wr;request[17]=append;request[459:187]=v;end
endfunction
function [479:0] marker;
 input [15:0] index,qp;input [23:0] p;input [63:0] e,s;
 begin marker=request(index,0,0,0);marker[18]=1;marker[34:19]=qp;marker[58:35]=p;marker[122:59]=e;marker[186:123]=s;end
endfunction
task send;
 input [479:0] word;integer deadline;
 begin
  @(negedge clk);idata=word;ivalid=1;deadline=cycle+5000;
  @(posedge clk);while(!iready)begin if(cycle>deadline)$fatal(1,"metadata input deadline");@(posedge clk);end
  @(negedge clk);ivalid=0;
 end
endtask
task receive;
 input [15:0] index,qp;input [23:0] p;input [63:0] e,s;input [7:0] status;integer deadline;
 begin
  deadline=cycle+5000;while(!fvalid)begin if(cycle>deadline)$fatal(1,"metadata response missing");@(negedge clk);end
  if(fdata[15:0]!==index || fdata[31:16]!==qp || fdata[55:32]!==p || fdata[119:56]!==e ||
   fdata[183:120]!==s || fdata[191:184]!==status || (^fdata)===1'bx)$fatal(1,"wrong metadata token/status %h expected%h",fdata,status);
  last=fdata;repeat(17)@(negedge clk);fready=1;@(posedge clk);@(negedge clk);fready=0;
 end
endtask
task query;
 input [15:0] index,qp;input [23:0] p;input [63:0] e,s;input [7:0] status;
 begin send(marker(index,qp,p,e,s));receive(index,qp,p,e,s,status);end
endtask
task check_data;
 input [272:0] v;
 begin if(!last[192] || last[465:193]!==v)$fatal(1,"wrong actual metadata RAM contents %h",last);end
endtask
task normal_take;
 input [272:0] v;input integer hold_cycles;integer deadline;
 begin
  deadline=cycle+5000;while(!nvalid)begin if(cycle>deadline)$fatal(1,"normal metadata missing");@(negedge clk);end
  if(ndata!=={15'd0,v})$fatal(1,"wrong normal metadata %h expected %h",ndata,v);
  repeat(hold_cycles)@(negedge clk);nready=1;@(posedge clk);@(negedge clk);nready=0;
 end
endtask
initial begin
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;reset_start=cycle;
 query(1999,7,24'hffffff,64'hffffffffffffffff,64'hffffffffffffffff,0);check_data(0);
 if(cycle-reset_start<2000)$fatal(1,"real full2000entry clear bypassed");
 for(idx=0;idx<2000;idx=idx+1)begin send(request(idx,0,0,0));normal_take(0,0);end
 for(j=0;j<5;j=j+1)begin
  case(j)0:idx=0;1:idx=1;2:idx=1023;3:idx=1998;4:idx=1999;endcase
  d=pattern(idx);epoch=64'hf123456789abc001+idx;seq=64'he123456789abc001+idx;
  send(request(idx,1,0,d));query(idx,idx%8,24'hffffff,epoch,seq,0);check_data(d);
  link=0;link[73:58]=(idx+17)%2000;send(request(idx,0,1,link));send(request(idx,0,0,0));
  query(idx,idx%8,0,epoch,seq+64'd1,0);d[73:58]=(idx+17)%2000;d[272]=0;check_data(d);
  if(!last[193+271] || !nvalid)$fatal(1,"valid record/held actual normal output lost at commit OK");
  repeat(37)begin @(negedge clk);if(!nvalid)$fatal(1,"commit OK discarded outstanding normal response");end
  normal_take(d,17);
 end
 a=pattern(2);b=pattern(3);send(request(2,1,0,a));send(marker(2,2,24'h123456,9,10));send(request(2,1,0,b));
 receive(2,2,24'h123456,9,10,0);check_data(a);query(2,2,24'h123457,9,11,0);check_data(b);
 query(2000,2,0,9,12,1);if(last[192])$fatal(1,"index2000 accessed RAM");
 query(16'hffff,2,0,9,13,1);if(last[192])$fatal(1,"full index aliased");
 query(2,16'hffff,0,9,14,2);if(last[192])$fatal(1,"invalid owner QPN got snapshot");
 query(2,2,0,0,15,3);query(2,2,0,9,0,3);
 send(request(16'hffff,1,0,pattern(0)));query(2,2,1,9,16,4);check_data(b);
 if(last[481:466]!==16'hffff)$fatal(1,"ordinary full index fault lost");
 bad=0;bad[73:58]=2000;send(request(0,0,1,bad));query(0,0,2,9,17,4);
 expected=pattern(0);expected[73:58]=17;expected[272]=0;check_data(expected);
 if(last[481:466]!==0)$fatal(1,"append out of range ignored");
 bad=pattern(0);bad[272]=0;bad[73:58]=2000;send(request(0,1,0,bad));query(0,0,3,9,18,4);check_data(expected);
 bad=pattern(0);bad[105:74]=32'hffffffff;send(request(0,1,0,bad));query(0,0,4,9,19,4);check_data(expected);
 send(marker(0,0,5,9,20)|(480'd1<<479));receive(0,0,5,9,20,4);check_data(expected);
 send(request(2000,1,0,pattern(0)));query(0,0,6,9,21,4);check_data(expected);
 send(request(0,1,1,pattern(0)));query(0,0,7,9,22,4);check_data(expected);
 // Every actual entry is written/read nonzero before a simulated private
 // DUT reset, then ALL2000are checked zero again. No hardware reset/unpin.
 for(idx=0;idx<2000;idx=idx+1)send(request(idx,1,0,pattern(idx)));
 query(1999,7,8,9,23,4);check_data(pattern(1999));
 for(idx=0;idx<2000;idx=idx+1)begin send(request(idx,0,0,0));normal_take(pattern(idx),0);end
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;reset_start=cycle;
 query(1999,7,9,64'hf123456789abcdef,64'he123456789abcdef,0);check_data(0);
 if(cycle-reset_start<2000)$fatal(1,"reset shortened clear sweep");
 for(idx=0;idx<2000;idx=idx+1)begin send(request(idx,0,0,0));normal_take(0,0);end
 if(reads!=6005)$fatal(1,"missing/extra full table response %0d",reads);
 $display("META_FENCE_RTL {\"pass_test\":true,\"queries\":%0d,\"normal_reads\":%0d,\"metadata_entries\":2000,\"all_entries_zero_checked\":true,\"all_entries_written_and_read_nonzero_before_reset\":true,\"all_entries_zero_after_simulated_reset\":true,\"actual_same_index_RAW\":true,\"normal_output_held_after_commit_OK\":true,\"valid_data_with_commit_OK\":true,\"whole_core_drain\":false,\"cycles\":%0d}",queries,reads,cycle);
 $finish;
end
endmodule
