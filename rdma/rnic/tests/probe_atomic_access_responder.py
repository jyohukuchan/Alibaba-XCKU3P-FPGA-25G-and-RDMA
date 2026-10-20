#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual QP AND MR Atomic permission with real exclusive paged-memory RTL.

QP permission is the immutable upstream trusted contract here; full native
SQC/RX propagation is NOT exercised by this component. Private PSN/MSN mode.
Reuse14 original memory/replay/failure cases unchanged, plus captured QP
denial/allow/unknown and denial BEFORE cached replay. No physical/API proof.
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
import probe_atomic_responder as old

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_access_native as source
digest=old.digest

EXTRA=r'''
  14,15,17:begin
   qp_access=scenario==15 ? 4'hx:4'h6;
   before_cmd=commands;before_queries=actual_mr_queries;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   if(scenario==17)qp_access=14;
   ack(0,24'hfffffe,24'hfffffe,0,8'h62);
   if(commands!=before_cmd || actual_mr_queries!=before_queries || actual_locks || a_executed_count ||
      load64(4096)!==64'hf123456789abcdef || a_m_response_advance || !atomic.qp_error[0])
    $fatal(1,"denied/unknown captured QP permission reached lock/MR/DMA/sequence");
  end
  16:begin
   qp_access=14;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   qp_access=6;
   ack(0,24'hfffffe,24'hffffff,64'hf123456789abcdef,8'h1f);
   if(load64(4096)!==64'hf123456789abcdf0 || a_executed_count!=1 || actual_mr_queries!=1 || commands!=2)
    $fatal(1,"accepted QP authority was replaced by live permission input");
  end
  18:begin
   one(8'h14,0,24'hfffffe,24'hffffff,1,0,64'hf123456789abcdef,64'hf123456789abcdf0);
   before_cmd=commands;before_queries=actual_mr_queries;qp_access=6;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   ack(0,24'hfffffe,24'hffffff,0,8'h62);
   if(commands!=before_cmd || actual_mr_queries!=before_queries || a_replay_count || a_executed_count!=1)
    $fatal(1,"denied QP replayed cached AtomicACK or accessed memory");
  end
'''


def bench():
    t=source.once(old.bench(),'rocev2_atomic_responder atomic(',
        "reg [3:0] qp_access=14;\ninteger actual_mr_queries=0,actual_locks=0,before_queries=0;\n"
        "always @(posedge clk)if(!rst)begin\n"
        " if(a_m_mr_valid && a_m_mr_ready)actual_mr_queries=actual_mr_queries+1;\n"
        " if(a_memory_lock_request)actual_locks=actual_locks+1;\nend\n"
        'rocev2_atomic_responder atomic(.s_request_access(qp_access),')
    return source.once(t,'  default:$fatal(1,"unknown case");',EXTRA+'\n  default:$fatal(1,"unknown case");')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    run=Path(tempfile.mkdtemp(prefix='atomic-access-responder-',dir=ROOT/'rdma/rnic/build'))
    own=[*old.SOURCES,Path(__file__).resolve(),Path(old.__file__).resolve(),Path(source.__file__).resolve(),Path(old.paged.__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in own}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        simulation_limit_seconds=10,hardware_verified=False,shared_HLS=False,native_integrated=False,
        QP_authority_source_modeled=True,physical_descriptor_host_visibility_modeled=True,tests={})
    try:
        (run/'atomic.v').write_text(source.executor());(run/'tb.v').write_text(bench())
        src=[run/'atomic.v',*old.SOURCES[1:]]
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,src)],
            capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('QP permission composition compile failed: '+str(run/'compile.log'))
        for case in range(19):
            start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp'),f'+case={case}'],capture_output=True,text=True,timeout=10)
            (run/f'{case}.log').write_text(r.stdout+r.stderr)
            row=dict(seconds=time.monotonic()-start,exit=r.returncode);report['tests'][case]=row
            if r.returncode:raise ValueError('actual permission runtime failed: '+str(run/f'{case}.log'))
            summary=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_RESULT ')]
            if len(summary)!=1 or not summary[0]['pass_test'] or summary[0]['case']!=case:raise ValueError('actual assertions absent')
            row['summary']=summary[0];replies=[]
            for line in r.stdout.splitlines():
                if not line.startswith('ATOMIC_REPLY '):continue
                _,raw,size,q,psn,msn,value,syn=line.split();size=int(size);q=int(q)
                psn,msn,value,syn=[int(s,16)for s in [psn,msn,value,syn]]
                expected=bytes([0x12 if syn==0x1f else 0x11,0])+struct.pack('!HII',0xffff,0xf12345+q,psn)
                expected+=bytes([syn])+msn.to_bytes(3,'big')+(struct.pack('!Q',value)if syn==0x1f else bytes(8))
                actual=int(raw,16).to_bytes(24,'little')
                if actual!=expected or size!=(24 if syn==0x1f else 16):raise ValueError('independent whole response oracle')
                replies.append(dict(bytes=size,wire_hex=actual[:size].hex(),wire_oracle_pass=True))
            row['independent_wire_replies']=replies
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(report['tests']),max_runtime_seconds=max(t['seconds']for t in report['tests'].values()))))


if __name__=='__main__':main()
