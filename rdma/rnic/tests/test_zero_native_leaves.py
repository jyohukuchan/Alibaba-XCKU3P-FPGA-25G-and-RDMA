#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual zero-native admission/executor/RX/lifetime/CQ leaves, four-state.

Reuse ALL prior Atomic128 cases against this new exact checked RTL, then add
zero/no-MR/no-DMA/response-token/owner/real-framer/CQ cases. Adjacent endpoints
remain explicit models: this is NOT generated-HLS/full-native/Linux runtime.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import test_atomic128_admission_rtl as admit
import test_atomic128_executor_rtl as execute
import test_atomic128_response_rtl as response
import test_atomic128_lifetime_rtl as life
import test_atomic128_cq_rtl as cq
import test_wqe_read_unpad_rtl as unpad
import test_zero_wqe as codec
import derive_zero_native as source

ROOT=source.ROOT;digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
OUT=source.derive()


def zero_owner(op=2,**changes):
    fields=dict(length=0,lkey=0,address=0,offset=0,
        remote=(1<<64)-1 if op in [1,2,6]else 0,rkey=0xfedcba98 if op in [1,2,6]else 0)
    fields.update(changes)
    return response.owner(op,immediate=0x89abcdef if op in [5,6]else 0,**fields)


def zero_response(read=True,syndrome=0x1f):
    # Legacy host READ encoding deliberately refuses empty payloads. Build
    # the real zero READ response from a complete four-byte AETH ACK, then
    # independently recompute actual IP/UDP lengths, checksum and ICRC.
    p=bytearray(response.old.packet(write=True,length=1,syndrome=syndrome))
    p[28]=0x10 if read else 0x11
    return response.old.repair(p)


def renamed(names):
    result={source.RTL/(n+'.v'):OUT[source.RTL/(n+'.v')]for n in names}
    for p,t in result.items():
        for n in names:t=re.sub(r'\b'+n+r'\b','rocev2_atomic128_'+n.removeprefix('rocev2_'),t)
        result[p]=t
    return result


def use_actual(module,names,single=False):
    facade=SimpleNamespace(**vars(module.source));derived=renamed(names)
    facade.derive=(lambda:next(iter(derived.values())))if single else(lambda:derived)
    if module is cq:facade.cq=lambda:OUT[source.RTL/'rocev2_cq_mmio.v']
    module.source=facade


use_actual(admit,['rocev2_wqe_admission','rocev2_sq_wqe_admission','rocev2_wqe_hls_sq'])
use_actual(execute,['rocev2_wqe_memory_executor'],True)
use_actual(response,['rocev2_wqe_response_guard'],True)
use_actual(life,life.source.NAMES)
use_actual(cq,['rocev2_cq_mmio'])


class ZeroAdmission(admit.Atomic128AdmissionTests):
    reports={}
    @classmethod
    def setUpClass(cls):codec.ZeroWQETests.setUpClass.__func__(cls)

    def zero_entry(self,op=2,error=0,mutate=None):
        w=codec.ZeroWQETests.zero(op);b=w.base;record=(C.c_uint8*128)()
        self.assertEqual(self.lib.as02_zero_wqe_encode(record,C.byref(w)),0)
        record=bytearray(record)
        if mutate:mutate(record)
        good=not error;original=admit.old.original
        values=[(64,b.wr_id),(64,original.SEQ),(64,original.EPOCH),(24,1),(16,7),(16,0xf123),
            (16,b.opcode if good else 0),(16,b.flags if good else 0),(32,0),(32,0),(64,0),(64,0),
            (64,b.remote_address if good else 0),(32,b.remote_key if good else 0),(8,error)]
        return f'''expected_cmp=0;expected_arg=0;expected_imm=32'h{b.immediate:08x};
issue(1024'h{int.from_bytes(record,'little'):0256x},128'hffffffffffffffffffffffffffffffff,1'b1,1'b1,
24'd1,16'd7,16'hf123,64'h{original.SEQ:x},64'h{original.EPOCH:x},
576'h{original.packed(values):0144x},0,7,9,11,1'b1,8'd0);
'''

    def test_zero_five_operations_have_actual_queue_owner_but_NO_MR_query(self):
        self.simulate(''.join(self.zero_entry(op)for op in [1,2,3,5,6]))

    def test_zero_never_licenses_local_address_key_Atomic_or_posted_RECV(self):
        self.simulate(''.join(self.zero_entry(op,error=0x26,mutate=lambda b,o=o:b.__setitem__(o,1))
            for op in [1,2,3,5,6]for o in [16,23,36,39]))
        self.simulate(self.zero_entry(4,error=0x26),receive_only=True)
        self.simulate(self.entry(admit.candidate(7),error=0x26,queries=0,mutate=lambda b:b.__setitem__(32,0)))


class ZeroExecutor(execute.Atomic128ExecutorTests):
    reports={}
    def test_zero_no_DMA_or_status_and_guarded_event_for_all_five_operations(self):
        for op in [1,2,3,5,6]:
            body=f'owner({zero_owner(op)});'
            if op==2:body+='repeat(19)begin @(negedge clk);if(m_memory_event_valid || !busy || fault)$fatal(1,"zero READ assumed response");end response();'
            body+='repeat(19)begin @(negedge clk);if(!m_memory_event_valid || m_memory_command_valid || command_count || memory_status_count || !busy || fault)$fatal(1,"zero memory owner or no-DMA event");end handoff();'
            self.simulate(body,length=0)

    def test_zero_rejects_even_exact_raw_command_without_DMA_or_status(self):
        for op in [1,2]:
            port='write'if op==2 else'read'
            self.simulate(f'owner({zero_owner(op)});'+('response();'if op==2 else'')+
                f's_hls_{port}_command={execute.old.raw_command(address=0,length=0)};s_hls_{port}_command_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h82 || m_memory_command_valid || command_count || memory_status_count || queue_guard!==8'hff)
 $fatal(1,"zero raw command invented DMA authority");
