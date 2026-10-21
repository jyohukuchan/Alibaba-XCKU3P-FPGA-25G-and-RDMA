#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""New actual protected segmented READ RX, all old Atomic/zero cases retained.

Trusted issued owner/PSN/MSN and downstream HLS/DMA/lease/event consumers
are MODELS. Actual unchanged ICRC and new guard run; not native placement,
whole-WR CQ, HLS, kernel, physical hardware or timing qualification.
All old/new short cases four-state; explicit full1MiB case two-state only.
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
import test_zero_native_leaves as old
import test_atomic128_response_rtl as response
import derive_segmented_read_response as source

ROOT=source.ROOT
TOOL=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
MSN=0x123456


def port_diagnostics(output):
    # Icarus describes module ports; Verilator also reports harmless arithmetic
    # operand promotion with "expects ... bits". Preserve those warnings in
    # logs, but do not misclassify them as disconnected/wrong-width ports.
    return [line for line in output.splitlines()if
        re.search(r'\bPort \d+ .* expects \d+ bits',line)or
        ('port connection'in line.lower()and'expects'in line.lower())or
        '%Warning-PINMISSING:'in line or '%Warning-PINNOTFOUND:'in line]

EXTRA=r'''
reg [23:0] s_expect_msn=1;
wire [31:0] m_read_segment_offset,m_read_segment_bytes;
wire m_read_segment_last,m_response_event_has_aeth;
reg read_meta_held=0;reg [65:0] saved_read_meta;
wire read_meta_stalled=(m_read_response_valid && !m_read_response_ready) ||
 (m_axis_hls_rx_tvalid && !m_axis_hls_rx_tready) ||
 (m_response_event_valid && !m_response_event_ready);
always @(posedge clk)if(!rst)begin
 if(read_meta_held && read_meta_stalled &&
  {m_read_segment_offset,m_read_segment_bytes,m_read_segment_last,m_response_event_has_aeth}!==saved_read_meta)
  $fatal(1,"segmented READ metadata changed under stall");
 read_meta_held=read_meta_stalled;
 saved_read_meta={m_read_segment_offset,m_read_segment_bytes,m_read_segment_last,m_response_event_has_aeth};
end
task segment_forward;
 input integer start,nbytes;input [23:0] psn;input [7:0] op;
 input integer logical_offset,payload_bytes;input is_last;
 begin
  expected_start=start;expected_bytes=nbytes;forwarded=0;allow_forward=0;
  deadline=cycle+5000;
  while(!m_axis_hls_rx_tvalid)begin
   if(cycle>deadline)$fatal(1,"segmented replay deadline");@(negedge clk);
  end
  repeat(9)@(negedge clk);allow_forward=1;
  while(!m_response_event_valid)begin
   if(cycle>deadline)$fatal(1,"segmented event deadline");@(negedge clk);
  end
  allow_forward=0;
  repeat(11)begin
   @(negedge clk);
   if(m_response_event_context!==expected_owner || m_response_event_psn!==psn ||
    m_response_event_opcode!==op || m_response_event_syndrome!==(op==8'h0e ? 8'd0:8'h1f) ||
    m_response_event_has_aeth!==(op!=8'h0e) || m_read_segment_offset!==logical_offset ||
    m_read_segment_bytes!==payload_bytes || m_read_segment_last!==is_last ||
    forwarded!=(nbytes+15)/16 || tokens!=1 || m_read_response_valid || fault ||
    !busy || queue_guard!==EXPECTED_GUARD || downstream_queue_guard!==EXPECTED_GUARD)
     $fatal(1,"segmented same whole owner/offset/class/lease/bytes event");
  end
  m_response_event_ready=1;@(posedge clk);@(negedge clk);m_response_event_ready=0;
  if(is_last)begin
   if(busy || queue_guard || m_response_event_valid || downstream_queue_guard!==EXPECTED_GUARD)
    $fatal(1,"final READ event released downstream placement lease");
   downstream_queue_guard=0;enable=1;halt=0;
  end else begin
   if(!busy || queue_guard!==EXPECTED_GUARD || m_response_event_valid || m_read_response_valid ||
    m_read_segment_offset!==logical_offset+payload_bytes || s_expect_ready)
    $fatal(1,"intermediate READ event released owner/reissued token/changed extent");
  end
 end
endtask
'''


