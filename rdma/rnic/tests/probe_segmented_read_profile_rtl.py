#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual private RNC16383/CQC63 register/CQ contract, not kernel support.

Retain all controller scenarios/dependency refusals and old CQ owners; add
whole large READ CQ owners. Upstream controller/ticket/commit/retire modeled.
Old8191/31/kernel/provider/default profile stays distinct and unchanged.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import probe_segmented_profile_rtl as old

ROOT=old.ROOT;digest=old.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_profile as source


def control_bench(disabled=None):
    t=old.control_bench(disabled)
    before=8191 if disabled is None else 8191^(1<<(old.FLAGS.index(disabled)+1))
    after=16383 if disabled is None else 16383^(1<<(old.FLAGS.index(disabled)+1))
    return source.once(t,f'if(value!=={before})',f'if(value!=={after})')


def cq_bench():
    t=source.once(old.cq_bench(),'host_value!=31)$fatal(1,"message feature ABI")',
        'host_value!=63)$fatal(1,"message feature ABI")')
    body=''
    for seq,length in enumerate([4097,8193,65537,1048576],9):
        body+=f'publish({old.cq.owner(2,pd=17,sequence=seq,tag=seq,length=length)},0,{seq},0);\n'
    return source.once(t,' if(pub_published!=8 || pub_acked!=8)',body+' if(pub_published!=12 || pub_acked!=12)')


def reject_bench(value):
    return old.reject_bench(value)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='segmented-read-profile-rtl-',dir=ROOT/'rdma/rnic/build'))
    generated=source.derive();parent=source.parent.derive()
    changed={q.name for q in generated if generated[q]!=parent[q]}
    if changed!={'rocev2_wqe_admission.v','rocev2_wqe_hls_sq.v','rocev2_control_regs.v','rocev2_cq_mmio.v'}:
        raise ValueError('only actual READ admission/identity/CQ gates may change')
    for n in ['rocev2_control_regs.v','rocev2_cq_mmio.v']:(run/n).write_text(generated[source.RTL/n])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*helpers,*list((ROOT/'rdma/rnic/fpga').glob('*.py')),*old.control.SOURCES,*source.RTL.glob('*.v')]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(inputs)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        four_state=True,RNC_features=16383,CQC_features=63,kernel_profile_matched=False,owner_bits=748,
        default_sources_changed=False,native_runtime=False,actual_Linux_runtime=False,hardware_verified=False,
        simulation_limit_seconds=10,tests={})
    try:
        cases=[('control'+str(i),control_bench(),['+case='+str(i)],False)for i in range(6)]
        cases += [('without_'+f,control_bench(f),['+case=0'],f!='IMMEDIATE')for f in old.FLAGS]
        cases += [('CQ_old8_and_READ4',cq_bench(),[],False)]
        invalid=[old.cq.owner(8,pd=17,compare=1),old.cq.owner(2,pd=17,argument=1),old.cq.owner(7,pd=17,length=9),
            old.cq.owner(7,pd=17,immediate=1),old.cq.owner(8,pd=17,remote=1)]
        invalid += [old.cq.owner(op,pd=17,length=1048577 if op in [1,2,3]else 8193)for op in [1,3,2,4,5,6]]
        cases += [('CQ_invalid'+str(i),reject_bench(v),[],False)for i,v in enumerate(invalid)]
        if len(cases)!=27:raise ValueError('all27 register/CQ cases required')
        for name,t,args,expected_fatal in cases:
            case=run/name;case.mkdir();(case/'tb.v').write_text(t)
            leaf=run/('rocev2_control_regs.v'if name.startswith(('control','without_'))else'rocev2_cq_mmio.v')
            cmd=['iverilog','-g2012','-s','tb','-o',str(case/'test.vvp'),str(case/'tb.v'),str(leaf),*map(str,old.control.SOURCES[1:])]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(case/'compile.log').write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('register/CQ compile failed:'+name)
            start=time.monotonic();r=subprocess.run(['vvp',str(case/'test.vvp'),*args],capture_output=True,text=True,timeout=10)
            output=r.stdout+r.stderr;(case/'simulation.log').write_text(output)
            item=dict(seconds=time.monotonic()-start,exit=r.returncode,expected_dependency_fatal=expected_fatal);report['tests'][name]=item
            if expected_fatal:
                if r.returncode==0 or 'Immediate capability requires the complete matched native profile'not in output:
                    raise ValueError('required dependency refusal missing:'+name)
            elif r.returncode or 'ERROR:'in output or 'FATAL:'in output:raise ValueError('register/CQ runtime failed:'+name)
            elif name.startswith(('control','without_')):
                rows=[json.loads(l[7:])for l in output.splitlines()if l.startswith('RESULT ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual RNC evidence missing:'+name)
                item['summary']=rows[0]
            elif name=='CQ_old8_and_READ4':
                if 'MESSAGE_CQ_RESULT 'not in output:raise ValueError('12 real immutable CQ events required')
                item['published_and_acked']=12
            elif 'SEGMENTED_CQ_REJECT'not in output:raise ValueError('CQ refusal missing')
            item['pass_test']=True
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.rglob('*')if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(report['tests']),RNC_features=16383,CQC_features=63)))


if __name__=='__main__':main()
