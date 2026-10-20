# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual Atomic full-owner TX/MAC/lifetime/816-bit core-receipt proof join.

Actual native Ethernet framer/tag/EOF/tail. Wire source, memory/RX/ACK/core
receipt/CQ boundaries are explicit MODELS, not native HLS/DMA/CQ runtime.
Also compile the retained replay/result-unpad leaves; compile-only isn't
runtime coverage. No global drain, board/timing/kernel/physical qualification.
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
import test_wqe_tx_lifetime_rtl as old
from test_atomic128_response_rtl import owner

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_lifetime as source


def packet(op=7,psn=0xfffffe):
    w=old.life.packets.read_wire
    import rocev2_wire as wire
    body=bytes([19 if op==7 else 20,0x40])+bytes.fromhex('ffff')+(196).to_bytes(4,'big')+(0x80000000|psn).to_bytes(4,'big')
    body+=(0xe23456789abcd008).to_bytes(8,'big')+bytes(4)+(0x8123456789abcdef).to_bytes(8,'big')
    body+=(0xfedcba9876543210 if op==7 else 0).to_bytes(8,'big')
    ip=bytearray(bytes.fromhex('450000480000400040110000c6120b02c6120b01'))
    ip[10:12]=w.internet_checksum(ip).to_bytes(2,'big')
    raw=bytes(ip)+bytes.fromhex('c00012b700340000')+body+bytes(4)
    return raw[:-4]+wire.icrc_ipv4(raw)


def prefix(op=7,psn=0xfffffe):
    return f'owner({owner(op)});transmit(72);expectation(24\'h{psn:06x});memory();response(24\'h{psn:06x},8\'h12);ack(40\'h{(psn<<11)|(7<<1):010x});mac();'


def done_word(op=7,psn=0xfffffe):
    n=int(owner(op).split("'h",1)[1],16)
    n|=psn<<748;n|=((psn+1)&0xffffff)<<772;n|=(19 if op==7 else 20)<<796
    return n


FINISH=r'''
repeat(17)begin @(negedge clk);if(m_cq_valid || committed_count || !busy || proof_flags[5:0]!=6'h3f)$fatal(1,"private core receipt required");
end
s_request_done_data=CORE_DONE;s_request_done_valid=1;
repeat(11)begin @(negedge clk);if(s_request_done_ready || m_cq_valid || queue_guard!==8'h80)$fatal(1,"core done substituted for real memory drain");end
memory_drained=1;@(posedge clk);if(!s_request_done_ready)$fatal(1,"matched816-bit core receipt not accepted");
@(negedge clk);s_request_done_valid=0;
deadline=cycle+100;while(!m_cq_valid)begin if(cycle>deadline)$fatal(1,"operation-owned core proof did not enable ticket");@(negedge clk);end
repeat(13)begin @(negedge clk);if(!m_cq_valid || m_cq_context!==expected_owner || committed_count || !busy || fault || hls_transport_drained)$fatal(1,"actual private receipt did not retain full owner");end
take_ticket();commit();
'''


class Atomic128LifetimeTests(unittest.TestCase):
    reports={}

    def simulate(self,body,op=7,psn=0xfffffe,pkt=None):
        generated=source.derive();tb=old.bench(body)
        tb=source.once(tb,'rocev2_wqe_tx_lifetime dut(.*);',
            'rocev2_atomic128_wqe_tx_lifetime #(.REQUEST_CQ_ENABLE(1)) dut(.*);')
        tb=tb.replace('[587:0]','[747:0]').replace('[655:0]','[815:0]').replace('[675:0]','[835:0]')
        pkt=packet(op,psn)if pkt is None else pkt
        files=[*generated,Path(source.__file__).resolve(),Path(source.geometry.__file__).resolve(),
            Path(source.geometry.base.__file__).resolve(),Path(__file__).resolve(),Path(old.__file__).resolve(),
            Path(old.mac.__file__).resolve(),Path(old.life.__file__).resolve(),ROOT/'rdma/rnic/tests/test_atomic128_response_rtl.py',
            ROOT/'rdma/host/rocev2_wire.py',*old.mac.SOURCES[1:]]
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in files}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-lifetime-')as temp:
            p=Path(temp);(p/'tb.v').write_text(tb)
            (p/'request.hex').write_text(''.join(f'{int.from_bytes(pkt[n:n+16].ljust(16,bytes([0])),"little"):032x}\n'for n in range(0,len(pkt),16)))
            sources=[]
            for original,text in generated.items():
                f=p/('rocev2_atomic128_'+original.name.removeprefix('rocev2_'));f.write_text(text);sources.append(f)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,sources+old.mac.SOURCES[1:])],
                capture_output=True,text=True,timeout=20)
            if c.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-lifetime-compile-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-lifetime-runtime-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_LIFETIME_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            frames=old.mac.decode_frames(r.stdout)
            self.assertEqual(frames,[(0x2001,0,bytes.fromhex('b8830367c5d08af3fbb975310800')+pkt)])
            # Additional RETRY_ENABLE1 compile, with actual new family, not an
            # unresolved inactive branch. No retry runtime is inferred here.
            c=subprocess.run(['iverilog','-g2012','-s','rocev2_atomic128_wqe_tx_lifetime',
                '-P','rocev2_atomic128_wqe_tx_lifetime.REQUEST_CQ_ENABLE=1','-P','rocev2_atomic128_wqe_tx_lifetime.RETRY_ENABLE=1',
                '-o',str(p/'replay.vvp'),*map(str,sources+old.mac.SOURCES[1:])],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),TX_packet_hex=pkt.hex(),
            actual_native_MAC_framing_tag_EOF_tail=True,modeled_memory_RX_ACK_core_CQ=True,
            retained_replay_family_elaborated_not_executed=True))

    def test_CAS_FADD_actual_MAC_and_private816bit_core_receipt_join(self):
        for op,psn in [(7,0xfffffe),(8,0xffffff)]:
            self.simulate(prefix(op,psn)+FINISH.replace('CORE_DONE',f"816'h{done_word(op,psn):0204x}"),op,psn)

    def test_all64_wire_operand_bits_including_beyond_old64byte_header_are_checked(self):
        for off in [52,59,60,64,67]:
            p=bytearray(packet());p[off]^=0x80;p=old.life.packets.repair(p)
            self.simulate(f'owner({owner()});transmit(72);'+r'''
repeat(13)@(negedge clk);if(!fault || fault_code!=8'hb2 || m_expect_valid || response_admission_ready || m_cq_valid || queue_guard!==8'hff)$fatal(1,"changed Atomic operand authorized expected response");
''',pkt=p)

    def test_changed_operand_PSN_opcode_or_error_in_core_receipt_cannot_release(self):
        for bit in [620,683,684,747,748,772,796,804,815]:
            value=done_word()^(1<<bit)
            self.simulate(prefix()+f'memory_drained=1;s_request_done_data=816\'h{value:0204x};s_request_done_valid=1;'+r'''
repeat(9)@(negedge clk);if(!fault || fault_code!=8'he9 || s_request_done_ready || m_cq_valid || committed_count || queue_guard!==8'hff)$fatal(1,"wrong816-bit core receipt authorized CQ");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128LifetimeTests))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,simulations=sum(map(len,Atomic128LifetimeTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128LifetimeTests.reports,actual_native_result_DMA_WR_CQ=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
