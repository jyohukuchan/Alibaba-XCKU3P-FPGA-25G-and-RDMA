#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual segmented lifetime/replay/framer/tag/EOF/tail composition.

HLS/IP source, positive RX/HLS-ACK, memory and CQ endpoints and physical MAC
completion pins are MODELS. Not actual HLS/native DMA/XGMII/Linux/physical
integration or timing proof. All simulations bounded to30s each.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import test_wqe_mac_tx_rtl as mac
import test_wqe_response_guard_rtl as packets
import test_segmented_source_executor_rtl as source_owner

ROOT=mac.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_wire as candidate


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def packet(op,total,offset,psn):
    count=min(4096,total-offset);first=offset==0;last=offset+count==total
    code=(0 if first else 2 if last else 1)if op==3 else(6 if first else 8 if last else 7)
    # Independent full packet encoding, not candidate Verilog helper logic.
    header=bytearray(mac.lifetime.request(True)[:28])
    bth=bytes([code,0x40|(((-count)&3)<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
    reth=struct.pack('!QII',0xe23456789abcdef0,0x81234567,total)if op==1 and first else b''
    payload=bytes((((offset+i)*37)^0xa5)&255 for i in range(count))
    return packets.repair(header+bth+reth+payload+bytes((-count)&3)+bytes(4))


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8,TX_TAG_WIDTH=16,TS_WIDTH=96;
// DECLARATIONS
rocev2_wqe_tx_lifetime #(.RETRY_ENABLE(1),.REQUEST_CQ_ENABLE(1)) dut(.*);
always #2 clk=~clk;
localparam [747:0] EXPECTED=748'hOWNER;
localparam TOTAL=TOTAL_BYTES,OPCODE=WR_OPCODE,PACKETS=PACKET_COUNT;
reg [127:0] words[0:WORD_COUNT-1];
integer offsets[0:PACKETS-1],sizes[0:PACKETS-1];
integer cycle=0,p,deadline,advances=0,retirements=0;
reg stalled=0;reg [161:0] held=0;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>2000000)$fatal(1,"bounded segmented wire deadline");
 if(stalled && (!m_axis_mac_tvalid || {m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser}!==held))
  $fatal(1,"segmented MAC beat retracted/changed under stall");
 stalled=m_axis_mac_tvalid&&!m_axis_mac_tready;
 held={m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser};
 if(m_axis_mac_tvalid && m_axis_mac_tready)
  $display("MAC_FRAME %032h %04h %b %05h",m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser);
 if(dut.packet_advance_valid && dut.packet_advance_ready)begin
  if(dut.packet_advance_context!==EXPECTED || dut.packet_advance_psn!==((24'hfffffe+advances)&24'hffffff) ||
   dut.packet_index!==advances || !dut.local_tx_drained || !busy || queue_guard!==4 || m_cq_valid)
   $fatal(1,"packet cache advance lost genuine packet/whole WR ownership");
  advances=advances+1;
 end
 if(s_cq_commit_valid && s_cq_commit_ready)retirements=retirements+1;
end
always @(negedge clk)m_axis_mac_tready=cycle%11>2;
task configure;
 begin
  @(negedge clk);cfg_qpn=2;cfg_pd=17;cfg_cookie=64'hfedcba9889abcdef;
  cfg_epoch=64'h9123456700000001;cfg_timeout=0;cfg_retry=1;cfg_rnr_retry=1;cfg_valid=1;
  @(posedge clk);if(!cfg_ready)$fatal(1,"segmented retry policy admission");
  @(negedge clk);cfg_valid=0;deadline=cycle+30;
  while(!rsp_valid)begin if(cycle>deadline)$fatal(1,"segmented policy readback");@(negedge clk);end
  if(rsp_error || rsp_qpn!==2 || rsp_pd!==17 || rsp_epoch!==cfg_epoch || rsp_cookie!==cfg_cookie ||
   rsp_timeout!==0 || rsp_retry!==1 || rsp_rnr_retry!==1)$fatal(1,"actual policy readback differs");
  rsp_ready=1;@(posedge clk);@(negedge clk);rsp_ready=0;
  s_owner_context=EXPECTED;s_owner_local_ip=32'hc6120b02;s_owner_peer_ip=32'hc6120b01;s_owner_peer_qpn=196;
  s_owner_local_mac=48'h8af3fbb97531;s_owner_peer_mac=48'hb8830367c5d0;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready)$fatal(1,"segmented full WR owner refused");
  @(negedge clk);s_owner_valid=0;
  if(!busy || queue_guard!==4 || m_cq_context!==EXPECTED)$fatal(1,"whole WR owner/guard absent");
 end
endtask
task transmit;
 input integer index;integer b,limit;
 begin
  for(b=0;b<sizes[index];b=b+16)begin
   @(negedge clk);s_axis_ip_tdata=words[offsets[index]+b/16];
   s_axis_ip_tkeep=b+16<=sizes[index] ? 16'hffff:(16'hffff>>(16-sizes[index]%16));
   s_axis_ip_tlast=b+16>=sizes[index];s_axis_ip_tvalid=1;limit=cycle+5000;
   @(posedge clk);while(!s_axis_ip_tready)begin
    if(cycle>limit || fault)$fatal(1,"next real HLS packet blocked/fault %h life%h mac%h replay%h",fault_code,dut.life_fault_code,dut.mac_fault_code,dut.replay_fault_code);
    @(posedge clk);
   end
   @(negedge clk);s_axis_ip_tvalid=0;
  end
 end
endtask
task expectation;
 input integer index;integer limit;
 begin
  limit=cycle+100;while(!m_expect_valid)begin
   if(cycle>limit || fault)$fatal(1,"segmented packet expectation deadline %h",fault_code);@(negedge clk);
  end
  repeat(7)begin
   @(negedge clk);if(m_expect_context!==EXPECTED || m_expect_psn!==((24'hfffffe+index)&24'hffffff) ||
    m_expect_local_ip!==32'hc6120b02 || m_expect_peer_ip!==32'hc6120b01 || response_admission_ready || m_cq_valid || fault)
    $fatal(1,"held full-owner packet expectation changed");
  end
  m_expect_ready=1;@(posedge clk);@(negedge clk);m_expect_ready=0;
 end
endtask
task positive;
 input integer index;
 begin
  s_response_context=EXPECTED;s_response_psn=(24'hfffffe+index)&24'hffffff;
  s_response_opcode=8'h11;s_response_syndrome=8'h1f;s_response_valid=1;
  @(posedge clk);if(!s_response_ready)$fatal(1,"segmented positive response identity");
  @(negedge clk);s_response_valid=0;
  s_hls_ack={5'd0,s_response_psn,10'd2,1'b1};s_hls_ack_valid=1;
  @(posedge clk);if(!s_hls_ack_ready)$fatal(1,"segmented HLS ACK identity");
  @(negedge clk);s_hls_ack_valid=0;
  if(index==PACKETS-1)begin
   s_memory_context=EXPECTED;s_memory_valid=1;
   @(posedge clk);if(!s_memory_ready)$fatal(1,"whole aggregate memory identity");
   @(negedge clk);s_memory_valid=0;memory_drained=1;
  end
 end
endtask
task receipt;
 input integer index;integer limit,j;
 begin
  limit=cycle+3000;while(frame_count!=index+1)begin
   if(cycle>limit || fault)$fatal(1,"segmented actual framed EOF deadline %h",fault_code);@(negedge clk);
  end
  // Keep the unchanged1024-cycle DUT tail for EVERY packet. The bulk
  // capacity case withholds past that tail at first/last, others still stall.
  for(j=0;j<((TOTAL<=65537 || index==0 || index==PACKETS-1) ? 1100:7);j=j+1)begin
   @(negedge clk);if(fault || m_cq_valid || advances!=index || dut.packet_index!==index ||
    dut.lifetime.owner!==EXPECTED || !busy || queue_guard!==4 || mac_proof_count!=index)
    $fatal(1,"ACK/memory substituted for withheld own MAC receipt/EOF/tail");
  end
  s_mac_cpl_tag=active_tag;s_mac_cpl_ts=index+1;s_mac_cpl_valid=1;
  @(posedge clk);if(!s_mac_cpl_ready || active_tag!==16'h2001+index)$fatal(1,"fresh exact per-packet MAC tag");
  @(negedge clk);s_mac_cpl_valid=0;#1;limit=cycle+1200;
  while(mac_proof_count!=index+1)begin
   if(cycle>limit || fault)$fatal(1,"packet SFD/EOF/tail join deadline %h life%h replay%h index%0d proof%0d frames%0d receipts%0d active%0d macdone%0d ipdone%0d seen%0d tail%0d busy%0d valid%0d ready%0d state%0d cycle%0d limit%0d",fault_code,dut.life_fault_code,dut.replay_fault_code,index,mac_proof_count,frame_count,receipt_count,dut.mac_owner.active,dut.mac_owner.mac_done,dut.mac_owner.ip_done,dut.mac_owner.receipt_seen,dut.mac_owner.tail_left,dut.mac_owner.framer_busy,dut.mac_valid,dut.mac_ready,dut.retained_replay.replay.state,cycle,limit);@(negedge clk);
  end
 end
endtask
task producer_receipt;
 begin
  s_request_done_data={12'd0,(OPCODE==1 ? 8'h0a:8'h04),24'((24'hfffffe+PACKETS)&24'hffffff),24'hfffffe,EXPECTED};
  s_request_done_valid=1;
  @(posedge clk);while(!s_request_done_ready)begin if(fault)$fatal(1,"full WR first/next PSN receipt fault %h",fault_code);@(posedge clk);end
  @(negedge clk);s_request_done_valid=0;
 end
endtask
task finish_WR;
 begin
  deadline=cycle+100;while(!m_cq_valid)begin if(cycle>deadline || fault)$fatal(1,"one final full-WR CQ missing %h",fault_code);@(negedge clk);end
  repeat(13)begin @(negedge clk);if(m_cq_context!==EXPECTED || !busy || queue_guard!==4 || advances!=PACKETS-1 ||
   committed_count || hls_transport_drained || frame_count!=PACKETS || receipt_count!=PACKETS || mac_proof_count!=PACKETS)
   $fatal(1,"whole WR ticket/real packet cardinality");end
  m_cq_ready=1;@(posedge clk);@(negedge clk);m_cq_ready=0;
  repeat(7)@(negedge clk);if(!busy || queue_guard!==4 || committed_count)$fatal(1,"ticket was mistaken for final CQ commit");
  s_cq_commit_context=EXPECTED;s_cq_commit_valid=1;
  @(posedge clk);if(!s_cq_commit_ready)$fatal(1,"one whole WR final commit refused");
  @(negedge clk);s_cq_commit_valid=0;repeat(3)@(negedge clk);
  if(busy || queue_guard || fault || committed_count!=1 || retirements!=1)$fatal(1,"full WR not retired exactly once");
 end
endtask
initial begin
 $readmemh("packets.hex",words);OFFSET_SETUP
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;configure();
 // BODY
 $display("SEGMENTED_WIRE_RESULT {\"pass_test\":true,\"packets\":%0d,\"advances\":%0d,\"frames\":%0d,\"receipts\":%0d,\"MAC_proofs\":%0d,\"committed\":%0d,\"fault\":%0d,\"cycles\":%0d}",
  PACKETS,advances,frame_count,receipt_count,mac_proof_count,committed_count,fault,cycle);$finish;
end
endmodule
'''


class SegmentedWireTests(unittest.TestCase):
    reports={}

    def simulate(self,op=1,total=8193,body=None,mutate=None,success=True):
        run=Path(tempfile.mkdtemp(prefix='segmented-wire-unit-',dir=ROOT/'rdma/rnic/build'))
        derived=candidate.derive();leaves=[]
        for n in ['rocev2_wqe_tx_lifetime.v','rocev2_wqe_lifetime.v','rocev2_wqe_replay.v','rocev2_wqe_mac_tx.v']:
            p=run/n;p.write_text(derived[candidate.RTL/n]);leaves.append(p)
        ports=candidate.helpers.module_ports(leaves[0]);decl='\n'.join(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        frames=[packet(op,total,o,(0xfffffe+o//4096)&0xffffff)for o in range(0,total,4096)]
        if mutate:frames=mutate(frames)
        words=[];setup=[]
        for i,f in enumerate(frames):
            setup.append(f'offsets[{i}]={len(words)};sizes[{i}]={len(f)};')
            words += [int.from_bytes(f[o:o+16].ljust(16,b'\0'),'little')for o in range(0,len(f),16)]
        body=body or r'''
 transmit(0);
 for(p=0;p<PACKETS;p=p+1)begin
  expectation(p);positive(p);
  if(p+1<PACKETS)begin
   fork transmit(p+1);receipt(p);join
  end else begin
   fork producer_receipt();receipt(p);join
  end
 end
 finish_WR();
'''
        tb=TB.replace('// DECLARATIONS',decl).replace('WORD_COUNT',str(len(words))).replace('PACKET_COUNT',str(len(frames)))\
            .replace('TOTAL_BYTES',str(total)).replace('WR_OPCODE',str(op)).replace('OFFSET_SETUP','\n'.join(setup))\
            .replace("748'hOWNER",f"748'h{source_owner.owner(op,total):0187x}").replace('// BODY',body)
        (run/'tb.v').write_text(tb);(run/'packets.hex').write_text(''.join(f'{w:032x}\n'for w in words))
        src=[*leaves,*[p for p in mac.SOURCES if p!=mac.RTL]]
        authored=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),Path(source_owner.__file__).resolve(),Path(mac.__file__).resolve(),Path(packets.__file__).resolve()]
        before={str(p.relative_to(ROOT)):digest(p)for p in [*src,*authored,run/'tb.v',run/'packets.hex']}
        info=dict(directory=str(run.relative_to(ROOT)),pass_test=False,WR_opcode=op,bytes=total,source_sha256=before)
        self.reports.setdefault(self._testMethodName,[]).append(info)
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,src)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);info['compile_seconds']=time.monotonic()-start
        self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();v=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        (run/'simulation.log').write_text(v.stdout+v.stderr);info['simulation_seconds']=time.monotonic()-start
        self.assertEqual(v.returncode,0,v.stdout[-5000:]+v.stderr)
        rows=[json.loads(l.split(' ',1)[1])for l in v.stdout.splitlines()if l.startswith('SEGMENTED_WIRE_RESULT ')]
        self.assertEqual(len(rows),1,v.stdout[-1000:]);self.assertEqual(rows[0]['committed'],int(success))
        if success:
            self.assertEqual(mac.decode_frames(v.stdout),[(0x2001+i,0,bytes.fromhex('b8830367c5d08af3fbb975310800')+f)for i,f in enumerate(frames)])
            self.assertEqual(rows[0]['advances'],len(frames)-1);self.assertFalse(rows[0]['fault'])
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        info.update(pass_test=True,summary=rows[0],byte_exact_MAC_frames=success,artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()})

    def test_three_packet_WRITE_and_SEND_PSN_wrap_hold_source_until_one_final_CQ(self):
        for op in [1,3]:self.simulate(op)

    def test_fragment_boundaries_and_one_MiB_owner_span(self):
        for op,total in [(1,4097),(3,8192),(1,1048576)]:self.simulate(op,total)

    def test_valid_CRC_wrong_first_RETH_or_later_PSN_or_opcode_never_completes(self):
        for kind in ['RETH','PSN','OPCODE']:
            def mutate(frames):
                f=list(frames);i=0 if kind=='RETH'else 1;p=bytearray(f[i]);p[55 if kind=='RETH'else 39 if kind=='PSN'else 28]^=1
                f[i]=packets.repair(p);return f
            body=r'''
 transmit(0);
'''
            if kind!='RETH':body+=r'''
 expectation(0);positive(0);fork transmit(1);receipt(0);join
'''
            body+=r'''
 repeat(30)@(negedge clk);
 if(!fault || dut.lifetime.fault_code!=8'hb2 || m_expect_valid || m_cq_valid || committed_count ||
  queue_guard!==8'hff || dut.lifetime.owner!==EXPECTED)$fatal(1,"wrong full-owner packet metadata not quarantined");
'''
            self.simulate(body=body,mutate=mutate,success=False)

    def test_missing_per_packet_HLS_ACK_cannot_rotate_replay_cache(self):
        self.simulate(body=r'''
 transmit(0);expectation(0);
 s_response_context=EXPECTED;s_response_psn=24'hfffffe;s_response_opcode=8'h11;s_response_syndrome=8'h1f;s_response_valid=1;
 @(posedge clk);if(!s_response_ready)$fatal(1,"positive RX witness");@(negedge clk);s_response_valid=0;
 receipt(0);repeat(20)@(negedge clk);
 if(fault || advances || m_cq_valid || committed_count || !busy || queue_guard!==4 ||
  dut.lifetime.owner!==EXPECTED || dut.retained_replay.replay.packet_index!=0)
  $fatal(1,"MAC/RX substituted for missing same-packet HLS ACK");
''',success=False)

    def test_wrong_final_first_next_PSN_receipt_never_releases_whole_WR(self):
        self.simulate(body=r'''
 transmit(0);
 for(p=0;p<PACKETS;p=p+1)begin
  expectation(p);positive(p);
  if(p+1<PACKETS)begin fork transmit(p+1);receipt(p);join end else receipt(p);
 end
 s_request_done_data={12'd0,8'h0a,24'h000002,24'hfffffe,EXPECTED};s_request_done_valid=1;
 repeat(20)@(negedge clk);
 if(!fault || !dut.request_fault || m_cq_valid || committed_count || queue_guard!==8'hff ||
  dut.lifetime.owner!==EXPECTED || advances!=2)$fatal(1,"wrong full-WR first/next PSN was accepted");
''',success=False)


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--report',type=Path,required=True);args=a.parse_args()
    if args.report.exists():a.error('preserve prior evidence')
    start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedWireTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    for cases in SegmentedWireTests.reports.values():
        for case in cases:
            run=ROOT/case['directory']
            case['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
    record=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,seconds=time.monotonic()-start,
        tests=SegmentedWireTests.reports,four_state=True,actual_lifetime_replay_framer_tag_EOF_tail=True,
        HLS_memory_RX_CQ_and_MAC_pins_modeled=True,native_large_or_hardware_runtime=False)
    with args.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful()else 1)


if __name__=='__main__':main()
