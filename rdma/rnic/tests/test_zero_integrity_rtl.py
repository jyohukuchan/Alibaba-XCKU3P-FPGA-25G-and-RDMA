#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native-only SEND44 integrity extension; strict real CRC/FIFO RTL.

TX/RX byte oracles, malformed short class/pad/length/ICRC/UDP/keep rejection,
ordinary packets and stalled full-frame recovery. Original module unchanged.
No HLS/full-native/Linux/physical/timing proof; every runtime bounded30s.
"""
import argparse
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

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'rdma/tests'),str(ROOT/'rdma/rnic/fpga')]
import test_icrc_rtl as old
import derive_zero_native as source
import test_wqe_response_guard_rtl as wire

digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def send0():
    p=bytearray(wire.packet(write=True,length=1));p[28]=4
    # Remove ACK's AETH, never remove any SEND payload or invent ICRC bytes.
    p=p[:40]+p[-4:]
    return wire.repair(p)


class ZeroIntegrity(unittest.TestCase):
    reports={}
    def simulate(self,tx,inputs,expected,bad):
        iw=[w for data,error,hole in inputs for w in old.words(data,error,hole)]
        ew=[w for data in expected for w in old.words(data)]
        t=source.once(old.TESTBENCH,'rocev2_ipv4_icrc #(','rocev2_zero_ipv4_icrc #(')
        for n,v in dict(TX_VALUE=int(tx),INPUT_COUNT=len(iw),OUTPUT_COUNT=len(ew),
                THROUGHPUT_MODE=1,GOOD_COUNT=len(expected),BAD_COUNT=bad).items():t=t.replace(n,str(v))
        # Independent deterministic backpressure still applies, without
        # requiring eight large packets to fill the old16KiB FIFO first.
        t=source.once(t,'mr=1 || (cycle>6000 && rng[2:0]!=0);',
            'mr=cycle%11>2;')
        run=Path(tempfile.mkdtemp(prefix='zero-integrity-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t);(run/'integrity.v').write_text(source.integrity())
        (run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in iw))
        (run/'expected.hex').write_text(''.join(f'{w:037x}\n'for w in ew))
        sources=[run/'integrity.v',ROOT/'external/corundum/fpga/lib/axis/rtl/axis_fifo.v',
            ROOT/'external/corundum/fpga/lib/axis/rtl/axis_register.v',ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        seconds=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
        rows=[json.loads(l[7:])for l in r.stdout.splitlines()if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout)
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],seconds=seconds,
            directory=str(run.relative_to(ROOT)),artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}))

    def test_actual_TX_RX_SEND44_and_ordinary_ACK_WRITE_all_pad_positions(self):
        frames=[send0(),wire.packet(write=True,length=1),*[old.packet(n,n)for n in [1,2,3,4,63,64,65,4096]],send0()]
        for tx in [True,False]:
            self.simulate(tx,[(p[:-4]if tx else p,None,None)for p in frames],frames,0)

    def test_short_packet_class_and_pad_are_not_generic_minimum_length_waivers(self):
        valid=send0();bad=[]
        for off,val in [(28,0x05),(28,0x0a),(28,0x0c),(28,0x10),(28,0x11),(28,0x12),(29,0x10),(29,0x30)]:
            p=bytearray(valid);p[off]=val;bad.append((wire.repair(p),None,None))
        # Deliberately incomplete BTH: the independent valid-packet ICRC
        # helper correctly refuses it. Keep malformed wire bytes malformed,
        # with explicit IP/UDP lengths/checksum, rather than weaken that helper.
        p=bytearray(valid[:36]+valid[-4:]);p[2:4]=(40).to_bytes(2,'big');p[24:26]=(20).to_bytes(2,'big')
        bad.append((old.update_ip_checksum(p),None,None))
        for tx in [True,False]:
            inputs=[];expected=[]
            for p,error,hole in bad:
                inputs.extend([(p[:-4]if tx else p,error,hole),(valid[:-4]if tx else valid,None,None)])
                expected.append(valid)
            self.simulate(tx,inputs,expected,len(bad))

    def test_zero_still_checks_ICRC_IP_checksum_UDP_dense_keep_and_final_length(self):
        good=send0();bad=[]
        for pos in [10,33,43]:
            p=bytearray(good);p[pos]^=0x80;bad.append((bytes(p),None,None))
        p=bytearray(good);p[23]^=1;bad.append((wire.repair(p),None,None))
        bad.extend([(good,1,None),(good,None,1),(good[:-4],None,None)])
        inputs=[]
        for p,error,hole in bad:inputs.extend([(p,error,hole),(good,None,None)])
        self.simulate(False,inputs,[good]*len(bad),len(bad))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all evidence')
    inputs=[source.ICRC,Path(source.__file__).resolve(),Path(source.base.__file__).resolve(),Path(old.__file__).resolve(),
        Path(wire.__file__).resolve(),Path(__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroIntegrity))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=ZeroIntegrity.reports,simulation_limit_seconds=30,four_state=True,
        original_integrity_unchanged=True,native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
