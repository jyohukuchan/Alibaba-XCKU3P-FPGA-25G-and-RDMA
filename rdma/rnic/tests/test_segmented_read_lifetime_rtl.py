#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual whole-READ lifetime/replay/MAC leaf composition, endpoints MODELED.

One actual outbound request; RX events, HLS ACK/receipt, aggregate memory/CQ
and physical MAC completion pins are models. No RX payload/HLS/native DMA/
Linux/physical qualification. All prior segmented WRITE/SEND cases retained.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import test_segmented_wire_rtl as old

ROOT=old.ROOT;digest=old.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_lifetime as candidate
import derive_segmented_wire as ports

READ_TASKS=r'''
localparam READ_SPAN=(TOTAL+4095)/4096;
task read_response;input integer index;
 begin
  s_response_context=EXPECTED;s_response_psn=(24'hfffffe+index)&24'hffffff;
  s_response_opcode=READ_SPAN==1 ? 8'h10:index==0 ? 8'h0d:index==READ_SPAN-1 ? 8'h0f:8'h0e;
  s_response_syndrome=s_response_opcode==8'h0e ? 0:8'h1f;s_response_valid=1;
  @(posedge clk);if(s_response_ready!==1'b1)$fatal(1,"READ packet PSN/class/full-owner refused");
  @(negedge clk);s_response_valid=0;#1;
  if(index+1<READ_SPAN)begin
   if(proof_flags[3] || dut.retained_replay.replay.acked || dut.retained_replay.replay.done_sent ||
    m_cq_valid || committed_count || !busy || queue_guard!==4 || advances)
    $fatal(1,"FIRST/MIDDLE released outbound request/cache/whole WR");
  end else if(proof_flags[3]!==1'b1)$fatal(1,"LAST failed to complete whole RX witness");
 end
endtask
task read_ack;
 begin
  s_hls_ack={5'd0,24'((24'hfffffe+READ_SPAN-1)&24'hffffff),10'd2,1'b0};s_hls_ack_valid=1;
  @(posedge clk);if(s_hls_ack_ready!==1'b1)$fatal(1,"final READ HLS ACK PSN refused");
  @(negedge clk);s_hls_ack_valid=0;
 end
endtask
task read_memory;
 begin
  s_memory_context=EXPECTED;s_memory_valid=1;
  @(posedge clk);if(s_memory_ready!==1'b1)$fatal(1,"whole READ aggregate memory witness refused");
  @(negedge clk);s_memory_valid=0;memory_drained=1;
 end
endtask
task read_producer;
 begin
  s_request_done_data={12'd0,8'h0c,24'((24'hfffffe+READ_SPAN)&24'hffffff),24'hfffffe,EXPECTED};
  s_request_done_valid=1;deadline=cycle+100;
  @(posedge clk);while(!s_request_done_ready)begin
   if(fault || cycle>deadline)$fatal(1,"whole READ first/next receipt not joined %h",fault_code);@(posedge clk);
  end
  @(negedge clk);s_request_done_valid=0;
 end
endtask
task read_quarantine;
 begin
  repeat(20)@(negedge clk);
  if(fault!==1'b1 || queue_guard!==8'hff || !busy || m_cq_valid || committed_count ||
   s_cq_commit_ready || dut.lifetime.owner!==EXPECTED)$fatal(1,"bad READ proof released whole owner");
 end
endtask
'''


