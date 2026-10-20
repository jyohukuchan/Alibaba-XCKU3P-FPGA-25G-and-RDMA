# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real Atomic lifetime/framer/mux, HLS/service/physical MAC ports MODELED.

Four-state bounded tests of owner/service/core/packet join and actual tag/
EOF/tail retirement. No native queue/host/physical or global-drain proof.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import probe_atomic_responder as helper
import atomic_mac_wire_fixture as physical

ROOT=helper.ROOT;RTL=helper.RTL/'rocev2_atomic_mac_tx.v'
AXIS=ROOT/'external/corundum/fpga/lib/axis/rtl'
ETH=ROOT/'external/corundum/fpga/lib/eth/rtl'
SOURCES=[RTL,ETH/'eth_axis_tx.v',*[AXIS/n for n in ['axis_arb_mux.v','arbiter.v','priority_encoder.v']]]
sys.path.insert(0,str(ROOT/'rdma/host'));import rocev2_wire as wire


def values(*,drop=False,advance=True,syndrome=0x1f,psn=0xabcdef,epsn=None,msn=6,wire_msn=None):
    epsn=((psn+1)&0xffffff)if advance else ((psn+5)&0xffffff)if epsn is None else epsn
    owner=2|(0x9123456780000001<<24)|(psn<<88)|(0x80001234<<112)
    response_psn=epsn if syndrome==0x60 else psn
    hdr=bytes([0x12 if syndrome==0x1f else 0x11,0])+struct.pack('!HII',0xffff,0xf12347,response_psn)
    hdr+=bytes([syndrome])+(msn if wire_msn is None else wire_msn).to_bytes(3,'big')
    if syndrome==0x1f:hdr+=struct.pack('!Q',0xf123456789abcdef)
    size=0 if drop else len(hdr)
    service=(0 if drop else int.from_bytes(hdr,'little'))|(2<<192)|(psn<<216)|(size<<240)|\
        (int(advance)<<246)|(int(drop)<<247)|(owner<<248)
    flags=7|(int(not drop)<<3)|(int(advance)<<4)|(int(drop)<<5)
    core=owner|(0x13<<144)|(epsn<<152)|(msn<<176)|(flags<<200)
    body=bytearray(hdr);body[1]|=0x40
    ip=bytearray(struct.pack('!BBHHHBBHII',0x45,0,32+len(body),0,0x4000,64,17,0,0xc6120b02,0xc6120b01))
    ip[10:12]=wire.internet_checksum(ip).to_bytes(2,'big')
    p=bytes(ip)+struct.pack('!HHHH',4791,4791,len(body)+12,0)+body+bytes(4)
    p=p[:-4]+wire.icrc_ipv4(p)
    return owner,service,core,p


TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycle=0,i,deadline,atomic_frames=0,native_frames=0,atomic_bytes=0;
reg [143:0] expected_owner=144'hOWNER;
reg [391:0] expected_reply=392'hREPLY;reg [223:0] expected_core=224'hCORE;
reg [127:0] words[0:3];reg stalled=0,retire_stalled=0;reg [161:0] held_mac;reg [479:0] held_retire;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>18000)$fatal(1,"bounded cycle deadline");
 if(stalled && (!m_axis_mac_tvalid || {m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser}!==held_mac))
  $fatal(1,"actual output changed under backpressure");
 stalled=m_axis_mac_tvalid&&!m_axis_mac_tready;held_mac={m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser};
 if(retire_stalled && (!m_retire_valid || {m_retire_owner,m_retire_core,m_retire_tag,m_retire_timestamp}!==held_retire))
  $fatal(1,"offered retirement changed under backpressure");
 retire_stalled=m_retire_valid&&!m_retire_ready;held_retire={m_retire_owner,m_retire_core,m_retire_tag,m_retire_timestamp};
 if(m_axis_mac_tvalid && m_axis_mac_tready)begin
  $display("ATOMIC_MAC_OUT %032h %04h %d %04h",m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser[16:1]);
  if(m_axis_mac_tuser[16:14]==0 && m_axis_mac_tuser[16:1]!=0)begin
   atomic_bytes=atomic_bytes+$countones(m_axis_mac_tkeep);if(m_axis_mac_tlast)atomic_frames=atomic_frames+1;
  end else if(m_axis_mac_tlast)native_frames=native_frames+1;
 end
