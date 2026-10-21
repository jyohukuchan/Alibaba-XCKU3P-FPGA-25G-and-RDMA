#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual RNC8191/CQC31 AXI reads and full-owner publisher, four-state.

Retain all six controller-mailbox scenarios and four prior CQ owners; add
large WRITE/SEND and fail-closed identity/owner controls. Controller and
upstream CQ ticket/commit/retire endpoints are models, not native DMA/Linux.
Never install/load/program hardware or alter the default RTL selection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import test_control_regs_rtl as control
import test_atomic128_cq_rtl as cq

ROOT=control.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_profile as source
sys.path.insert(0,str(ROOT/'rdma/rnic/kernel'))
import derive_segmented_kernel as kernel

FLAGS=['QP_TX','SEND','RECV','RNR','RECV_RETIRE','RECV_CQ','REQUEST_CQ','SEPARATE_RQ','IMMEDIATE']
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def control_bench(disabled=None):
    decl=[]
    ports=control.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    for line in ports.splitlines():
        m=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
        if m:
            decl.append(('reg 'if m[1]=='input'else'wire ')+m[2].rstrip(',')+('=0;'if m[1]=='input'else';'))
    abi=[f"localparam {n}=32'h{int(v,0):x};"for n,v in re.findall(
        r'^#define (AS02_CTL_\w+) (0x[0-9a-fA-F]+|\d+)U$',control.HEADER.read_text(),re.M)]
    t=control.TB.replace('// PORTS','\n'.join(decl)).replace('// ABI','\n'.join(abi))
    params=','.join('.'+n+'_ENABLE('+str(int(n!=disabled))+')'for n in FLAGS)
    t=source.once(t,'rocev2_control_regs dut(.*);','rocev2_control_regs #('+params+') dut(.*);')
    expected=8191 if disabled is None else 8191^(1<<(FLAGS.index(disabled)+1))
    return source.once(t,'if(value!==1) $fatal(1,"capability overclaim");',
        f'if(value!=={expected}) $fatal(1,"exact private capability identity");')


def cq_bench():
    t=source.once(cq.bench(),'host_value!=15)$fatal(1,"message feature ABI")',
        'host_value!=31)$fatal(1,"message feature ABI")')
    body='notification=0;notification_flags=0;\n'
    for seq,(op,length)in enumerate([(1,8193),(3,8193),(1,1048576),(3,1048576)],5):
        body+=f'publish({cq.owner(op,pd=17,sequence=seq,tag=seq,length=length)},0,{seq},0);\n'
    t=source.once(t,' if(pub_published!=4 || pub_acked!=4)',body+' if(pub_published!=8 || pub_acked!=8)')
    return t


