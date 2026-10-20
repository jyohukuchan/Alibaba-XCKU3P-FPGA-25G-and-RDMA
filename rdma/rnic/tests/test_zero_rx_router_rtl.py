# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual private Ethernet routing: only exact SEND44 admits60-byte frames.

Response-mode minimum, ordinary host sidebands, dense keeps and errors stay
checked. No CRC/HLS/MR/native runtime proof follows this routing test alone.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
import derive_zero_rq_native as source
import zero_rq_native_fixture as fixture
import test_zero_integrity_rtl as wire

ROOT=source.ROOT;digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def frame(ip):return bytes.fromhex('8af3fbb97531b8830367c5d00800')+ip


class ZeroRXRouter(unittest.TestCase):
    reports={}
    def simulate(self,mode,cases):
        generated=source.derive()[source.INGRESS]
        ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',generated.split(')(\n',1)[1].split('\n);',1)[0])
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        words=[];body='';expected={'HOST':[],'ROCE':[]}
        for data,route,error,hole in cases:
            start=len(words);encoded=fixture.split.encode_frame(data)
            if hole is not None:encoded[hole]^=1<<128
            words+=encoded
            body+=f's_axis_tuser=97\'h{(0x12345678<<1)|error:x};send({start},{len(encoded)});\n'
            if route in expected:expected[route].append(data if route=='HOST'else data[14:])
        counts={r:sum(c[1]==r for c in cases)for r in ['HOST','ROCE','DROP']}
        t='`timescale 1ns/1ps\nmodule tb;localparam USER_WIDTH=97;\n'+decl+f'\nrocev2_responder_ethernet_rx #(.RESPONSE_MODE({mode})) dut(.*);\n'+r'''
always #2 clk=~clk;
reg [144:0] words[0:LAST];integer cycle=0;
reg host_stall=0,roce_stall=0;reg [241:0] held_host;reg [145:0] held_roce;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>3000)$fatal(1,"bounded router deadline");
 if(host_stall && (!m_axis_host_tvalid || {m_axis_host_tdata,m_axis_host_tkeep,m_axis_host_tlast,m_axis_host_tuser}!==held_host))$fatal(1,"host changed under stall");
 if(roce_stall && (!m_axis_roce_tvalid || {m_axis_roce_tdata,m_axis_roce_tkeep,m_axis_roce_tlast,m_axis_roce_tuser}!==held_roce))$fatal(1,"RoCE changed under stall");
 host_stall=m_axis_host_tvalid&&!m_axis_host_tready;roce_stall=m_axis_roce_tvalid&&!m_axis_roce_tready;
 held_host={m_axis_host_tdata,m_axis_host_tkeep,m_axis_host_tlast,m_axis_host_tuser};
 held_roce={m_axis_roce_tdata,m_axis_roce_tkeep,m_axis_roce_tlast,m_axis_roce_tuser};
 if(m_axis_host_tvalid && m_axis_host_tready)begin
  if(m_axis_host_tuser!==97'h2468acf0)$fatal(1,"host sideband changed");
  $display("HOST %032h %04h %0d",m_axis_host_tdata,m_axis_host_tkeep,m_axis_host_tlast);
 end
 if(m_axis_roce_tvalid && m_axis_roce_tready)begin
  if(m_axis_roce_tuser)$fatal(1,"bad frame routed to RoCE");
  $display("ROCE %032h %04h %0d",m_axis_roce_tdata,m_axis_roce_tkeep,m_axis_roce_tlast);
 end
end
always @(negedge clk)begin m_axis_host_tready=cycle%3!=0;m_axis_roce_tready=cycle%5>1;end
task send;input integer start,count;integer i;
 begin
  for(i=start;i<start+count;i=i+1)begin
   @(negedge clk);{s_axis_tlast,s_axis_tkeep,s_axis_tdata}=words[i];s_axis_tvalid=1;
   @(posedge clk);while(!s_axis_tready)@(posedge clk);
  end
  @(negedge clk);s_axis_tvalid=0;
 end
endtask
initial begin
 rst=1;$readmemh("input.hex",words);repeat(5)@(negedge clk);rst=0;
 enable=1;run_id=1;local_mac=48'h8af3fbb97531;peer_mac=48'hb8830367c5d0;local_ip=32'hc6120b02;
BODY
 while(!quiescent)@(negedge clk);repeat(5)@(negedge clk);
 if(host_frame_count!=HOST_COUNT || roce_frame_count!=ROCE_COUNT || drop_frame_count!=DROP_COUNT || overflow_count || stale_frame_count)$fatal(1,"router count mismatch");
 $finish;
end
endmodule
'''
        for a,b in dict(LAST=len(words)-1,BODY=body,HOST_COUNT=counts['HOST'],ROCE_COUNT=counts['ROCE'],DROP_COUNT=counts['DROP']).items():t=t.replace(a,str(b))
        run=Path(tempfile.mkdtemp(prefix='zero-rx-router-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t);(run/'router.v').write_text(generated);(run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in words))
        src=[run/'router.v',ROOT/'external/corundum/fpga/lib/axis/rtl/axis_fifo.v',ROOT/'external/corundum/fpga/lib/eth/rtl/eth_axis_rx.v']
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v'),*map(str,src)],capture_output=True,text=True,timeout=20)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(run/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        for prefix,wanted in expected.items():
            result=[];p=bytearray()
            for l in r.stdout.splitlines():
                if l.startswith(prefix+' '):
                    _,data,keep,last=l.split();p+=int(data,16).to_bytes(16,'little')[:int(keep,16).bit_count()]
                    if last=='1':result.append(bytes(p));p.clear()
            self.assertFalse(p);self.assertEqual(result,wanted)
        self.reports[self._testMethodName]=dict(seconds=time.monotonic()-start,counts=counts,directory=str(run.relative_to(ROOT)),
            artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()})

    def test_request_mode_exact_short_SEND_only_and_unchanged_host_errors(self):
        p=wire.send0();f=frame(p)+bytes(2);q=bytearray(p);q[29]=0x50
        ordinary=bytes.fromhex('8af3fbb97531b8830367c5d088b5')+bytes(46)
        ack=frame(wire.wire.packet(write=True,length=1))
        self.simulate(0,[(f,'ROCE',0,None),(frame(p),'DROP',0,None),(frame(p)+bytes(1),'DROP',0,None),
            (frame(wire.wire.repair(q))+bytes(2),'DROP',0,None),(ack,'HOST',0,None),
            (ordinary,'HOST',0,None),(f,'DROP',1,None),(f,'DROP',0,1),(f,'ROCE',0,None)])

    def test_response_mode_never_inherits_short_request_minimum(self):
        p=wire.send0();f=frame(p)+bytes(2);ack=frame(wire.wire.packet(write=True,length=1))
        q=bytearray(p);q[28]=0x11
        self.simulate(1,[(f,'HOST',0,None),(ack,'ROCE',0,None),(frame(wire.wire.repair(q))+bytes(2),'DROP',0,None)])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    if a.report.exists():parser.error('preserve evidence')
    files=[source.INGRESS,Path(source.__file__),Path(__file__).resolve(),Path(fixture.__file__),Path(wire.__file__)]
    before={str(p.relative_to(ROOT)):digest(p)for p in files};start=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroRXRouter))
    if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=ZeroRXRouter.reports,four_state=True,native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
