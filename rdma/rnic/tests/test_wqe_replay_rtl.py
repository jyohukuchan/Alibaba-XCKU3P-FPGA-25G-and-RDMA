# SPDX-License-Identifier: BSD-2-Clause-Views
"""Retained native replay + actual MAC/framer/tag/lifetime composition.

Config/authorized control and HLS/memory/core-drain inputs are explicit test
models. MAC bytes/receipts/EOF/tail and retained replay are real production
RTL. No kernel, real HLS drain, native board or error-CQ release proof.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import test_wqe_tx_lifetime_rtl as original

ROOT=original.ROOT
REPLAY=ROOT/'rdma/rnic/rtl/rocev2_wqe_replay.v'

TASKS=r'''
task configure_retry;
 input [4:0] timeout_value;input [2:0] retry_value,rnr_value;
 begin
  @(negedge clk);cfg_qpn=7;cfg_pd=16'hffff;cfg_cookie=64'hfedcba9876543210;
  cfg_epoch=64'h9123456700000001;cfg_timeout=timeout_value;cfg_retry=retry_value;cfg_rnr_retry=rnr_value;cfg_valid=1;
  @(posedge clk);if(!cfg_ready)$fatal(1,"retry config not admitted while idle");
  @(negedge clk);cfg_valid=0;deadline=cycle+20;
  while(!rsp_valid)begin if(cycle>deadline)$fatal(1,"actual retry table readback missing");@(negedge clk);end
  if(rsp_error || rsp_qpn!=7 || rsp_pd!=16'hffff || rsp_cookie!=cfg_cookie || rsp_epoch!=cfg_epoch ||
   rsp_timeout!=timeout_value || rsp_retry!=retry_value || rsp_rnr_retry!=rnr_value)$fatal(1,"retry table readback mismatch");
  rsp_ready=1;@(posedge clk);@(negedge clk);rsp_ready=0;
 end
endtask
task receipt;
 input integer attempt;
 begin
  deadline=cycle+6000;while(frame_count<attempt)begin if(cycle>deadline || fault)$fatal(1,"retry frame deadline");@(negedge clk);end
  @(negedge clk);s_mac_cpl_tag=active_tag;s_mac_cpl_ts=attempt;s_mac_cpl_valid=1;
  @(posedge clk);if(!s_mac_cpl_ready)$fatal(1,"retry actual MAC receipt");
  @(negedge clk);s_mac_cpl_valid=0;#1;
  deadline=cycle+1200;while(mac_proof_count<attempt)begin
   if(cycle>deadline || fault)$fatal(1,"retry receipt/EOF/tail deadline code%h life%h mac%h replay%h state%0d",fault_code,dut.life_fault_code,dut.mac_fault_code,dut.replay_fault_code,dut.retained_replay.replay.state);@(negedge clk);end
 end
endtask
task control;
 input [7:0] syndrome;
 begin
  @(negedge clk);s_control_context=expected_owner;s_control_psn=24'hfffffe;
  s_control_syndrome=syndrome;s_control_valid=1;
  @(posedge clk);if(!s_control_ready)$fatal(1,"authorized retry control not consumed");
  @(negedge clk);s_control_valid=0;
 end
endtask
task wait_final_mac;
 begin
  deadline=cycle+30;
  while(!proof_flags[5] || !local_tx_drained)begin
   if(cycle>deadline || fault)$fatal(1,"final multi-attempt MAC proof missing");@(negedge clk);end
 end
endtask
integer retry_start;
'''

class WQEReplayTests(unittest.TestCase):
    reports={}
    def simulate(self,body,attempts,success=True):
        tb=original.bench(body)
        tb=tb.replace('rocev2_wqe_tx_lifetime dut(.*);',
            'rocev2_wqe_tx_lifetime #(.RETRY_ENABLE(1)) dut(.*);')
        tb=tb.replace('task transmit;',TASKS+'\ntask transmit;',1).replace('cycle>6000','cycle>20000')
        sources=[*original.mac.SOURCES,original.life.RTL,original.RTL,REPLAY]
        consumed=sources+[Path(__file__).resolve(),Path(original.__file__).resolve(),Path(original.life.__file__).resolve()]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in consumed}
        pkt=original.life.request(False)
        with tempfile.TemporaryDirectory(prefix='as02-retained-replay-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            (p/'request.hex').write_text(''.join(f'{int.from_bytes(pkt[i:i+16].ljust(16,b"\0"),"little"):032x}\n'for i in range(0,len(pkt),16)))
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_LIFETIME_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertEqual(rows[0]['committed'],int(success))
            frames=original.mac.decode_frames(r.stdout)
            self.assertEqual(frames,[(0x2000+i,0,bytes.fromhex('b8830367c5d08af3fbb975310800')+pkt)for i in range(1,attempts+1)])
            self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
            self.reports[self._testMethodName]=dict(summary=rows[0],source_sha256=before,attempts=attempts,
                identical_MAC_frames_with_fresh_tags=True,source_unchanged=True,
                models='Authorized control/config, HLS/memory and genuine internal core drain; real MAC/framer/receipt/EOF/tail RTL')
    def prefix(self,timeout=1,retries=1,rnr=1):
        return f'configure_retry(5\'d{timeout},3\'d{retries},3\'d{rnr});'+original.life.body_prefix(False)
    def finish(self):
        return 'wait_final_mac();ticket();take_ticket();commit();'
    def positive(self):return original.life.proofs(False,order=('memory','response','ack'))
    def test_timeout_replays_identical_frame_with_fresh_actual_MAC_receipt(self):
        body=self.prefix()+'receipt(1);'+r'''
if(proof_flags[5] || local_tx_drained || m_cq_valid)$fatal(1,"first attempt receipt became final WR proof");
deadline=cycle+6000;while(frame_count<2)begin if(cycle>deadline || fault)$fatal(1,"timeout did not replay");@(negedge clk);end
'''+self.positive()+'receipt(2);'+self.finish()
        self.simulate(body,2)
    def test_RNR_waits_remote_delay_and_uses_its_separate_retry_budget(self):
        body=self.prefix(retries=0,rnr=1)+'receipt(1);control(8\'h21);retry_start=cycle;'+r'''
deadline=cycle+6000;while(frame_count<2)begin if(cycle>deadline || fault)$fatal(1,"RNR did not replay");@(negedge clk);end
if(cycle-retry_start<2500 || retry_count!=1 || rnr_count!=1)$fatal(1,"RNR delay/budget bypassed");
'''+self.positive()+'receipt(2);'+self.finish()
        self.simulate(body,2)
    def test_timeout_zero_disables_expiration_but_not_actual_completion(self):
        body=self.prefix(timeout=0)+'receipt(1);'+r'''
repeat(3000)begin @(negedge clk);if(frame_count!=1 || retry_count || fault || proof_flags[5] || m_cq_valid)$fatal(1,"infinite ACK timeout expired or completed");end
'''+self.positive()+self.finish()
        self.simulate(body,1)
    def test_exhausted_timeout_retains_full_owner_and_never_publishes_success(self):
        body=self.prefix(retries=0)+'receipt(1);'+r'''
deadline=cycle+6000;while(!fault)begin if(cycle>deadline)$fatal(1,"retry exhaustion missing");@(negedge clk);end
repeat(17)begin @(negedge clk);if(failed_status!=12 || !busy || queue_guard!==8'hff || m_cq_valid || committed_count ||
 dut.retained_replay.replay.owner!==expected_owner || frame_count!=1)$fatal(1,"retry exhaustion released memory/context");end
'''
        self.simulate(body,1,False)
    def test_exhausted_RNR_retains_full_owner_and_never_publishes_success(self):
        body=self.prefix(rnr=0)+'receipt(1);control(8\'h21);'+r'''
repeat(17)begin @(negedge clk);if(!fault || failed_status!=13 || !busy || queue_guard!==8'hff || m_cq_valid || committed_count ||
 dut.retained_replay.replay.owner!==expected_owner || frame_count!=1)$fatal(1,"RNR exhaustion released owner");end
'''
        self.simulate(body,1,False)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_REPLAY_REPORT'):
            result=dict(scope=__doc__,pass_test=len(cls.reports)==5,methods=len(cls.reports),tests=cls.reports,
                actual_MAC_and_cached_replay=True,HLS_memory_core_drain_models=True,hardware_verified=False,
                actual_native_main=False,kernel_or_error_CQ_release=False)
            with (ROOT/name).open('x')as f:f.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':unittest.main()
