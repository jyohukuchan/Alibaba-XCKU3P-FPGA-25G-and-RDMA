# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual whole-packet integrity/trusted-WQE response protection and replay.

Expected issued peer/PSN/WQE and downstream executor/HLS/wire/CQ are MODELS.
This is a real receive protection component, not native placement or CQ proof.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_wqe_hls_sq_rtl import context

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/read/host'))
import read_wire

RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_response_guard.v'
SOURCES=[RTL,ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',
    ROOT/'external/corundum/fpga/lib/axis/rtl/axis_fifo.v',
    ROOT/'external/corundum/fpga/lib/axis/rtl/axis_register.v',
    ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']


def packet(write=False,length=65,mig=0,syndrome=0x1f,qpn=7,psn=0xfffffe):
    p=bytearray(read_wire.encode(opcode=read_wire.ONLY,source_ip='198.18.11.1',destination_ip='198.18.11.2',
        destination_qpn=qpn,psn=psn,payload=bytes((i*131^0x5a)&255 for i in range(length)),syndrome=syndrome)[14:])
    if write:p=p[:44]+bytearray(4);p[28]=0x11;p[29]=0
    p[29]|=mig<<6
    return repair(p)


def repair(p):
    p=bytearray(p);p[2:4]=len(p).to_bytes(2,'big');p[24:26]=(len(p)-20).to_bytes(2,'big')
    p[10:12]=b'\0\0';p[10:12]=read_wire.internet_checksum(p[:20]).to_bytes(2,'big')
    p[-4:]=read_wire.icrc_ipv4(p);return bytes(p)


def declarations():
    h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
    if len(ports)!=47:raise ValueError(('response interface changed',len(ports)))
    return '\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in ports if n!='m_axis_hls_rx_tready')+\
        '\nwire m_axis_hls_rx_tready=allow_forward && cycle%11>2;'


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
localparam [7:0] EXPECTED_GUARD=8'h80;
localparam [23:0] EXPECTED_PSN=24'hfffffe;
reg allow_forward=0;integer cycle=0;
// DECLARATIONS
rocev2_wqe_response_guard dut(.*);
always #2 clk=~clk;
reg [127:0] frames[0:2047];integer deadline,position,expected_start=0,expected_bytes=0,forwarded=0,tokens=0,events=0;
reg hs=0,ts=0,es=0;reg [144:0] held_frame;reg [587:0] held_token;reg [627:0] held_event;
reg [587:0] expected_owner;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>25000)$fatal(1,"response finite-cycle deadline");
 if(hs && (!m_axis_hls_rx_tvalid || {m_axis_hls_rx_tlast,m_axis_hls_rx_tkeep,m_axis_hls_rx_tdata}!==held_frame))$fatal(1,"response HLS replay retracted/changed");
 if(ts && (!m_read_response_valid || m_read_response_context!==held_token))$fatal(1,"placement token retracted/changed");
 if(es && (!m_response_event_valid || {m_response_event_context,m_response_event_psn,m_response_event_opcode,m_response_event_syndrome}!==held_event))$fatal(1,"response event changed");
 hs=m_axis_hls_rx_tvalid&&!m_axis_hls_rx_tready;held_frame={m_axis_hls_rx_tlast,m_axis_hls_rx_tkeep,m_axis_hls_rx_tdata};
 ts=m_read_response_valid&&!m_read_response_ready;held_token=m_read_response_context;
 es=m_response_event_valid&&!m_response_event_ready;held_event={m_response_event_context,m_response_event_psn,m_response_event_opcode,m_response_event_syndrome};
 // This RTL's guarded token transfer also requires the downstream lease.
 // The deliberate missing-guard fault injection is NOT a legal acceptance;
 // that case separately proves sticky fault and retained token/all guards.
 if(m_read_response_valid && m_read_response_ready && downstream_queue_guard===EXPECTED_GUARD)begin
  if(m_read_response_context!==expected_owner || m_axis_hls_rx_tvalid)$fatal(1,"actual READ placement authority/order");
  tokens=tokens+1;
 end
 if(m_axis_hls_rx_tvalid && m_axis_hls_rx_tready)begin
  if(forwarded*16>=expected_bytes || m_axis_hls_rx_tdata!==frames[expected_start+forwarded] ||
    m_axis_hls_rx_tlast!==(16*(forwarded+1)>=expected_bytes) || downstream_queue_guard!==EXPECTED_GUARD)$fatal(1,"actual response bytes/peer ownership changed");
  if(m_axis_hls_rx_tkeep!==(16*(forwarded+1)<=expected_bytes ? 16'hffff : (16'hffff>>(16-expected_bytes%16))))$fatal(1,"response replay keep");
  forwarded=forwarded+1;
 end
 if(m_response_event_valid && m_response_event_ready)events=events+1;
