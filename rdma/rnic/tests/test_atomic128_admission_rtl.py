# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C128 WQE -> actual SQ-result bridge/local-MR table, four-state.

Raw SQ-result source and downstream work consumer are modeled, NOT PCIe DMA,
Atomic HLS/ACK/result/CQ/API or unpin evidence. No invented MR responses:
negative protocol tests corrupt only the real table's external reply ports.
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
import unittest
import test_atomic_wqe as codec
import test_sq_wqe_admission_rtl as old

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_admission as source


def bench(body,receive_only=False):
    t=old.bench(body)
    t=source.once(t,'rocev2_sq_wqe_admission dut(',
        f'rocev2_atomic128_sq_wqe_admission #(.SEND_ENABLE(1),.IMMEDIATE_ENABLE(1),.RECV_ENABLE(1),.RECV_ONLY({int(receive_only)})) dut(')
    t=source.once(t,'reg [511:0] wd=0;reg [63:0] wk=0;','reg [1023:0] wd=0;reg [127:0] wk=0;')
    t=source.once(t,'input [511:0] data;input [63:0] keep;','input [1023:0] data;input [127:0] keep;')
    t=t.replace('{512{', '{1024{')
    t=source.once(t,'.m_work_remote_key(ork),',
        '.m_work_remote_key(ork),.m_work_immediate(oimm),.m_work_compare(ocmp),.m_work_swap_add(oarg),')
    t=source.once(t,'reg clk=0;',EXTRA+'\nreg clk=0;')
    return t


EXTRA=r'''
wire [31:0] oimm;wire [63:0] ocmp,oarg;
reg [31:0] expected_imm=0;reg [63:0] expected_cmp=0,expected_arg=0;
reg [2:0] expected_mr_op=1;
reg operand_stalled=0;reg [159:0] held_operands;
always @(posedge clk)if(!rst)begin
 if(qv && qr && allow_q && qop!==expected_mr_op)$fatal(1,"Atomic result was not authorized as local write");
 if(ov && {ocmp,oarg,oimm}!==(oe ? 160'd0:{expected_cmp,expected_arg,expected_imm}))
  $fatal(1,"full immutable operands/Immediate lost or leaked on denied record");
 if(operand_stalled && (!ov || {ocmp,oarg,oimm}!==held_operands))$fatal(1,"held operands changed/retracted");
 operand_stalled=ov&&!ready;held_operands={ocmp,oarg,oimm};
end
'''


def candidate(op=7,**changes):
    fields=dict(opcode=op,local_address=old.original.BASE+1,length=8 if op in [7,8]else 65,
        remote_address=0 if op in [3,4,5]else 0xe23456789abcd008,
        remote_key=0 if op in [3,4,5]else 0xffffffff,
        immediate=0x89abcdef if op in [5,6]else 0)
    fields.update(changes)
    return codec.AtomicWQE(codec.base.candidate(**fields),0xfedcba9876543210 if op==7 else 0,
        0x8123456789abcdef if op in [7,8]else 0)