class ReadLifetime(old.SegmentedWireTests):
    reports={}

    def read(self,total=8193,body=None,success=True):
        run=Path(tempfile.mkdtemp(prefix='segmented-read-lifetime-',dir=ROOT/'rdma/rnic/build'))
        derived=candidate.derive();leaves=[]
        for n in ['rocev2_wqe_tx_lifetime.v','rocev2_wqe_lifetime.v','rocev2_wqe_replay.v','rocev2_wqe_mac_tx.v']:
            p=run/n;p.write_text(derived[candidate.RTL/n]);leaves.append(p)
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';')
            for d,w,n in ports.helpers.module_ports(leaves[0]))
        frame=old.packets.read_wire.encode(opcode=old.packets.read_wire.REQUEST,
            source_ip='198.18.11.2',destination_ip='198.18.11.1',destination_qpn=196,psn=0xfffffe,
            remote_address=0xe23456789abcdef0,rkey=0x81234567,read_bytes=total)[14:]
        words=[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')for i in range(0,len(frame),16)]
        owner=(old.source_owner.owner(1,total)&~(0xffff<<324))|(2<<324)
        body=body or r'''
transmit(0);expectation(0);read_response(0);receipt(0);
for(p=1;p<READ_SPAN;p=p+1)read_response(p);
read_ack();read_memory();read_producer();finish_WR();
'''
        tb=old.TB.replace('// DECLARATIONS',decl).replace('WORD_COUNT',str(len(words))).replace('PACKET_COUNT','1')\
            .replace('TOTAL_BYTES',str(total)).replace('WR_OPCODE','2').replace('OFFSET_SETUP',f'offsets[0]=0;sizes[0]={len(frame)};')\
            .replace("748'hOWNER",f"748'h{owner:0187x}").replace('// BODY',body)
        tb=candidate.once(tb,'initial begin\n $readmemh',READ_TASKS+'\ninitial begin\n $readmemh')
        (run/'tb.v').write_text(tb);(run/'packets.hex').write_text(''.join(f'{w:032x}\n'for w in words))
        src=[*leaves,*[p for p in old.mac.SOURCES if p!=old.mac.RTL]]
        info=dict(directory=str(run.relative_to(ROOT)),pass_test=False,WR_opcode=2,bytes=total,
            modeled_RX_events=(total+4095)//4096,outbound_requests=1,runtime_limit_seconds=30)
        self.reports.setdefault(self._testMethodName,[]).append(info)
        try:
            cmd=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,src)]
            start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            (run/'compile.log').write_text(c.stdout+c.stderr);info['compile_seconds']=time.monotonic()-start
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
            (run/'simulation.log').write_text(r.stdout+r.stderr);info['simulation_seconds']=time.monotonic()-start
            self.assertEqual(r.returncode,0,r.stdout[-3500:]+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('SEGMENTED_WIRE_RESULT ')]
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['committed'],int(success))
            if success:
                self.assertEqual(old.mac.decode_frames(r.stdout),[(0x2001,0,bytes.fromhex('b8830367c5d08af3fbb975310800')+frame)])
                self.assertEqual(rows[0]['advances'],0);self.assertFalse(rows[0]['fault'])
            info.update(pass_test=True,summary=rows[0])
        finally:
            info['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}

    def test_READ_single_and_multiple_response_span_one_request_one_CQ(self):
        for total in [65,4097,8193,1048576]:self.read(total)

    def test_READ_missing_final_RX_ACK_memory_or_producer_never_releases(self):
        for missing in ['LAST','ACK','MEMORY','PRODUCER']:
            body='transmit(0);expectation(0);read_response(0);receipt(0);\n'
            body+='for(p=1;p<READ_SPAN'+('-1'if missing=='LAST'else'')+';p=p+1)read_response(p);\n'
            if missing!='ACK':body+='read_ack();\n'
            if missing!='MEMORY':body+='read_memory();\n'
            body+=r'''
repeat(25)@(negedge clk);
if(fault || m_cq_valid || committed_count || !busy || queue_guard!==4 || advances ||
 dut.lifetime.owner!==EXPECTED || hls_transport_drained || dut.request_proved)
 $fatal(1,"missing READ witness was replaced by idle/other certificates");
'''
            if missing=='LAST':body+='if(dut.retained_replay.replay.acked || dut.retained_replay.replay.done_sent)$fatal(1,"nonterminal READ ACKed cache");'
            self.read(body=body,success=False)

    def test_READ_wrong_response_PSN_class_syndrome_owner_or_unknown_quarantines(self):
        for mutation in ["s_response_psn=0;","s_response_opcode=8'h0f;","s_response_opcode=8'h10;",
                         "s_response_syndrome=8'h80;","s_response_context=EXPECTED^1;","s_response_psn[2]=1'bx;"]:
            self.read(body='transmit(0);expectation(0);s_response_context=EXPECTED;s_response_psn=24\'hfffffe;'
                's_response_opcode=8\'h0d;s_response_syndrome=8\'h1f;'+mutation+
                's_response_valid=1;read_quarantine();',success=False)

    def test_READ_wrong_whole_request_first_next_or_opcode_never_retires(self):
        for mutation in ["s_request_done_data[771:748]^=1;","s_request_done_data[795:772]=24'hffffff;",
                         "s_request_done_data[803:796]=8'h0a;","s_request_done_data[410]=1'bx;"]:
            self.read(body=r'''
transmit(0);expectation(0);read_response(0);receipt(0);
for(p=1;p<READ_SPAN;p=p+1)read_response(p);read_ack();read_memory();
repeat(15)@(negedge clk);
if(proof_flags[5:0]!==6'h3f)$fatal(1,"real leaf witnesses incomplete before bad receipt control");
s_request_done_data={12'd0,8'h0c,24'h000001,24'hfffffe,EXPECTED};
'''+mutation+'s_request_done_valid=1;read_quarantine();',success=False)

    def test_READ_legacy_first_PSN_HLS_ACK_cannot_complete_multi_response(self):
        self.read(body=r'''
transmit(0);expectation(0);read_response(0);
s_hls_ack={5'd0,24'hfffffe,10'd2,1'b0};s_hls_ack_valid=1;read_quarantine();
''',success=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    # Exact inherited tests/oracles, new derived leaf family only.
    old.candidate=candidate
    modules=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*modules,*list((ROOT/'rdma/rnic/fpga').glob('*.py')),Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReadLifetime);start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    for cases in ReadLifetime.reports.values():
        for case in cases:
            run=ROOT/case['directory'];case['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
    same=all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,
        cases=sum(map(len,ReadLifetime.reports.values())),seconds=time.monotonic()-start,source_sha256=before,source_unchanged=same,
        all_five_original_segmented_wire_methods_retained=True,actual_lifetime_replay_MAC=True,
        RX_HLS_memory_CQ_MAC_pins_modeled=True,native_runtime=False,hardware_verified=False,READ_admission_limit=4096,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors],tests=ReadLifetime.reports)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not report['pass_test'])


if __name__=='__main__':main()
