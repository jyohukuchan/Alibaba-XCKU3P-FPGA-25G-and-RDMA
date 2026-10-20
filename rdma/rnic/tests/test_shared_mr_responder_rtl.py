# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C WQE + actual responder/parser/ICRC + ONE actual MR table.

Fast units explicitly stub ONLY the HLS transport. The separately invokable
probe uses the same constructed fixture with actual immutable generated HLS.
Host SQ fetch/PCIe/local executor/CQE/verbs are not implemented or modeled as
successful hardware. The downstream local lease is an explicit fixture owner.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import shared_mr_fixture as fixture
import test_protected_responder_rtl as protected
import test_wqe_codec as codec

ROOT=fixture.probe.ROOT
SOURCES=[ROOT/'rdma/rnic/rtl'/n for n in [
    'rocev2_protected_responder.v','rocev2_mr_table.v','rocev2_mr_query_arbiter.v','rocev2_wqe_admission.v']]
SOURCES += [ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
SOURCES += [ROOT/'external/corundum/fpga/lib/axis/rtl'/n for n in ['axis_register.v','axis_fifo.v']]


class SharedMRResponderRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-shared-mr-codec-')
        cls.path=Path(cls.directory.name)
        c=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(codec.KERNEL),
            str(codec.KERNEL/'wqe.c'),'-o',str(cls.path/'wqe.so')],capture_output=True,text=True,timeout=30)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        cls.lib=C.CDLL(str(cls.path/'wqe.so'))
        cls.lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(codec.WQE)]
        cls.lib.as02_wqe_encode.restype=C.c_int

    def record(self,**values):
        fields=dict(local_address=fixture.probe.VA+0x210,local_key=16,
                    remote_address=0xf123456789abc001,remote_key=0,length=65)
        fields.update(values);w=codec.candidate(**fields)
        output=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(output,C.byref(w)),0)
        self.assertEqual(bytes(output),codec.oracle(w))
        return f"512'h{int.from_bytes(output,'little'):0128x}",w

    def local(self,*,error=0,**values):
        record,w=self.record(**values)
        return (f"offer_local({record});expect_local(8'd{error},64'h{w.local_address:x},"
                f"64'h{(w.local_address-fixture.probe.VA)&codec.U64:x},32'h{w.local_key:x},32'd{w.length});")

    def namespace_case(self):
        fixtures,body,cases=fixture.probe.stimulus()
        body += [self.local(opcode=1),self.local(opcode=2),self.local(local_key=8,error=1),
                 self.local(local_key=0,error=1),self.local(local_key=0x80000010,error=1),
                 'local_pd=18;',self.local(error=2),'local_pd=17;',
                 self.local(local_key=10,opcode=2,error=3),self.local(local_key=10,opcode=1),
                 self.local(local_address=fixture.probe.VA-1,error=4),
                 self.local(local_address=(fixture.probe.VA+0x210)&((1<<48)-1),error=4),
                 self.local(local_address=fixture.probe.VA+4095,error=4),
                 'if(local_results!=11 || local_queries!=11 || local_leases!=0)$fatal(1,"local namespace count mismatch");']
        return fixtures,'\n'.join(body),cases

    def lease_case(self):
        fixtures=fixture.packet()
        record,w=self.record(local_key=8)
        body=f'''
// Exercise one real incoming operation before the separate local owner.
send_frame(0,{len(fixtures)});allow();
// Management OFFER and every accepted/held-response phase take precedence.
// Register an independent slot; the WQE still uses the same live slot0/key8.
@(negedge clk);ci=3;cp=17;cf=7;cc=1;ck=0;cv=1;car=0;local_data={record};local_valid=1;
#1;if(local_input_ready || local_guard)$fatal(1,"WQE overtook management offer");
@(posedge clk);while(!cr)@(posedge clk);
@(negedge clk);cv=0;
while(!cav)begin
 if(local_input_ready || local_busy || local_guard)$fatal(1,"WQE admitted during accepted management");
 @(negedge clk);
end
if(ce!==0 || cak!==11)$fatal(1,"independent MR registration failed");
repeat(9)begin @(negedge clk);if(local_input_ready || local_guard || local_busy)$fatal(1,"WQE bypassed held management response");end
car=1;@(posedge clk);@(negedge clk);car=0;
@(posedge clk);while(!local_input_ready)@(posedge clk);
@(negedge clk);local_valid=0;local_data=0;
expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
// An offered management pause takes priority before WQE admission.
@(negedge clk);admission_pause=1;local_data={record};local_valid=1;
repeat(9)begin @(negedge clk);if(local_input_ready || local_guard || local_busy)$fatal(1,"WQE bypassed management pause");end
local_valid=0;admission_pause=0;retain_local_lease=1;
{self.local(local_key=8)}
retain_local_lease=0;
if(local_busy || !executor_guard || quiet || cr)$fatal(1,"lookup completion mistaken for lifetime drain");
@(negedge clk);ci=0;cp=17;cc=2;ck=8;cv=1;car=0;
repeat(12)begin @(negedge clk);if(cr || cav || quiet)$fatal(1,"revoke overtook downstream lease");end
release_local_lease();
@(posedge clk);while(!cr)@(posedge clk);
@(negedge clk);cv=0;while(!cav)@(negedge clk);
if(ce!==0 || cak!==0)$fatal(1,"deferred revoke failed");
car=1;@(negedge clk);car=0;configure_mr(0,17,7,16);
{self.local(local_key=8,error=1)}
{self.local(local_key=16)}
if(local_results!=4 || local_queries!=4 || local_leases!=1 || executor_guard)$fatal(1,"lease/rekey count mismatch");
'''
        return fixtures,body,[]

    def overlap_case(self):
        fixtures=fixture.packet()
        record,w=self.record(local_key=8)
        body=f'''
local_allow_response=0;offer_local({record});
expiry=cycle+100;while(!lrv && cycle<expiry)@(negedge clk);
if(!lrv || !local_busy || quiet || cr)$fatal(1,"shared local response not held");
// Incoming parser may collect a packet while the other MR client stalls.
send_frame(0,{len(fixtures)});
repeat(120)begin @(negedge clk);if(accepted || commands || !lrv || quiet || cr)$fatal(1,"remote bypassed stalled MR owner");end
local_enable=0;admission_pause=1;local_allow_response=1;
expiry=cycle+100;while(!local_work_valid && cycle<expiry)@(negedge clk);
if(!local_work_valid)$fatal(1,"accepted WQE cancelled by pause/disable");
// Lookup has retired, but work result ownership still excludes management;
// the independent remote lookup and memory operation must now make progress.
expiry=cycle+2000;while(completed==0 && cycle<expiry)@(negedge clk);
if(completed!=1 || commands!=1 || !local_work_valid || quiet || cr)$fatal(1,"shared clients deadlocked or released local owner");
expect_local(0,64'h{w.local_address:x},64'h210,32'd8,32'd65);
local_enable=1;admission_pause=0;repeat(3)@(negedge clk);
if(!quiet || !cr || local_busy || executor_guard || local_results!=1 || local_queries!=1)$fatal(1,"shared clients failed to return idle");
'''
        return fixtures,body,[]

    def simulate(self,case):
        fixtures,body,_=case
        tb=fixture.make_tb(fixtures,body)
        self.assertNotIn('force ',tb)
        own=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(protected.__file__).resolve(),
             Path(codec.__file__).resolve(),codec.KERNEL/'wqe.c',codec.KERNEL/'wqe.h',
             Path(fixture.probe.__file__).resolve(),ROOT/'rdma/rtl/rocev2_integrity_transport.v']
        own += [ROOT/n for n in ['rdma/host/rocev2_wire.py','rdma/read/host/read_wire.py','rdma/tests/test_icrc_rtl.py']]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in SOURCES+own}
        with tempfile.TemporaryDirectory(prefix='as02-shared-mr-unit-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(protected.stub_source())
            (p/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),
                              *map(str,SOURCES)],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line[7:])for line in r.stdout.splitlines()if line.startswith('RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            local_rows=[json.loads(line[13:])for line in r.stdout.splitlines()if line.startswith('LOCAL_RESULT ')]
            self.assertEqual(len(local_rows),1,r.stdout)
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports[self._testMethodName]=dict(summary=rows[0],local_summary=local_rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            fixture_sha256=hashlib.sha256(''.join(f'{v:x}\n'for v in fixtures).encode()).hexdigest())

    def test_local_and_incoming_share_same_keys_PD_permissions_ranges_and_rekey(self):self.simulate(self.namespace_case())
    def test_downstream_owner_blocks_revoke_after_local_lookup_and_work_handoff(self):self.simulate(self.lease_case())
    def test_stalled_local_response_then_result_allows_remote_progress_without_configuration(self):self.simulate(self.overlap_case())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        if name:=os.environ.get('AS02_RNIC_SHARED_MR_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            result=dict(scope=__doc__,pass_test=len(cls.reports)==3,methods=len(cls.reports),tests=cls.reports,
                actual_C_codec=True,actual_single_MR_table=True,actual_local_WQE_frontend=True,
                actual_protected_parser_integrity_and_lease=True,transport_stub=True,
                downstream_local_executor_lease_model=True,native_host_queue_DMA=False,
                actual_PCIe_or_pinned_pages=False,standard_verbs_implemented=False,hardware_verified=False)
            with p.open('x')as f:json.dump(result,f,indent=2);f.write('\n')


if __name__=='__main__':unittest.main()
