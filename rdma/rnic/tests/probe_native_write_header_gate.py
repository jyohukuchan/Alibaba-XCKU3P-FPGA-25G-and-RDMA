#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native FIRST-header gate plus every512 unchanged classifier oracle.

Hold a new frame while the previous WRITE classification is still opposite;
zero/unknown admission must not accept it. Release with the current real
message state, then close admission after FIRST: SECOND and all buffered/body
beats must still drain. No authority, full-native payload or physical claim.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import probe_native_write_classifier as parent

ROOT=parent.ROOT;digest=parent.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_native as candidate
once=candidate.once


def bench():
    t=once(parent.TB,'force_write=0;always','force_write=0,allow_header=1;always')
    t=once(t,'force_write=held;expected=held || op>=6 && op<=9;out_count=0;',
        'allow_header=0;force_write=!held;expected=held || op>=6 && op<=9;out_count=0;')
    t=once(t,'  for(i=0;i<5;i=i+1)begin\n   s_data=words[i];',r'''
  s_data=words[0];s_keep=16'hffff;s_last=0;s_valid=1;
  for(i=0;i<5;i=i+1)begin
   allow_header=i[0] ? 1'bx:1'b0;
   @(posedge clk);
   if(s_ready || ov || !configuration_guard || dut.state!==dut.FIRST)
    $fatal(1,"new header accepted before current message classification ready");
   @(negedge clk);
  end
  force_write=held;allow_header=1;
  for(i=0;i<5;i=i+1)begin
   s_data=words[i];''')
    t=once(t,'   if(i==1)force_write=!held;',
        '   if(i==0)allow_header=0;\n   if(i==1)force_write=!held;')
    return once(t,'"force_states\\\":2,','"force_states\\\":2,\\\"blocked_FIRST_cycles\\\":2560,\\\"gate_closed_after_FIRST\\\":true,')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every earlier report')
    run=Path(tempfile.mkdtemp(prefix='native-write-header-gate-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-native-write-header-gate-',dir='/dev/shm'))
    inputs=[Path(__file__).resolve(),Path(parent.__file__).resolve(),Path(candidate.__file__).resolve(),
        Path(candidate.leaves.__file__).resolve(),candidate.leaves.ROUTER]
    before={str(q.relative_to(ROOT)):digest(q)for q in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        compile_limit_seconds=10,runtime_limit_seconds=10,clock_ns=4,cycle_limit=100000,
        hardware_verified=False,complete_native=False,actual_native_header_extension=True)
    try:
        (run/'router.v').write_text(candidate.native_router());(run/'tb.v').write_text(bench())
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/'router.v')],capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('native header gate compile failed')
        start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(c.stdout+c.stderr);result.update(exit=c.returncode,simulation_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('actual512-frame native header gate failed')
        rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_CLASSIFIER_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['blocked_FIRST_cycles']!=2560 or not rows[0]['gate_closed_after_FIRST']:
            raise ValueError('full actual gated routing assertions missing')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,frames=512,seconds=result['simulation_seconds'])),flush=True)


if __name__=='__main__':main()
