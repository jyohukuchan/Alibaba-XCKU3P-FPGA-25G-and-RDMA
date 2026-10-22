// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual authority RTL, qualified recorded native1000 seeds; producer/live
// context/lease signals below are MODELS. No cancellation/drain/CQ/unpin proof.
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,parent_fault=0,event_taken=0,trusted_valid=1,noncontrol_lease_guard=0;
reg [999:0] event_data=0;reg [355:0] trusted_context=0;reg [23:0] trusted_psn=0;
reg [7:0] quarantined=4;wire [7:0] cancel_only_authorized;wire fault;wire [7:0] fault_code;
rocev2_fatal_rq_cancel_authority dut(.*);
reg [31:0] words[0:31];integer mode=0,i,cycle=0;reg bad;
always @(posedge clk)begin cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded authority cycle gate");end
initial begin
 if(!$value$plusargs("MODE=%d",mode))$fatal(1,"explicit authority mode required");
 if(mode==0 || mode==17 || mode==18)$readmemh("seed0.hex",words);else $readmemh("seed1.hex",words);
 for(i=0;i<32;i=i+1)if(i<31)event_data[i*32+:32]=words[i];else event_data[999:992]=words[i][7:0];
 trusted_context=event_data[779:424];trusted_psn=event_data[867:844];
 repeat(4)@(negedge clk);rst=0;
 // A held offered certificate is not the actual completed upstream handshake.
 repeat(71)begin @(negedge clk);if(cancel_only_authorized!==0 || fault)$fatal(1,"VALID/data/host observation cannot become completed native join authority");end
 case(mode)
 2:trusted_context[167]=~trusted_context[167];
 3:trusted_context[103]=~trusted_context[103];
 4:trusted_valid=0;
 5:trusted_psn=trusted_psn+1;
 6:quarantined=0;
 7:event_data[999:992]=3;
 8:event_data[959:952]=1;
 9:event_data[983:960]=1;
 10:event_data[899:892]=8'h60;
 11:event_data[843:780]=0;
 12:event_data[255:224]=0;
 13:event_data[383]=~event_data[383];
 14:event_data[103:72]=1;
 15:event_data[71:40]=4080;
 16:event_data[223:160]=64'hffffffffffffffff;
 17:event_data[0]=1;
 18:event_data[943:928]=16'h6001;
 20:event_data[300]=1'bx;
 30:begin event_data[447:424]=24'h100002;trusted_context[23:0]=24'h100002;end
 endcase
 event_taken=mode==19 ? 1'bx:1'b1;@(negedge clk);event_taken=0;#1;
 bad=(mode>=2 && mode<=20)||mode==30;
 if(bad)begin
  if(!fault || cancel_only_authorized!==0)$fatal(1,"wrong/unknown/full-width owner or malformed proof must fail closed");
 end else begin
  if(fault || cancel_only_authorized!==4)$fatal(1,"actual recorded completed native join/current full owner must grant only selected RQC cancellation distinction");
  case(mode)
 21:begin event_taken=1;@(negedge clk);event_taken=0;#1;if(!fault || cancel_only_authorized!==0)$fatal(1,"native certificate replay cannot rearm authority");end
 22:begin noncontrol_lease_guard=1;#1;if(cancel_only_authorized!==0 || fault)$fatal(1,"other actual lease must retain all guards");noncontrol_lease_guard=0;#1;if(cancel_only_authorized!==4)$fatal(1,"same native certificate/current identity remains exact after other real lease ends");end
 23:begin trusted_valid=0;#1;if(cancel_only_authorized!==0 || fault)$fatal(1,"temporarily unavailable actual lookup is not authority");end
 24:begin trusted_context[167]=~trusted_context[167];#1;if(cancel_only_authorized!==0)$fatal(1,"old full64 cookie cannot bind another owner");end
 25:begin trusted_psn=trusted_psn+1;#1;if(cancel_only_authorized!==0)$fatal(1,"old actual PSN frontier cannot bind later traffic");end
 26:begin quarantined=0;#1;if(cancel_only_authorized!==0)$fatal(1,"cancel permission never creates or clears native quarantine");end
 27:begin parent_fault=1;#1;if(cancel_only_authorized!==0)$fatal(1,"real parent fault closes authority immediately");@(negedge clk);if(!fault)$fatal(1,"parent failure must stay latched");end
 28:begin noncontrol_lease_guard=1'bx;#1;if(cancel_only_authorized!==0)$fatal(1,"unknown lease cannot be idle proof");end
 29:begin trusted_context[23:0]=24'h100002;#1;if(cancel_only_authorized!==0)$fatal(1,"never narrow actual24-bit owner before bounds");end
 31:begin event_data[843:780]=2;event_taken=1;@(negedge clk);event_taken=0;#1;if(!fault || cancel_only_authorized!==0)$fatal(1,"new serial is not legitimate recovery/rearm for same quarantined owner");end
 endcase
 end
 $display("FATAL_RQ_AUTHORITY_RESULT {\"pass_test\":true,\"mode\":%0d,\"recorded_native_seed\":true,\"producer_and_live_context_modeled\":true,\"cancellation_CQ_STOP_drain_unpin\":false}",mode);
 $finish;
end
endmodule
