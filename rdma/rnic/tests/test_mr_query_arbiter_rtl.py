# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state arbitration/ownership units; external validator is an explicit model.

The separate shared-responder fixture exercises the actual single MR table.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl'
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;reg rst=1;
reg [31:0] pd=32'h00110022,tags=32'hf123f123;
reg [63:0] keys=64'h8000000880000010,lengths=64'h0000004100000042;
reg [127:0] addresses=128'hfedcba9876543001f123456789abc001;
reg [5:0] operations={3'd1,3'd3};
reg [1:0] valid=0,ready=0;wire [1:0] qr,rv;
wire [31:0] rt;wire [15:0] re;wire [127:0] ro,rd;wire [63:0] rl;
wire [15:0] tp,tt;wire [31:0] tk,tl;wire [63:0] ta;wire [2:0] top;
wire tv,tr,busy,fault;wire [7:0] fc;
reg tqready=0,respvalid=0;reg [15:0] resptag=0;reg [7:0] resperror=0;
reg [63:0] respoffset=0,respaddress=0;reg [31:0] resplength=0;
wire [162:0] request_fields={tp,tk,ta,tl,top,tt};
wire [369:0] response_fields={rt,re,ro,rd,rl,rv};
rocev2_mr_query_arbiter dut(
 .clk(clk),.rst(rst),.s_request_pd(pd),.s_request_key(keys),.s_request_address(addresses),
 .s_request_length(lengths),.s_request_operation(operations),.s_request_tag(tags),
 .s_request_valid(valid),.s_request_ready(qr),.m_response_tag(rt),.m_response_error(re),
 .m_response_offset(ro),.m_response_dma_address(rd),.m_response_length(rl),.m_response_valid(rv),.m_response_ready(ready),
 .m_request_pd(tp),.m_request_key(tk),.m_request_address(ta),.m_request_length(tl),.m_request_operation(top),
 .m_request_tag(tt),.m_request_valid(tv),.m_request_ready(tqready),
 .s_response_tag(resptag),.s_response_error(resperror),.s_response_offset(respoffset),
 .s_response_dma_address(respaddress),.s_response_length(resplength),.s_response_valid(respvalid),.s_response_ready(tr),
 .busy(busy),.fault(fault),.fault_code(fc));
integer cycles=0,queries=0,responses=0,order=0;
reg stalled=0;reg [162:0] saved;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>1000)$fatal(1,"arbiter deadline");
 if(stalled && (!tv || request_fields!==saved))$fatal(1,"offered query withdrawn/changed");
 stalled=tv&&!tqready;saved=request_fields;
 if(tv&&tqready)queries=queries+1;
 if(|(rv&ready))responses=responses+1;
 if(rv==3 || qr==3)$fatal(1,"two clients own one response/query");
end
task offer;
 input integer client_index;
 integer deadline;
 begin
  @(negedge clk);valid[client_index]=1;deadline=cycles+20;
  @(posedge clk);while(qr[client_index]!==1)begin if(cycles>deadline)$fatal(1,"client admission deadline");@(posedge clk);end
  @(negedge clk);valid[client_index]=0;
 end
endtask
task respond;
 input integer client_index;input [7:0] error_code;input integer stall;
 reg [369:0] held;
 begin
  if(!tv || tp!==pd[client_index*16+:16] || tk!==keys[client_index*32+:32] ||
    ta!==addresses[client_index*64+:64] || tl!==lengths[client_index*32+:32] ||
    top!==operations[client_index*3+:3] || tt!==tags[client_index*16+:16])$fatal(1,"query tuple truncated or mixed");
  resptag=tt;resplength=tl;resperror=error_code;
  respoffset=64'hf123456789abcdef;respaddress=64'h8123456789abcdef;
  tqready=1;@(posedge clk);@(negedge clk);tqready=0;respvalid=1;#1;
  if(rv!==(1<<client_index) || rt[client_index*16+:16]!==resptag || re[client_index*8+:8]!==error_code)
   $fatal(1,"response went to wrong owner (same cookies must not alias)");
  if(rt[(1-client_index)*16+:16]!==0 || re[(1-client_index)*8+:8]!==0 ||
    ro[(1-client_index)*64+:64]!==0 || rd[(1-client_index)*64+:64]!==0 || rl[(1-client_index)*32+:32]!==0)
   $fatal(1,"non-owner observed result");
  if(error_code==0)begin
   if(ro[client_index*64+:64]!==respoffset || rd[client_index*64+:64]!==respaddress || rl[client_index*32+:32]!==resplength)
    $fatal(1,"successful response truncated");
  end else if(ro!==0 || rd!==0 || rl!==0)$fatal(1,"denial leaked extent/address");
  held=response_fields;
  repeat(stall)begin
   @(negedge clk);if(!busy || qr!=0 || tr || response_fields!==held)$fatal(1,"stalled owner lost");
  end
  ready=1<<client_index;@(posedge clk);@(negedge clk);ready=0;respvalid=0;
  #1;if(busy || fault)$fatal(1,"normal response did not retire");
 end
