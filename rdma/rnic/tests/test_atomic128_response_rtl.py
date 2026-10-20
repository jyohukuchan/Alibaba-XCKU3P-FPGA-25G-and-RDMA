# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual Atomic result-response integrity/owner/placement protection RTL.

Full748-bit expected owner/issued peer/PSN and downstream executor/HLS/DMA/CQ
are MODELS. Actual integrity checker and protected replay/token logic run in
four-state RTL. Not native result placement, WR/CQ/unpin/API evidence.
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
import test_wqe_response_guard_rtl as old

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_response as source


def owner(op=7,compare=None,argument=None,immediate=0,**changes):
    fields=dict(opcode=op,length=8 if op in [7,8]else 65,remote=0 if op in [3,5]else 0xe23456789abcd008)
    if op in [3,5]:fields['rkey']=0
    fields.update(changes)
    low=int(old.context(**fields).split("'h",1)[1],16)
    compare=(0xfedcba9876543210 if op==7 else 0)if compare is None else compare
    argument=(0x8123456789abcdef if op in [7,8]else 0)if argument is None else argument
    n=low|(immediate<<588)|(compare<<620)|(argument<<684)
    return f"748'h{n:0187x}"


def packet(**changes):
    p=bytearray(old.packet(length=8,**changes));p[28]=0x12
    p[44:52]=(0xfedcba9876543210).to_bytes(8,'big')
    return old.repair(p)


class Atomic128ResponseTests(unittest.TestCase):
    reports={}

    def simulate(self,packets,body,qpn=7,psn=0xfffffe,control=False):
        words=[]
        for i,p in enumerate(packets):
            first=len(words);words.extend(int.from_bytes(p[n:n+16].ljust(16,b'\0'),'little')for n in range(0,len(p),16))
            body=re.sub(r'\bPACKET'+str(i)+r'\b',f'{first},{len(p)}',body)
        tb=old.TB.replace('// DECLARATIONS',old.declarations()).replace('// BODY',body)
        tb=tb.replace('[587:0]','[747:0]').replace('[627:0]','[787:0]')
        tb=source.once(tb,'rocev2_wqe_response_guard dut(.*);',
            f'rocev2_atomic128_wqe_response_guard #(.CONTROL_ENABLE({int(control)})) dut(.*);')
        tb=tb.replace("EXPECTED_GUARD=8'h80",f"EXPECTED_GUARD=8'h{1<<qpn:02x}")
        tb=tb.replace("EXPECTED_PSN=24'hfffffe",f"EXPECTED_PSN=24'h{psn:06x}")
        rtl=source.derive();files=[source.SOURCE,Path(source.__file__).resolve(),Path(source.base.__file__).resolve(),
            Path(__file__).resolve(),Path(old.__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',
            Path(old.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',*old.SOURCES[1:]]
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in files}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-response-')as temp:
            p=Path(temp);(p/'tb.v').write_text(tb);(p/'rocev2_atomic128_wqe_response_guard.v').write_text(rtl)
            (p/'frames.hex').write_text(''.join(f'{w:032x}\n'for w in words or[0]))
            compile_start=time.monotonic()
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                str(p/'rocev2_atomic128_wqe_response_guard.v'),*map(str,old.SOURCES[1:])],capture_output=True,text=True,timeout=30)
            compile_seconds=time.monotonic()-compile_start
            if c.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-response-compile-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            simulation_start=time.monotonic()
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            simulation_seconds=time.monotonic()-simulation_start
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-response-runtime-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_RESPONSE_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            generated_RTL_sha256=hashlib.sha256(rtl.encode()).hexdigest(),bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            compile_seconds=compile_seconds,simulation_seconds=simulation_seconds,
            packet_sha256=[hashlib.sha256(p).hexdigest()for p in packets]))

    def test_CAS_FADD_full_immutable_owner_and_result_token_before_HLS(self):
        for op in [7,8]:
            for credit in [0,7,31]:
                self.simulate([packet(syndrome=credit,mig=op%2)],f'expect_owner({owner(op)});send(PACKET0);token();forward(PACKET0,8\'h12,8\'h{credit:02x});if(tokens!=1 || events!=1)$fatal(1,"actual Atomic result token/event missing");')

    def test_full64_ranges_keys_PD_QP0_and_PSN_wrap_boundary(self):
        for psn in [0,0xffffff]:
            n=owner(7,qpn=0,pd=0,lkey=0,rkey=0,address=(1<<64)-8,offset=(1<<64)-8,remote=(1<<64)-8)
            self.simulate([packet(qpn=0,psn=psn)],f'expect_owner({n});send(PACKET0);token();forward(PACKET0,8\'h12,8\'h1f);',qpn=0,psn=psn)

    def test_same_guard_normal_READ_WRITE_SEND_Immediate_stay_supported(self):
        for op in [1,2,3,5,6]:
            p=old.packet(write=op!=2);imm=0x89abcdef if op in [5,6]else 0
            body=f'expect_owner({owner(op,immediate=imm)});send(PACKET0);'
            if op==2:body+='token();'
            body+=f'forward(PACKET0,8\'h{0x10 if op==2 else 0x11:02x},8\'h1f);'
            body+=f'if(tokens!={int(op==2)})$fatal(1,"ordinary operation acquired wrong result token");'
            self.simulate([p],body)

    def test_good_ICRC_cannot_bypass_peer_QPN_PSN_class_AETH_or_exact8_length(self):
        bad=[]
        for off,value in [(12,199),(16,199),(35,6),(37,1),(28,0x10),(28,0x11),(40,0x20),
                          (40,0x40),(40,0x60),(40,0x80),(30,0),(29,0x50),(32,1),(36,1),(26,1)]:
            p=bytearray(packet());p[off]=value;bad.append(old.repair(p))
        p=bytearray(packet());p[32:36]=(0x800007).to_bytes(4,'big');bad.append(old.repair(p))
        p=bytearray(packet());p=p[:48]+p[-4:];bad.append(old.repair(p))
        p=bytearray(packet());p=p[:-4]+b'\0'*4+p[-4:];bad.append(old.repair(p))
        body=f'expect_owner({owner()});'
        for i in range(len(bad)):body+=f'send(PACKET{i});reject();'
        body+=f'if(rejected_count!={len(bad)} || accepted_count || tokens || events)$fatal(1,"invalid Atomic response gained authority");send(PACKET{len(bad)});token();forward(PACKET{len(bad)},8\'h12,8\'h1f);'
        self.simulate(bad+[packet()],body)

    def test_bad_ICRC_and_unknown_response_never_offer_placement_or_HLS(self):
        good=packet();bad=bytearray(good);bad[-1]^=0x80
        port=bytearray(good);port[23]=0xb8;port=old.repair(port)
        # Destination-port rejection is performed by the REAL earlier whole
        # packet integrity checker, not a later response-parser rejection.
        self.simulate([bytes(bad),port,good],f'expect_owner({owner()});send(PACKET0);'+r'''
deadline=cycle+5000;while(integrity_drop_count!=1)begin if(cycle>deadline)$fatal(1,"actual ICRC rejection");@(negedge clk);end
if(tokens || events || accepted_count || m_read_response_valid || m_axis_hls_rx_tvalid || !busy)$fatal(1,"bad ICRC gained authority");
send(PACKET1);deadline=cycle+5000;while(integrity_drop_count!=2)begin if(cycle>deadline)$fatal(1,"actual UDP-port integrity rejection");@(negedge clk);end
if(tokens || events || accepted_count || m_read_response_valid || m_axis_hls_rx_tvalid || !busy)$fatal(1,"bad UDP port gained authority");
send(PACKET2);token();forward(PACKET2,8'h12,8'h1f);
''')
        self.simulate([],f'expect_owner({owner()});'+r'''
s_axis_rx_tdata={128{1'bx}};s_axis_rx_tkeep=16'hffff;s_axis_rx_tvalid=1;
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h98 || m_read_response_valid || m_axis_hls_rx_tvalid || queue_guard!==8'hff)$fatal(1,"unknown response fabricated placement");
''')

    def test_noncanonical_operand_owner_alignment_length_range_and_unknown_refused(self):
        cases=[owner(8,compare=1),owner(1,argument=1),owner(immediate=1),owner(length=7),owner(length=9),
            owner(remote=0xe23456789abcd009),owner(address=(1<<64)-7),owner(offset=(1<<64)-7),
            owner(qpn=0x800007),owner(epoch=0),owner(sequence=0),owner(authorized=0),"{64'hx,684'd0}"]
        for n in cases:self.simulate([],f's_expect_context={n};s_expect_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h96 || s_expect_ready || m_read_response_valid || m_axis_hls_rx_tvalid || queue_guard!==8'hff)$fatal(1,"noncanonical Atomic authority accepted");
