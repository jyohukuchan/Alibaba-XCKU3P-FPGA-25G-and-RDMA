# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state Atomic packet/lease guard; integrity/downstream are MODELS."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import probe_atomic_generated as probe

RTL=probe.ROOT/'rdma/rnic/rtl/rocev2_atomic_packet_guard.v'
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
reg [145:0] input_words[0:4];reg [31:0] first_tag=0;integer cycle=0,j,forwarded=0;
reg stalled=0;reg [144:0] held;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>1500)$fatal(1,"bounded cycle deadline");
 if(stalled && (!m_axis_tvalid || {m_axis_tlast,m_axis_tkeep,m_axis_tdata}!==held))$fatal(1,"forwarded beat lost");
 stalled=m_axis_tvalid&&!m_axis_tready;held={m_axis_tlast,m_axis_tkeep,m_axis_tdata};
 if(m_axis_tvalid && m_axis_tready)begin
  if({m_axis_tlast,m_axis_tkeep,m_axis_tdata}!==input_words[forwarded%5][144:0])$fatal(1,"unchanged wire bytes");
  forwarded=forwarded+1;
 end
end
task send;
 begin
  for(j=0;j<5;j=j+1)begin
   @(negedge clk);{s_axis_tlast,s_axis_tkeep,s_axis_tdata}=input_words[j][144:0];
   // MUTATION
   s_axis_tvalid=1;@(posedge clk);while(!s_axis_tready)@(posedge clk);
  end
  @(negedge clk);s_axis_tvalid=0;repeat(4)@(negedge clk);
 end
endtask
task owned;
 begin
  m_axis_tready=1;m_owner_ready=1;
  while(forwarded%5!=0 || !forwarded)@(negedge clk);
  repeat(4)@(negedge clk);m_owner_ready=0;m_axis_tready=0;
  if(!busy || !configuration_guard || m_owner_valid || m_axis_tvalid)$fatal(1,"released before retirement");
 end
endtask
task retire;
 begin
  @(negedge clk);s_retire_qpn=2;s_retire_epoch=64'h9123456780000001;
  s_retire_psn=24'hfffffe;s_retire_tag=m_owner_tag;s_retire_valid=1;
  @(posedge clk);if(!s_retire_ready)$fatal(1,"matching owner not retireable");
  @(negedge clk);s_retire_valid=0;repeat(3)@(negedge clk);
  if(busy || configuration_guard || fault)$fatal(1,"successful ownership handoff failed");
 end
endtask
initial begin
 rst=1;$readmemh("input.hex",input_words);repeat(4)@(negedge clk);rst=0;enable=1;
 trusted_valid=1;trusted_qpn=2;trusted_epoch=64'h9123456780000001;
 trusted_local_ip=32'hc6120b02;trusted_peer_ip=32'hc6120b01;
 // BODY
 $display("ATOMIC_GUARD_RESULT {\"pass_test\":true,\"cycles\":%0d,\"forwarded\":%0d}",cycle,forwarded);$finish;
end
endmodule
'''


class AtomicPacketGuardTests(unittest.TestCase):
    def simulate(self,body,packet=None,mutation=''):
        packet=packet or probe.packet(19,2,0xfffffe,0x8123456789abcdef,0xf123456789abcdef)
        words=[]
        for offset in range(0,len(packet),16):
            part=packet[offset:offset+16]
            words.append(int.from_bytes(part.ljust(16,b'\0'),'little')|(((1<<len(part))-1)<<128)|(int(offset+16>=len(packet))<<144))
        tb=TB.replace('// DECLARATIONS',probe.fixture.prior.rtl.instance(RTL,'dut','',{}))
        tb=tb.replace('// BODY',body).replace('// MUTATION',mutation)
        before=probe.fixture.prior.digest(RTL)
        with tempfile.TemporaryDirectory(prefix='as02-atomic-packet-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'input.hex').write_text(''.join(f'{x:x}\n'for x in words))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_GUARD_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,probe.fixture.prior.digest(RTL))

    def test_full_packet_trusted_snapshot_stable_owner_and_unique_duplicate_tags(self):
        self.simulate(r'''
send();if(!m_axis_tvalid || !m_owner_valid || m_owner_qpn!==2 || m_owner_epoch!==64'h9123456780000001 ||
 m_owner_psn!==24'hfffffe || m_owner_tag!==1)$fatal(1,"full validated owner");
first_tag=m_owner_tag;trusted_qpn=3;trusted_epoch=64'hffffffffffffffff;trusted_peer_ip=0;enable=0;
repeat(13)begin @(negedge clk);
 if(!m_axis_tvalid || !m_owner_valid || m_owner_qpn!==2 || m_owner_epoch!==64'h9123456780000001 || !configuration_guard)
  $fatal(1,"mutable trusted input/disable replaced accepted owner");
end
owned();retire();
trusted_qpn=2;trusted_epoch=64'h9123456780000001;trusted_peer_ip=32'hc6120b01;enable=1;
send();if(m_owner_tag!==2 || m_owner_tag==first_tag)$fatal(1,"same PSN reused packet tag");
// forwarded==5 from first packet, so explicitly wait for the second EOF.
m_axis_tready=1;m_owner_ready=1;while(forwarded!=10)@(negedge clk);
repeat(4)@(negedge clk);m_axis_tready=0;m_owner_ready=0;retire();
''')

    def test_wrong_peer_QP_format_or_unknown_valid_bytes_never_forward(self):
        frames=[probe.packet(19,4,0xfffffe,1),probe.packet(19,2,0xfffffe,1,source='198.18.11.99'),
                probe.packet(19,2,0xfffffe,1,flags=0x10),probe.packet(19,2,0xfffffe,1,flags=0x80)]
        for frame in frames:
            with self.subTest(frame=frame.hex()):self.simulate('send();repeat(5)@(negedge clk);if(forwarded || m_owner_valid || accepted_count || dropped_count!=1 || busy)$fatal(1,"bad admission");',frame)
        for mutation in ["if(j==2)s_axis_tdata[7:0]=8'hxx;","if(j==2)s_axis_tkeep=16'hfff7;",
                         "if(j==4)s_axis_tkeep=16'h00xf;"]:
            with self.subTest(mutation=mutation):self.simulate('send();repeat(5)@(negedge clk);if(forwarded || m_owner_valid || accepted_count || dropped_count!=1 || busy)$fatal(1,"unknown/malformed admission");',mutation=mutation)

    def test_old_retirement_tag_cannot_release_new_duplicate_packet(self):
        self.simulate(r'''
send();first_tag=m_owner_tag;owned();retire();send();
m_axis_tready=1;m_owner_ready=1;while(forwarded!=10)@(negedge clk);repeat(4)@(negedge clk);
s_retire_qpn=2;s_retire_epoch=64'h9123456780000001;s_retire_psn=24'hfffffe;
s_retire_tag=first_tag;s_retire_valid=1;repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h92 || !busy || !configuration_guard || s_retire_ready)$fatal(1,"stale packet retired reused PSN");
''')

    def test_missing_or_unknown_trusted_epoch_does_not_gain_packet_authority(self):
        for change in ['trusted_valid=0;','trusted_epoch=0;',"trusted_epoch[63:60]=4'hx;",'trusted_qpn=24\'h800002;']:
            with self.subTest(change=change):self.simulate(change+r'''
send();repeat(5)@(negedge clk);
if(forwarded || m_owner_valid || accepted_count || dropped_count!=1 || busy)$fatal(1,"untrusted epoch/QPN admitted");
''')


if __name__=='__main__':unittest.main()