endtask
initial begin
 repeat(4)@(negedge clk);rst=0;
 // BODY
 $display("MR_ARBITER_PASS queries=%0d responses=%0d cycles=%0d",queries,responses,cycles);$finish;
end
endmodule
'''


class MRQueryArbiterRTLTests(unittest.TestCase):
    def simulate(self,body):
        tb=TB.replace('// BODY',body)
        self.assertNotIn('force ',tb)
        with tempfile.TemporaryDirectory(prefix='as02-mr-arbiter-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                              str(RTL/'rocev2_mr_query_arbiter.v')],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn('MR_ARBITER_PASS',r.stdout)

    def test_full_tuples_same_cookie_response_stalls_and_denial_zeroing(self):
        self.simulate('offer(0);respond(0,0,7);offer(1);respond(1,3,9);offer(0);respond(0,10,3);')

    def test_pending_query_is_registered_and_not_replaced_by_competing_client(self):
        self.simulate(r'''
offer(1);saved=request_fields;
valid[0]=1;
repeat(12)begin @(negedge clk);if(!tv || qr!=0 || request_fields!==saved)$fatal(1,"pending query owner changed");end
respond(1,0,5);
@(posedge clk);if(!qr[0])$fatal(1,"competing client starved");
@(negedge clk);valid=0;respond(0,0,5);
''')

    def test_continuously_offered_clients_alternate_without_starvation(self):
        self.simulate(r'''
valid=3;
repeat(10)begin
 @(posedge clk);if(qr!==(order%2==0 ? 1 : 2))$fatal(1,"round-robin unfair owner=%d ready=%b",order,qr);
 @(negedge clk);respond(order%2,0,3);order=order+1;
end
valid=0;
if(queries!=10 || responses!=10)$fatal(1,"arbitration count mismatch");
''')

    def test_wrong_tag_length_unknown_error_retains_owner_without_fake_response(self):
        for mutation in ["resptag=tt^16'h8000;",'resplength=tl+1;',"resperror=8'hff;"]:
            with self.subTest(mutation=mutation):
                self.simulate(r'''
offer(0);resptag=tt;resplength=tl;resperror=0;tqready=1;
@(posedge clk);@(negedge clk);tqready=0;
'''+mutation+r'''
respvalid=1;ready=3;repeat(4)@(negedge clk);
if(!fault || fc!==8'h40 || !busy || rv!=0 || qr!=0 || tr || responses!=0)$fatal(1,"uncertain response released owner");
respvalid=0;repeat(8)@(negedge clk);
if(!fault || !busy || rv!=0 || qr!=0)$fatal(1,"fault was not sticky");
''')

    def test_unexpected_response_does_not_accept_a_new_owner(self):
        self.simulate(r'''
valid=3;respvalid=1;ready=3;#1;if(qr!=0 || rv!=0 || tr)$fatal(1,"unsolicited response admitted work");
repeat(5)@(negedge clk);
if(!fault || !busy || queries!=0 || responses!=0 || qr!=0)$fatal(1,"unsolicited response not contained");
''')

    def test_protocol_fault_does_not_withdraw_already_offered_query(self):
        self.simulate(r'''
offer(1);saved=request_fields;respvalid=1;repeat(3)@(negedge clk);
respvalid=0;repeat(5)begin @(negedge clk);if(!fault || !busy || !tv || request_fields!==saved || qr!=0 || rv!=0)
 $fatal(1,"fault retracted offered query");end
tqready=1;@(posedge clk);@(negedge clk);tqready=0;repeat(3)@(negedge clk);
if(tv || !fault || !busy || responses!=0 || qr!=0)$fatal(1,"fault invented drain or completion");
''')


if __name__=='__main__':unittest.main()