''',length=0)

    def test_zero_rejects_fabricated_data_and_status_and_missing_downstream_guard(self):
        for inject,code in [('s_axis_hls_write_tvalid=1;',0x85),('s_memory_status_valid=1;',0x86),
                ('m_memory_event_ready=1;',0x87)]:
            self.simulate(f'owner({zero_owner(1)});'+inject+f'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h{code:02x} || !busy || queue_guard!==8'hff || command_count || memory_status_count)
 $fatal(1,"zero fabricated completion released owner");
''',length=0)

    def test_zero_READ_mismatched_protected_token_cannot_retire(self):
        n=int(zero_owner().split("'h")[1],16)
        self.simulate(f'owner({zero_owner()});s_read_response_context=748\'h{n^(1<<396):0187x};s_read_response_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h83 || m_memory_event_valid || s_read_response_ready || !busy || queue_guard!==8'hff)
 $fatal(1,"wrong zero READ response token retired");
''',length=0)


class ZeroResponse(response.Atomic128ResponseTests):
    reports={}
    def test_zero_five_real_ACK_or_AETH_frames_with_token_before_HLS(self):
        for op in [1,2,3,5,6]:
            pkt=zero_response(read=op==2)
            body=f'expect_owner({zero_owner(op)});send(PACKET0);'+('token();'if op==2 else'')
            body+=f"forward(PACKET0,8'h{16 if op==2 else 17:02x},8'h1f);"
            body+=f'if(tokens!={int(op==2)} || events!=1)$fatal(1,"zero response owner/token count");'
            self.simulate([pkt],body)

    def test_zero_nonempty_wrongclass_and_negative_AETH_cannot_supply_token(self):
        packets=[response.old.packet(write=False,length=1),zero_response(read=False),
            zero_response(syndrome=0x60)]
        body=f'expect_owner({zero_owner()});'
        for i in range(3):body+=f'send(PACKET{i});reject();'
        body+='if(tokens || events || accepted_count)$fatal(1,"invalid zero READ gained authority");send(PACKET3);token();forward(PACKET3,8\'h10,8\'h1f);'
        self.simulate(packets+[zero_response()],body)


class ZeroCQ(cq.Atomic128CQTests):
    reports={}
    def test_zero_tickets_keep_full_owner_commit_retire_and_host_ACK(self):
        t=cq.bench();a=t.index('notification=0;notification_flags=0;\npublish(')
        b=t.index('\n if(pub_published!=4',a)
        body='notification=0;notification_flags=0;\n'+''.join(
            f'publish({zero_owner(op,pd=17,sequence=i,tag=i)},0,{i},0);\n'for i,op in enumerate([1,2,3,5,6],1))
        t=t[:a]+body+t[b:];t=t.replace('pub_published!=4 || pub_acked!=4','pub_published!=5 || pub_acked!=5')
        self.simulate(t)


class ZeroUnpad(unittest.TestCase):
    reports={}
    def simulate(self,body):
        t=unpad.bench(body).replace('[587:0]','[747:0]')
        run=Path(tempfile.mkdtemp(prefix='zero-unpad-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t);(run/'unpad.v').write_text(OUT[source.RTL/'rocev2_wqe_read_unpad.v'])
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(run/'unpad.v')],capture_output=True,text=True,timeout=20)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(directory=str(run.relative_to(ROOT)),
            artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}))

    def test_protected_zero_token_has_no_padding_or_command_and_keeps_executor_guard(self):
        self.simulate(f'capture({zero_owner()});'+r'''
repeat(11)@(negedge clk);if(busy || queue_guard || fault || m_command_valid || m_axis_tvalid || context_count!=1 || command_count || discarded_padding_bytes || downstream_queue_guard!==8'h80)
 $fatal(1,"zero unpad invented data or ended downstream owner");
''')

    def test_zero_command_or_data_is_rejected_before_any_output(self):
        for inject,code in [(f's_command={execute.old.raw_command(address=0,length=0)};s_command_valid=1;',0xa2),
                ('s_axis_tvalid=1;s_axis_tkeep=0;s_axis_tlast=1;',0xa3)]:
            self.simulate(f'capture({zero_owner()});'+inject+f'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h{code:02x} || m_command_valid || m_axis_tvalid || command_count || queue_guard!==8'hff)
 $fatal(1,"zero pad adapter fabricated command/data");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    inputs=list(dict.fromkeys([*OUT,*[Path(m.__file__).resolve()for m in list(sys.modules.values())
        if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]]))
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
    run=Path(tempfile.mkdtemp(prefix='zero-native-leaves-',dir=ROOT/'rdma/rnic/build'))
    for n in ['sources','RTL']:(run/n).mkdir()
    for f in inputs:
        target=run/'sources'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    for f,t in OUT.items():(run/'RTL'/f.name).write_text(t)
    classes=[ZeroAdmission,ZeroExecutor,ZeroResponse,life.Atomic128LifetimeTests,ZeroCQ,ZeroUnpad]
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in classes))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed during leaf tests')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,directory=str(run.relative_to(ROOT)),four_state=True,
        tests={c.__name__:c.reports for c in classes},
        simulations=sum(sum(map(len,c.reports.values()))for c in classes),
        frozen_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()},
        actual_generated_HLS_or_full_native_runtime=False,actual_Linux_or_hardware=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
