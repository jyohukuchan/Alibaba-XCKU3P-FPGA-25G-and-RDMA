# SPDX-License-Identifier: BSD-2-Clause-Views
"""Production MAC/tag/lifetime composition; physical pins/other proofs/CQ models.

No caller-supplied full-context MAC proof exists: the actual accepted framed
tag must return on MAC completion pins, and actual EOF/tail must drain.
No native runtime, real HLS drain, physical MAC, kernel CQ or recovery claim.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_wqe_lifetime_rtl as life
import test_wqe_mac_tx_rtl as mac

ROOT=life.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_tx_lifetime.v'


def bench(body):
    h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)\s*,?$',h,re.M)
    decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports)
    tb=life.TB.replace('localparam MAX_QPS=8;','localparam MAX_QPS=8,TX_TAG_WIDTH=16,TS_WIDTH=96;')
    tb=tb.replace('// DECLARATIONS',decl).replace('rocev2_wqe_lifetime dut(.*);','rocev2_wqe_tx_lifetime dut(.*);')
    start=tb.index('task transmit;');end=tb.index('endtask',start)+len('endtask')
    tb=tb[:start]+r'''
task transmit;
 input integer length;
 begin
  for(pos=0;pos<length;pos=pos+16)begin
   @(negedge clk);s_axis_ip_tdata=words[pos/16];s_axis_ip_tkeep=pos+16<=length ? 16'hffff : (16'hffff>>(16-length%16));
   s_axis_ip_tlast=pos+16>=length;s_axis_ip_tvalid=1;
   deadline=cycle+100;@(posedge clk);while(!s_axis_ip_tready)begin if(cycle>deadline)$fatal(1,"real TX binding IP deadline");@(posedge clk);end
   @(negedge clk);s_axis_ip_tvalid=0;
  end
 end
endtask'''+tb[end:]
    start=tb.index('task mac;');end=tb.index('endtask',start)+len('endtask')
    tb=tb[:start]+r'''
task mac;
 begin
  deadline=cycle+100;while(frame_count!=1)begin if(cycle>deadline)$fatal(1,"actual framed TX missing");@(negedge clk);end
  @(negedge clk);s_mac_cpl_tag=active_tag;s_mac_cpl_ts=96'hfedcba987654321012345678;s_mac_cpl_valid=1;
  @(posedge clk);if(!s_mac_cpl_ready)$fatal(1,"actual tag receipt not accepted");@(negedge clk);s_mac_cpl_valid=0;#1;
  deadline=cycle+1200;while(!proof_flags[5] || !local_tx_drained)begin
   if(cycle>deadline || fault)$fatal(1,"actual tag/EOF/tail proof join missing");@(negedge clk);
  end
  if(receipt_count!=1 || mac_proof_count!=1 || active_tag!=16'h2001)$fatal(1,"real MAC mapping counters/tag");
 end
endtask'''+tb[end:]
    tb=re.sub(r'\btransport_drained\b','hls_transport_drained',tb)
    tb=tb.replace('// BODY',body).replace('rst=0;enable=1;',
        "rst=0;enable=1;s_owner_local_mac=48'h8af3fbb97531;s_owner_peer_mac=48'hb8830367c5d0;m_axis_mac_tready=1;")
    tb=tb.replace('cycle>3000','cycle>6000')
    return tb.replace('always #2 clk=~clk;',r'''
always #2 clk=~clk;
always @(posedge clk)if(!rst && m_axis_mac_tvalid && m_axis_mac_tready)
 $display("MAC_FRAME %032h %04h %b %05h",m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser);
''')


class WQETXLifetimeTests(unittest.TestCase):
    reports={}

    def simulate(self,body,write=False):
        tb=bench(body);pkt=life.request(write)
        paths=mac.SOURCES+[RTL,life.RTL,Path(__file__).resolve(),Path(life.__file__).resolve(),Path(mac.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(life.packets.__file__).resolve(),
            Path(life.packets.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-tx-lifetime-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            (p/'request.hex').write_text(''.join(f'{int.from_bytes(pkt[n:n+16].ljust(16,bytes([0])),"little"):032x}\n'for n in range(0,len(pkt),16)))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,mac.SOURCES+[life.RTL,RTL])],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[len('WQE_LIFETIME_RESULT '):])for l in r.stdout.splitlines()if l.startswith('WQE_LIFETIME_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            # Real MAC output is independently checked, not just its tag.
            frames=mac.decode_frames(r.stdout)
            if frames:self.assertEqual(frames,[(0x2001,0,bytes.fromhex('b8830367c5d08af3fbb975310800')+pkt)])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_real_MAC_joins_independent_memory_RX_ACK_and_two_drains(self):
        for write in [False,True]:
            for order in [('memory','response','ack','mac'),('mac','ack','response','memory'),
                          ('response','mac','memory','ack'),('ack','memory','mac','response')]:
                self.simulate(life.body_prefix(write)+life.proofs(write,order=order)+'ticket();take_ticket();commit();',write)

    def test_memory_RX_ACK_HLS_drain_cannot_substitute_for_MAC_receipt(self):
        for write in [False,True]:
            self.simulate(life.body_prefix(write)+life.proofs(write,order=('memory','response','ack'))+r'''
memory_drained=1;hls_transport_drained=1;
repeat(1100)begin @(negedge clk);if(m_cq_valid || !busy || local_tx_drained || proof_flags[5] || receipt_count)$fatal(1,"memory/ACK became MAC proof");end
mac();deadline=cycle+100;while(!m_cq_valid)begin if(cycle>deadline)$fatal(1,"final actual MAC join");@(negedge clk);end
take_ticket();commit();
''',write)

    def test_same_edge_duplicate_MAC_or_parent_fault_blocks_CQ_commit(self):
        for fault in ['duplicate',"1'b1","1'bx","1'bz"]:
            body=life.body_prefix()+life.proofs()+'ticket();take_ticket();'
            body+='s_cq_commit_context=expected_owner;s_cq_commit_error=0;s_cq_commit_valid=1;\n'
            body+=("s_mac_cpl_tag=active_tag;s_mac_cpl_ts=96'hfedcba987654321012345678;s_mac_cpl_valid=1;"if fault=='duplicate'else f'parent_fault={fault};')
            body+=r'''
#1;if(s_cq_commit_ready)$fatal(1,"same-edge outer fault acknowledged CQ commit");
@(posedge clk);@(negedge clk);s_cq_commit_valid=0;s_mac_cpl_valid=0;
repeat(17)begin @(negedge clk);if(!fault || !busy || queue_guard!==8'hff || committed_count)$fatal(1,"outer fault released whole-WR owner");end
'''
            self.simulate(body)

    def test_invalid_atomic_broadcast_never_half_captures_owner(self):
        for expr in ["s_owner_peer_qpn='hx;","s_owner_local_ip='hx;","s_owner_peer_mac=0;",
                     "s_owner_context='hx;","s_owner_valid=1'bx;"]:
            self.simulate(f's_owner_context={life.context(opcode=2)};s_owner_local_ip=32\'hc6120b02;s_owner_peer_ip=32\'hc6120b01;s_owner_peer_qpn=196;s_owner_valid=1;'+expr+r'''
#1;if(s_owner_valid===1'b1 && s_owner_ready)$fatal(1,"invalid owner ready");
@(posedge clk);@(negedge clk);s_owner_valid=0;
repeat(17)begin @(negedge clk);if(!fault || !busy || queue_guard!==8'hff || dut.lifetime.active || dut.mac_owner.active || frame_count || committed_count)$fatal(1,"invalid owner half captured");end
''')

    def test_offered_CQ_ticket_stays_owned_when_late_MAC_duplicate_faults(self):
        self.simulate(life.body_prefix()+life.proofs()+'ticket();'+r'''
s_mac_cpl_tag=active_tag;s_mac_cpl_ts=96'hfedcba987654321012345678;s_mac_cpl_valid=1;
@(posedge clk);@(negedge clk);s_mac_cpl_valid=0;
repeat(17)begin @(negedge clk);if(!m_cq_valid || m_cq_context!==expected_owner || !fault || !busy || queue_guard!==8'hff || committed_count)$fatal(1,"late duplicate retracted ticket or released owner");end
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_TX_LIFETIME_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            methods=len(cls.reports);simulations=sum(map(len,cls.reports.values()))
            d=dict(scope=__doc__,pass_test=methods==5 and simulations==20,methods=methods,simulations=simulations,
                tests=cls.reports,actual_MAC_tag_lifetime_binding=True,physical_MAC_other_proofs_CQ_are_models=True,
                actual_native_WR_CQ_runtime=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
