# SPDX-License-Identifier: BSD-2-Clause-Views
"""Enabled real native/shared-MR/control graph; explicit HLS transport STUB.

Portable local authorization/management/fault checks, not HLS/wire/payload
execution proof. Generic PCIe/mux/parent guard are real RTL but no DMA traffic
is submitted. Physical host/MAC/AXI and downstream local lease are MODELS.
Actual-HLS native probes separately retain all-byte READ/WRITE wire evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import probe_native_shared_mr as enabled
import test_shared_mr_responder_rtl as shared

ROOT=enabled.ROOT


def sources():
    # Same portable support RTL as rw_sim.modules; the generated HLS and its
    # bridge are deliberately replaced by the EXPLICIT actual-port stub.
    paths=[ROOT/'rdma/rtl'/n for n in ['rocev2_write_engine.v','rocev2_pattern_source.v',
        'rocev2_ethernet_tx.v','rocev2_ipv4_icrc.v','rocev2_tx_padding.v','rocev2_tx_guard.v']]
    paths += [ROOT/'rdma/read/rtl'/n for n in ['rocev2_read_engine.v','rocev2_read_buffer.v',
        'rocev2_rw_control.v','rocev2_rw_ethernet_rx.v','rocev2_rw_endpoint.v']]
    paths += [ROOT/'external/corundum/fpga/lib/axis/rtl'/n for n in [
        'axis_fifo.v','axis_register.v','axis_adapter.v','axis_arb_mux.v','arbiter.v','priority_encoder.v']]
    paths += [ROOT/'external/corundum/fpga/lib/eth/rtl'/n for n in ['eth_axis_rx.v','eth_axis_tx.v','lfsr.v']]
    return paths+shared.SOURCES[:2]


class NativeSharedMRRTLTests(unittest.TestCase):
    reports={}
    record=shared.SharedMRResponderRTLTests.record
    local=shared.SharedMRResponderRTLTests.local

    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def test_same_local_namespace_and_actual_native_STOP_route_guard(self):
        body=r'''
host_api(8,301,0,0,0,0,0,0,0,2);
if(!config_safe)$fatal(1,"unit initial STOP unsafe");
write_reg(24'h401014,1,15,0,0);
if(ethernet_config_error)$fatal(1,"unit clean initial error");
host_api(7,302,0,0,0,0,0,0,0,0);
'''+enabled.local_setup(self)
        body+='retain_local_lease=1;'+self.local(local_key=8)+'retain_local_lease=0;\n'
        body+=r'''
host_stage(8,303,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(20)begin @(negedge clk);
 if(!control_busy || !admission_pause || config_safe || quiet || local_configuration_idle ||
  dut.datapath.responder.cfg_mr_valid || dut.datapath.responder.cfg_page_valid)$fatal(1,"unit native STOP escaped owner");
end
write_reg(24'h401010,1,15,0,0);
read_reg(24'h40100c,host_value);
if(host_value!==1 || !ethernet_config_error)$fatal(1,"unit retained owner permitted route commit");
read_reg(24'h401040,host_value);if(host_value!==32'hfbb97531)$fatal(1,"unit route changed");
release_local_lease();host_collect(8,303,0,0,2);
if(!config_safe || local_input_ready || local_configuration_idle)$fatal(1,"unit stopped route admitted WQE");
write_reg(24'h401014,1,15,0,0);host_api(7,304,0,0,0,0,0,0,0,0);
repeat(3)@(negedge clk);
if(!local_configuration_idle || !local_input_ready || !quiet || local_busy || executor_guard ||
 local_results!=11 || local_queries!=11 || local_leases!=1 || commands || completed || read_tlps || write_tlps)$fatal(1,"unit native namespace/ownership/count");
$display("LOCAL_UNIT_RESULT {\"pass_test\":true,\"queries\":%0d,\"results\":%0d,\"modeled_leases\":%0d,\"native_DMA_operations\":0}",local_queries,local_results,local_leases);
$finish;
'''
        self.simulate(enabled.fixture.packet(),body,'LOCAL_UNIT_RESULT')

    def test_outer_MAC_fault_blocks_new_work_but_preserves_accepted_result_and_lease(self):
        fixtures,body,_,_=enabled.outer_fault_case(self)
        self.simulate(fixtures,body,'NATIVE_FAULT_RESULT')

    def simulate(self,fixtures,body,prefix):
        tb=enabled.bench(fixtures,body);self.assertNotIn('force ',tb)
        paths=sources()+[Path(p)for p in re.findall(r'`include "([^\"]+)"',tb)]
        paths += [Path(m.__file__).resolve()for m in [enabled,enabled.native,enabled.native.dual,
            enabled.parent,enabled.native.pcie,enabled.native.pcie.controlled,
            enabled.native.pcie.controlled.registers,enabled.native.pcie.controlled.integration,
            enabled.native.pcie.controlled.integration.paged,shared,shared.codec,shared.protected,
            enabled.fixture,enabled.fixture.probe]]
        paths += [Path(__file__).resolve(),shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',
            ROOT/'rdma/rtl/rocev2_integrity_transport.v',enabled.native.HEADER,
            enabled.native.pcie.controlled.registers.HEADER]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-native-shared-stub-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(shared.protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),
                              *map(str,sources())],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in [
                'rocev2_mr_table','rocev2_mr_query_arbiter','rocev2_native_endpoint',
                'rocev2_dual_ethernet_endpoint','rocev2_pcie_parent_guard']}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[len(prefix)+1:])for l in r.stdout.splitlines()if l.startswith(prefix+' ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,
            source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            input_sha256=hashlib.sha256(''.join(f'{v:x}\n'for v in fixtures).encode()).hexdigest())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_SHARED_UNIT_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            result=dict(scope=__doc__,pass_test=len(cls.reports)==2,methods=len(cls.reports),tests=cls.reports,
                actual_C_UBSan_codec=True,actual_native_control_shared_MR=True,HLS_transport_stub=True,
                actual_HLS_or_wire=False,native_host_SQ=False,local_payload_executor=False,native_CQ=False,
                kernel_runtime=False,hardware_verified=False,board_integrated=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':unittest.main()
