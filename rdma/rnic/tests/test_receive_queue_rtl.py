# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short four-state checks of the actual posted receive-owner store.

Whole native placement/HLS is tested separately. No retirement/CQ/unpin or
real multi-QP transport claim is inferred from these storage checks.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_receive_queue.v'

def context(qpn=2,sequence=1):
    value=3|(0x210<<116)|(0xfedcba9876543210<<180)|(8<<244)|(128<<276)|(1<<308)|(4<<324)|\
        (sequence<<340)|(17<<356)|(qpn<<372)|(0x9123456700000001<<396)|\
        (sequence<<460)|((0xf123456789abc000+sequence)<<524)
    return f"588'h{value:x}"

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,parent_fault=0;always #2 clk=~clk;
reg cancel_block=0,cancel_valid=0,cancel_safe=0;
reg [23:0] cancel_qpn=0;reg [15:0] cancel_pd=0;reg [63:0] cancel_epoch=0;
wire cancel_ready;wire [31:0] cancelled_count;
reg [587:0] s_post_context=0;reg s_post_valid=0;wire s_post_ready;
reg [23:0] query_qpn=2;wire [587:0] m_head_context;wire m_head_valid;reg m_head_ready=0;
reg [587:0] s_placement_context=0;reg [31:0] s_placement_length=0;reg s_placement_valid=0;
wire s_placement_ready;wire [7:0] queue_guard;wire active,fault;wire [7:0] fault_code;
wire [31:0] posted_count,taken_count,placement_count,received_bytes;
reg [23:0] s_placement_psn=24'h987654;
reg [31:0] s_placement_notification=0;reg [7:0] s_placement_notification_flags=0;
reg [679:0] s_core_data=0;reg s_core_valid=0;wire s_core_ready;
wire core_proved;wire [31:0] core_proof_count;wire [23:0] core_msn;
wire [587:0] held_context,m_ticket_context;
wire [679:0] held_core_data;
reg [695:0] s_mac_data=0;reg s_mac_valid=0;wire s_mac_ready;
reg memory_drained=0;wire [31:0] m_ticket_received_bytes;
wire [31:0] m_ticket_notification;wire [7:0] m_ticket_notification_flags;
wire m_ticket_valid;reg m_ticket_ready=0;
reg [587:0] s_commit_context=0,s_retire_context=0;
reg s_commit_valid=0,s_retire_valid=0;wire s_commit_ready,s_retire_ready;
rocev2_receive_queue #(.RECV_RETIRE_ENABLE(RETIRE_PROFILE)) dut(.*);
initial begin repeat(4)@(negedge clk);rst=0;
// BODY
$display("RQ_OWNER_RESULT {\"pass_test\":true,\"posted\":%0d,\"taken\":%0d,\"placed\":%0d,\"received\":%0d,\"fault\":%0d}",posted_count,taken_count,placement_count,received_bytes,fault);
$finish;end
endmodule
'''

class ReceiveQueueTests(unittest.TestCase):
    reports={}
    def simulate(self,body,retire=False):
        with tempfile.TemporaryDirectory(prefix='as02-rq-owner-')as d:
            p=Path(d);(p/'tb.v').write_text(TB.replace('// BODY',body).replace('RETIRE_PROFILE',str(int(retire))))
            r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test'),str(p/'tb.v'),str(RTL)],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            r=subprocess.run(['vvp',str(p/'test')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr+'\n'+(p/'tb.v').read_text())
            rows=[json.loads(x.split(' ',1)[1])for x in r.stdout.splitlines()if x.startswith('RQ_OWNER_RESULT ')]
            self.assertEqual(len(rows),1);self.reports[self._testMethodName+str(len(self.reports))]=rows[0]
    def test_full_eight_QP_eight_entry_owner_capacity_and_placement_keeps_all_refs(self):
        body=[]
        for qpn in range(8):
            for seq in range(1,9):
                body.append(f"@(negedge clk);s_post_context={context(qpn,seq)};s_post_valid=1;#1;"
                    "if(!s_post_ready)$fatal(1,\"actual RQ capacity\");@(posedge clk);@(negedge clk);s_post_valid=0;")
        body.append("#1;if(posted_count!=64 || queue_guard!==8'hff || fault)$fatal(1,\"posted full owners lost\");")
        for qpn in range(8):
            body.append(f"query_qpn={qpn};#1;if(!m_head_valid || m_head_context!=={context(qpn,1)})"
                "$fatal(1,\"full QP identity/head context lost\");")
        body.append(f"@(negedge clk);query_qpn=2;s_post_context={context(2,9)};#1;if(s_post_ready)$fatal(1,\"RQ overcommit\");"
            "m_head_ready=1;@(posedge clk);@(negedge clk);m_head_ready=0;#1;"
            "if(!active || m_head_valid || taken_count!=1)$fatal(1,\"real receive owner take\");")
        body.append(f"@(negedge clk);s_placement_context={context(2,1)};s_placement_length=65;s_placement_valid=1;#1;"
            "if(!s_placement_ready)$fatal(1,\"actual receive byte count\");@(posedge clk);@(negedge clk);s_placement_valid=0;"
            "repeat(12)@(negedge clk);if(placement_count!=1 || received_bytes!=65 || !active || queue_guard!==8'hff ||"
            "posted_count!=64 || fault)$fatal(1,\"placement fabricated retirement/unpin count%0d recv%0d active%0d guard%h posted%0d fault%0d code%h placed%0d\",placement_count,received_bytes,active,queue_guard,posted_count,fault,fault_code,dut.placed);")
        self.simulate('\n'.join(body))
    def test_full_high_QPN_and_unknown_epoch_cannot_alias_a_receive_owner(self):
        for value,extra in [(context(0x800002),''),(context(2),"s_post_context[400]=1'bx;")]:
            with self.subTest(value=value):
                self.simulate(f's_post_context={value};{extra}s_post_valid=1;#1;'
                    'if(s_post_ready)$fatal(1,"untrusted RQ authority accepted known%0d ok%0d epochbit%b context%h",dut.post_known,dut.post_ok,s_post_context[400],s_post_context);repeat(3)@(negedge clk);'
                    'if(!fault || queue_guard!==8\'hff || posted_count || taken_count || placement_count)'
                    '$fatal(1,"invalid receive owner did not quarantine");')
    def test_core_receipt_waits_for_matching_placement_and_never_releases_posted_owner(self):
        self.simulate(f'''@(negedge clk);s_post_context={context()};s_post_valid=1;
@(posedge clk);@(negedge clk);s_post_valid=0;m_head_ready=1;
@(posedge clk);@(negedge clk);m_head_ready=0;
s_core_data={{8'd0,24'd1,4'd0,24'h987654,32'd65,{context()}}};s_core_valid=1;
repeat(4)begin #1;if(s_core_ready || core_proved || fault)$fatal(1,"core receipt bypassed placement");@(negedge clk);end
s_placement_context={context()};s_placement_length=65;s_placement_valid=1;
@(posedge clk);@(negedge clk);s_placement_valid=0;#1;
if(!s_core_ready || core_proved)$fatal(1,"actual full-owner/length/PSN proof missing");
@(posedge clk);@(negedge clk);s_core_valid=0;
repeat(12)@(negedge clk);
if(!core_proved || core_proof_count!=1 || core_msn!=1 || !active || queue_guard!==8'h04 ||
 posted_count!=1 || placement_count!=1 || received_bytes!=65 || fault)
 $fatal(1,"internal receipt fabricated CQ/pop/unpin or lost identity");''',True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_RQ_OWNER_REPORT'):
            with (ROOT/name).open('x')as f:f.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,
                four_state_simulation=True,cases=cls.reports,hardware_verified=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
