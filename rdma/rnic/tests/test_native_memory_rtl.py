# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual coherent SQ/SAME-MR + shared payload PTE/RAM/router/mux/PCIe.

Actual C/UBSan WQEs and original production paths. HLS is explicitly STUBBED;
local transport/executor/WR-CQ lifetime, physical host/link/MAC are MODELS.
Local memory DMA is real RTL, NOT actual RDMA completion/pins/verbs/runtime.
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

ROOT=memory.ROOT


class NativeMemoryTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):shared.SharedMRResponderRTLTests.setUpClass.__func__(cls)

    def simulate(self,placement):
        words=memory.sq.local.fixture.packet();tb=memory.make_tb(words,placement)
        paths=sq.input_paths(tb)+[Path(__file__).resolve(),Path(memory.__file__).resolve(),memory.ARBITER]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        records=[]
        for i in range(2):
            w=shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=2 if placement else 1,flags=1,length=65)
            data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0)
            self.assertEqual(bytes(data),shared.codec.oracle(w));records.append(bytes(data))
        with tempfile.TemporaryDirectory(prefix='as02-native-memory-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(shared.protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
            (p/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),*map(str,memory.sq.portable.sources())],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            vvp=(p/'test.vvp').read_text()
            names=['rocev2_native_sq_endpoint','rocev2_native_endpoint','rocev2_memory_client_arbiter',
                'rocev2_mr_table','rocev2_mr_page_table','rocev2_paged_memory_backend','rocev2_dma_client_router',
                'rocev2_sq_fetch','rocev2_pcie_parent_guard']
            counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
            self.assertTrue(all(v==1 for v in counts.values()),counts)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[21:])for l in r.stdout.splitlines()if l.startswith('NATIVE_MEMORY_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(rows[0]['payload_bytes_checked'],65);self.assertEqual(rows[0]['local_memory_operations'],1)
            self.assertEqual(rows[0]['physical_descriptors'],4 if placement else 3)
            self.assertEqual(rows[0]['read_tlps'],2 if placement else 3)
            self.assertEqual(rows[0]['write_tlps'],2 if placement else 0);self.assertEqual(rows[0]['fences'],int(placement))
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],actual_elaborated_module_counts=counts,
            source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            local_transport_executor_CQ_lifetime_model=True,local_RDMA_completion=False)

    def test_actual_authorized_SQ_WRITE_source_reads_same_registered_scattered_host_pages(self):self.simulate(False)
    def test_actual_authorized_SQ_READ_destination_placement_uses_same_pages_and_visibility_fence(self):self.simulate(True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_NATIVE_MEMORY_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            result=dict(scope=__doc__,pass_test=len(cls.reports)==2,methods=len(cls.reports),tests=cls.reports,
                actual_C_UBSan_codec=True,actual_single_MR_PTE_payload_backend=True,
                actual_coherent_SQ_generic_PCIe=True,local_transport_executor_CQ_lifetime_model=True,
                HLS_transport_stub=True,actual_RDMA_completion=False,actual_kernel_pins=False,
                board_integrated=False,hardware_verified=False,standard_verbs=False)
            with p.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':unittest.main()
