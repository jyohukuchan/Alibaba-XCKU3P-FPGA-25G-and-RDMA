#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual remote-WRITE message guard, MR table and late-notice RQ coupling.

Real MR management/checks, full-message/per-packet authorization, guards,
RQ take, count, CQ ticket/commit/retirement run together in four-state RTL.
Integrity/QP metadata, posted RQ admission, backend/HLS/MAC certificates
and CQ consumers remain explicit models. No payload DMA, native generated
HLS or Linux/physical execution is claimed by this component test.
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

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_notice_binding_queue as queue
import probe_write_notice_queue as old_queue_test

GUARD=ROOT/'rdma/rnic/rtl/rocev2_remote_write_message_guard.v'
MR=ROOT/'rdma/rnic/rtl/rocev2_mr_table.v'
BENCH=Path(__file__).with_name('remote_write_mr_notice_tb.v')
MODES=list(range(46))


def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def ports(text):
    """Inventory every comma-shared ANSI port, not only the first name."""
    header=text.split(')(\n',1)[1].split('\n);',1)[0]
    header=re.sub(r'//[^\n]*','',header)
    result=[];direction=None;width=''
    for item in header.split(','):
        item=item.strip()
        m=re.fullmatch(r'(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s*)?(\w+)(?:\s*=\s*\S+)?',item)
        if m:direction,width,name=m.group(1),m.group(2)or'',m.group(3)
        else:
            m=re.fullmatch(r'(\w+)(?:\s*=\s*\S+)?',item)
            if not m or direction is None:raise ValueError('unparsed port:'+item)
            name=m.group(1)
        result.append((direction,width.strip(),name))
    if len({n for _,_,n in result})!=len(result):raise ValueError('duplicate port')
    return result


def bench(guard_text,queue_text):
    wire_inputs={'m_mr_ready','s_mr_tag','s_mr_error','s_mr_offset','s_mr_address',
        's_mr_length','s_mr_valid','s_rq_context','s_rq_valid','m_notice_ready',
        's_notice_retire_context','s_notice_retire_valid'}
    decl=[]
    for d,w,n in ports(guard_text):
        reg=d=='input'and n not in wire_inputs
        decl.append(('reg 'if reg else'wire ')+(w+' 'if w else'')+n+('=0;'if reg else';'))
    special=dict(clk='clk',rst='rst',parent_fault='parent_fault || fault',query_qpn='trusted_qpn',
        s_write_notice_context='m_notice_context',s_write_notice_last_psn='m_notice_last_psn',
        s_write_notice_valid='m_notice_valid',s_write_notice_ready='m_notice_ready',
        m_notice_head_context='s_rq_context',m_notice_head_valid='s_rq_valid',m_head_ready='m_notice_valid',
        m_write_retire_context='raw_notice_retire_context',m_write_retire_valid='raw_notice_retire_valid',
        m_write_retire_ready='s_notice_retire_ready && retire_allow')
    q_decl=[];connections=[]
    for d,w,n in ports(queue_text):
        connections.append('.'+n+'('+special.get(n,'q_'+n)+')')
        if n not in special:
            q_decl.append(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+'q_'+n+('=0;'if d=='input'else';'))
    text=BENCH.read_text()
    for marker,value in [('GUARD_PORT_DECLARATIONS','\n'.join(decl)),
        ('QUEUE_PORT_DECLARATIONS','\n'.join(q_decl)),
        ('QUEUE_INSTANTIATION',queue.NAME+' actual_rq(\n'+',\n'.join(connections)+'\n);')]:
        if text.count('// '+marker)!=1:raise ValueError('exact fixture marker:'+marker)
        text=text.replace('// '+marker,value)
    return text


