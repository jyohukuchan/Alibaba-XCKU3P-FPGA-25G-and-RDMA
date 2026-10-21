#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched pre-padded LAST + unchanged legacy normalization/real ICRC.

Keep ALL three original padding tests/oracles and add strict segmented-tail
coverage. Five methods use four-state simulation; the unchanged largest
capacity case uses two-state Verilator to retain its full workload <=30s.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/tests'))
import test_padding_rtl as legacy
import test_zero_integrity_rtl as native
import test_segmented_wire_rtl as wire

PAD=ROOT/'rdma/rnic/rtl/rocev2_segmented_tx_padding.v'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


class SegmentedPadding(legacy.PaddingRTLTests):
    all_runs={}

    def simulate(self,inputs,expected,bad_count,throughput=False):
        t=legacy.TESTBENCH
        for old,new in [('tdata(sd)','tdata(pd)'),('tkeep(sk)','tkeep(pk)'),('tvalid(sv)','tvalid(pv)'),
                        ('tready(sr)','tready(pr)'),('tlast(sl)','tlast(pl)'),('tuser(su)','tuser(pu)')]:
            if old not in t:raise ValueError('unchanged integrity scoreboard anchor missing')
            t=t.replace(old,new)
        t=native.source.once(t,'rocev2_ipv4_icrc #(',PREFIX+'\nrocev2_zero_ipv4_icrc #(')
        iw=[w for frame,error,hole in inputs for w in legacy.words(frame,error,hole)]
        ew=[w for frame in expected for w in legacy.words(frame)]
        for k,v in dict(TX_VALUE=1,INPUT_COUNT=len(iw),OUTPUT_COUNT=len(ew),GOOD_COUNT=len(expected),
                        BAD_COUNT=bad_count,THROUGHPUT_MODE=int(throughput)).items():t=t.replace(k,str(v))
        run=Path(tempfile.mkdtemp(prefix='segmented-padding-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t);(run/'integrity.v').write_text(native.source.integrity())
        (run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in iw))
        (run/'expected.hex').write_text(''.join(f'{w:037x}\n'for w in ew))
        src=[PAD,run/'integrity.v',*[ROOT/'external/corundum/fpga/lib/axis/rtl'/n for n in ['axis_fifo.v','axis_register.v']],
             ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
        if throughput:
            tool=ROOT.parent/'fpga-rocev2-research/verilator-v5.036-install/bin/verilator'
            obj=Path(tempfile.mkdtemp(prefix='as02-segmented-padding-obj-',dir='/dev/shm'))
            command=[str(tool),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
                     '--Mdir',str(obj),'-CFLAGS','-O1',str(run/'tb.v'),*map(str,src)]
            execute=[str(obj/'Vtb')];engine='verilator-two-state'
        else:
            command=['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v'),*map(str,src)]
            execute=['vvp',str(run/'test')];engine='icarus-four-state'
        c=subprocess.run(command,capture_output=True,text=True,timeout=180 if throughput else 30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        start=time.monotonic()
        try:c=subprocess.run(execute,cwd=run,capture_output=True,text=True,timeout=30)
        except subprocess.TimeoutExpired as error:
            (run/'simulation.log').write_bytes((error.stdout or b'')+(error.stderr or b''))
            raise
        seconds=time.monotonic()-start;output=c.stdout+c.stderr;(run/'simulation.log').write_text(output)
        self.assertEqual(c.returncode,0,output);self.assertNotIn('ERROR:',output)
        rows=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('RESULT ')]
        self.assertEqual(len(rows),1,output)
        self.all_runs.setdefault(self._testMethodName,[]).append(dict(pass_test=True,summary=rows[0],seconds=seconds,engine=engine,
            directory=str(run.relative_to(ROOT)),artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}))
        return rows[0]

    def test_pre_padded_LAST_all_pad_counts_and_payload_tail_positions(self):
        frames=[wire.packet(op,4096+n,4096,0)for op in [1,3]for n in [*range(1,34),63,64,65,4095,4096]]
        self.simulate([(p[:-4],None,None)for p in frames],frames,0)

    def test_zero_SEND_and_ordinary_unpadded_WRITE_SEND_stay_compatible(self):
        frames=[native.send0()]
        for op in [4,0x0a]:
            for length in [1,2,3,4,65]:
                p=bytearray(native.wire.packet(write=False,length=length))
                if op==0x0a:p=bytearray(native.wire.packet(write=True,length=length))
                else:p[28]=4
                frames.append(native.wire.repair(p))
        self.simulate([(legacy.unpadded(p),None,None)for p in frames],frames,0)

    def test_pre_padded_LAST_never_heals_bad_pad_class_lengths_or_masks(self):
        good=wire.packet(1,4097,4096,0);raw=good[:-4];bad=[]
        for byte in range(len(raw)-3,len(raw)):
            p=bytearray(raw);p[byte]=0x80;bad.append((bytes(p),None,None))
        p=bytearray(raw);p[28]=4;bad.append((bytes(p),None,None))
        for pos in [3,25]:
            p=bytearray(raw);p[pos]^=1;bad.append((bytes(p),None,None))
        # LAST must already be aligned/padded, never repaired as legacy input.
        bad.append((legacy.unpadded(good),None,None))
        bad.extend([(raw,1,None),(raw,None,1),(raw[:-1],None,None)])
        # Same real FIFO-pressure prefix as the retained legacy negative test;
        # keep the scoreboard's mandatory actual input-backpressure assertion.
        prefix=[legacy.packet(4095,i)for i in range(8)]
        inputs=[(legacy.unpadded(p),None,None)for p in prefix]
        for b in bad:inputs.extend([b,(raw,None,None)])
        self.simulate(inputs,[*prefix,*([good]*len(bad))],len(bad))


PREFIX=r'''
wire [127:0] pd;wire [15:0] pk;wire pv,pr,pl,pu;
rocev2_segmented_tx_padding padding(
 .clk(clk),.rst(rst),.s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser(su),
 .m_axis_tdata(pd),.m_axis_tkeep(pk),.m_axis_tvalid(pv),.m_axis_tready(pr),.m_axis_tlast(pl),.m_axis_tuser(pu),
 .status_padded_frame(),.status_bad_frame());
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    files=[PAD,ROOT/'rdma/rtl/rocev2_tx_padding.v',native.source.ICRC,Path(native.source.__file__).resolve(),
           Path(__file__).resolve(),Path(legacy.__file__).resolve(),ROOT/'rdma/tests/test_icrc_rtl.py',
           Path(native.__file__).resolve(),Path(native.wire.__file__).resolve(),Path(wire.__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in files};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedPadding))
    if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('padding/integrity input changed')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
                source_sha256=before,tests=SegmentedPadding.all_runs,four_state_all_methods=False,
                four_state_methods=5,two_state_capacity_methods=1,simulation_limit_seconds=30,
                all_three_original_padding_tests_retained=True,original_padding_and_integrity_unchanged=True,
                actual_native_HLS_runtime=False,hardware_verified=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())


if __name__=='__main__':main()