def packets(length):
    payload=bytes(((i*131)^0x5a)&255 for i in range(length))
    frames=response.old.read_wire.responses(payload,initial_psn=0xfffffe,msn=MSN,
        source_ip='198.18.11.1',destination_ip='198.18.11.2',destination_qpn=7)
    for f in frames:response.old.read_wire.decode(f)
    return [p[14:]for p in frames]


def expectation(length):
    return f"s_expect_msn=24'h{MSN:x};expect_owner({response.owner(2,length=length)});"


def segment(index,length,packet_index=None):
    packet_index=index if packet_index is None else packet_index
    offset=index*4096;count=min(4096,length-offset);last=offset+count==length
    op=0x0d if index==0 else 0x0f if last else 0x0e
    return f"send(PACKET{packet_index});"+('token();'if index==0 else'')+\
        f"segment_forward(PACKET{packet_index},24'h{(0xfffffe+index)&0xffffff:06x},8'h{op:02x},{offset},{count},1'b{int(last)});"


class SegmentedReadResponseTests(old.ZeroResponse):
    reports={}

    def simulate(self,frames,body,qpn=7,psn=0xfffffe,control=False,engine='icarus-four-state'):
        words=[]
        for i,p in enumerate(frames):
            start=len(words);words.extend(int.from_bytes(p[n:n+16].ljust(16,b'\0'),'little')for n in range(0,len(p),16))
            body=re.sub(r'\bPACKET'+str(i)+r'\b',f'{start},{len(p)}',body)
        tb=response.old.TB.replace('// DECLARATIONS',response.old.declarations()+EXTRA).replace('// BODY',body)
        tb=tb.replace('[587:0]','[747:0]').replace('[627:0]','[787:0]')
        tb=source.once(tb,'rocev2_wqe_response_guard dut(.*);',
            f'{source.NAME} #(.CONTROL_ENABLE({int(control)})) dut(.*);')
        tb=tb.replace("EXPECTED_GUARD=8'h80",f"EXPECTED_GUARD=8'h{1<<qpn:02x}")
        tb=tb.replace("EXPECTED_PSN=24'hfffffe",f"EXPECTED_PSN=24'h{psn:06x}")
        if len(words)>2048:tb=source.once(tb,'frames[0:2047]',f'frames[0:{len(words)-1}]')
        if len(frames)>20:tb=source.once(tb,'cycle>25000',f'cycle>{len(frames)*1600}')
        run=Path(tempfile.mkdtemp(prefix='segmented-read-response-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(tb);(run/'guard.v').write_text(source.derive())
        (run/'frames.hex').write_text(''.join(f'{w:032x}\n'for w in words or[0]))
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
            Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
        inputs=[*helpers,*source.RTL.glob('*.v'),*(ROOT/'rdma/rtl').glob('*.v'),
            ROOT/'rdma/read/host/read_wire.py',ROOT/'rdma/host/rocev2_wire.py',*response.old.SOURCES[1:]]
        before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(inputs)}
        item=dict(pass_test=False,directory=str(run.relative_to(ROOT)),engine=engine,source_sha256=before,
            packet_sha256=[hashlib.sha256(p).hexdigest()for p in frames],runtime_limit_seconds=30)
        ram=None
        try:
            if engine=='icarus-four-state':
                command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(run/'guard.v'),*map(str,response.old.SOURCES[1:])]
                runtime=['vvp',str(run/'test.vvp')]
            else:
                if engine!='verilator-two-state':raise ValueError('unreviewed engine')
                ram=Path(tempfile.mkdtemp(prefix='as02-segmented-read-obj-',dir='/dev/shm'))
                command=[str(TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','2',
                    '--Mdir',str(ram),str(run/'tb.v'),str(run/'guard.v'),*map(str,response.old.SOURCES[1:])]
                runtime=[str(ram/'Vtb')]
                item['compiler_sha256']=digest(TOOL.resolve())
            item['compile_command']=command;start=time.monotonic()
            c=subprocess.run(command,capture_output=True,text=True,timeout=180)
            (run/'compile.log').write_text(c.stdout+c.stderr);item['compile_seconds']=time.monotonic()-start
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            item['port_diagnostics']=port_diagnostics(c.stderr)
            self.assertFalse(item['port_diagnostics'],c.stderr)
            start=time.monotonic();r=subprocess.run(runtime,cwd=run,capture_output=True,text=True,timeout=30)
            item['runtime_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_RESPONSE_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.assertEqual(before,{n:digest(ROOT/n)for n in before})
            item.update(pass_test=True,summary=rows[0])
        finally:
            item['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
            if ram:item['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
            self.reports.setdefault(self._testMethodName,[]).append(item)

    def test_segmented_READ_all_tail_pads_and_PSN_wrap_one_whole_token(self):
        for length in [4097,4098,4099,4100,8192,8193,12289]:
            ps=packets(length)
            body=expectation(length)+''.join(segment(i,length)for i in range(len(ps)))
            body+=f'if(tokens!=1 || events!={len(ps)} || accepted_count!={len(ps)} || rejected_count || integrity_drop_count)$fatal(1,"segmented whole transaction counts");'
            self.simulate(ps,body)

    def test_segmented_READ_wrong_first_peer_PSN_MSN_class_length_then_recover(self):
        good=packets(8193)
        for offset,value in [(12,0x11),(33,0x01),(39,0x01),(43,0x55),(28,0x10)]:
            bad=bytearray(good[0]);bad[offset]^=value;bad=response.old.repair(bad)
            body=expectation(8193)+'send(PACKET0);reject();if(tokens || events || accepted_count)$fatal(1,"bad first acquired authority");'
            body+=''.join(segment(i,8193,i+1)for i in range(3))
            self.simulate([bad,*good],body)
        bad=response.old.repair(good[0][:-8]+good[0][-4:])
        body=expectation(8193)+'send(PACKET0);reject();'+''.join(segment(i,8193,i+1)for i in range(3))
        self.simulate([bad,*good],body)

    def test_segmented_READ_wrong_middle_never_advances_or_reissues_token(self):
        good=packets(8193)
        bads=[]
        for offset,value in [(39,1),(28,1)]:
            p=bytearray(good[1]);p[offset]^=value;bads.append(response.old.repair(p))
        bads += [good[0]]
        for bad in bads:
            body=expectation(8193)+segment(0,8193)
            body+='send(PACKET3);reject();if(tokens!=1 || events!=1 || m_read_segment_offset!=4096)$fatal(1,"rejected middle advanced whole owner");'
            body+=segment(1,8193)+segment(2,8193)
            self.simulate([*good,bad],body)

    def test_segmented_READ_bad_ICRC_and_wrong_last_MSN_keep_progress_and_lease(self):
        good=packets(8193)
        for which in [0,1]:
            bad=bytearray(good[which]);bad[-1]^=1
            body=expectation(8193)
            if which:body+=segment(0,8193)
            body+='send(PACKET3);repeat(1000)@(negedge clk);'
            body+=f'if(integrity_drop_count!=1 || tokens!={which} || events!={which} || m_read_response_valid || m_axis_hls_rx_tvalid || m_response_event_valid || m_read_segment_offset!={which*4096})$fatal(1,"bad CRC changed progress/authority");'
            body+=''.join(segment(i,8193)for i in range(which,3))
            self.simulate([*good,bytes(bad)],body)
        bad=bytearray(good[2]);bad[43]^=1;bad=response.old.repair(bad)
        body=expectation(8193)+segment(0,8193)+segment(1,8193)+'send(PACKET3);reject();'
        body+='if(tokens!=1 || events!=2 || m_read_segment_offset!=8192 || queue_guard!==EXPECTED_GUARD)$fatal(1,"wrong LAST MSN released authority");'+segment(2,8193)
        self.simulate([*good,bad],body)

    def test_segmented_READ_lost_downstream_lease_quarantines_whole_WR(self):
        body=expectation(8193)+segment(0,8193)+r'''
downstream_queue_guard=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h97 || queue_guard!==8'hff || !busy || tokens!=1 || events!=1 ||
 m_response_event_context!==expected_owner || s_expect_ready || m_read_response_valid || m_axis_hls_rx_tvalid)
 $fatal(1,"lost whole placement lease did not quarantine");
'''
        self.simulate(packets(8193),body)

    def test_segmented_READ_requires_known_trusted_MSN_before_owner_capture(self):
        body=f"s_expect_msn=24'bx;s_expect_context={response.owner(2,length=8193)};s_expect_valid=1;"+r'''
repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h96 || queue_guard!==8'hff || tokens || events || m_read_response_valid || m_axis_hls_rx_tvalid)
 $fatal(1,"unknown trusted MSN acquired READ authority");
'''
        self.simulate([],body)

    def test_segmented_READ_full_1MiB_256_packets_explicit_two_state(self):
        length=1048576;ps=packets(length)
        self.assertEqual([len(p)for p in ps],[4144]+[4140]*254+[4144])
        # The identical256 packets/checks use a procedural loop, avoiding a
        # giant compiler-inlined coroutine. No smaller transfer or weaker
        # byte/offset/PSN/stall/lease/deadline oracle substitutes for the run.
        body=r'''
begin : full_read_test
 integer packet_index,read_start,read_packet_bytes;
 reg [23:0] response_psn;
 read_start=0;response_psn=24'hfffffe;
'''+expectation(length)+r'''
 for(packet_index=0;packet_index<256;packet_index=packet_index+1)begin
  read_packet_bytes=(packet_index==0 || packet_index==255) ? 4144:4140;
  send(read_start,read_packet_bytes);if(packet_index==0)token();
  segment_forward(read_start,read_packet_bytes,response_psn,
   packet_index==0 ? 8'h0d:packet_index==255 ? 8'h0f:8'h0e,
   packet_index*4096,4096,packet_index==255);
  read_start=read_start+(read_packet_bytes+15)/16;response_psn=response_psn+24'd1;
 end
 if(tokens!=1 || events!=256 || accepted_count!=256 || rejected_count || integrity_drop_count)
  $fatal(1,"full1MiB READ cardinality");
end
'''
        self.simulate(ps,body,engine='verilator-two-state')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    if a.report.exists():parser.error('preserve previous evidence')
    for bad in ['warning: Port 4 (data) of dut expects 32 bits, got 16.',
                "%Warning-WIDTHTRUNC: tb.v: Input port connection 'data' expects 32 bits on the pin connection, but generates 16 bits.",
                '%Warning-PINMISSING: Cell missing pin: data']:
        if not port_diagnostics(bad):raise ValueError('port gate self-test failed')
    if port_diagnostics('%Warning-WIDTHEXPAND: Operator EQ expects 32 bits on the LHS, but bytes_received generates 16 bits.'):
        raise ValueError('arithmetic warning confused with port mismatch')
    suite=list(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedReadResponseTests))
    suite.sort(key=lambda t:(t._testMethodName!='test_segmented_READ_full_1MiB_256_packets_explicit_two_state',t._testMethodName))
    if len(suite)!=17:raise ValueError('all17 methods required')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suite))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        all_eight_original_Atomic_methods_and_two_zero_methods_retained=True,
        standard_API_runtime=False,native_DMA_runtime=False,actual_generated_HLS=False,hardware_verified=False,
        full_board_timing=False,default_graph_changed=False,tests=SegmentedReadResponseTests.reports)
    a.report.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
