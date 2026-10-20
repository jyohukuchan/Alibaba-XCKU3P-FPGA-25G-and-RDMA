# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual MAC-padding adapter plus unchanged private IP checksum/ICRC/FIFO.

Full original65536 keep-mask and21-bit RX checksum predicate checks stay.
Not whole native/HLS/Linux/physical qualification; <=30s per simulation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import test_zero_integrity_rtl as prior

ROOT=prior.ROOT;digest=prior.digest;PAD=ROOT/'rdma/rnic/rtl/rocev2_zero_rx_padding.v'


class ZeroRXPadding(unittest.TestCase):
    reports={}
    def simulate(self,inputs,expected,bad):
        iw=[w for data,error,hole in inputs for w in prior.old.words(data,error,hole)]
        ew=[w for data in expected for w in prior.old.words(data)]
        t=prior.source.once(prior.old.TESTBENCH,'rocev2_ipv4_icrc #(','rocev2_zero_ipv4_icrc #(')
        for n,v in dict(TX_VALUE=0,INPUT_COUNT=len(iw),OUTPUT_COUNT=len(ew),THROUGHPUT_MODE=1,
                GOOD_COUNT=len(expected),BAD_COUNT=bad).items():t=t.replace(n,str(v))
        t=prior.source.once(t,'mr=1 || (cycle>6000 && rng[2:0]!=0);','mr=cycle%11>2;')
        t=prior.source.once(t,'rocev2_zero_ipv4_icrc #(',r'''
wire [127:0] pad_data;wire [15:0] pad_keep;wire pad_valid,pad_ready,pad_last,pad_user;
rocev2_zero_rx_padding padding(.clk(clk),.rst(rst),.s_axis_tdata(sd),.s_axis_tkeep(sk),
 .s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser(su),
 .m_axis_tdata(pad_data),.m_axis_tkeep(pad_keep),.m_axis_tvalid(pad_valid),.m_axis_tready(pad_ready),
 .m_axis_tlast(pad_last),.m_axis_tuser(pad_user));
rocev2_zero_ipv4_icrc #(''')
        # Replace ONLY the integrity instance inputs, not the actual input
        # source/handshake or either original exhaustive predicate oracle.
        a=t.index('rocev2_zero_ipv4_icrc #(');head=t[:a];tail=t[a:]
        for old,new in [('s_axis_tdata(sd)','s_axis_tdata(pad_data)'),('s_axis_tkeep(sk)','s_axis_tkeep(pad_keep)'),
            ('s_axis_tvalid(sv)','s_axis_tvalid(pad_valid)'),('s_axis_tready(sr)','s_axis_tready(pad_ready)'),
            ('s_axis_tlast(sl)','s_axis_tlast(pad_last)'),('s_axis_tuser(su)','s_axis_tuser(pad_user)')]:
            tail=prior.source.once(tail,old,new)
        t=head+tail
        run=Path(tempfile.mkdtemp(prefix='zero-rx-padding-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t);(run/'integrity.v').write_text(prior.source.integrity())
        (run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in iw));(run/'expected.hex').write_text(''.join(f'{w:037x}\n'for w in ew))
        src=[PAD,run/'integrity.v',*[ROOT/'external/corundum/fpga/lib/axis/rtl'/n for n in ['axis_fifo.v','axis_register.v']],
            ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v'),*map(str,src)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(run/'test')],cwd=run,capture_output=True,text=True,timeout=30)
        seconds=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
        rows=[json.loads(l[7:])for l in r.stdout.splitlines()if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout)
        self.reports[self._testMethodName]=dict(summary=rows[0],seconds=seconds,directory=str(run.relative_to(ROOT)),
            artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()})

    def test_exact_Ethernet_padding_and_normal_packets_keep_real_ICRC_backpressure(self):
        p=prior.send0();others=[prior.wire.packet(write=True,length=1),*[prior.old.packet(n,n)for n in [1,2,3,4,63,65]]]
        frames=[p+bytes(2),p+b'\xa5\x5a',p,*others,p+bytes(2)]
        self.simulate([(x,None,None)for x in frames],[p,p,p,*others,p],0)

    def test_padding_never_waives_crc_checksum_packet_class_dense_keep_or_length(self):
        p=prior.send0();bad=[(p+bytes(n),None,None)for n in [1,3,4]]
        for offset,value in [(28,5),(29,0x10)]:
            q=bytearray(p);q[offset]=value;bad.append((prior.wire.repair(q)+bytes(2),None,None))
        for offset in [10,33,43]:
            q=bytearray(p);q[offset]^=0x80;bad.append((bytes(q)+bytes(2),None,None))
        bad.extend([(p+bytes(2),1,None),(p+bytes(2),None,1)])
        inputs=[]
        for entry in bad:inputs.extend([entry,(p+bytes(2),None,None)])
        self.simulate(inputs,[p]*len(bad),len(bad))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    if a.report.exists():parser.error('preserve evidence')
    files=[PAD,Path(__file__).resolve(),Path(prior.__file__),Path(prior.old.__file__),prior.source.ICRC,Path(prior.source.__file__)]
    before={str(p.relative_to(ROOT)):digest(p)for p in files};start=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroRXPadding))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=ZeroRXPadding.reports,four_state=True,simulation_limit_seconds=30,
        original_integrity_oracles_unchanged=True,native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