end
task expect_owner;
 input [587:0] value;
 begin
  @(negedge clk);s_expect_context=value;expected_owner=value;s_expect_local_ip=32'hc6120b02;s_expect_peer_ip=32'hc6120b01;s_expect_psn=EXPECTED_PSN;s_expect_valid=1;
  @(posedge clk);if(!s_expect_ready || queue_guard!==EXPECTED_GUARD)$fatal(1,"trusted expectation capture/guard");
  @(negedge clk);s_expect_valid=0;s_expect_context=0;
  if(m_response_event_context!==value || !busy || queue_guard!==EXPECTED_GUARD)$fatal(1,"full response owner lost");
 end
endtask
task send;
 input integer start,nbytes;
 begin
  deadline=cycle+5000;
  for(position=0;position<nbytes;position=position+16)begin
   @(negedge clk);s_axis_rx_tdata=frames[start+position/16];s_axis_rx_tkeep=position+16<=nbytes ? 16'hffff : (16'hffff>>(16-nbytes%16));
   s_axis_rx_tlast=position+16>=nbytes;s_axis_rx_tvalid=1;
   @(posedge clk);while(!s_axis_rx_tready)begin if(cycle>deadline)$fatal(1,"protected RX input deadline");@(posedge clk);end
  end
  @(negedge clk);s_axis_rx_tvalid=0;
 end
endtask
task token;
 begin
  deadline=cycle+5000;while(!m_read_response_valid)begin if(cycle>deadline)$fatal(1,"READ context token deadline");@(negedge clk);end
  enable=0;halt=1;
  repeat(13)begin @(negedge clk);if(!m_read_response_valid || m_read_response_context!==expected_owner || m_axis_hls_rx_tvalid || fault || !busy || queue_guard!==EXPECTED_GUARD)$fatal(1,"premature READ/HLS/owner release");end
  downstream_queue_guard=EXPECTED_GUARD;m_read_response_ready=1;@(posedge clk);@(negedge clk);m_read_response_ready=0;
 end
endtask
task forward;
 input integer start,nbytes;input [7:0] op,syndrome;
 begin
  expected_start=start;expected_bytes=nbytes;forwarded=0;downstream_queue_guard=EXPECTED_GUARD;allow_forward=0;
  deadline=cycle+5000;while(!m_axis_hls_rx_tvalid)begin if(cycle>deadline)$fatal(1,"protected replay deadline");@(negedge clk);end
  repeat(9)@(negedge clk);allow_forward=1;
  while(!m_response_event_valid)begin if(cycle>deadline)$fatal(1,"protected response event deadline");@(negedge clk);end
  allow_forward=0;
  repeat(11)begin @(negedge clk);if(m_response_event_context!==expected_owner || m_response_event_psn!==EXPECTED_PSN ||
   m_response_event_opcode!==op || m_response_event_syndrome!==syndrome || forwarded!=(nbytes+15)/16 || fault || !busy || queue_guard!==EXPECTED_GUARD)$fatal(1,"response event not actual complete validated frame");end
  m_response_event_ready=1;@(posedge clk);@(negedge clk);m_response_event_ready=0;
  if(busy || queue_guard || m_response_event_valid || downstream_queue_guard!==EXPECTED_GUARD)$fatal(1,"response forwarding falsely released downstream WR/CQ owner");
  // Explicit downstream MODEL release, not real DMA visibility/CQ/unpin.
  downstream_queue_guard=0;enable=1;halt=0;
 end
endtask
task reject;
 begin
  deadline=cycle+5000;while(!m_reject_valid)begin if(cycle>deadline)$fatal(1,"response rejection deadline");@(negedge clk);end
  repeat(7)begin @(negedge clk);if(fault || m_read_response_valid || m_axis_hls_rx_tvalid || m_response_event_valid || !busy || queue_guard!==EXPECTED_GUARD)$fatal(1,"rejected response produced authority/side effects");end
  m_reject_ready=1;@(posedge clk);@(negedge clk);m_reject_ready=0;repeat(3)@(negedge clk);
 end
endtask
initial begin
 $readmemh("frames.hex",frames);rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("WQE_RESPONSE_RESULT {\"pass_test\":true,\"accepted\":%0d,\"rejected\":%0d,\"ICRC_drops\":%0d,\"unowned_drops\":%0d,\"tokens\":%0d,\"events\":%0d,\"fault\":%0d,\"cycles\":%0d}",accepted_count,rejected_count,integrity_drop_count,unowned_drop_count,tokens,events,fault,cycle);
 $finish;
