# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual composite/config/MR/page/DMA/RAM with EXPLICIT transport stub.

Finite control/ownership tests, NOT HLS wire or real PCIe/host-pin evidence.
The separate --composite actual-HLS probe verifies real response packets.
"""
import hashlib
import json
import os
from pathlib import Path
import unittest

import probe_protected_responder as probe
import probe_protected_paged_dma as integration
import test_protected_responder_rtl as admission

ROOT=probe.ROOT


def transport_stub():
    stub=admission.stub_source()
    # Real known test payload rather than the corruption harness's zeros.
    fn='''
function [511:0] finite_payload;
 input [31:0] pos;integer b;
 begin
  for(b=0;b<64;b=b+1) finite_payload[b*8+:8]=((pos+b)*179)^((pos+b)>>7)^8'hd3;
 end
endfunction
'''
    return stub.replace("assign m_axis_mem_write_tdata=512'd0;",fn+'assign m_axis_mem_write_tdata=finite_payload(position);')


class PagedResponderControlTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*integration.paged.SOURCES,Path(__file__),Path(integration.__file__),Path(admission.__file__),Path(probe.__file__),
            ROOT/'rdma/rnic/rtl/rocev2_paged_responder.v',ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
            ROOT/'rdma/rnic/rtl/rocev2_mr_table.v',ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',
            ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v',ROOT/'external/corundum/fpga/lib/axis/rtl/axis_fifo.v']
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}

    def run_body(self,body,*,unpublished=False):
        frame=probe.rocev2_wire.write_only_frame(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
            destination_qpn=2,psn=probe.PSN,remote_address=probe.VA+0x210,rkey=8,payload=probe.PAYLOAD)
        fixtures=probe.words(frame[14:])
        tb=integration.composite_bench().replace('STIMULUS_LAST',str(len(fixtures)-1))
        if unpublished:tb=tb.replace('publish_pages(0,8);','')
        begin=tb.index(' if(deferred==0');end=tb.index('$fatal(',begin)
        tb=tb[:begin]+''' if(deferred==0 || commands!=1 || statuses!=1 || completed!=1 || fault ||
 command_count!=1 || fence_count!=1 || completion_count!=1 || pcie_physical_reads!=1 || pcie_physical_writes!=2) '''+tb[end:]
        tb=tb.replace('// TEST_BODY',body.replace('FRAME_WORDS',str(len(fixtures))))
        # Instance-only report storage: do NOT pollute the original test class's
        # shared report counts when unittest discovers both suites together.
        harness=admission.ProtectedResponderUnitTests('test_admission_rejections_lease_and_invalidation')
        harness.reports={};harness._testMethodName=self._testMethodName
        harness.simulate(tb,fixtures,transport_stub())
        self.reports[self._testMethodName]=harness.reports[self._testMethodName][0]

    def test_queued_frame_waits_for_full_mr_pte_publication(self):
        self.run_body('''
admission_pause=1;send_frame(0,FRAME_WORDS);
repeat(80) @(negedge clk);
if(commands || accepted || txframes || rxgood!=1 || !quiet) $fatal(1,"paused publication admitted queued frame");
publish_pages(0,8);
repeat(20) @(negedge clk);
if(commands || accepted || txframes || !quiet) $fatal(1,"seal alone reopened admission");
admission_pause=0;allow();
''',unpublished=True)

    def test_pause_and_held_invalidation_do_not_deadlock_partial_packet(self):
        self.run_body('''
send_frame(0,FRAME_WORDS);
while(quiet) @(negedge clk);
admission_pause=1;ci=0;cp=17;cc=2;ck=8;cv=1;car=0;revoke_watch=1;
pc=4;pi=0;pk=8;pv=1;par=0;
expiry=cycle+2000;while(completed==0 && cycle<expiry) @(negedge clk);
if(completed!=1) $fatal(1,"pause/management stopped accepted partial packet");
revoke_watch=0;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;
while(!cav) begin @(negedge clk);if(cfg_ready) $fatal(1,"PTE preempted MR configuration");end
if(ce!=0 || cak!=0 || cfg_ready) $fatal(1,"MR invalidate proof/priority");
car=1;@(negedge clk);car=0;
@(posedge clk);while(!cfg_ready) @(posedge clk);
@(negedge clk);pv=0;
while(!cfg_response_valid) @(negedge clk);
if(cfg_response_error!=0 || cfg_response_key!=8) $fatal(1,"PTE invalidate proof");
par=1;@(negedge clk);par=0;repeat(4) @(negedge clk);
if(!quiet || !dma_drained) $fatal(1,"configuration did not drain");
''')

    def test_mr_and_pte_transactions_and_responses_are_mutually_exclusive(self):
        self.run_body('''
admission_pause=1;
@(negedge clk);ci=3;cp=17;cf=7;cc=1;ck=0;cv=1;car=0;
pc=1;pi=3;pk=11;pp=0;pa=pcie_dma_page(0);pv=1;par=0;
@(posedge clk);while(!cr) @(posedge clk);
if(cfg_ready) $fatal(1,"MR and PTE captured simultaneously");
@(negedge clk);cv=0;
while(!cav) begin @(negedge clk);if(cfg_ready) $fatal(1,"PTE entered captured MR pipeline");end
if(ce!=0 || cak!=11 || cfg_ready) $fatal(1,"MR response not owned");
repeat(7) begin @(negedge clk);if(cfg_ready) $fatal(1,"PTE bypassed MR response backpressure");end
car=1;@(negedge clk);car=0;
@(posedge clk);while(!cfg_ready) @(posedge clk);
@(negedge clk);pv=0;qv=1;
while(!cfg_response_valid) begin @(negedge clk);if(qr || cr) $fatal(1,"QP/MR bypassed PTE pipeline");end
if(cfg_response_error!=0 || cfg_response_key!=11) $fatal(1,"PTE BEGIN failed");
repeat(7) begin @(negedge clk);if(qr || cr || quiet) $fatal(1,"PTE response did not retain global ownership");end
par=1;@(negedge clk);par=0;
@(posedge clk);while(!qr) @(posedge clk);
@(negedge clk);qv=0;while(!qready) @(negedge clk);
admission_pause=0;send_frame(0,FRAME_WORDS);allow();
''')

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        if after!=cls.before:raise RuntimeError('composite control test inputs changed')
        if name:=os.environ.get('AS02_RNIC_PAGED_RESPONDER_UNIT_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            report=dict(scope='Actual composite/MR/PTE/DMA/RAM and EXPLICIT transport stub; descriptor engine MODEL',
                pass_test=len(cls.reports)==3,method_count=3,transport_stub=True,actual_hls=False,
                hardware_verified=False,board_integrated=False,completion_claim=False,tests=cls.reports,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
