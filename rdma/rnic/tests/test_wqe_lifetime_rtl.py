# SPDX-License-Identifier: BSD-2-Clause-Views
"""Production issued-PSN/WR-lifetime proof join; TX/proof/CQ/drains are MODELS.

Actual hardware decisions, full identities and persistent ownership are tested.
Not an actual TX-integrity/MAC publisher/native CQ/Linux lifetime implementation.
"""
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_wqe_hls_sq_rtl import context,DEFAULT
import test_wqe_response_guard_rtl as packets

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_lifetime.v'


def request(write=False,psn=0xfffffe):
    wire=packets.read_wire
    if write:
        from rocev2_wire import write_only_frame
        return write_only_frame(source_mac='8a:f3:fb:b9:75:31',destination_mac='b8:83:03:67:c5:d0',udp_source_port=49152,
            source_ip='198.18.11.2',destination_ip='198.18.11.1',destination_qpn=196,
            psn=psn,remote_address=DEFAULT[12],rkey=0,payload=bytes(i^0x5a for i in range(65)),bth_flags=0x40)[14:]
    return wire.encode(opcode=wire.REQUEST,source_ip='198.18.11.2',destination_ip='198.18.11.1',destination_qpn=196,
        psn=psn,remote_address=DEFAULT[12],rkey=0,read_bytes=65)[14:]


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
rocev2_wqe_lifetime dut(.*);
always #2 clk=~clk;
reg [127:0] words[0:7];reg [587:0] expected_owner;integer cycle=0,pos,deadline;
reg es=0,cs=0;reg [675:0] held_expect;reg [587:0] held_cq;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>3000)$fatal(1,"lifetime finite deadline");
 if(es && (!m_expect_valid || {m_expect_context,m_expect_local_ip,m_expect_peer_ip,m_expect_psn}!==held_expect))$fatal(1,"issued expectation changed/retracted");
 if(cs && (!m_cq_valid || m_cq_context!==held_cq))$fatal(1,"prepared CQ ticket changed/retracted");
 es=m_expect_valid&&!m_expect_ready;held_expect={m_expect_context,m_expect_local_ip,m_expect_peer_ip,m_expect_psn};
 cs=m_cq_valid&&!m_cq_ready;held_cq=m_cq_context;
end
task owner;
 input [587:0] ctx;
 begin
  @(negedge clk);s_owner_context=ctx;expected_owner=ctx;s_owner_local_ip=32'hc6120b02;s_owner_peer_ip=32'hc6120b01;s_owner_peer_qpn=196;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready || queue_guard!==8'h80)$fatal(1,"WR owner capture/offer guard");
  @(negedge clk);s_owner_valid=0;s_owner_context=0;s_owner_local_ip=0;s_owner_peer_ip=0;s_owner_peer_qpn=0;
  if(!busy || queue_guard!==8'h80 || m_cq_context!==ctx || m_expect_valid || m_cq_valid)$fatal(1,"full WR owner not saved");
 end
endtask
task transmit;
 input integer length;
 begin
  for(pos=0;pos<length;pos=pos+16)begin
   s_tx_data=words[pos/16];s_tx_keep=pos+16<=length ? 16'hffff : (16'hffff>>(16-length%16));s_tx_last=pos+16>=length;s_tx_valid=1;
   s_tx_ready=0;repeat(3)begin @(negedge clk);if(m_expect_valid || response_admission_ready || m_cq_valid)$fatal(1,"unaccepted/partial TX authorized response or CQ");end
   s_tx_ready=1;@(posedge clk);@(negedge clk);s_tx_ready=0;s_tx_valid=0;
  end
 end
