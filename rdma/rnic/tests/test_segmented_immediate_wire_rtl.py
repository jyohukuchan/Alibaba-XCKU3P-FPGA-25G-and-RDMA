#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real large-Immediate lifetime/cache/MAC RTL plus all old wire cases.

HLS/source memory/RX/ACK/CQ and MAC completion pins are MODELS. Independent
wire constants, retained whole owner and actual per-packet ownership gates;
no generated-HLS/native/Linux/physical/timing success follows these cases.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time
import unittest
import test_segmented_wire_rtl as old

ROOT=old.ROOT;digest=old.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_immediate as candidate

old_packet=old.packet;old_owner=old.source_owner.owner;old_tb=old.TB


def owner(op=1,length=8193):
    if op not in [5,6]:return old_owner(op,length)
    n=old_owner(3 if op==5 else 1,length)
    return (n&~(0xffff<<324))|(op<<324)|(0x89abcdef<<588)


def packet(op,total,offset,psn):
    if op not in [5,6]:return old_packet(op,total,offset,psn)
    count=min(4096,total-offset);first=offset==0;last=offset+count==total
    code=(0 if first else 3 if last else 1)if op==5 else(6 if first else 9 if last else 7)
    header=bytearray(old.mac.lifetime.request(True)[:28])
    bth=bytes([code,0x40|(((-count)&3)<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
    reth=struct.pack('!QII',0xe23456789abcdef0,0x81234567,total)if op==6 and first else b''
    imm=int(0x89abcdef).to_bytes(4,'big')if last else b''
    payload=bytes((((offset+i)*37)^0xa5)&255 for i in range(count))
    return old.packets.repair(header+bth+reth+imm+payload+bytes((-count)&3)+bytes(4))


class SegmentedImmediateWire(old.SegmentedWireTests):
    reports={}

    def simulate(self,*args,**kwargs):
        saved=(old.candidate,old.packet,old.source_owner.owner,old.TB)
        try:
            old.candidate=candidate;old.packet=packet;old.source_owner.owner=owner
            old.TB=candidate.once(old_tb,"(OPCODE==1 ? 8'h0a:8'h04)",
                "(OPCODE==1 ? 8'h0a:OPCODE==5 ? 8'h05:OPCODE==6 ? 8'h0b:8'h04)")
            super().simulate(*args,**kwargs)
        finally:old.candidate,old.packet,old.source_owner.owner,old.TB=saved

    def test_Immediate_only_on_LAST_same_owner_per_packet_gates_and_one_CQ(self):
        for op in [5,6]:self.simulate(op)

    def test_Immediate_fragment_boundary_padding_and_maximum_span(self):
        for op,total in [(5,4097),(6,8192),(5,1048576)]:self.simulate(op,total)

    def test_valid_CRC_wrong_LAST_Immediate_retains_owner_and_never_CQ(self):
        for op in [5,6]:
            def mutate(frames):
                out=list(frames);p=bytearray(out[-1]);p[40]^=1;out[-1]=old.packets.repair(p);return out
            body=r'''
 transmit(0);expectation(0);positive(0);
 fork transmit(1);receipt(0);join
 expectation(1);positive(1);
 fork transmit(2);receipt(1);join
 repeat(30)@(negedge clk);
 if(!fault || dut.lifetime.fault_code!=8'hb2 || m_cq_valid || committed_count ||
  queue_guard!==8'hff || dut.lifetime.owner!==EXPECTED)$fatal(1,"wrong LAST Immediate escaped ownership checks");
'''
            self.simulate(op,body=body,mutate=mutate,success=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    inputs=[Path(__file__).resolve(),Path(old.__file__).resolve(),*[Path(m.__file__).resolve()for m in list(sys.modules.values())
        if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedImmediateWire))
    same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,tests=SegmentedImmediateWire.reports,four_state=True,
        all5_previous_methods_retained=True,actual_lifetime_replay_framer_tag_EOF_tail=True,
        HLS_memory_RX_ACK_CQ_and_MAC_pins_modeled=True,large_Immediate_max_bytes=1048576,
        default_sources_changed=False,native_or_hardware_runtime=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
