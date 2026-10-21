#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C descriptor -> real local-write MR -> actual whole posted RQ.

Fetched record/context/MMIO management and error-result consumer are models.
No MR success is invented, no HLS/MAC/CQ proof is injected and no RQ retire
is synthesized. This proves the admitted owner handoff/guard, not PCIe DMA,
HLS receive execution, CQ completion, installed Linux or physical operation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import probe_segmented_receive_admission as admission

ROOT=admission.ROOT;candidate=admission.candidate;once=candidate.once
QUEUE=candidate.RTL/'rocev2_receive_message_queue.v';KERNEL=admission.codec.KERNEL
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def bench(case,encoder):
    original=admission.base.admission.old.old.original
    count=1048576 if case in [0,2]else 8193
    w=admission.base.admission.old.candidate(4,length=count,local_key=original.KEY+(case==1))
    if case==3:w.base.local_key=original.KEY^0x80000000
    error=[0,3,4,1][case];extent=1048576 if case==2 else 1052672
    body=encoder.encoded_entry(w,error=error)
    # Exact full context expected independently from the registered MR grant.
    context=(w.base.wr_id<<524)|(original.SEQ<<460)|(original.EPOCH<<396)|(1<<372)|(7<<356)|(0xf123<<340)|\
        (4<<324)|(1<<308)|(count<<276)|(w.base.local_key<<244)|(w.base.local_address<<180)|(1<<116)|3
    body+=f'''
repeat(5)@(negedge clk);
if(queries!=1 || results!=1 || busy || guard || rq_fault || rq_posted_count!={int(case==0)})$fatal(1,"real MR grant/error did not control RQ posting");
'''
    if case==0:
        body+=f'''
if(rq_queue_guard!==8'h02 || rq_active || !rq_m_head_valid || rq_m_head_context!==620'h{context:0155x})
 $fatal(1,"posted full capacity/MR key/VA/offset/identity changed");
rq_m_head_ready=1;@(posedge clk);if(!rq_m_head_valid)$fatal(1,"actual receive owner take");
@(negedge clk);rq_m_head_ready=0;
if(!rq_active || rq_held_context!==620'h{context:0155x} || rq_taken_count!=1)$fatal(1,"full admitted owner not retained");
// The frontend has handed off, but actual RQ ownership now blocks MR revoke.
cfg_command=2;cfg_index=0;cfg_key=32'h80000008;cfg_valid=1;
repeat(17)begin @(negedge clk);
 if(cfg_ready || cfg_response_valid || rq_queue_guard!==8'h02 || !rq_active || rq_m_ticket_valid || rq_m_packet_retire_valid)
 $fatal(1,"MR/RQ guard handoff lost owner or invented a completion");
end
cfg_valid=0;
'''
    else:body+='if(rq_queue_guard || rq_active || rq_m_head_valid || rq_m_ticket_valid)$fatal(1,"denied MR posted receive authority");\n'
    t=admission.base.admission.old.bench(body,True)
    t=once(t,'rocev2_atomic128_sq_wqe_admission #(','rocev2_sq_wqe_admission #(')
    if t.count("64'd8192")!=2:raise ValueError('both real registered MR extents required')
    t=t.replace("64'd8192",f"64'd{extent}")
    t=once(t,'.m_work_ready(ready)', '.m_work_ready(ready && (oe!=0 || rq_s_post_ready))')
    t=once(t,'.cfg_quiescent(!guard)', '.cfg_quiescent(!guard && rq_queue_guard==0)')
    t=once(t,'ostalled=ov&&!ready;', 'ostalled=ov&&!(ready && (oe!=0 || rq_s_post_ready));')
    t=once(t,'if(ov&&ready)results=results+1;', 'if(ov&&ready && (oe!=0 || rq_s_post_ready))results=results+1;')
    header=QUEUE.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',header)
    wires={'clk':'clk','rst':'rst','parent_fault':'fault','s_post_context':'rq_post_context',
        's_post_valid':'ov && ready && authorized && oe==0','query_qpn':"24'd1"}
    lines=['localparam MAX_QPS=8;', 'wire [619:0] rq_post_context={oimm,oid,oseq,oepoch,oq,opd,ot,oop,oflags,olen,olk,ola,ooff,ora,ork,20\'d3};']
    connections=[]
    for d,width,n in ports:
        if n in wires:connections.append('.'+n+'('+wires[n]+')');continue
        lines.append(('reg 'if d=='input'else'wire ')+(width or'')+'rq_'+n+('=0;'if d=='input'else';'))
        connections.append('.'+n+'(rq_'+n+')')
    lines.append('rocev2_receive_message_queue rq('+','.join(connections)+');')
    lines.append(f'''always @(posedge clk)if(!rst && qv && qr && allow_q)begin
if(qlen!==32'd{count} || qa!==64'h{w.base.local_address:016x} || qkey!==32'h{w.base.local_key:08x} || qop!==3'd1)
 $fatal(1,"full-capacity actual local-write MR query required before RQ authority");
end''')
    t=once(t,'reg clk=0;','\n'.join(lines)+'\nreg clk=0;')
    return t,count,extent


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    generated=candidate.derive();run=Path(tempfile.mkdtemp(prefix='receive-mr-post-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-mr-post-',dir='/dev/shm'))
    inputs=[QUEUE,candidate.RTL/'rocev2_mr_table.v',Path(__file__).resolve(),Path(admission.__file__).resolve(),
        *list((ROOT/'rdma/rnic/fpga').glob('derive_*.py')),*[KERNEL/n for n in admission.codec.SOURCES],*KERNEL.glob('wqe*.h')]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs};leaves=[]
    for n in ['rocev2_wqe_admission.v','rocev2_sq_wqe_admission.v']:
        q=run/n;q.write_text(generated[candidate.RTL/n]);leaves.append(q)
    shutil.copy2(QUEUE,run/QUEUE.name)
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        runtime_limit_seconds=10,actual_C128_real_MR_and_posted_RQ=True,no_synthetic_MR_or_completion=True,
        raw_fetch_context_MMIO_and_error_consumer_modeled=True,full_native_or_physical=False,hardware_verified=False)
    try:
        admission.ReceiveAdmission.setUpClass();encoder=admission.ReceiveAdmission('test_receive_full_posted_capacity_real_MR_query_and_stalls')
        for case in range(4):
            tb,count,extent=bench(case,encoder);path=run/(str(case)+'.v');path.write_text(tb)
            command=['iverilog','-g2012','-s','tb','-o',str(ram/str(case)),str(path),*map(str,leaves),str(run/QUEUE.name),str(candidate.RTL/'rocev2_mr_table.v')]
            c=subprocess.run(command,capture_output=True,text=True,timeout=30);(run/(str(case)+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise ValueError('real MR/RQ compile failed:'+str(run/(str(case)+'-compile.log')))
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/str(case))],capture_output=True,text=True,timeout=10)
            (run/(str(case)+'.log')).write_text(c.stdout+c.stderr)
            result['tests'][str(case)]=dict(exit=c.returncode,seconds=time.monotonic()-start,posted_capacity=count,registered_extent=extent)
            if c.returncode or 'WQE_ADMISSION_PASS'not in c.stdout:raise ValueError('real MR/RQ failed:'+str(run/(str(case)+'.log')))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,full_range_query_and_guard_handoff=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        if hasattr(admission.ReceiveAdmission,'directory'):admission.ReceiveAdmission.directory.cleanup()
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),maximum_case_seconds=max(t['seconds']for t in result['tests'].values()))))


if __name__=='__main__':main()
