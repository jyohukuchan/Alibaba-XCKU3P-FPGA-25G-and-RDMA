# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native AXI/SQC1/SQ fetch/shared-MR/router/RAM/mux/generic PCIe.

Explicit HLS transport STUB, physical MAC/host/root/link and downstream
executor/CQ guards are MODELS. No constant drain/descriptor/RAM engine agents,
local payload execution, actual kernel pins/board/verbs or completion claim.
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

import native_sq_fixture as fixture
import test_shared_mr_responder_rtl as shared

ROOT=fixture.ROOT


def input_paths(tb):
    paths=fixture.portable.sources()+[Path(p)for p in re.findall(r'`include "([^\"]+)"',tb)]
    paths += [Path(m.__file__).resolve()for m in [fixture,fixture.native,fixture.native.dual,
        fixture.native.pcie,fixture.parent,fixture.local,fixture.portable,shared,shared.codec,
        shared.protected,fixture.native.pcie.controlled,fixture.native.pcie.controlled.registers,
        fixture.native.pcie.controlled.integration,fixture.native.pcie.controlled.integration.paged]]
    return list(dict.fromkeys(paths+[fixture.HEADER,fixture.native.HEADER,shared.codec.KERNEL/'wqe.c',
        shared.codec.KERNEL/'wqe.h',ROOT/'rdma/rtl/rocev2_integrity_transport.v',Path(__file__).resolve()]))


class NativeSQRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def records(self,key=8):
        out=[]
        for i in range(2):
            w=shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=key,remote_address=0xf123456789abc001,
                remote_key=0,opcode=1,flags=1,length=65)
            data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0)
            self.assertEqual(bytes(data),shared.codec.oracle(w));out.append(bytes(data))
        return out

    def simulate(self,body):
        words=fixture.local.fixture.packet();tb=fixture.make_tb(words,body)
        self.assertNotIn('force ',tb)
        paths=input_paths(tb);before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in self.records())
        with tempfile.TemporaryDirectory(prefix='as02-native-sq-unit-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
            (p/'records.hex').write_text(records);(p/'stub.v').write_text(shared.protected.stub_source())
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),
                              *map(str,fixture.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            names=['rocev2_native_sq_endpoint','rocev2_native_endpoint','rocev2_sq_wqe_admission',
                   'rocev2_sq_dma_fetch','rocev2_sq_fetch','rocev2_sq_control_regs','rocev2_dma_client_router',
                   'rocev2_mr_table','rocev2_mr_query_arbiter','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[17:])for l in r.stdout.splitlines()if l.startswith('NATIVE_SQ_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,
            source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            coherent_ring_input_sha256=hashlib.sha256(records.encode()).hexdigest())

    def test_real_coherent_SQ_native_decode_local_MR_and_downstream_lifetime(self):self.simulate(fixture.forward_body())
    def test_inflight_SQ_fetch_yields_to_MR_management_then_stale_key_is_denied(self):self.simulate(fixture.priority_body())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_SQ_UNIT_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            result=dict(scope=__doc__,pass_test=len(cls.reports)==2,methods=len(cls.reports),tests=cls.reports,
                actual_C_UBSan_codec=True,actual_SQC1_native_decode_and_SQ_fetch=True,
                actual_single_MR_PTE_and_shared_router_PCIe_parent_guard=True,
                HLS_transport_stub=True,actual_HLS_wire=False,constant_parent_proof_or_RAM_agents=False,
                actual_kernel_pins=False,local_payload_executor=False,native_CQ=False,standard_verbs=False,
                hardware_verified=False,board_integrated=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':unittest.main()
