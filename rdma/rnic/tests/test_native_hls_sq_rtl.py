# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual coherent SQ/native SAME-MR -> guarded owner ->248-bit HLS SQ.

Transport is explicitly STUBBED and executor/HLS-SQ receiver/WR-CQ lifetime
are MODELS. No local memory/ACK/wire/CQ execution or hardware claim.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import native_memory_fixture as memory
import test_native_sq_rtl as sq
import test_shared_mr_responder_rtl as shared
from test_wqe_hls_sq_rtl import context,expected_sq

ROOT=memory.ROOT
ADAPTER=ROOT/'rdma/rnic/rtl/rocev2_wqe_hls_sq.v'


def bench(words,denied=False):
    ctx=context(id=0xf123456789abc001,sequence=1,epoch=0x9123456700000001,qpn=2,pd=17,tag=1,
        lkey=0 if denied else 8,address=0 if denied else 0xfedcba9876543210,offset=0 if denied else 0x210,
        remote=0 if denied else 0xf123456789abc001,opcode=0 if denied else 1,flags=0 if denied else 1,
        length=0 if denied else 65,error=1 if denied else 0,source=2 if denied else 0,authorized=not denied)
    expected=expected_sq(qpn=2,remote=0xf123456789abc001)
    body=memory.sq.prefix()
    if denied:
        body+=r'''
host_stage(5,OWNER0,0,8,0,0,0,0);extra_invalidate_completed=0;
sq_stage(2,1);enable=1;sq_hold_cycles=160;sq_bell();
sq_deadline=cycle+1000;while(!sq_queue_guard[2] && cycle<sq_deadline)@(negedge clk);
if(!sq_queue_guard[2])$fatal(1,"no actual SQ fetch before revoke");
write_reg(AS02_CTL_DOORBELL,1,15,0,1);sq_collect(0,0,0);collect_native(5,OWNER0,0,8,3);
'''
    else:body+='enable=1;sq_command(2,1,0,0,0);\n'
    body+=f'''
sq_deadline=cycle+5000;while(!m_executor_context_valid && cycle<sq_deadline)@(negedge clk);
if(!m_executor_context_valid || m_executor_context!=={ctx} || m_hls_sq_tvalid ||
 sq_submission_guard!==8'h04 || sq_submission_busy!==1 || sq_work_results!=1 || sq_submission_fault ||
 m_work_valid || admission_queue_guard || read_tlps!=1 || write_tlps)$fatal(1,"actual native authorized owner/early HLS metadata mismatch");
repeat(13)begin @(negedge clk);if(!m_executor_context_valid || m_executor_context!=={ctx} || quiet || config_safe || m_hls_sq_tvalid)$fatal(1,"held native owner escaped management");end
host_stage(8,405,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(20)begin @(negedge clk);if(!control_busy || !admission_pause || quiet || config_safe)$fatal(1,"native STOP ignored submission owner");end
// EXPLICIT modeled executor takes complete owner before HLS is allowed SQ.
executor_queue_guard=8'h04;m_executor_context_ready=1;@(posedge clk);@(negedge clk);m_executor_context_ready=0;
'''
    if denied:
        body+=r'''
repeat(17)begin @(negedge clk);if(m_hls_sq_tvalid || sq_submission_busy || sq_submission_guard || !control_busy || quiet)$fatal(1,"denied work became HLS SQ or false completed owner");end
'''
    else:
        body+=f'''
sq_deadline=cycle+100;while(!m_hls_sq_tvalid && cycle<sq_deadline)@(negedge clk);
if(!m_hls_sq_tvalid || m_hls_sq_tdata!=={expected} || sq_submission_owner_count!=1 || sq_submission_hls_count)$fatal(1,"native full per-WR248-bit SQ ABI");
enable=0;repeat(17)begin @(negedge clk);if(!m_hls_sq_tvalid || m_hls_sq_tdata!=={expected} || quiet || config_safe || !control_busy)$fatal(1,"stalled native SQ changed/released refs");end
m_hls_sq_tready=1;@(posedge clk);@(negedge clk);m_hls_sq_tready=0;
if(sq_submission_busy || sq_submission_guard || sq_submission_hls_count!=1 || executor_queue_guard!==8'h04 || quiet || config_safe)$fatal(1,"SQ acceptance mistaken for real WR completion");
'''
    body+=r'''
sq_command(3,1,35,0,0);
executor_queue_guard=0;collect_native(8,405,0,0,2);
sq_command(3,1,0,31,1);
if(!quiet || !config_safe || sq_submission_fault || sq_submission_owner_count!=1 || sq_control_owner_active ||
 sq_work_results!=1 || sq_fetch_count!=1 || router_descriptor_count!=1 || read_tlps!=1 || write_tlps || commands || completed || txframes || local_memory_busy)$fatal(1,"native submission final scope/drain");
check_ring();
$display("NATIVE_HLS_SQ_RESULT {\"pass_test\":true,\"actual_SQ_fetches\":%0d,\"owner_handoffs\":%0d,\"HLS_SQ_handoffs\":%0d,\"local_RDMA_execution\":false}",sq_fetch_count,sq_submission_owner_count,sq_submission_hls_count);
$finish;
'''
    tb=memory.enable_memory(memory.sq.make_tb(words,body))
    tb=memory.sq.once(tb,'#(.LOCAL_MEMORY_ENABLE(1)) dut(','#(.LOCAL_MEMORY_ENABLE(1),.HLS_SQ_ENABLE(1)) dut(')
    return f'`include "{ADAPTER}"\n'+tb


class NativeHlsSQTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def simulate(self,denied):
        words=memory.sq.local.fixture.packet();tb=bench(words,denied)
        paths=sq.input_paths(tb)+[Path(__file__).resolve(),Path(memory.__file__).resolve(),ADAPTER,ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=sq.NativeSQRTLTests.records(self)
        with tempfile.TemporaryDirectory(prefix='as02-native-hls-sq-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(shared.protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words));(p/'records.hex').write_text(''.join(f'{int.from_bytes(v,"little"):0128x}\n'for v in records))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            names=['rocev2_wqe_hls_sq','rocev2_native_sq_endpoint','rocev2_mr_table','rocev2_mr_page_table','rocev2_memory_client_arbiter','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[21:])for l in r.stdout.splitlines()if l.startswith('NATIVE_HLS_SQ_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(rows[0]['HLS_SQ_handoffs'],0 if denied else 1)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest())

    def test_actual_coherent_WQE_and_same_MR_precede_full248bit_HLS_SQ(self):self.simulate(False)
    def test_stale_key_after_inflight_revoke_goes_to_owner_but_never_HLS(self):self.simulate(True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_HLS_SQ_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==2,methods=len(cls.reports),tests=cls.reports,
                HLS_transport_stub=True,actual_native_SQ_MR_PTE_generic_PCIe=True,
                executor_HLS_receiver_CQ_owner_models=True,actual_local_RDMA_execution=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
