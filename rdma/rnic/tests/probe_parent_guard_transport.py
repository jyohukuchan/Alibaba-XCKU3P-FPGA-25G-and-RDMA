#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run existing full native-control/PCIe assertions with real parent-proof RTL.

Only replace the testbench's public drain expression, not DUT state or any
permission/integrity check. Model counters remain independent assertions but
are no longer inputs to drain proof. Actual patched parent hierarchy has a
separate elaboration gate; this test is NOT full-board/parent simulation.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys

import probe_native_control as native

ROOT=native.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_pcie_parent_guard.v'
ORIGINAL_SIMULATE=native.simulate
GUARD=r'''
wire actual_parent_drained,actual_parent_fault;
rocev2_pcie_parent_guard #(.SEG_COUNT(2),.COUNT_WIDTH(16)) actual_parent_guard (
 .clk(clk),.rst(rst),.rd_busy(tlp_status_rd_busy),.wr_busy(tlp_status_wr_busy),
 .rd_desc_valid(eng_m_dma_read_valid),.rd_desc_ready(eng_m_dma_read_ready),
 .wr_desc_valid(eng_m_dma_write_valid),.wr_desc_ready(eng_m_dma_write_ready),
 .rd_status_valid(eng_s_dma_read_status_valid),.rd_status_error(eng_s_dma_read_status_error),
 .wr_status_valid(eng_s_dma_write_status_valid),.wr_status_error(eng_s_dma_write_status_error),
 .ram_wr_cmd_valid(eng_dma_ram_wr_cmd_valid),.ram_wr_cmd_ready(eng_dma_ram_wr_cmd_ready),.ram_wr_done(eng_dma_ram_wr_done),
 .ram_rd_cmd_valid(eng_dma_ram_rd_cmd_valid),.ram_rd_cmd_ready(eng_dma_ram_rd_cmd_ready),
 .ram_rd_resp_valid(eng_dma_ram_rd_resp_valid),.ram_rd_resp_ready(eng_dma_ram_rd_resp_ready),
 .tlp_activity(tlp_tx_rd_req_tlp_valid || tlp_tx_wr_req_tlp_valid || tlp_rx_cpl_tlp_valid),
 .error_event(tlp_status_error_cor || tlp_status_error_uncor),
 .drained(actual_parent_drained),.fault(actual_parent_fault),.fault_code()
);
// All actual mux stages/leaf RAM offers are required. No host-model integer
// read_outstanding/write_outstanding/posted_bytes participates in the proof.
assign parent_dma_drained=actual_parent_drained && !actual_parent_fault &&
 !m_dma_read_valid && !m_dma_write_valid && !mid_m_dma_read_valid && !mid_m_dma_write_valid &&
 !s_dma_read_status_valid && !s_dma_write_status_valid &&
 !mid_s_dma_read_status_valid && !mid_s_dma_write_status_valid &&
 !(|dma_ram_wr_cmd_valid) && !(|dma_ram_wr_done) &&
 !(|dma_ram_rd_cmd_valid) && !(|dma_ram_rd_resp_valid);
always @(posedge clk) if(!rst && sv && sr) begin
 if(se!=0 && !actual_parent_fault)$fatal(1,"actual PCIe error did not latch parent ownership fault");
 if(se==0 && actual_parent_fault)$fatal(1,"normal operation crossed parent ownership fault");
 $display("PARENT_GUARD_STATUS fault%0d error%0d",actual_parent_fault,se);
end
'''


def simulate(tb,fixtures,hls_build,wall_timeout=240):
    sources=[RTL,Path(__file__).resolve()]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    tb,n=re.subn(r'assign parent_dma_drained=.*?;',GUARD,tb,count=1,flags=re.S)
    if n!=1:raise ValueError('unreviewed testbench parent-proof layout')
    tb='`include "'+str(RTL)+'"\n'+tb
    output,identity=ORIGINAL_SIMULATE(tb,fixtures,hls_build,wall_timeout=wall_timeout)
    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    if before!=after:raise ValueError('parent proof inputs changed')
    identity['source_sha256'].update(after)
    identity.update(actual_parent_proof_RTL=True,parent_proof_uses_host_model_counters=False,
        actual_patched_parent_hierarchy_simulated=False,
        generated_testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
        parent_proof_scope=__doc__)
    return output,identity


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--parent-error',choices=['read','fence'])
    args,remaining=parser.parse_known_args()
    sys.argv=[sys.argv[0],*remaining]
    if args.parent_error:
        sys.argv+=['--completion-error',args.parent_error]
        native.pcie.simulate=simulate
        native.pcie.main()
    else:
        native.simulate=simulate
        native.main()


if __name__=='__main__':main()