class Atomic128AdmissionTests(unittest.TestCase):
    reports={}
    @classmethod
    def setUpClass(cls):codec.AtomicWQETests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def entry(self,w=None,*,error=0,queries=1,context=None,mutate=None,unknown_byte=None,stalls=(7,9,11),fault=0):
        w=w or candidate();b=w.base
        raw=(C.c_uint8*128)();self.assertEqual(self.lib.as02_atomic_wqe_encode(raw,C.byref(w)),0)
        record=bytearray(raw)
        if mutate:mutate(record)
        q,pd,tag,seq,epoch=context or (1,7,0xf123,old.original.SEQ,old.original.EPOCH)
        good=error==0;values=[(64,b.wr_id if unknown_byte is None else 0),(64,seq),(64,epoch),(24,q),(16,pd),(16,tag),
            (16,b.opcode if good else 0),(16,b.flags if good else 0),(32,b.length if good else 0),
            (32,b.local_key if good else 0),(64,b.local_address if good else 0),
            (64,b.local_address-old.original.BASE if good else 0),(64,b.remote_address if good else 0),
            (32,b.remote_key if good else 0),(8,error)]
        text=f'{int.from_bytes(record,"little"):0256x}'
        if unknown_byte is not None:
            off=255-unknown_byte*2;text=text[:off]+'x'+text[off+1:]
        return f'''expected_cmp=64'h{w.compare:016x};expected_arg=64'h{w.swap_add:016x};expected_imm=32'h{b.immediate:08x};
expected_mr_op={int(b.opcode in [2,4,7,8])};
issue(1024'h{text},128'hffffffffffffffffffffffffffffffff,1'b1,1'b1,
24'd{q},16'd{pd},16'd{tag},64'h{seq:x},64'h{epoch:x},576'h{old.original.packed(values):0144x},
{queries},{stalls[0]},{stalls[1]},{stalls[2]},1'b1,8'd{fault});
'''

    def simulate(self,body,receive_only=False):
        generated=source.derive();tb=bench(body,receive_only)
        files=[Path(__file__).resolve(),Path(source.__file__).resolve(),Path(source.fetch.__file__).resolve(),
            source.WQE,source.SQ,source.HLS,old.original.RTL/'rocev2_mr_table.v',
            Path(old.__file__).resolve(),Path(old.original.__file__).resolve(),Path(codec.__file__).resolve(),
            *[codec.KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h']]]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-admission-')as temporary:
            run=Path(temporary);rtl=[]
            for original,text in generated.items():
                if original==source.HLS:continue
                p=run/('rocev2_atomic128_'+original.name.removeprefix('rocev2_'));p.write_text(text);rtl.append(p)
            (run/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),
                *map(str,rtl),str(old.original.RTL/'rocev2_mr_table.v')],capture_output=True,text=True,timeout=20)
            r=None
            if not c.returncode:r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=15)
            if c.returncode or r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-admission-failure-',dir=ROOT/'rdma/rnic/build'))
                for p in run.iterdir():shutil.copy2(p,diag/p.name)
                (diag/'compile.log').write_text(c.stdout+c.stderr)
                if r:(diag/'simulation.log').write_text(r.stdout+r.stderr)
                print('Preserved '+str(diag),flush=True)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            m=re.search(r'WQE_ADMISSION_PASS checked=(\d+) queries=(\d+) results=(\d+) fault=(\d+) cycles=(\d+)',r.stdout)
            self.assertIsNotNone(m,r.stdout)
            self.reports.setdefault(self._testMethodName,[]).append(dict(summary=dict(zip(['checked','queries','results','fault','cycles'],map(int,m.groups()))),
                bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),derived_RTL_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in rtl}))
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files})

    def test_CAS_FADD_full_operands_keys_real_local_write_MR_and_stalls(self):
        rows=[]
        for op in [7,8]:
            for value in [0,0x0123456789abcdef,0x8000000000000000,0xffffffffffffffff]:
                w=candidate(op,remote_key=value&0xffffffff);w.swap_add=value
                if op==7:w.compare=value^0x8123456789abcdef
                rows.append(self.entry(w))
        self.simulate(''.join(rows))

    def test_actual_table_denies_keys_PD_readonly_and_range_without_authority(self):
        self.simulate(''.join([self.entry(candidate(7,local_key=0),error=1),
            self.entry(candidate(8,local_key=old.original.KEY^0x80000000),error=1),
            self.entry(candidate(7,local_key=old.original.KEY+1),error=3),
            self.entry(context=(1,8,0xf123,old.original.SEQ,old.original.EPOCH),error=2),
            self.entry(candidate(8,local_address=old.original.BASE+8185),error=4),
            self.entry(candidate(7,local_address=(old.original.BASE+1)&((1<<48)-1)),error=4)]))

    def test_canonical_extension_length_and_remote_alignment_before_any_MR_query(self):
        changes=[(candidate(7),lambda b:b.__setitem__(80,1),0x20),
            (candidate(8),lambda b:b.__setitem__(64,1),0x20),
            (candidate(7),lambda b:b.__setitem__(48,1),0x20),
            (candidate(7),lambda b:b.__setitem__(24,b[24]|1),0x27),
            (candidate(8),lambda b:b.__setitem__(32,16),0x26),
            (candidate(1),lambda b:b.__setitem__(72,1),0x20)]
        self.simulate(''.join(self.entry(w,mutate=mutation,error=error,queries=0)for w,mutation,error in changes))

    def test_unknown_header_operand_or_reserved_bytes_never_query_or_invent_WRID(self):
        for byte in [0,20,63,64,72,79,80,127]:
            with self.subTest(byte=byte):self.simulate(self.entry(error=0x20,queries=0,unknown_byte=byte))

    def test_failed_fetch_all_real_status_codes_erase_old_operands_while_disabled(self):
        self.simulate(self.entry()+''.join(f"failed_fetch(8'd{code});\n"for code in range(1,16)))

    def test_normal_WRITE_READ_SEND_RECV_Immediate_remain_canonical(self):
        self.simulate(''.join(self.entry(candidate(op))for op in [1,2,3,4,5,6]))
        self.simulate(self.entry(candidate(7),error=0x24,queries=0)+self.entry(candidate(4)),receive_only=True)

    def test_wrong_tag_length_or_invalid_MR_status_holds_uncertain_owner(self):
        for corrupt,code in [(1,0x31),(2,0x32),(3,0x33)]:
            with self.subTest(corrupt=corrupt):self.simulate(f'corrupt={corrupt};\n'+self.entry(fault=code))

    def test_untrusted_unknown_queue_context_never_aliases_or_completes(self):
        for mutation in ["cq=24'h100001;","cp=16'hxxx7;","ct=0;","ce=0;","cs=0;","fe=8'hx0;"]:
            with self.subTest(mutation=mutation):self.simulate('''
@(negedge clk);enable=1;cfg_idle=1;wv=1;
'''+mutation+'''
repeat(10)@(negedge clk);
if(!fault || fault_code!==8'h51 || !busy || !guard || queue_guard!==255 || wr || ov || cfg_ready || queries || results)
 $fatal(1,"bad trusted source became Atomic authority");
checked=checked+1;
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    files=[Path(__file__).resolve(),Path(source.__file__).resolve(),Path(source.fetch.__file__).resolve(),
        source.WQE,source.SQ,source.HLS,old.original.RTL/'rocev2_mr_table.v',
        Path(old.__file__).resolve(),Path(old.original.__file__).resolve(),Path(codec.__file__).resolve(),
        *[codec.KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h']]]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files};started=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128AdmissionTests))
    if before!={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,
        simulations=sum(map(len,Atomic128AdmissionTests.reports.values())),tests=Atomic128AdmissionTests.reports,
        seconds=time.monotonic()-started,source_sha256=before,actual_C_UBSan=True,actual_MR_table=True,
        four_state=True,SQ_result_source_modeled=True,native_requester_integrated=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