end
endmodule
'''


class WQEResponseGuardTests(unittest.TestCase):
    reports={}

    def simulate(self,packets,body,qpn=7,psn=0xfffffe):
        offsets=[];words=[]
        for p in packets:
            offsets.append((len(words),len(p)))
            words.extend(int.from_bytes(p[n:n+16].ljust(16,b'\0'),'little')for n in range(0,len(p),16))
        # Match the WHOLE placeholder: PACKET1 must never corrupt PACKET10.
        for i,(start,size)in enumerate(offsets):body=re.sub(r'\bPACKET'+str(i)+r'\b',f'{start},{size}',body)
        tb=TB.replace('// DECLARATIONS',declarations()).replace('// BODY',body)
        tb=tb.replace("EXPECTED_GUARD=8'h80",f"EXPECTED_GUARD=8'h{1<<qpn:02x}").replace("EXPECTED_PSN=24'hfffffe",f"EXPECTED_PSN=24'h{psn:06x}")
        paths=SOURCES+[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',Path(read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-wqe-response-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'frames.hex').write_text(''.join(f'{w:032x}\n'for w in words or[0]))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[20:])for l in r.stdout.splitlines()if l.startswith('WQE_RESPONSE_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),packet_sha256=[hashlib.sha256(p).hexdigest()for p in packets]))

    def test_READ_ONLY_M0_M1_and_payload_boundaries_require_token_before_any_HLS_byte(self):
        for size in [1,64,65,4096]:
            for mig in [0,1]:
                self.simulate([packet(length=size,mig=mig)],f'expect_owner({context(opcode=2,length=size)});send(PACKET0);token();forward(PACKET0,8\'h10,8\'h1f);')

    def test_WRITE_ACK_M0_M1_and_credit_bits_do_not_grant_READ_placement(self):
        for mig in [0,1]:
            for syndrome in [0,0x1f]:
                self.simulate([packet(write=True,mig=mig,syndrome=syndrome)],f'expect_owner({context()});send(PACKET0);forward(PACKET0,8\'h11,8\'h{syndrome:02x});if(tokens)$fatal(1,"WRITE ACK became READ placement");')

    def test_QP0_PD0_key0_full_high_authority_and_PSN_extremes_remain_exact(self):
        for psn in [0,0xffffff]:
            c=context(opcode=2,qpn=0,pd=0,lkey=0,rkey=0,flags=0,address=(1<<64)-65,offset=(1<<64)-65,remote=(1<<64)-65)
            self.simulate([packet(qpn=0,psn=psn,mig=1)],f'expect_owner({c});send(PACKET0);token();forward(PACKET0,8\'h10,8\'h1f);',qpn=0,psn=psn)

    def test_good_ICRC_never_bypasses_trusted_peer_QPN_PSN_opcode_AETH_PKey_or_length(self):
        bad=[]
        for index,value in [(12,199),(16,199),(35,6),(39,0xff),(28,0x11),(40,0x20),(40,0x60),(30,0),(29,0),(29,0x80),(29,0x31),(32,1),(36,1),(26,1)]:
            p=bytearray(packet());p[index]=value;bad.append(repair(p))
        bad.append(packet(length=64))
        good=packet();body=f'expect_owner({context(opcode=2)});'
        for i in range(len(bad)):body+=f'send(PACKET{i});reject();'
        body+=f'if(rejected_count!={len(bad)} || accepted_count || tokens || events)$fatal(1,"protected rejection counts/authority");send(PACKET{len(bad)});token();forward(PACKET{len(bad)},8\'h10,8\'h1f);'
        self.simulate(bad+[good],body)

    def test_bad_ICRC_IP_checksum_and_error_sideband_drop_whole_frame_without_token(self):
        good=packet();bad=bytearray(good);bad[-1]^=1;bad_ip=bytearray(good);bad_ip[10]^=1
        body=f'expect_owner({context(opcode=2)});'
        for i in range(3):
            body+=('s_axis_rx_tuser=1;'if i==2 else'')+f'send(PACKET{i});s_axis_rx_tuser=0;deadline=cycle+5000;while(integrity_drop_count!={i+1})begin if(cycle>deadline)$fatal(1,"integrity drop deadline");@(negedge clk);end;'
            body+='if(m_read_response_valid || m_axis_hls_rx_tvalid || m_response_event_valid || fault || !busy)$fatal(1,"bad integrity caused response side effect");'
        body+='send(PACKET3);token();forward(PACKET3,8\'h10,8\'h1f);'
        self.simulate([bytes(bad),bytes(bad_ip),good,good],body)

    def test_invalid_unknown_or_overflowed_expectation_never_authorizes_RX(self):
        for c in [context(qpn=0x800007),context(authorized=0),context(tag=0),context(epoch=0),context(sequence=0),context(length=0),context(length=4097),context(address=(1<<64)-1,length=2),context(offset=(1<<64)-1,length=2),context(remote=(1<<64)-1,length=2),"{4'hx,584'd0}"]:
            self.simulate([],f's_expect_context={c};s_expect_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h96 || queue_guard!==8'hff || s_expect_ready || m_read_response_valid || m_axis_hls_rx_tvalid)$fatal(1,"invalid expected authority admitted RX");
''')

    def test_token_ready_without_downstream_guard_faults_and_retains_full_offer(self):
        self.simulate([packet()],f'expect_owner({context(opcode=2)});send(PACKET0);'+r'''
deadline=cycle+5000;while(!m_read_response_valid)begin if(cycle>deadline)$fatal(1,"token wait");@(negedge clk);end
m_read_response_ready=1;@(posedge clk);@(negedge clk);m_read_response_ready=0;
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h97 || !m_read_response_valid || m_read_response_context!==expected_owner || queue_guard!==8'hff || m_axis_hls_rx_tvalid)$fatal(1,"response token lost lifetime owner");
''')

    def test_lost_guard_never_retracts_already_offered_HLS_beat_or_fakes_event(self):
        self.simulate([packet()],f'expect_owner({context(opcode=2)});send(PACKET0);token();'+r'''
deadline=cycle+5000;while(!m_axis_hls_rx_tvalid)begin if(cycle>deadline)$fatal(1,"held replay wait");@(negedge clk);end
downstream_queue_guard=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h97 || !m_axis_hls_rx_tvalid || queue_guard!==8'hff || m_response_event_valid)$fatal(1,"lost downstream guard erased frame/owner");
''')

    def test_unowned_frames_are_drained_not_saved_for_a_future_WQE(self):
        self.simulate([packet()],r'''send(PACKET0);repeat(5)@(negedge clk);
if(unowned_drop_count!=1 || accepted_count || integrity_drop_count || busy || m_read_response_valid || m_axis_hls_rx_tvalid)$fatal(1,"unowned response retained authority");
'''+f'expect_owner({context(opcode=2)});send(PACKET0);token();forward(PACKET0,8\'h10,8\'h1f);')

    def test_unowned_SOP_coincident_with_expectation_capture_keeps_its_tail_discarded(self):
        self.simulate([packet()],f'''
@(negedge clk);s_expect_context={context(opcode=2)};expected_owner=s_expect_context;
s_expect_local_ip=32'hc6120b02;s_expect_peer_ip=32'hc6120b01;s_expect_psn=24'hfffffe;s_expect_valid=1;
s_axis_rx_tdata=frames[0];s_axis_rx_tkeep=16'hffff;s_axis_rx_tlast=0;s_axis_rx_tvalid=1;
@(posedge clk);if(!s_expect_ready || !s_axis_rx_tready)$fatal(1,"simultaneous unowned SOP/owner fixture");
@(negedge clk);s_expect_valid=0;s_axis_rx_tvalid=0;
send(1,{len(packet())-16});repeat(13)@(negedge clk);
if(unowned_drop_count!=1 || accepted_count || integrity_drop_count || m_read_response_valid || m_axis_hls_rx_tvalid || fault || queue_guard!==8'h80)$fatal(1,"old unowned tail became new owner's response");
send(PACKET0);token();forward(PACKET0,8'h10,8'h1f);
''')

    def test_unknown_RX_meaningful_bytes_or_shape_fault_closed(self):
        for mutation in ["s_axis_rx_tdata={128{1'bx}};s_axis_rx_tkeep=16'hffff;", "s_axis_rx_tkeep=16'hxxxx;", "s_axis_rx_tlast=1'bx;"]:
            self.simulate([],f'expect_owner({context(opcode=2)});'+mutation+r'''
s_axis_rx_tvalid=1;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h98 || m_read_response_valid || m_axis_hls_rx_tvalid || m_response_event_valid || queue_guard!==8'hff)$fatal(1,"unknown RX gained memory authority");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_RESPONSE_GUARD_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==11,methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_integrity_peer_PSN_QP_opcode_AETH_length_guard=True,issued_context_downstream_HLS_executor_CQ_models=True,
                actual_native_READ_placement=False,actual_WR_completion=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
