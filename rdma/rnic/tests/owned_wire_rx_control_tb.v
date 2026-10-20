// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual same tables/timer/process and real pool. Packet/QP admission is still
// a test stimulus, not a native/wire RX/CQ/recovery proof. No test pool mux.
`timescale 1ns/1ps
module wire_rx_tb;
reg clk=0,rst=0;always #2 clk=~clk;
reg [415:0] idata=0;reg iv=0;wire ir;
reg [223:0] udata=0;reg uv=0;wire ur;
reg [191:0] retry_data=0;reg retry_valid=0;wire retry_ready;
reg [319:0] descriptor_data=0;reg descriptor_valid=0;wire descriptor_ready;
reg [79:0] packet_data=0;reg packet_valid=0;wire packet_ready;
wire [1023:0] meta_data;wire meta_valid;reg meta_ready=0;
wire [79:0] body_data;wire body_valid;reg body_ready=0;
wire [575:0] event_data;wire event_valid;
wire [319:0] rdinit_data,fence_data;wire rdinit_valid,fence_valid;reg fence_ready=0;
wire [31:0] fault,inserted,released,partial;wire [7:0] phase;
wire pool_initialized,pool_fault;wire [11:0] pool_free,pool_active;
integer which=1,cycle=0,deadline,i,bindings=0,fences=0,rdinits=0;
integer meta_count=0,body_count=0,body_frames=0;
integer expect_offset=0,expect_end=0,b;
reg compare_body=0;
reg [7:0] frame [0:65534];
integer frame_len=0;
reg [95:0] expected_bth;reg [127:0] expected_exh;
reg [319:0] frame_descriptor;
reg mheld=0,bheld=0;reg [1023:0] mprior;reg [79:0] bprior;
reg fheld=0;reg [319:0] prior_fence;
reg pheld=0;reg [79:0] pprior;
integer blocked_beats=0;reg quarantine_stall=0;
localparam [63:0] EP=64'hfedcba9876543210,SQ=64'h8765432100000001;
localparam [63:0] LA=64'hfedcba9876540000,RA=64'h123456789abc0000;
rocev2_owned_wire_rx dut(.clk(clk),.rst(rst),
 .s_insert_data(idata),.s_insert_valid(iv),.s_insert_ready(ir),
 .s_update_data(udata),.s_update_valid(uv),.s_update_ready(ur),
 .s_retry_data(retry_data),.s_retry_valid(retry_valid),.s_retry_ready(retry_ready),
 .s_rx_descriptor_data(descriptor_data),.s_rx_descriptor_valid(descriptor_valid),.s_rx_descriptor_ready(descriptor_ready),
 .s_rx_packet_data(packet_data),.s_rx_packet_valid(packet_valid),.s_rx_packet_ready(packet_ready),
 .m_rx_meta_data(meta_data),.m_rx_meta_valid(meta_valid),.m_rx_meta_ready(meta_ready),
 .m_rx_body_data(body_data),.m_rx_body_valid(body_valid),.m_rx_body_ready(body_ready),
 .m_event_data(event_data),.m_event_valid(event_valid),.m_event_ready(1'b0),
 .m_rdinit_data(rdinit_data),.m_rdinit_valid(rdinit_valid),.m_rdinit_ready(1'b1),
 .m_fence_data(fence_data),.m_fence_valid(fence_valid),.m_fence_ready(fence_ready),
 .fault(fault),.phase(phase),.inserted(inserted),.released(released),.partial(partial),
 .pool_initialized(pool_initialized),.pool_fault(pool_fault),.pool_free(pool_free),.pool_active(pool_active));
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>400000)$fatal(1,"bounded actual RX lookup deadline");
 if(pheld && (packet_valid!==1'b1 || packet_data!==pprior))$fatal(1,"source packet changed under actual backpressure");
 pheld=packet_valid&&!packet_ready;pprior=packet_data;
 if(mheld && (meta_valid!==1'b1 || meta_data!==mprior))$fatal(1,"held wire metadata changed");
 mheld=meta_valid&&!meta_ready;mprior=meta_data;
 if(bheld && (body_valid!==1'b1 || body_data!==bprior))$fatal(1,"held wire body changed");
 bheld=body_valid&&!body_ready;bprior=body_data;
 if(body_valid && !dut.body_active)$fatal(1,"raw body before actual metadata acceptance");
 if(fheld && (fence_valid!==1'b1 || fence_data!==prior_fence))$fatal(1,"lookup fence changed under stall");
 fheld=fence_valid&&!fence_ready;prior_fence=fence_data;
 if(meta_valid&&meta_ready)meta_count=meta_count+1;
 if(body_valid&&body_ready)begin
  if(body_data[79:73]!==0)$fatal(1,"body reserved bits");
  for(b=0;b<8;b=b+1)if(body_data[64+b])begin
   if(!compare_body || expect_offset>=expect_end || body_data[8*b+:8]!==frame[expect_offset])
    $fatal(1,"wrong actual raw body byte offset%0d data%h expected%h",expect_offset,body_data[8*b+:8],frame[expect_offset]);
   expect_offset=expect_offset+1;body_count=body_count+1;
  end
  if(body_data[72])begin
   if(expect_offset!=expect_end)$fatal(1,"raw body short at last");
   body_frames=body_frames+1;
  end
 end
 if(fence_valid&&fence_ready)fences=fences+1;
 if(rdinit_valid)rdinits=rdinits+1;
 if(pool_fault || (fault!==0 && which!=9 && which!=10 && which!=11 && which!=12))$fatal(1,"actual RX lookup fault%h phase%0d",fault,phase);
end else begin mheld=0;bheld=0;fheld=0;pheld=0;end
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
function [247:0] lease(input [15:0] index,input [63:0] generation,input [23:0] psn,input [63:0] seq);
begin lease={seq,EP,psn,16'd2,generation,index};end endfunction
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

task build_frame(input [7:0] op,syndrome,input [23:0] qpn,psn,input integer bytes,input [63:0] epoch);
integer n;
begin
 frame_len=bytes;
 for(n=0;n<bytes;n=n+1)frame[n]=(n*17+3)&255;
 frame[0]=op;frame[1]=8'h40;frame[2]=8'hff;frame[3]=8'hff;frame[4]=0;
 frame[5]=qpn[23:16];frame[6]=qpn[15:8];frame[7]=qpn[7:0];
 frame[8]=0;frame[9]=psn[23:16];frame[10]=psn[15:8];frame[11]=psn[7:0];
 if(op==13 || op==15 || op==16 || op==17)begin
  frame[12]=syndrome;frame[13]=8'hab;frame[14]=8'hcd;frame[15]=8'hef;
 end
 expected_bth=0;expected_exh=0;
 for(n=0;n<12;n=n+1)expected_bth[n*8+:8]=frame[n];
 if(op==13 || op==15 || op==16 || op==17)
  for(n=0;n<4;n=n+1)expected_exh[n*8+:8]=frame[n+12];
 else if(op==6 || op==10 || op==12)
  for(n=0;n<16;n=n+1)expected_exh[n*8+:8]=frame[n+12];
 frame_descriptor=0;frame_descriptor[23:0]=qpn;frame_descriptor[87:24]=epoch;
 frame_descriptor[103:88]=bytes;frame_descriptor[104]=1;frame_descriptor[289:274]=16'hffff;
end endtask
task send_descriptor(input [319:0] d);
begin
 @(negedge clk);descriptor_data=d;descriptor_valid=1;
 @(posedge clk);while(!descriptor_ready)@(posedge clk);@(negedge clk);descriptor_valid=0;
end endtask
task send_packet(input integer bytes,input badkeep);
integer n,k,validbytes;
begin
 for(n=0;n<bytes;n=n+8)begin
  @(negedge clk);packet_data=0;validbytes=(bytes-n<8)?bytes-n:8;
  for(k=0;k<validbytes;k=k+1)begin packet_data[k*8+:8]=frame[n+k];packet_data[64+k]=1;end
  packet_data[72]=(n+8>=bytes);if(badkeep && n==0)packet_data[71:64]=8'hfd;
  packet_valid=1;@(posedge clk);while(!packet_ready)@(posedge clk);@(negedge clk);packet_valid=0;
 end
end endtask
task send_frame;begin send_descriptor(frame_descriptor);send_packet(frame_len,0);end endtask
task expect_meta(input [7:0] status,input [11:0] walked,input head,input [23:0] delta,
 input [247:0] token,input remote_raw,input [21:0] numpkg,input isnak);
reg [1023:0] expected;reg [7:0] op,syndrome;reg aeth;
begin
 deadline=cycle+30000;while(!meta_valid)begin if(cycle>deadline)$fatal(1,"missing wire meta phase%0d f%h ingress%h front%h words%0d",phase,fault,dut.rx_ingress_fault,dut.rx_front_fault,dut.rx_parser_words);@(negedge clk);end
 op=frame[0];aeth=op==13 || op==15 || op==16 || op==17;syndrome=aeth?frame[12]:0;
 expected=0;expected[247:0]=token;expected[271:248]=frame_descriptor[23:0];
 expected[295:272]={frame[9],frame[10],frame[11]};expected[303:296]=op;expected[367:304]=frame_descriptor[87:24];
 expected[391:368]=delta;expected[399:392]=status;expected[411:400]=walked;
 expected[419:412]=syndrome;expected[420]=aeth;expected[421]=head;expected[422]=!remote_raw;
 expected[543:448]=expected_bth;expected[671:544]=expected_exh;expected[693:672]=numpkg;
 expected[694]=isnak;expected[695]=remote_raw;expected[1015:696]=frame_descriptor;
 if(meta_data!==expected)$fatal(1,"wire meta mismatch got%h expected%h",meta_data,expected);
 repeat(31)@(negedge clk);
 if(body_valid)$fatal(1,"body overtook metadata acceptance");
end endtask
task accept_meta;begin @(negedge clk);meta_ready=1;@(posedge clk);@(negedge clk);meta_ready=0;end endtask
task accept_body(input integer offset,lastbyte);
integer target;
begin
 expect_offset=offset;expect_end=lastbyte;compare_body=1;target=body_frames+1;
 @(negedge clk);body_ready=1;deadline=cycle+30000;
 while(body_frames<target)begin if(cycle>deadline)$fatal(1,"missing bound raw body");@(negedge clk);end
 body_ready=0;compare_body=0;repeat(37)@(negedge clk);
end endtask
task descriptor_marker;
reg [319:0] d;
begin d=0;d[105]=1;d[273:106]=marker_owner(SQ);send_descriptor(d);end endtask
task no_effect;
begin
 if(released!==0 || partial!==0 || rdinits!=0 || pool_active!==inserted)
  $fatal(1,"wire identity handoff became retirement/DMA");
end endtask
task malformed_until_upstream_stall(input nonfinal_at_declared_end);
integer n,k,waited;reg transferred;
begin
 build_frame(17,0,2,0,256,EP);
 if(nonfinal_at_declared_end)frame_descriptor[103:88]=16;
 send_descriptor(frame_descriptor);
 for(n=0;n<32 && !quarantine_stall;n=n+1)begin
  @(negedge clk);packet_data=0;
  for(k=0;k<8;k=k+1)packet_data[k*8+:8]=frame[n*8+k];
  packet_data[71:64]=8'hff;packet_data[72]=0;
  if(n==0 && !nonfinal_at_declared_end)packet_data[71:64]=8'hfd;
  packet_valid=1;waited=0;transferred=0;
  while(!transferred && waited<32)begin
   @(posedge clk);if(packet_ready)transferred=1;else waited=waited+1;
  end
  if(transferred)blocked_beats=blocked_beats+1;else quarantine_stall=1;
 end
 if(!quarantine_stall || blocked_beats>=32)$fatal(1,"quarantined pipeline silently consumed/dropped unlimited packet beats");
 if(fault===0 || dut.rx_frame_fault!==32'd40)$fatal(1,"no actual frame-commit quarantine");
 // Hold the unaccepted source beat, do not reset/force/withdraw it.
 repeat(127)begin
  @(negedge clk);
  if(packet_ready!==1'b0 || meta_valid || body_valid || fence_valid || event_valid || rdinit_valid)
   $fatal(1,"actual quarantine reopened input/emitted parser/owner/completion work");
 end
 no_effect();
 if(inserted!==0 || meta_count!=0 || body_frames!=0 || pool_free!==2000)
  $fatal(1,"malformed long frame acquired or retired a real owner");
 $display("WIRE_RX_QUARANTINE {\"pass_test\":true,\"case\":%0d,\"accepted_before_stall\":%0d,\"held_cycles\":127,\"frame_fault\":%0d,\"input_stopped\":true,\"no_parser_or_owner_effect\":true,\"DUT_force\":false}",which,blocked_beats,dut.rx_frame_fault);
end endtask
initial begin
 if(!$value$plusargs("CASE=%d",which))which=1;
 @(negedge clk);rst=1;repeat(8)@(negedge clk);rst=0;while(!pool_initialized)@(negedge clk);
 if(which>=1 && which<=8)begin
  insert_record(12,65,24'hffffff,SQ);wait_inserted(1);
  // Full byte values are parser/identity data, not implemented retry policy.
  for(i=(which-1)*32;i<which*32;i=i+1)begin
   build_frame(16,i,2,24'hffffff,81,EP);send_frame();
   // Original FNS isNAK checks bits6:5 only, also true for E0..FF.
   // Full8bit syndrome, NOT this legacy flag, controls raw body discard.
   expect_meta(0,1,1,0,lease(0,1,24'hffffff,SQ),0,1,((i&96)==96));
   accept_meta();
   if(i<32)accept_body(12,81);
   else begin repeat(93)@(negedge clk);if(body_valid)$fatal(1,"control AETH leaked as READ data syndrome%h",i);end
   no_effect();
  end
  if(meta_count!=32 || body_frames!=((which==1)?32:0) || body_count!=((which==1)?2208:0))$fatal(1,"syndrome coverage mismatch");
 end else if(which==9 || which==10)begin
  build_frame(17,0,2,0,16,EP);
  if(which==9)begin send_descriptor(frame_descriptor);send_packet(frame_len,1);end
  else begin frame[1]=8'h41;send_frame();end
  deadline=cycle+1000;while(fault===0)begin if(cycle>deadline)$fatal(1,"invalid keep/header version accepted");@(negedge clk);end
  repeat(127)@(negedge clk);
  if(meta_valid || body_valid || released!==0 || inserted!==0)$fatal(1,"invalid frame side effect");
 end else if(which==11 || which==12)begin
  malformed_until_upstream_stall(which==12);
 end else $fatal(1,"unknown control case");
 repeat(53)@(negedge clk);
 $display("OWNED_WIRE_RX_CONTROL_RTL {\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"meta\":%0d,\"body_bytes\":%0d,\"body_frames\":%0d,\"fences\":%0d,\"inserted\":%0d,\"released\":%0d,\"partial\":%0d,\"fault\":%0d,\"AETH_values\":%0d,\"native_CQ\":false}",which,cycle,meta_count,body_count,body_frames,fences,inserted,released,partial,fault,(which<=8)?32:0);$finish;
end
endmodule