''')

    def test_result_token_requires_real_downstream_guard_and_keeps_offer_on_fault(self):
        self.simulate([packet()],f'expect_owner({owner()});send(PACKET0);'+r'''
deadline=cycle+5000;while(!m_read_response_valid)begin if(cycle>deadline)$fatal(1,"result token wait");@(negedge clk);end
m_read_response_ready=1;@(posedge clk);@(negedge clk);m_read_response_ready=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h97 || !m_read_response_valid || m_read_response_context!==expected_owner || m_axis_hls_rx_tvalid || queue_guard!==8'hff)$fatal(1,"lost Atomic placement lifetime");
''')
        self.simulate([packet()],f'expect_owner({owner()});send(PACKET0);token();'+r'''
deadline=cycle+5000;while(!m_axis_hls_rx_tvalid)begin if(cycle>deadline)$fatal(1,"held actual HLS word");@(negedge clk);end
downstream_queue_guard=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h97 || !m_axis_hls_rx_tvalid || m_response_event_valid || queue_guard!==8'hff)$fatal(1,"late fault retracted owned Atomic packet");
''')

    def test_control_NAK_holds_same_Atomic_owner_without_result_or_HLS(self):
        p=old.packet(write=True,syndrome=0x60)
        self.simulate([p,packet()],f'expect_owner({owner()});send(PACKET0);'+r'''
deadline=cycle+5000;while(!m_control_valid)begin if(cycle>deadline)$fatal(1,"actual control event");@(negedge clk);end
repeat(9)@(negedge clk);
if(m_control_context!==expected_owner || m_control_psn!==EXPECTED_PSN || m_control_syndrome!=8'h60 || m_read_response_valid || m_axis_hls_rx_tvalid || tokens || events)$fatal(1,"control event fabricated positive Atomic result");
downstream_queue_guard=EXPECTED_GUARD;m_control_ready=1;@(posedge clk);@(negedge clk);m_control_ready=0;
send(PACKET1);token();forward(PACKET1,8'h12,8'h1f);
''',control=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128ResponseTests))
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,simulations=sum(map(len,Atomic128ResponseTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128ResponseTests.reports,actual_native_result_DMA_WR_CQ=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