def verify(mode,s):
    if s.get('pass_test')is not True or s['mode']!=mode:raise ValueError('missing RTL assertion result')
    positive={0:(8193,0),1:(8193,1),2:(1048576,1),3:(8192,1),4:(8193,1),5:(4097,1),38:(8193,0)}
    if mode in positive:
        total,imm=positive[mode];packets=(total+4095)//4096
        expected=dict(MR_queries=packets+1+(mode==4),grants=packets,completed_packets=packets,
            completed_messages=1,cancelled_messages=0,RQ_posted=imm,RQ_taken=imm,fault=0,message_active=0)
    elif mode in [34,40]:
        expected=dict(MR_queries=2,grants=1,completed_packets=1,completed_messages=0,
            cancelled_messages=1,RQ_taken=0,fault=0,message_active=0)
    elif mode<=21 or mode==37:
        expected=dict(MR_queries=1 if mode<=10 else 0,grants=0,completed_packets=0,
            completed_messages=0,cancelled_messages=0,RQ_taken=0,fault=0,message_active=0)
    else:
        faults={27,28,29,30,31,32,33,35,36,39,41,42,43,44,45}
        expected=dict(completed_messages=0,cancelled_messages=0,fault=int(mode in faults))
    for k,v in expected.items():
        if s[k]!=v:raise ValueError(f'independent case{mode} {k}: {s[k]} != {v}')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='remote-write-mr-notice-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-remote-write-mr-notice-',dir='/dev/shm'))
    authored=[GUARD,MR,BENCH,Path(__file__).resolve(),Path(queue.__file__).resolve(),queue.SOURCE,
        Path(queue.parent.__file__).resolve(),Path(old_queue_test.__file__).resolve(),
        ROOT/'rdma/rnic/tests/probe_receive_message_queue.py']
    before={str(n.relative_to(ROOT)):digest(n)for n in authored}
    q_text=queue.derive()
    for path in [GUARD,MR]:shutil.copy2(path,run/path.name)
    (run/(queue.NAME+'.v')).write_text(q_text)
    (run/'tb.v').write_text(bench(GUARD.read_text(),q_text))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        tests={},planned_modes=MODES,case_limit_seconds=10,compile_limit_seconds=10,
        original_clock_ns=4,cycle_limit=100000,MAX_QPS=8,four_state=True,
        actual_remote_MR_table=True,actual_late_RQ=True,MR_response_successes_never_fabricated=True,
        negative_MR_transport_corruptions=[31,32,45],posted_RQ_admission_modeled=True,
        integrity_QP_context_backend_HLS_MAC_CQ_consumers_modeled=True,
        payload_DMA_executed=False,generated_HLS_or_native_integration=False,
        live_Linux_RTL_coupling=False,hardware_verified=False)
    base=['iverilog','-g2012','-s','tb']
    inputs=[str(run/n)for n in ['tb.v',GUARD.name,MR.name,queue.NAME+'.v']]
    try:
        result['compile_commands']=[]
        for name,override in [('normal',[]),('exhausted',["-Ptb.COOKIE_INIT=64'hffffffffffffffff"])]:
            command=base+override+['-o',str(ram/name)]+inputs;result['compile_commands'].append(command)
            start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=10)
            (run/(name+'-compile.log')).write_text(c.stdout+c.stderr)
            result[name+'_compile_seconds']=time.monotonic()-start
            if c.returncode:raise ValueError('actual component compile failure:'+str(run/(name+'-compile.log')))
        for mode in MODES:
            name='exhausted'if mode==37 else'normal';start=time.monotonic()
            try:c=subprocess.run(['vvp',str(ram/name),'+MODE='+str(mode)],capture_output=True,text=True,timeout=10)
            except subprocess.TimeoutExpired as e:
                (run/(str(mode)+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''))
                result['tests'][str(mode)]=dict(exit=None,timed_out=True,seconds=time.monotonic()-start)
                raise
            (run/(str(mode)+'.log')).write_text(c.stdout+c.stderr)
            t=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=t
            if c.returncode:raise ValueError('actual MR/notice assertion failed:'+str(run/(str(mode)+'.log')))
            rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith('REMOTE_WRITE_MR_RESULT ')]
            if len(rows)!=1:raise ValueError('exactly one RTL summary required')
            t['summary']=rows[0];verify(mode,rows[0])
        # Re-run all62 exact earlier queue modes on the new variant. These
        # remain component certificate-producer models, not native proof.
        old_bench=old_queue_test.write_notice_bench(run/(queue.NAME+'.v'))
        old_bench=queue.once(old_bench,old_queue_test.candidate.NAME+' dut(.*);',queue.NAME+' dut(.*);')
        (run/'old-queue-tb.v').write_text(old_bench)
        old_command=base+['-o',str(ram/'old-queue'),str(run/'old-queue-tb.v'),str(run/(queue.NAME+'.v'))]
        c=subprocess.run(old_command,capture_output=True,text=True,timeout=10)
        (run/'old-queue-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('unchanged old queue test compilation failed')
        result['old_queue_tests']={};result['old_queue_compile_command']=old_command
        for mode in [*range(6),*range(10,16),*range(20,56),*range(100,114)]:
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'old-queue'),'+MODE='+str(mode)],capture_output=True,text=True,timeout=10)
            (run/('old-'+str(mode)+'.log')).write_text(c.stdout+c.stderr)
            t=dict(exit=c.returncode,seconds=time.monotonic()-start);result['old_queue_tests'][str(mode)]=t
            if c.returncode:raise ValueError('retained old queue assertion failed:'+str(mode))
            rows=[json.loads(l.split(' ',1)[1])for l in c.stdout.splitlines()if l.startswith('MESSAGE_RQ_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['mode']!=mode:raise ValueError('old queue RTL result missing')
            t['summary']=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('actual input changed')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),
        maximum_seconds=max(v['seconds']for v in result['tests'].values()),native_or_physical=False)))


if __name__=='__main__':main()
