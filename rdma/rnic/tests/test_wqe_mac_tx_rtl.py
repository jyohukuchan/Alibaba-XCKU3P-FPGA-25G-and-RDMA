# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real WQE Ethernet framer/role arbiter/tag-to-owner mapper, modeled MAC pins.

No HLS/native DMA/actual MAC hardware/CQ/Linux runtime or recovery proof.
Finite four-state tests preserve full owner identity and ordinary native traffic.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_wqe_lifetime_rtl as lifetime
from test_wqe_hls_sq_rtl import context

ROOT=lifetime.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_mac_tx.v'
AXIS=ROOT/'external/corundum/fpga/lib/axis/rtl'
SOURCES=[RTL,ROOT/'external/corundum/fpga/lib/eth/rtl/eth_axis_tx.v',
    *[AXIS/n for n in ['axis_arb_mux.v','arbiter.v','priority_encoder.v']]]

TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8,TX_TAG_WIDTH=16,TS_WIDTH=96;
// DECLARATIONS
rocev2_wqe_mac_tx #(.TAG_SEQUENCE_WIDTH(3)) dut(.*);
always #2 clk=~clk;
integer cycle=0,pos,deadline,local_bytes=0,local_frames=0,native_frames=0;
reg [127:0] words[0:7];reg [587:0] expected_owner;
reg stalled=0,proof_stalled=0;reg [161:0] held;reg [691:0] held_proof;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"MAC finite deadline");
 if(stalled && (!m_axis_mac_tvalid || {m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser}!==held))$fatal(1,"MAC output retracted/changed under stall");
 stalled=m_axis_mac_tvalid&&!m_axis_mac_tready;held={m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser};
 if(proof_stalled && (!m_mac_valid || {m_mac_context,m_mac_error,m_mac_timestamp}!==held_proof))$fatal(1,"held MAC proof changed/retracted");
 proof_stalled=m_mac_valid&&!m_mac_ready;held_proof={m_mac_context,m_mac_error,m_mac_timestamp};
 if(m_axis_mac_tvalid && m_axis_mac_tready)begin
  $display("MAC_FRAME %032h %04h %b %05h",m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser);
  if((m_axis_mac_tuser[16:1]&16'he000)==16'h2000)begin
   if(m_axis_mac_tuser[16:1]!==active_tag || (m_axis_mac_tuser[0] && !fault))$fatal(1,"local MAC tag/user");
   local_bytes=local_bytes+$countones(m_axis_mac_tkeep);if(m_axis_mac_tlast)local_frames=local_frames+1;
  end else if(m_axis_mac_tlast)native_frames=native_frames+1;
 end
end
task owner;
 input [587:0] value;
 begin
  @(negedge clk);s_owner_context=value;expected_owner=value;s_owner_local_mac=48'h8af3fbb97531;s_owner_peer_mac=48'hb8830367c5d0;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready || queue_guard!==8'h80)$fatal(1,"MAC owner offer not protected");
  @(negedge clk);s_owner_valid=0;s_owner_context=0;s_owner_local_mac=0;s_owner_peer_mac=0;
  if(!busy || queue_guard!==8'h80 || m_mac_context!==value || local_tx_drained || m_mac_valid)$fatal(1,"MAC full owner snapshot/guard");
 end
endtask
task ip_word;
 input integer n;input integer length;
 begin
  @(negedge clk);s_axis_ip_tdata=words[n/16];s_axis_ip_tkeep=n+16<=length ? 16'hffff : (16'hffff>>(16-length%16));
  s_axis_ip_tlast=n+16>=length;s_axis_ip_tuser=0;s_axis_ip_tvalid=1;
  deadline=cycle+100;@(posedge clk);while(!s_axis_ip_tready)begin if(cycle>deadline)$fatal(1,"IP readiness deadline");@(posedge clk);end
  @(negedge clk);s_axis_ip_tvalid=0;
 end
endtask
task transmit;
 input integer length;
 begin for(pos=0;pos<length;pos=pos+16)ip_word(pos,length);end
endtask
task native;
 input [15:0] tag;
 begin
  @(negedge clk);s_axis_native_tdata=128'h0123456789abcdef_fedcba9876543210;s_axis_native_tkeep=16'hffff;
  s_axis_native_tlast=0;s_axis_native_tuser={tag,1'b0};s_axis_native_tvalid=1;
  deadline=cycle+100;@(posedge clk);while(!s_axis_native_tready)begin if(cycle>deadline)$fatal(1,"native first deadline");@(posedge clk);end
  @(negedge clk);s_axis_native_tdata=128'h0000000000000000_00000000a1b2c3d4;s_axis_native_tkeep=16'h000f;s_axis_native_tlast=1;
  @(posedge clk);while(!s_axis_native_tready)begin if(cycle>deadline)$fatal(1,"native final deadline");@(posedge clk);end
  @(negedge clk);s_axis_native_tvalid=0;
 end
endtask
task receipt;
 input [15:0] tag;
 begin
  @(negedge clk);s_mac_cpl_tag=tag;s_mac_cpl_ts=96'hfe123456789abcdef0123456;s_mac_cpl_valid=1;
  @(posedge clk);if(!s_mac_cpl_ready)$fatal(1,"local receipt unexpectedly blocked");
  @(negedge clk);s_mac_cpl_valid=0;#1;
 end
endtask
task await_frame;
 input integer count;
 begin deadline=cycle+100;while(local_frames!=count)begin if(cycle>deadline)$fatal(1,"framed MAC final deadline");@(negedge clk);end end
endtask
task await_proof;
 begin
  deadline=cycle+1200;while(!m_mac_valid)begin
   if(cycle>deadline || fault || !busy || queue_guard!==8'h80 || local_tx_drained)$fatal(1,"MAC/tail full owner proof deadline");@(negedge clk);
  end
  repeat(17)begin @(negedge clk);if(m_mac_context!==expected_owner || m_mac_error || m_mac_timestamp!==96'hfe123456789abcdef0123456 ||
   !m_mac_valid || !busy || queue_guard!==8'h80 || local_tx_drained)$fatal(1,"held actual receipt/full-owner proof");end
 end
endtask
task consume;
 begin
  m_mac_ready=1;@(posedge clk);@(negedge clk);m_mac_ready=0;
  if(m_mac_valid || busy || queue_guard || !local_tx_drained || fault)$fatal(1,"MAC mapper did not release after its proof handoff");
 end
endtask
task quarantined;
 begin repeat(20)begin @(negedge clk);if(!fault || queue_guard!==8'hff || local_tx_drained || s_owner_ready || proof_count)$fatal(1,"MAC fault released/aliased owner");end end
endtask
initial begin
 $readmemh("request.hex",words);rst=1;repeat(4)@(negedge clk);rst=0;enable=1;m_axis_mac_tready=1;
 // BODY
 $display("WQE_MAC_RESULT {\"pass_test\":true,\"local_frames\":%0d,\"local_bytes\":%0d,\"native_frames\":%0d,\"receipts\":%0d,\"proofs\":%0d,\"fault\":%0d,\"cycles\":%0d}",local_frames,local_bytes,native_frames,receipt_count,proof_count,fault,cycle);
 $finish;
end
endmodule
'''


def decode_frames(stdout):
    result=[];buf=bytearray();tags=[]
    for line in stdout.splitlines():
        if not line.startswith('MAC_FRAME '):continue
        _,data,keep,last,user=line.split();word=int(data,16).to_bytes(16,'little');mask=int(keep,16)
        buf.extend(v for i,v in enumerate(word)if mask>>i&1);tags.append(int(user,16))
        if int(last):
            if len(set(tags))!=1:raise ValueError('interleaved frame roles/tags')
            result.append((tags[0]>>1,tags[0]&1,bytes(buf)));buf=bytearray();tags=[]
    if tags:raise ValueError('unfinished output frame')
    return result


class WQEMACTests(unittest.TestCase):
    reports={}

    def simulate(self,body,write=False,check_frames=True):
        h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
        self.assertEqual(len(ports),50)
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        tb=TB.replace('// DECLARATIONS',decl).replace('// BODY',body);pkt=lifetime.request(write)
        paths=SOURCES+[Path(__file__).resolve(),Path(lifetime.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(lifetime.packets.__file__).resolve(),
            Path(lifetime.packets.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-wqe-mac-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            (p/'request.hex').write_text(''.join(f'{int.from_bytes(pkt[n:n+16].ljust(16,bytes([0])),"little"):032x}\n'for n in range(0,len(pkt),16)))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[len('WQE_MAC_RESULT '):])for l in r.stdout.splitlines()if l.startswith('WQE_MAC_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            frames=decode_frames(r.stdout)if check_frames else []
            if check_frames:
                expected=b'\xb8\x83\x03\x67\xc5\xd0\x8a\xf3\xfb\xb9\x75\x31\x08\x00'+pkt
                for tag,user,frame in frames:
                    self.assertEqual(user,0)
                    if tag&0xe000==0x2000:self.assertEqual(frame,expected)
                    else:
                        self.assertIn(tag,[0,0x4000,0x8001,0xffff])
                        self.assertEqual(frame,bytes.fromhex('1032547698badcfeefcdab8967452301d4c3b2a1'))
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),frames=[dict(tag=t,user=u,hex=p.hex())for t,u,p in frames]))

    def test_actual_framing_role_arbitration_and_full_owner_receipt(self):
        for write in [False,True]:
            self.simulate(f'owner({context(opcode=1 if write else 2)});'+r'''
enable=0;
fork begin repeat(110)begin @(negedge clk);m_axis_mac_tready=cycle%7>2;end m_axis_mac_tready=1;end
begin
fork transmit(LENGTH);begin native(16'h8001);native(0);native(16'h4000);native(16'hffff);end join
end join
await_frame(1);if(m_mac_valid || receipt_count || !busy)$fatal(1,"EOF became MAC receipt");
receipt(active_tag);repeat(1000)begin @(negedge clk);if(m_mac_valid || !busy)$fatal(1,"SFD became EOF/drain");end
await_proof();consume();if(proof_count!=1 || frame_count!=1 || receipt_count!=1 || native_frames!=4)$fatal(1,"MAC positive counts");
'''.replace('LENGTH','128'if write else'60'),write)

    def test_native_completions_preserve_every_tag_timestamp_and_backpressure(self):
        self.simulate(r'''
for(pos=0;pos<4;pos=pos+1)begin
 @(negedge clk);s_mac_cpl_tag=pos==0 ? 16'h8001 : pos==1 ? 16'hffff : pos==2 ? 0 : 16'h4000;
 s_mac_cpl_ts=96'hfeddcba987654321012345678;s_mac_cpl_valid=1;m_native_cpl_ready=0;
 repeat(11)begin @(negedge clk);if(s_mac_cpl_ready || !m_native_cpl_valid || m_native_cpl_tag!==s_mac_cpl_tag || m_native_cpl_ts!==s_mac_cpl_ts || fault || !local_tx_drained)$fatal(1,"native completion stolen/changed");end
 m_native_cpl_ready=1;@(posedge clk);if(!s_mac_cpl_ready)$fatal(1,"native completion ready");@(negedge clk);s_mac_cpl_valid=0;m_native_cpl_ready=0;
end
if(receipt_count || proof_count || busy)$fatal(1,"native completion became local proof");
''')

    def test_SFD_before_output_EOF_and_late_SFD_each_keep_full_tail(self):
        self.simulate(f'owner({context()});'+r'''
ip_word(0,60);ip_word(16,60);
deadline=cycle+100;while(!dut.mac_started)begin if(cycle>deadline)$fatal(1,"no actual first MAC beat");@(negedge clk);end
receipt(active_tag);repeat(1100)begin @(negedge clk);if(m_mac_valid || local_tx_drained || !busy)$fatal(1,"SFD timer completed unfinished frame");end
ip_word(32,60);ip_word(48,60);await_frame(1);
repeat(1000)begin @(negedge clk);if(m_mac_valid)$fatal(1,"tail did not restart after actual final beat");end
await_proof();consume();
''')
        self.simulate(f'owner({context()});transmit(60);await_frame(1);'+r'''
repeat(1100)begin @(negedge clk);if(m_mac_valid)$fatal(1,"no receipt");end
receipt(active_tag);repeat(1000)begin @(negedge clk);if(m_mac_valid)$fatal(1,"late SFD lacked full tail");end
await_proof();consume();
''')

    def test_unissued_wrong_stale_unknown_and_duplicate_receipts_quarantine(self):
        self.simulate(f'owner({context()});receipt(active_tag);quarantined();')
        for bad in ["16'h2000","16'h2002","16'h3fff","16'h1000","16'h200x"]:
            self.simulate(f'owner({context()});transmit(60);await_frame(1);receipt({bad});quarantined();')
        self.simulate(f'owner({context()});transmit(60);await_frame(1);receipt(active_tag);receipt(active_tag);quarantined();')
        self.simulate(f'owner({context()});transmit(60);await_frame(1);'+r'''
@(negedge clk);s_mac_cpl_tag=active_tag;s_mac_cpl_ts='hx;s_mac_cpl_valid=1;
@(posedge clk);@(negedge clk);s_mac_cpl_valid=0;quarantined();
''')

    def test_offered_proof_survives_fault_but_cannot_release_owner(self):
        self.simulate(f'owner({context()});transmit(60);await_frame(1);receipt(active_tag);await_proof();receipt(active_tag);'+r'''
repeat(17)begin @(negedge clk);if(!m_mac_valid || m_mac_context!==expected_owner)$fatal(1,"offered proof retracted on duplicate");end
m_mac_ready=1;repeat(13)@(negedge clk);m_mac_ready=0;quarantined();
native(16'h8001);repeat(20)@(negedge clk);if(native_frames!=1)$fatal(1,"local quarantine halted ordinary host Ethernet");
''')

    def test_nonreused_tags_preserve_distinct_full_epochs_until_exhaustion(self):
        body=''
        for n in range(1,8):
            body+=f'owner({context(sequence=n,epoch=(0xf123456700000000+n))});if(active_tag!=16\'h{0x2000+n:04x})$fatal(1,"tag wrapped/reused");transmit(60);await_frame({n});receipt(active_tag);await_proof();consume();enable=1;\n'
        body+=f's_owner_context={context(sequence=8)};s_owner_local_mac=48\'h8af3fbb97531;s_owner_peer_mac=48\'hb8830367c5d0;s_owner_valid=1;'+r'''
repeat(17)begin @(negedge clk);if(!tags_exhausted || s_owner_ready || fault || !local_tx_drained || proof_count!=7)$fatal(1,"finite tag exhaustion reused identity");end
s_owner_valid=0;native(16'hffff);repeat(20)@(negedge clk);if(native_frames!=1)$fatal(1,"exhaustion blocked native traffic");
'''
        self.simulate(body)

    def test_full_owner_errors_never_narrow_or_authorize_a_MAC_tag(self):
        for ctx in [context(qpn=0x800007),context(sequence=0),context(epoch=0),context(tag=0),context(authorized=0),
            context(error=2),context(flags=2),context(length=0),context(length=4097),context(address=(1<<64)-1,length=2),
            context(remote=(1<<64)-1,length=2),"588'hx"]:
            self.simulate(f's_owner_context={ctx};s_owner_local_mac=48\'h8af3fbb97531;s_owner_peer_mac=48\'hb8830367c5d0;s_owner_valid=1;'+r'''
@(posedge clk);if(s_owner_ready)$fatal(1,"bad full owner accepted");@(negedge clk);s_owner_valid=0;quarantined();if(frame_count || receipt_count)$fatal(1,"bad owner emitted frame");
''')

    def test_malformed_IP_and_reserved_native_tags_fail_closed(self):
        for keep,user in [("16'hffef",0),("16'h0000",0),("16'hffff",1)]:
            self.simulate(f'owner({context()});'+f'''
@(negedge clk);s_axis_ip_tdata=words[0];s_axis_ip_tkeep={keep};s_axis_ip_tlast=1;s_axis_ip_tuser={user};s_axis_ip_tvalid=1;
@(posedge clk);while(!s_axis_ip_tready)@(posedge clk);@(negedge clk);s_axis_ip_tvalid=0;quarantined();
''',check_frames=False)
        for tag in [0x2001,0x1000,0x4001]:
            self.simulate(f's_axis_native_tuser=17\'h{tag<<1:05x};s_axis_native_tvalid=1;s_axis_native_tkeep=16\'hffff;s_axis_native_tlast=1;'+r'''
repeat(3)begin @(posedge clk);if(s_axis_native_tready)$fatal(1,"reserved native tag admitted");@(negedge clk);end
s_axis_native_tvalid=0;quarantined();if(local_frames || native_frames)$fatal(1,"reserved class escaped");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_MAC_TX_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            methods=len(cls.reports);simulations=sum(map(len,cls.reports.values()))
            d=dict(scope=__doc__,pass_test=methods==8 and simulations==33,methods=methods,simulations=simulations,
                tests=cls.reports,real_framer_arbiter_tag_mapper_RTL=True,physical_MAC_pins_are_model=True,
                actual_native_WR_CQ_runtime=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