def reject_bench(value):
    t=cq_bench();a=t.index('initial begin\n repeat(5)')
    t=t[:a]+r'''
initial begin
 repeat(5)@(posedge clk);@(negedge clk);rst=0;
 m_cq_context=BAD_OWNER;m_cq_valid=1;
 repeat(7)@(negedge clk);
 if(!pub_fault || pub_fault_code!==8'hc2 || m_cq_ready || s_cq_commit_valid || pub_retire_valid ||
   pub_published || pub_acked || pub_guard!==8'hff)$fatal(1,"invalid owner acquired CQ authority");
 $display("SEGMENTED_CQ_REJECT");$finish;
end
endmodule
'''
    return source.once(t,' if(pub_fault)$fatal(1,"message CQ fault %h",pub_fault_code);','').replace('BAD_OWNER',value)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    run=Path(tempfile.mkdtemp(prefix='segmented-profile-rtl-',dir=ROOT/'rdma/rnic/build'))
    out=source.derive();parent=source.parent.derive();k=kernel.derive()
    changed=[p.name for p in out if out[p]!=parent[p]]
    if set(changed)!={'rocev2_control_regs.v','rocev2_cq_mmio.v'}:raise ValueError('only exact identity leaves may change')
    if '#define AS02_CTL_SEGMENTED_NATIVE_FEATURES 8191U'not in k[kernel.KERNEL/'rnic_regs.h']or \
       '#define AS02_CQC_SEGMENTED_FEATURE_VALUE 31U'not in k[kernel.KERNEL/'atomic_profile.h']:
        raise ValueError('actual matched kernel tuple differs')
    for n in changed:(run/n).write_text(out[source.RTL/n])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    inputs=[*helpers,control.RTL,control.HEADER,cq.source.CQ,*control.SOURCES[1:],
        *[p for p in parent if p.is_file()],*source.RTL.glob('*.v'),*(ROOT/'rdma/rtl').glob('*.v'),
        *[p for p in kernel.KERNEL.glob('*')if p.is_file()and p.suffix in ['.c','.h']]]
    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(inputs)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        four_state=True,RNC_features=8191,CQC_features=31,software_profile=4,owner_bits=748,
        changed_parent_leaves=changed,default_sources_changed=False,native_DMA_runtime=False,
        actual_Linux_runtime=False,hardware_verified=False,simulation_limit_seconds=10,tests={})
    try:
        cases=[('control'+str(i),control_bench(),['+case='+str(i)],False)for i in range(6)]
        cases += [('without_'+f,control_bench(f),['+case=0'],f!='IMMEDIATE')for f in FLAGS]
        cases += [('CQ_old4_and_large4',cq_bench(),[],False)]
        invalid=[cq.owner(8,pd=17,compare=1),cq.owner(2,pd=17,argument=1),cq.owner(7,pd=17,length=9),
                 cq.owner(7,pd=17,immediate=1),cq.owner(8,pd=17,remote=1)]
        invalid += [cq.owner(op,pd=17,length=1048577 if op in [1,3]else 8193)for op in [1,3,2,4,5,6]]
        cases += [('CQ_invalid'+str(i),reject_bench(v),[],False)for i,v in enumerate(invalid)]
        if len(cases)!=27:raise ValueError('all27 cases required')
        for name,t,args,expected_fatal in cases:
            case=run/name;case.mkdir();(case/'tb.v').write_text(t)
            leaf=run/('rocev2_control_regs.v'if name.startswith(('control','without_'))else'rocev2_cq_mmio.v')
            command=['iverilog','-g2012','-s','tb','-o',str(case/'test.vvp'),str(case/'tb.v'),str(leaf),*map(str,control.SOURCES[1:])]
            c=subprocess.run(command,capture_output=True,text=True,timeout=20);(case/'compile.log').write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('compile failed:'+name)
            start=time.monotonic();r=subprocess.run(['vvp',str(case/'test.vvp'),*args],cwd=case,capture_output=True,text=True,timeout=10)
            output=r.stdout+r.stderr;(case/'simulation.log').write_text(output)
            result=dict(seconds=time.monotonic()-start,exit=r.returncode,expected_dependency_fatal=expected_fatal)
            report['tests'][name]=result
            if expected_fatal:
                if r.returncode==0 or 'Immediate capability requires the complete matched native profile'not in output:
                    raise ValueError('missing dependency refusal:'+name)
            elif r.returncode or 'ERROR:'in output or 'FATAL:'in output:raise ValueError('runtime failed:'+name)
            elif name.startswith('control')or name.startswith('without_'):
                rows=[json.loads(l[7:])for l in output.splitlines()if l.startswith('RESULT ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('controller evidence missing:'+name)
                result['summary']=rows[0]
            elif name=='CQ_old4_and_large4':
                if 'MESSAGE_CQ_RESULT 'not in output:raise ValueError('eight actual immutable CQ events required')
                result['published_and_acked']=8
            elif 'SEGMENTED_CQ_REJECT'not in output:raise ValueError('CQ refusal not observed')
            result['pass_test']=True
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.rglob('*')if p.is_file()}
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(report['tests']),directory=str(run))))


if __name__=='__main__':main()
