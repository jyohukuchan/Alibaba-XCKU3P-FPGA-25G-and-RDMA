# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged READ/29-regression fixture with read-only fault diagnostics.

Only print real subfaults immediately before the existing fatal assertion.
No input, expected value, producer/status/MR/CQ event or deadline changes.
"""
import segmented_read_native_fixture as parent

ROOT=parent.ROOT;once=parent.once


def __getattr__(name):
    return getattr(parent,name)


def bench():
    original='if(fault)$fatal(1,"main native RNIC fault %h",fault_code);'
    return once(parent.bench(),original,r'''
if(fault)begin
 $display("NATIVE_ROUTE_FAULT msn=%b/%h raw_route=%b/%h/%h/%h/%h query=%b/%h guard=%b active=%b bad_event=%b",
  dut.msn_fault,dut.msn_fault_code,dut.msn_route_valid,dut.msn_route_qpn,dut.msn_route_peer_qpn,
  dut.msn_route_local_ip,dut.msn_route_peer_ip,dut.msn_query_valid,dut.msn_query_qpn,
  dut.msn_cfg_guard,dut.remote_msn.active,dut.remote_msn.bad_event);
 $display("NATIVE_SUBFAULTS native=%b/%h ex=%b/%h tx=%b/%h rx=%b/%h up=%b/%h hls=%b/%h cq=%b/%h rq=%b/%h recv_ack=%b/%h",
  dut.native_fault,dut.native_fault_code,dut.ex_fault,dut.ex_fault_code,dut.tx_fault,dut.tx_fault_code,
  dut.rx_fault,dut.rx_fault_code,dut.up_fault,dut.up_fault_code,dut.h_shared_hls_fault,dut.h_shared_hls_fault_code,
  dut.cq_fault,dut.cq_fault_code,dut.rq_fault,dut.rq_fault_code,dut.recv_ack_fault,dut.recv_ack_fault_code);
 if(fault)$fatal(1,"main native RNIC fault %h",fault_code);
end
''')
