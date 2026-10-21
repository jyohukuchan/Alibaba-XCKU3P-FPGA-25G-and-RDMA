#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE PSN/fatal allocator; retain all46 old cases plus actual fatal fanout.

All native certification/HLS/MAC/abort-report-release inputs are MODELS.
This is not native coupling, fatal63, QP/global drain, STOP/error CQ/unpin.
Original4ns/10s/100000-cycle and every old assertion remain.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import probe_write_psn_control as prior
import audit_segmented_receive as binding
sys.path.insert(0,str(prior.ROOT/'rdma/rnic/fpga'))
import derive_write_error_control as candidate
ROOT=prior.ROOT;digest=binding.digest;once=candidate.once

TASK=r'''
task fatal_case;
 begin
  // Helper-only serial test: ordinary control precedes fatal; this is not
  // permission to resume a quarantined native QP after fatal completion.
  if(mode==105)exchange;
  s_error=mode>=100 && mode<=103 ? mode-99:16;s_cert_valid=0;s_valid=1;
  s_qpn=trusted_context[23:0];s_psn=trusted_expected_psn;s_msn=0;s_keep_message=1;
  s_fatal_cert_valid=1;s_fatal_context=trusted_context;
  s_fatal_received_psn=s_psn;s_fatal_expected_psn=trusted_expected_psn;
  s_fatal_syndrome=s_error==16 ? 8'h61:8'h62;
  case(mode)
   120:s_fatal_cert_valid=1'bx;
   121:begin s_cert_valid=1;s_error=18;end
   122:s_fatal_context[23:0]=3;
   123:s_fatal_context[39:24]=0;
   124:s_fatal_context[103:40]=0;
   125:s_fatal_context[167:104]=0;
   126:s_fatal_received_psn[0]=~s_fatal_received_psn[0];
   127:s_fatal_expected_psn[0]=~s_fatal_expected_psn[0];
   128:s_qpn=3;
   129:s_psn=s_psn+24'd1;
   130:s_fatal_syndrome=8'h63;
   131:begin s_error=5;s_fatal_syndrome=8'h62;end
   132:s_fatal_context[104]=1'bx;
   133:s_fatal_syndrome[0]=1'bx;
   134:trusted_expected_psn[0]=1'bx;
   135:trusted_valid=0;
   136:parent_fault=1;
   137:s_valid=1'bx;
   138:s_error[0]=1'bx;
  endcase
  if(mode>=120 && mode<=139)begin tick;bad;end
  else begin
   next_serial=next_serial+64'd1;
   expected_owner={4'd0,s_fatal_syndrome,s_psn,trusted_expected_psn,next_serial,trusted_context};
   proof={16'h6001+issued[15:0],8'd0,24'habc123,expected_owner};tick;
   if(!m_fatal_held || m_fatal_context!==trusted_context)$fatal(1,"fatal quarantine authority absent before wire issue");
   if(mode==146 || mode==147 || mode==149)begin
    if(mode==146)s_fatal_context[104]=~s_fatal_context[104];
    if(mode==147)s_fatal_cert_valid=0;
    if(mode==149)s_fatal_syndrome=8'h62;
    bad;
   end else begin
    owner_and_event;
    s_ack_done=proof;s_ack_done_valid=1;
    if(mode>=140 && mode<=145)begin
     case(mode)
      140:s_ack_done[40]=~s_ack_done[40];
      141:s_ack_done[356]=~s_ack_done[356];
      142:s_ack_done[504]=1;
      143:s_ack_done[527:512]=16'h4001;
      144:s_ack_done[527:512]=16'h6000;
      145:s_ack_done_valid=1'bx;
     endcase
     bad;
    end else begin
     repeat(37)begin tick;
      if(fault || s_ack_done_ready || !m_fatal_wire_valid || m_fatal_wire!==proof ||
       m_ack_retire_valid || m_error_valid || s_ready || !m_fatal_held)
       $fatal(1,"fatal528 fanout did not retain exact owner for abort consumer");
     end
     m_fatal_wire_ready=1;@(posedge clk);
     if(!s_ack_done_ready || !m_fatal_wire_valid)$fatal(1,"fatal proof fanout not one actual handshake");
     @(negedge clk);s_ack_done_valid=0;m_fatal_wire_ready=0;
     repeat(17)begin tick;if(!m_ack_retire_valid || m_fatal_retire_taken ||
       m_fatal_retire_owner!==expected_owner || m_error_valid || s_ready)$fatal(1,"fatal480 real retirement not retained");end
     m_ack_retire_ready=1;@(posedge clk);
     if(!m_fatal_retire_taken || m_fatal_retire_owner!==expected_owner)$fatal(1,"fatal ACK retirement fanout missing");
     @(negedge clk);m_ack_retire_ready=0;m_error_ready=1;
     repeat(37)begin tick;if(fault || m_error_valid || s_ready || m_report_taken || !m_fatal_held)
       $fatal(1,"local fatal reject escaped before abort controller release");end
     fatal_report_release=1;m_error_ready=0;
     repeat(17)begin tick;if(fault || !m_error_valid || s_ready || m_report_taken ||
       m_report_owner!==expected_owner)$fatal(1,"independent local reject consumer did not retain full owner");end
     m_error_ready=1;@(posedge clk);
     if(!s_ready || !m_report_taken || m_report_owner!==expected_owner)$fatal(1,"fatal local report fanout not actual handshake");
     @(negedge clk);s_valid=0;s_fatal_cert_valid=0;fatal_report_release=0;m_error_ready=0;issued=issued+1;#1;
     if(fault || configuration_guard || queue_guard || m_fatal_held || requests!=issued || wire_proofs!=issued ||
       retirements!=issued || reports!=issued)$fatal(1,"PSN/fatal shared serial/event lifecycle corrupted");
     $display("WRITE_FATAL_OWNER %0d %0120h",mode,expected_owner);
    end
   end
  end
 end
endtask
'''