endtask
task expectation;
 input [23:0] psn;
 begin
  deadline=cycle+100;while(!m_expect_valid)begin if(cycle>deadline)$fatal(1,"actual TX-derived expectation missing");@(negedge clk);end
  enable=0;
  repeat(13)begin @(negedge clk);if(m_expect_context!==expected_owner || m_expect_psn!==psn || m_expect_local_ip!==32'hc6120b02 ||
   m_expect_peer_ip!==32'hc6120b01 || response_admission_ready || m_cq_valid || !busy || fault)$fatal(1,"issued PSN/context/peer mismatch");end
  m_expect_ready=1;@(posedge clk);@(negedge clk);m_expect_ready=0;
  if(!response_admission_ready || m_expect_valid || proof_flags[1:0]!=3)$fatal(1,"RX enabled before real expectation capture");
 end
endtask
task memory;
 begin s_memory_context=expected_owner;s_memory_error=0;s_memory_valid=1;
  @(posedge clk);if(!s_memory_ready)$fatal(1,"memory proof acceptance");@(negedge clk);s_memory_valid=0;end
endtask
task response;
 input [23:0] psn;input [7:0] op;
 begin s_response_context=expected_owner;s_response_psn=psn;s_response_opcode=op;s_response_syndrome=8'h1f;s_response_valid=1;
  @(posedge clk);if(!s_response_ready)$fatal(1,"response proof acceptance");@(negedge clk);s_response_valid=0;end
endtask
task ack;
 input [39:0] value;
 begin s_hls_ack=value;s_hls_ack_valid=1;@(posedge clk);if(!s_hls_ack_ready)$fatal(1,"HLS ACK acceptance");@(negedge clk);s_hls_ack_valid=0;end
endtask
task mac;
 begin s_mac_context=expected_owner;s_mac_error=0;s_mac_valid=1;
  @(posedge clk);if(!s_mac_ready)$fatal(1,"MAC proof acceptance");@(negedge clk);s_mac_valid=0;end
endtask
task ticket;
 begin
  repeat(11)begin @(negedge clk);if(m_cq_valid || !busy || queue_guard!==8'h80 || committed_count)$fatal(1,"proofs substituted for actual drains/CQ commit");end
  memory_drained=1;repeat(11)begin @(negedge clk);if(m_cq_valid)$fatal(1,"memory drain substituted for transport drain");end
  transport_drained=1;deadline=cycle+100;while(!m_cq_valid)begin if(cycle>deadline)$fatal(1,"all-proof CQ ticket missing");@(negedge clk);end
  repeat(13)begin @(negedge clk);if(!m_cq_valid || m_cq_context!==expected_owner || !busy || queue_guard!==8'h80 || fault)$fatal(1,"held CQ ticket lost owner");end
 end
endtask
task take_ticket;
 begin m_cq_ready=1;@(posedge clk);@(negedge clk);m_cq_ready=0;
  repeat(17)begin @(negedge clk);if(m_cq_valid || !busy || queue_guard!==8'h80 || committed_count || proof_flags!==7'h7f)$fatal(1,"ticket acceptance mistaken for CQ publication/commit");end
 end
endtask
task commit;
 begin
  s_cq_commit_context=expected_owner;s_cq_commit_error=0;s_cq_commit_valid=1;
  @(posedge clk);if(!s_cq_commit_ready)$fatal(1,"exact CQ commit missing");@(negedge clk);s_cq_commit_valid=0;
  if(busy || queue_guard || fault || committed_count!=1)$fatal(1,"exact final commit did not retire WR");
 end
endtask
initial begin
 $readmemh("request.hex",words);rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("WQE_LIFETIME_RESULT {\"pass_test\":true,\"proofs\":%0d,\"committed\":%0d,\"fault\":%0d,\"cycles\":%0d}",proof_flags,committed_count,fault,cycle);
 $finish;
end
endmodule
'''


def body_prefix(write=False,psn=0xfffffe):
    return f'owner({context(opcode=1 if write else 2)});transmit({128 if write else 60});expectation(24\'h{psn:06x});'


def proofs(write=False,psn=0xfffffe,order=('memory','response','ack','mac')):
    a=(psn<<11)|(7<<1)|int(write)
    actions={'memory':'memory();','response':f'response(24\'h{psn:06x},8\'h{17 if write else 16:02x});','ack':f'ack(40\'h{a:010x});','mac':'mac();'}
    return ''.join(actions[v]for v in order)


class WQELifetimeTests(unittest.TestCase):
    reports={}

    def simulate(self,body,write=False,psn=0xfffffe,packet=None):
        h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
        self.assertEqual(len(ports),55)
        d='\n'.join(('reg 'if k=='input'else'wire ')+(w or'')+n+('=0;'if k=='input'else';')for k,w,n in ports)
        tb=TB.replace('// DECLARATIONS',d).replace('// BODY',body);pkt=packet if packet is not None else request(write,psn)
        words=[int.from_bytes(pkt[i:i+16].ljust(16,b'\0'),'little')for i in range(0,len(pkt),16)]
        paths=[RTL,Path(__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(packets.__file__).resolve(),
            Path(packets.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-wqe-lifetime-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'request.hex').write_text(''.join(f'{v:032x}\n'for v in words))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            run=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            rows=[json.loads(l[20:])for l in run.stdout.splitlines()if l.startswith('WQE_LIFETIME_RESULT ')]
            self.assertEqual(len(rows),1,run.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),TX_packet_sha256=hashlib.sha256(pkt).hexdigest()))

    def test_WRITE_READ_PSN_extremes_and_proof_orders_do_not_retire_before_exact_commit(self):
        for write,psn,order in itertools.product([False,True],[0,0xfffffe,0xffffff],[('ack','response','memory','mac'),('mac','memory','response','ack')]):
            self.simulate(body_prefix(write,psn)+proofs(write,psn,order)+'ticket();take_ticket();commit();',write,psn)

    def test_each_missing_proof_or_drain_prevents_new_CQ_ticket(self):
        for absent in ['memory','response','ack','mac']:
            self.simulate(body_prefix()+proofs(order=[p for p in ['memory','response','ack','mac']if p!=absent])+r'''
memory_drained=1;transport_drained=1;repeat(19)@(negedge clk);
if(m_cq_valid || committed_count || !busy || queue_guard!==8'h80 || fault)$fatal(1,"missing actual proof became CQ ticket");
''')

    def test_valid_integrity_TX_metadata_mismatch_never_authorizes_expected_response(self):
        for index in [12,16,28,29,30,35,40,48,55]:
            pkt=bytearray(request());pkt[index]^=1;pkt=packets.repair(pkt)
            self.simulate(f'owner({context(opcode=2)});transmit(60);'+r'''
repeat(13)@(negedge clk);if(!fault || fault_code!=8'hb2 || m_expect_valid || response_admission_ready || m_cq_valid || queue_guard!==8'hff)$fatal(1,"wrong own-TX WQE/peer metadata became RX authority");
''',packet=pkt)

    def test_full_memory_response_and_MAC_identity_never_uses_shortened_or_stale_context(self):
        good=int(context(opcode=2).split("'h")[1],16)
        for port,code in [('memory',0xb3),('response',0xb4),('mac',0xb6)]:
            for bit in [0,19,50,150,260,310,400,500,587]:
                inject=f's_{port}_context=588\'h{good^(1<<bit):0147x};s_{port}_valid=1;'
                if port=='response':inject+="s_response_psn=24'hfffffe;s_response_opcode=8'h10;s_response_syndrome=8'h1f;"
                self.simulate(body_prefix()+inject+f'repeat(7)@(negedge clk);if(!fault || fault_code!=8\'h{code:02x} || m_cq_valid || queue_guard!==8\'hff)$fatal(1,"wrong full proof identity acquired completion authority");')

    def test_HLS_ACK_full_QPN_PSN_kind_and_padding_cannot_substitute_for_memory(self):
        a=(0xfffffe<<11)|(7<<1)
        for bit in [0,1,11,34,35,39]:
            self.simulate(body_prefix()+f's_hls_ack=40\'h{a^(1<<bit):010x};s_hls_ack_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'hb5 || m_cq_valid || queue_guard!==8'hff)$fatal(1,"wrong HLS ACK became completion");
''')

    def test_memory_and_MAC_error_are_exact_quarantine_not_success(self):
        for port,code in [('memory',0xb3),('mac',0xb6)]:
            self.simulate(body_prefix()+f's_{port}_context=expected_owner;s_{port}_error=8\'ha5;s_{port}_valid=1;'+f'''
@(posedge clk);if(!s_{port}_ready)$fatal(1,"matching error proof not consumed");@(negedge clk);s_{port}_valid=0;
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h{code:02x} || failed_status!=8'ha5 || !busy || m_cq_valid || queue_guard!==8'hff)$fatal(1,"backend error became safe completion");
''')

    def test_early_bad_stale_or_nondrained_CQ_commit_cannot_release_WR(self):
        self.simulate(body_prefix()+r'''
s_cq_commit_context=expected_owner;s_cq_commit_valid=1;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'hb7 || s_cq_commit_ready || committed_count || queue_guard!==8'hff)$fatal(1,"early commit released WR");
''')
        for inject in ["s_cq_commit_context=0;", "s_cq_commit_error=1;", "memory_drained=0;"]:
            self.simulate(body_prefix()+proofs()+'ticket();take_ticket();s_cq_commit_context=expected_owner;'+inject+r'''
s_cq_commit_valid=1;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'hb7 || s_cq_commit_ready || committed_count || queue_guard!==8'hff)$fatal(1,"bad/stale/nondrained commit released WR");
''')

    def test_already_offered_expectation_and_ticket_survive_fault_but_do_not_commit(self):
        self.simulate(f'owner({context(opcode=2)});transmit(60);'+r'''
deadline=cycle+100;while(!m_expect_valid)begin if(cycle>deadline)$fatal(1,"held expectation");@(negedge clk);end
repeat(7)@(negedge clk);s_hls_ack_valid=1;
repeat(7)@(negedge clk);if(!fault || !m_expect_valid || response_admission_ready || queue_guard!==8'hff || m_cq_valid)$fatal(1,"fault retracted expectation or authorized new work");
''')
        self.simulate(body_prefix()+proofs()+'ticket();s_memory_context=expected_owner;s_memory_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || !m_cq_valid || m_cq_context!==expected_owner || queue_guard!==8'hff)$fatal(1,"fault retracted already-offered CQ ticket");
m_cq_ready=1;@(posedge clk);@(negedge clk);m_cq_ready=0;
if(!busy || committed_count || queue_guard!==8'hff)$fatal(1,"fault-ticket handshake freed pages");
''')

    def test_same_cycle_bad_duplicate_prevents_NEW_CQ_offer(self):
        a=(0xfffffe<<11)|(7<<1)
        self.simulate(body_prefix()+proofs()+f's_hls_ack=40\'h{a:010x};s_hls_ack_valid=1;memory_drained=1;transport_drained=1;'+r'''
repeat(7)@(negedge clk);if(!fault || m_cq_valid || committed_count || queue_guard!==8'hff)$fatal(1,"concurrent bad proof created new CQ ticket");
''')

    def test_invalid_unknown_and_overflowed_full_owner_never_gets_lifetime_authority(self):
        cases=[context(opcode=0),context(flags=2),context(authorized=0),context(available=0),context(qpn=0x800007),
            context(epoch=0),context(sequence=0),context(tag=0),context(length=0),context(length=4097),
            context(address=(1<<64)-1,length=2),context(offset=(1<<64)-1,length=2),context(remote=(1<<64)-1,length=2),"{4'hx,584'd0}"]
        for c in cases:self.simulate(f's_owner_context={c};s_owner_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'hb1 || s_owner_ready || m_expect_valid || m_cq_valid || queue_guard!==8'hff || committed_count)$fatal(1,"bad full owner acquired lifetime");
''')

    def test_WRITE_memory_source_can_finish_before_wire_issue_without_releasing_WR(self):
        self.simulate(f'owner({context()});memory();'+r'''
repeat(11)begin @(negedge clk);if(m_expect_valid || m_cq_valid || committed_count || !busy || queue_guard!==8'h80 || fault)$fatal(1,"early source-memory status became transport completion");end
transmit(128);expectation(24'hfffffe);
'''+proofs(write=True,order=('ack','mac','response'))+'ticket();take_ticket();commit();',write=True)

    def test_same_cycle_bad_proof_blocks_even_an_exact_final_CQ_commit(self):
        a=(0xfffffe<<11)|(7<<1)
        self.simulate(body_prefix()+proofs()+'ticket();take_ticket();'+f's_hls_ack=40\'h{a:010x};s_hls_ack_valid=1;'+r'''
s_cq_commit_context=expected_owner;s_cq_commit_error=0;s_cq_commit_valid=1;
repeat(7)@(negedge clk);if(!fault || s_cq_commit_ready || committed_count || !busy || queue_guard!==8'hff)$fatal(1,"concurrent fault outran exact CQ commit/MR release");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_LIFETIME_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            simulations=sum(map(len,cls.reports.values()))
            d=dict(scope=__doc__,pass_test=len(cls.reports)==12 and simulations==83,methods=len(cls.reports),simulations=simulations,tests=cls.reports,
                TX_integrity_proofs_MAC_drain_and_CQ_models=True,real_native_CQ_or_runtime=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