end
task bind_owner;
 begin
  @(negedge clk);s_owner=expected_owner;s_owner_local_mac=48'h020000000002;s_owner_peer_mac=48'h020000000001;
  s_owner_local_ip=32'hc6120b02;s_owner_peer_ip=32'hc6120b01;s_owner_peer_qpn=24'hf12347;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready || queue_guard!==4)$fatal(1,"genuine owner not offered/protected");
  @(negedge clk);s_owner_valid=0;s_owner=0;s_owner_local_mac=0;s_owner_peer_mac=0;s_owner_local_ip=0;s_owner_peer_ip=0;s_owner_peer_qpn=0;
  if(!busy || !configuration_guard || queue_guard!==4 || m_retire_valid)$fatal(1,"accepted snapshot lost");
 end
endtask
task offer_service;
 begin
  @(negedge clk);s_service_reply=expected_reply;s_service_valid=1;
  @(posedge clk);while(!s_service_ready)@(posedge clk);
  @(negedge clk);s_service_valid=0;
 end
endtask
task offer_core;
 begin
  if(!fault)begin
  @(negedge clk);s_core_done=expected_core;s_core_valid=1;
  @(posedge clk);while(!s_core_ready && !fault)@(posedge clk);
  @(negedge clk);s_core_valid=0;
  end
 end
endtask
task send_ip;
 begin
  for(i=0;i<IP_BYTES && !fault;i=i+16)begin
   @(negedge clk);s_axis_ip_tdata=words[i/16];s_axis_ip_tkeep=i+16>=IP_BYTES && IP_BYTES==56 ? 16'h00ff:16'hffff;
   s_axis_ip_tlast=i+16>=IP_BYTES;s_axis_ip_tvalid=1;
   @(posedge clk);while(!s_axis_ip_tready && !fault)@(posedge clk);
  end
  @(negedge clk);s_axis_ip_tvalid=0;
 end
endtask
task receipt;
 input [15:0] t;
 begin
  @(negedge clk);s_mac_cpl_tag=t;s_mac_cpl_ts=96'h8123456789abcdef12345678;s_mac_cpl_valid=1;
  @(posedge clk);while(!s_mac_cpl_ready)@(posedge clk);
  @(negedge clk);s_mac_cpl_valid=0;
 end
endtask
task await_frame;
 begin
  deadline=cycle+200;while(atomic_frames!=1)begin if(cycle>deadline || fault)$fatal(1,"no atomic Ethernet EOF");@(negedge clk);end
 end
endtask
task await_retire;
 begin
  deadline=cycle+1200;while(!m_retire_valid)begin if(cycle>deadline || fault)$fatal(1,"no genuine owner retirement");@(negedge clk);end
  if(m_retire_owner!==expected_owner || m_retire_core!==expected_core || !busy || !configuration_guard || queue_guard!==4)
   $fatal(1,"retirement lost immutable owner/core");
  repeat(13)@(negedge clk);
 end
endtask
task retire;
 begin
  m_retire_ready=1;@(negedge clk);m_retire_ready=0;
  if(busy || configuration_guard || queue_guard || m_retire_valid || fault)$fatal(1,"valid owner not retired");
 end