def bench():
    source=candidate.derive()
    decl='\n'.join(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';')
        for d,w,n in candidate.parent.native.ports(source))
    t=once(prior.TB,'rocev2_write_psn_control #(',candidate.NAME+' #(')
    t=once(t,'initial begin',TASK+'\ninitial begin')
    t=once(t,' if(mode==1 || mode==7 || mode==11)begin',
        ' if(mode>=100)begin fatal_case;end else begin\n if(mode==1 || mode==7 || mode==11)begin')
    return once(t,' $display("WRITE_PSN_CONTROL_RESULT ', ' end\n $display("WRITE_PSN_CONTROL_RESULT ').replace('DECLARATIONS',decl)


def fatal_oracle(output,mode):
    rows=[s.split()for s in output.splitlines()if s.startswith('WRITE_FATAL_OWNER ')]
    ctx=0
    for w,v in [(4,2),(48,0xb8830367c5d0),(48,0x8af3fbb97531),(32,0xc6120b01),(32,0xc6120b02),
        (24,196),(64,0x123456789abcdef0),(64,0xfedcba9876543210),(16,7),(24,2)]:ctx=(ctx<<w)|v
    serial=2 if mode==105 else 1;syndrome=0x62 if mode<104 else 0x61
    owner=(syndrome<<468)|(0xffffff<<444)|(0xffffff<<420)|(serial<<356)|ctx
    if len(rows)!=1 or len(rows[0])!=3 or int(rows[0][1])!=mode or int(rows[0][2],16)!=owner:
        raise ValueError('independent full480 fatal owner/same serial required')
    return dict(owner480=f'{owner:0120x}',serial=serial,syndrome=syndrome)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='write-error-control-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-error-control-',dir='/dev/shm'))
    inputs=[Path(__file__).resolve(),Path(prior.__file__).resolve(),Path(candidate.__file__).resolve(),candidate.SOURCE]
    before={str(q.relative_to(ROOT)):digest(q)for q in inputs}
    old_modes=[*range(16),*range(20,50)];modes=[*old_modes,*range(100,106),*range(120,148),149]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},compilations={},planned_modes=modes,
        clock_ns=4,runtime_limit_seconds=10,compile_limit_seconds=10,cycle_limit=100000,producer_boundaries_modeled=True,
        native_fatal_integration=False,QP_global_drain_or_unpin=False,hardware_verified=False,overall_goal_complete=False)
    try:
        (run/'tb.v').write_text(bench());(run/(candidate.NAME+'.v')).write_text(candidate.derive())
        for name,initial in [('normal',0),('near-exhausted',2**64-2),('exhausted',2**64-1)]:
            start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-Ptb.INITIAL_SERIAL='+str(initial),'-o',str(ram/name),str(run/'tb.v'),str(run/(candidate.NAME+'.v'))],capture_output=True,text=True,timeout=10)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr);r['compilations'][name]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            if c.returncode:raise ValueError('actual merged PSN/fatal compile failed:'+name)
        for n in modes:
            name='near-exhausted'if n==13 else'exhausted'if n in [14,139]else'normal'
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/name),'+MODE='+str(n)],capture_output=True,text=True,timeout=10)
            (run/(str(n)+'.log')).write_text(c.stdout+c.stderr);t=dict(exit=c.returncode,seconds=time.monotonic()-start);r['tests'][str(n)]=t
            if c.returncode:raise ValueError('actual PSN/fatal control failed:'+str(n))
            rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_PSN_CONTROL_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['mode']!=n:raise ValueError('actual lifecycle assertions absent')
            t['summary']=rows[0]
            if 100<=n<106:t['independent_fatal_oracles']=fatal_oracle(c.stdout,n)
        old,_=binding.bindings('write-psn-control-001')
        if any(r['tests'][n]['summary']!=t['summary']for n,t in old['tests'].items()):raise ValueError('old46 actual outcomes changed')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during execution')
        r.update(pass_test=True,source_unchanged=True,all46_old_summaries_identical=True,one_PSN_fatal_nonwrapping_serial=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(r['tests']),maximum_seconds=max(t['seconds']for t in r['tests'].values()),native=False)))


if __name__=='__main__':main()