endtask
task quarantined;
 begin
  repeat(15)@(negedge clk);
  if(!fault || !busy || !configuration_guard || queue_guard!==8'hff || m_retire_valid)$fatal(1,"fault released/falsely completed owner");
 end
endtask
initial begin
 rst=1;$readmemh("ip.hex",words);repeat(4)@(negedge clk);rst=0;enable=1;m_axis_mac_tready=1;m_native_cpl_ready=1;
 // BODY
 $display("ATOMIC_MAC_RESULT {\"pass_test\":true,\"frames\":%0d,\"native_frames\":%0d,\"bytes\":%0d,\"receipts\":%0d,\"retired\":%0d,\"drops_retired\":%0d,\"cycles\":%0d}",atomic_frames,native_frames,atomic_bytes,receipt_count,retired_count,drop_retired_count,cycle);
 $finish;
end
endmodule
'''


class AtomicMACTests(unittest.TestCase):
    def simulate(self,body,real_mac=False,**options):
        owner,service,core,packet=values(**options);_,positive_reply,positive_core,positive_packet=values()
        if options.get('drop'):packet=positive_packet
        tb=TB.replace('// DECLARATIONS',helper.instance(RTL,'dut','',{}))
        tb=tb.replace('OWNER',f'{owner:036x}').replace('REPLY',f'{service:098x}').replace('CORE',f'{core:056x}')
        tb=tb.replace('IP_BYTES',str(len(packet))).replace('// BODY',body.replace('POS_REPLY',f"392'h{positive_reply:098x}").replace('POS_CORE',f"224'h{positive_core:056x}"))
        sources=list(SOURCES)
        if real_mac:
            import re
            for name in ['m_axis_mac_tready','s_mac_cpl_tag','s_mac_cpl_ts','s_mac_cpl_valid']:
                tb=re.sub(r'reg (\[[^]]+\]\s+)?'+name+r'=0;',lambda m:'wire '+(m[1]or'')+name+';',tb)
            a=tb.index('task receipt;');b=tb.index('endtask',a)+len('endtask');tb=tb[:a]+tb[b:]
            tb=tb.replace('m_axis_mac_tready=1;','')
            connections=r'''
assign link_s_data=m_axis_mac_tdata;assign link_s_keep=m_axis_mac_tkeep;assign link_s_valid=m_axis_mac_tvalid;
assign m_axis_mac_tready=link_s_ready;assign link_s_last=m_axis_mac_tlast;assign link_s_user=m_axis_mac_tuser;
assign s_mac_cpl_tag=link_m_cpl_tag;assign s_mac_cpl_ts=link_m_cpl_ts;assign s_mac_cpl_valid=link_m_cpl_valid;
assign link_m_cpl_ready=s_mac_cpl_ready;
'''
            tb=tb.replace('always #2 clk=~clk;',physical.LINK+connections+'\nalways #2 clk=~clk;')
            sources+=physical.SOURCES
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources}
        with tempfile.TemporaryDirectory(prefix='as02-atomic-mac-')as temporary:
            p=Path(temporary);(p/'tb.v').write_text(tb)
            (p/'ip.hex').write_text(''.join(f'{int.from_bytes(packet[i:i+16].ljust(16,bytes(1)),"little"):032x}\n'for i in range(0,64,16)))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'tb.vvp'),str(p/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'tb.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_MAC_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            frames=[];current=bytearray();current_tag=None
            for line in r.stdout.splitlines():
                if not line.startswith('ATOMIC_MAC_OUT '):continue
                _,data,keep,last,tag=line.split();t=int(tag,16);k=int(keep,16)
                self.assertEqual(k&(k+1),0)
                # AXI does not specify data in lanes whose keep bit is0.
                # Check every VALID byte, not unknown unused framer padding.
                d=bytes(int(data[30-2*i:32-2*i],16)for i in range(16)if (k>>i)&1)
                if current_tag is None:current_tag=t
                self.assertEqual(current_tag,t);current.extend(d)
                if int(last):frames.append((current_tag,bytes(current)));current=bytearray();current_tag=None
            for tag,frame in frames:
                if tag and tag<8192:
                    self.assertEqual(frame,bytes.fromhex('0200000000010200000000020800')+packet)
                    self.assertEqual(wire.internet_checksum(frame[14:34]),0)
                    self.assertEqual(frame[-4:],wire.icrc_ipv4(frame[14:]))
            if real_mac:
                actual=physical.frames(r.stdout)
                self.assertEqual(len(actual),1);self.assertEqual(actual[0][1],bytes.fromhex('0200000000010200000000020800')+packet)
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources})

    def test_positive_requires_consumed_core_real_matching_receipt_EOF_and_tail(self):
        self.simulate(r'''
bind_owner();offer_service();send_ip();repeat(1100)@(negedge clk);
if(atomic_frames || m_retire_valid || fault)$fatal(1,"wire or retire without core receipt");
offer_core();enable=0;await_frame();repeat(1100)@(negedge clk);
if(m_retire_valid || fault)$fatal(1,"EOF/quiet forged SFD receipt");
receipt(active_tag);repeat(900)begin @(negedge clk);if(m_retire_valid)$fatal(1,"tail omitted");end
await_retire();if(m_retire_tag!==active_tag || m_retire_timestamp!==96'h8123456789abcdef12345678)$fatal(1,"actual tag timestamp lost");retire();
''')

    def test_cached_wire_MSN_is_not_current_core_MSN_and_NAK_and_PSN_wrap(self):
        for opt in [dict(advance=False,msn=5,wire_msn=2),dict(advance=False,syndrome=0x60,msn=5),
                    dict(advance=False,syndrome=0x62,msn=0),dict(psn=0xffffff,msn=0)]:
            with self.subTest(options=opt):self.simulate('bind_owner();offer_core();offer_service();send_ip();await_frame();receipt(active_tag);await_retire();retire();',**opt)

    def test_actual_25G_MAC_XGMII_FCS_SFD_and_receipt_CDC(self):
        self.simulate(r'''
bind_owner();offer_service();offer_core();send_ip();await_retire();
if(actual_Atomic_SFD_count!=1 || actual_native_SFD_count || frame_count!=1 || receipt_count!=1 ||
 m_retire_tag!==active_tag || m_retire_timestamp==0)$fatal(1,"missing real MAC SFD/CDC/tag proof");retire();
''',real_mac=True)

    def test_SFD_does_not_replace_unaccepted_EOF(self):
        self.simulate(r'''
bind_owner();offer_service();offer_core();send_ip();
while(!m_axis_mac_tvalid)@(negedge clk);@(negedge clk);m_axis_mac_tready=0;
receipt(active_tag);repeat(1150)begin @(negedge clk);if(m_retire_valid || atomic_frames)$fatal(1,"SFD/delay replaced final MAC beat");end
m_axis_mac_tready=1;await_frame();await_retire();retire();
''')

    def test_existing_native_frames_and_completions_keep_their_tag_classes(self):
        self.simulate(r'''
bind_owner();offer_service();
for(i=0;i<5;i=i+1)begin
 @(negedge clk);s_axis_native_tdata=128'h0123456789abcdef_fedcba9876543210;s_axis_native_tkeep=16'hffff;
 s_axis_native_tlast=1;s_axis_native_tvalid=1;s_axis_native_tuser={i==0 ? 16'd0:i==1 ? 16'h4000:i==2 ? 16'h2001:i==3 ? 16'h6001:16'h9234,1'b0};
 @(posedge clk);while(!s_axis_native_tready)@(posedge clk);
 @(negedge clk);s_axis_native_tvalid=0;
 receipt(s_axis_native_tuser[16:1]);
end
repeat(10)@(negedge clk);
if(atomic_frames || receipt_count || m_retire_valid || native_frames!=5 || fault)$fatal(1,"native class aliased Atomic receipt");
offer_core();send_ip();await_frame();receipt(active_tag);await_retire();retire();
''')

    def test_drop_consumes_actual_core_without_MAC_or_delay_then_next_positive(self):
        self.simulate(r'''
bind_owner();offer_service();repeat(100)@(negedge clk);if(m_retire_valid || atomic_frames)$fatal(1,"service/drop is not core consumed");
offer_core();await_retire();if(m_retire_tag || m_retire_timestamp || atomic_frames || receipt_count)$fatal(1,"drop invented MAC proof");retire();
expected_owner[143:112]=expected_owner[143:112]+1;expected_reply=POS_REPLY;expected_reply[391:248]=expected_owner;
expected_core=POS_CORE;expected_core[143:0]=expected_owner;
bind_owner();offer_core();offer_service();send_ip();await_frame();receipt(active_tag);await_retire();retire();
if(retired_count!=2 || drop_retired_count!=1 || active_tag!=2)$fatal(1,"drop lost forward progress/nonce-tag separation");
''',drop=True,advance=False,msn=5)

    def test_wrong_owner_core_service_or_wire_never_transmits_or_retires(self):
        bodies=["expected_reply[360]=~expected_reply[360];","expected_core[112]=~expected_core[112];",
            "expected_core[202]=1'b0;","expected_core[208]=1'b1;","expected_core[176]=~expected_core[176];",
            "words[0][103:96]=8'hff;","words[2][71:64]=8'hff;","words[3][7:0]=8'hff;"]
        for change in bodies:
            with self.subTest(change=change):self.simulate('bind_owner();'+change+'offer_service();offer_core();send_ip();quarantined();if(atomic_frames)$fatal(1,"bad owner/body transmitted");')

    def test_stale_duplicate_unknown_or_premature_MAC_receipt_never_retires(self):
        for change in ["receipt(16'h0002);","receipt(16'h0000);receipt(active_tag);receipt(active_tag);",
                       "receipt(16'h000x);","receipt(active_tag);"]:
            # Last variant is deliberately BEFORE any generated packet.
            prefix='bind_owner();'if change=='receipt(active_tag);'else'bind_owner();offer_core();offer_service();send_ip();await_frame();'
            with self.subTest(change=change):self.simulate(prefix+change+'quarantined();')

    def test_unknown_owner_does_not_acquire_wire_authority(self):
        for change in ["s_owner[23:0]=24'h800002;","s_owner[87:24]=0;","s_owner[143:140]=4'hx;",
                       "s_owner_local_mac=48'h030000000002;"]:
            with self.subTest(change=change):self.simulate(r'''
@(negedge clk);s_owner=expected_owner;s_owner_local_mac=48'h020000000002;s_owner_peer_mac=48'h020000000001;
s_owner_valid=1;'''+change+r'''
repeat(5)@(negedge clk);if(!fault || !configuration_guard || s_owner_ready || m_retire_valid || atomic_frames)$fatal(1,"unknown owner acquired authority");
''')


if __name__=='__main__':unittest.main()
