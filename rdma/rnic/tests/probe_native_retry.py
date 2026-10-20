#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short whole-native-path retry integration, not standalone timer evidence.

Actual AXI/SQC1 owner lookup/RRP1/replay/MAC/response guard/READ placement,
single MR/PTE/executor and PCIe ownership. HLS state/wire, host and physical
MAC are explicit models. Two-state compiled simulation does NOT prove X/Z,
whole-core drain, physical timing, standard verbs or hardware operation.
"""
import argparse
import hashlib
import json
import os
import resource
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import test_native_qp_tx_rtl as qp

ROOT=qp.ROOT
TOOL=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator')

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def case(write=False):
    m=qp.main;tb,words,records,request=qp.case(write)
    tb=m.sq.once(tb,'.QP_TX_ENABLE(1)', '.QP_TX_ENABLE(1),.RETRY_ENABLE(1)')
    tb=m.sq.once(tb,"expect_decerr(24'h404000);",r'''
read_reg(24'h404000,sq_value);if(sq_value!==32'h52525031)$fatal(1,"actual RRP1 aperture missing");
read_reg(24'h40401c,sq_value);if(sq_value!==4000)$fatal(1,"actual replay timer clock contract");
''')
    policy=r'''
// Program through the ACTUAL main AXI decoder and trusted SQC1 owner query.
write_reg(24'h404040,1,15,0,1);write_reg(24'h404044,2,15,0,1);
write_reg(24'h404048,17,15,0,1);
write_reg(24'h40404c,$test$plusargs("RNR") ? 4 : 1,15,0,1);
write_reg(24'h404050,1,15,0,1);write_reg(24'h404054,1,15,0,1);
write_reg(24'h404058,32'h89abcdef,15,0,1);write_reg(24'h40405c,32'hfedcba98,15,0,1);
write_reg(24'h404010,1,15,0,1);sq_deadline=cycle+1000;sq_value=0;
while(!(sq_value&4))begin
 if(cycle>sq_deadline)$fatal(1,"actual RRP policy readback deadline");
 read_reg(24'h40400c,sq_value);if(sq_value&8)$fatal(1,"actual RRP policy fault");
end
for(sq_i=0;sq_i<8;sq_i=sq_i+1)begin
 read_reg(24'h404080+sq_i*4,sq_value);
 case(sq_i)
 0,4,5:if(sq_value!==1)$fatal(1,"policy sequence/retry readback");
 1:if(sq_value!==2)$fatal(1,"policy full QPN");
 2:if(sq_value!==17)$fatal(1,"policy actual PD");
 3:if(sq_value!==($test$plusargs("RNR") ? 4 : 1))$fatal(1,"policy actual timeout");
 6:if(sq_value!==32'h89abcdef)$fatal(1,"policy owner cookie low");
 7:if(sq_value!==32'hfedcba98)$fatal(1,"policy owner cookie high");
 endcase
end
read_reg(24'h4040a0,sq_value);if(sq_value!==1)$fatal(1,"policy actual epoch low");
read_reg(24'h4040a4,sq_value);if(sq_value!==32'h91234567)$fatal(1,"policy actual epoch high");
read_reg(24'h4040a8,sq_value);if(sq_value)$fatal(1,"policy consumer error");
write_reg(24'h404014,1,15,0,1);
enable=1;sq_command(2,1,0,0,0);
'''
    tb=m.sq.once(tb,'enable=1;sq_command(2,1,0,0,0);',policy)
    # Both runs lose the first positive response. The RNR run first receives
    # a real ICRC-valid ACK/RNR packet: no direct control-token injection.
    control=m.response.packet(write=True,mig=1,syndrome=0x21,qpn=2,psn=qp.PSN)
    frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+control
    start=len(words);extra=[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')|
        (((1<<min(16,len(frame)-i))-1)<<128)|((i+16>=len(frame))<<144)for i in range(0,len(frame),16)]
    tb=m.sq.once(tb,f'stimulus[0:{len(words)-1}]',f'stimulus[0:{len(words)+len(extra)-1}]')
    tb=m.sq.once(tb,'sq_deadline=cycle+5000;\nwhile(!dut.tx_response_admission_ready || dut.tx_frame_count!=1)',f'''
sq_deadline=cycle+10000;
if($test$plusargs("RNR"))begin
 while(!dut.tx_response_admission_ready || dut.tx_frame_count!=1)begin
  if(cycle>sq_deadline)$fatal(1,"first attempt deadline");@(negedge clk);
 end
 send_frame({start},{len(extra)});
end
while(!dut.tx_response_admission_ready || dut.tx_frame_count!=2)''')
    tb=m.sq.once(tb,'dut.tx_receipt_count!=1 || dut.tx_mac_proof_count!=1',
        'dut.tx_receipt_count!=2 || dut.tx_mac_proof_count!=2')
    tb=m.sq.once(tb,'dut.rx_accepted_count!=1',
        'dut.rx_accepted_count!=($test$plusargs("RNR") ? 2 : 1)')
    tb=m.sq.once(tb,'check_ring();\nhost_stage(8,405',r'''
if(dut.native_retry_count!==1 || dut.native_rnr_count!==($test$plusargs("RNR") ? 1 : 0))
 $fatal(1,"actual whole-path retry/RNR ownership counts");
check_ring();
host_stage(8,405''')
    return tb,words+extra,records,request

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--reuse-objects',type=Path)
    p.add_argument('--actual-hls-elaboration',type=Path)
    p.add_argument('--reuse-compiled-report',type=Path)
    p.add_argument('--send',action='store_true')
    p.add_argument('--recv',action='store_true');p.add_argument('--wire-rnr',action='store_true');p.add_argument('--recv-retire',action='store_true')
    p.add_argument('--recv-cq',action='store_true')
    p.add_argument('--request-cq',action='store_true')
    p.add_argument('--independent-queues',action='store_true')
    p.add_argument('--duplex',action='store_true')
    p.add_argument('--recv-cancel',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if a.recv_cancel and not a.independent_queues:p.error('receive cancellation requires full independent native queues')
    if a.duplex and not(a.independent_queues or a.request_cq):p.error('duplex requires full actual independent queues or matched requester regression')
    if a.independent_queues:
        if a.send or a.request_cq or not a.actual_hls_elaboration:p.error('independent queues require the real combined HLS profile')
        a.recv=True;a.wire_rnr=True;a.recv_retire=True;a.recv_cq=True
    if a.send and a.recv:p.error('select one actual operation')
    if a.wire_rnr and not a.recv:p.error('wire RNR test requires actual RECV')
    if a.recv_retire and not a.wire_rnr:p.error('receive receipts require actual RNR profile')
    if a.recv_cq and not a.recv_retire:p.error('receive CQ requires actual operation receipts')
    if (a.send or a.recv) and not a.actual_hls_elaboration:p.error('SEND/RECV test requires the real matched generated HLS')
    if a.request_cq and (a.send or a.recv or not a.actual_hls_elaboration):p.error('request CQ selects the real generated three-operation profile')
    if a.independent_queues:
        import native_independent_queues_fixture as split
        receive=split.old
        if a.recv_cancel:
            import native_receive_cancel_fixture as cancel
        if a.duplex:
            import native_duplex_fixture as duplex
            tb,words,records,receive_records,request=duplex.case(case,a.recv_cancel)
        elif a.recv_cancel:tb,words,records,receive_records,request=cancel.case(case)
        else:tb,words,records,receive_records,request=split.case(case)
    elif a.request_cq:
        if a.duplex:import native_duplex_request_fixture as requester
        else:import native_request_cq_fixture as requester
        tb,words,records,request=requester.case(case)
    elif a.send:
        import native_send_fixture as send
        tb,words,records,request=send.case(case)
    elif a.recv:
        if a.recv_cq:import native_receive_cq_fixture as receive
        else:import native_receive_fixture as receive
        tb,words,records,request=receive.case(a.wire_rnr,a.recv_retire)
    else:tb,words,records,request=case()
    m=qp.main
    evidence=None;actual_rtl=[];actual_data=[]
    if a.actual_hls_elaboration:
        evidence=json.loads(a.actual_hls_elaboration.read_text())
        if bool(evidence.get('duplex_routing_selected'))!=a.duplex:raise ValueError('selected core and duplex routing mode differ')
        if a.duplex and evidence.get('DUPLEX_ENABLE')!=1:raise ValueError('matched physical-memory/own-MAC completion profile required')
        if a.recv_cancel and evidence.get('RECV_CANCEL_ENABLE')!=1:raise ValueError('actual receive-cancel native hierarchy required')
        if a.independent_queues and (evidence.get('SEPARATE_RQ_ENABLE')!=1 or evidence.get('REQUEST_CQ_ENABLE')!=1):raise ValueError('actual independent SQ/RQ hierarchy required')
        if a.request_cq and evidence.get('REQUEST_CQ_ENABLE')!=1:raise ValueError('actual requester CQ hierarchy required')
        if a.send and evidence.get('SEND_ENABLE')!=1:raise ValueError('actual opt-in SEND hierarchy required')
        if a.recv and evidence.get('RECV_ENABLE')!=1:raise ValueError('actual opt-in RECV hierarchy required')
        if a.wire_rnr and evidence.get('RNR_ENABLE')!=1:raise ValueError('actual opt-in wire RNR hierarchy required')
        if a.recv_retire and evidence.get('RECV_RETIRE_ENABLE')!=1:raise ValueError('actual opt-in receive receipt hierarchy required')
        if a.recv_cq and evidence.get('RECV_CQ_ENABLE')!=1:raise ValueError('actual receive CQ hierarchy required')
        if not evidence.get('pass_test') or evidence.get('HLS_stub') or not evidence.get('generated_new_QP_HLS_verified') or \
            evidence.get('RETRY_ENABLE')!=1 or evidence['module_counts'].get('rocev2_top')!=1 or \
            evidence['module_counts'].get('rocev2_native_duplex_top'if a.duplex else'rocev2_native_request_top'if a.request_cq or a.independent_queues else'rocev2_native_recv_top'if a.recv_retire else'rocev2_native_rnr_top'if a.wire_rnr else'rocev2_native_replay_top')!=1:
            raise ValueError('actual matched native+legacy HLS elaboration required')
        for n,h in evidence['source_sha256'].items():
            if digest(ROOT/n)!=h:raise ValueError('actual HLS evidence input changed: '+n)
            if n.endswith('.dat'):actual_data.append(ROOT/n)
        actual_rtl=[Path(x)for x in evidence['command']if x.endswith('.v')]
        if any(not x.is_relative_to(ROOT)for x in actual_rtl):raise ValueError('unexpected HLS source path')
        # The model-only forced application stall is not wired to a real
        # generated core. Real RNC1 still waits for actual QPI table readback.
        if not a.recv:tb=m.sq.once(tb,r'''qp_model_allow=0;write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(23)begin @(negedge clk);if(!control_busy || quiet || config_safe)$fatal(1,"QP TX returned before real apply");end
read_reg(AS02_CTL_STATUS,sq_value);if(sq_value&AS02_ST_REPLY)$fatal(1,"fabricated state apply reply");
qp_model_allow=1;collect_native(9,403,0,0,0);''',
            'write_reg(AS02_CTL_DOORBELL,1,15,0,1);collect_native(9,403,0,0,0);')
        if not a.request_cq:tb=m.sq.once(tb,r'\"HLS_model\":true',r'\"HLS_model\":false')
    sources=list(dict.fromkeys([*m.original.input_paths(tb),m.TOP,*m.EXTRA,Path(m.__file__).resolve(),
        Path(m.derive.__file__).resolve(),Path(m.derive.recv.__file__).resolve(),m.derive.ORIGINAL,Path(qp.__file__).resolve(),Path(__file__).resolve(),
        *actual_rtl,*actual_data,*([a.actual_hls_elaboration.resolve()]if evidence else []),
        *([Path(send.__file__).resolve()]if a.send else []),*([Path(receive.__file__).resolve()]if a.recv else []),
        *([Path(requester.__file__).resolve(),Path(requester.send.__file__).resolve()]if a.request_cq else []),
        *([Path(split.__file__).resolve()]if a.independent_queues else []),
        *([Path(receive.old.__file__).resolve()]if a.recv_cq else []),
        *([Path(cancel.__file__).resolve()]if a.recv_cancel else [])]))
    if a.duplex:
        sources += ([Path(duplex.__file__).resolve()]if a.independent_queues else[Path(requester.parent.__file__).resolve()])
    before={str(x.relative_to(ROOT)):digest(x)for x in sources}
    run=Path(tempfile.mkdtemp(prefix='native-retry-main-',dir=ROOT/'rdma/rnic/build'))
    obj=a.reuse_objects.resolve() if a.reuse_objects else Path(tempfile.mkdtemp(prefix='as02-native-retry-obj-',dir='/dev/shm'))
    if obj.parent!=Path('/dev/shm') or not obj.name.startswith('as02-native-retry-obj-') or not obj.is_dir():
        raise ValueError('compiler cache must be the exact existing task-owned RAM directory')
    (run/'tb.v').write_text(tb);(run/'legacy.v').write_text(m.core_model(False))
    (run/'new.v').write_text(qp.model())
    (run/'shared.v').write_text(m.derive.derive(m.derive.ORIGINAL.read_text()))
    (run/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
    if a.independent_queues:(run/'receive-records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in receive_records))
    (run/'request.hex').write_text(''.join(f'{v:x}\n'for v in m.octets(request)))
    for x in actual_data:shutil.copy2(x,run/x.name)
    rtl=([run/'tb.v',*actual_rtl]if evidence else
        [run/'tb.v',run/'legacy.v',run/'new.v',run/'shared.v',m.TOP,*m.EXTRA,*m.sq.portable.sources()])
    cmd=[str(TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
        '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
        '-CFLAGS','-O0','--Mdir',str(obj),*map(str,rtl)]
    compile_limit=1200 if a.duplex else 600
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        compile_directory=str(obj),compile_command=cmd,compile_limit_seconds=compile_limit,simulation_limit_seconds=30,
        HLS_model=not bool(evidence),physical_host_MAC_models=True,two_state_simulation=True,hardware_verified=False,
        actual_matched_generated_HLS=bool(evidence),
        operation='RECV'if a.recv else 'SEND'if a.send else'READ',wire_RNR_enabled=a.wire_rnr,receive_internal_receipts=a.recv_retire,
        whole_core_drain_proved=False,standard_verbs=False,CQ_or_MR_release=a.recv_cq or a.request_cq,
        native_request_CQ_enabled=a.request_cq or a.independent_queues,
        independent_physical_queues_enabled=a.independent_queues,
        duplex_routing_selected=a.duplex,
        receive_cancellation_enabled=a.recv_cancel,
        native_receive_CQ_enabled=a.recv_cq,real_kernel_MR_unpin=False)
    print(json.dumps(dict(directory=str(run),compile_directory=str(obj),simulation_bound_seconds=30)),flush=True)
    try:
        started=time.monotonic()
        if a.reuse_compiled_report:
            if not evidence or a.reuse_objects:raise ValueError('exact executable reuse requires actual HLS and no compiler-cache mutation')
            previous=json.loads(a.reuse_compiled_report.read_text());old=ROOT/previous['directory']
            if old.parent!=ROOT/'rdma/rnic/build' or not old.name.startswith('native-retry-main-') or old.is_symlink():
                raise ValueError('previous executable must be in the exact task-owned run')
            if digest(old/'Vtb')!=previous.get('binary_sha256'):raise ValueError('previous compiled binary changed')
            if (old/'tb.v').read_bytes()!=tb.encode():raise ValueError('testbench changed; translate and compile normally')
            for x in [*rtl,*actual_data,*[Path(n)for n in __import__('re').findall(r'`include "([^\"]+)"',tb)]]:
                if x==run/'tb.v':continue
                n=str(x.relative_to(ROOT))
                if digest(x)!=previous['source_sha256'].get(n):raise ValueError('compiled input changed: '+n)
            # Runtime input arrays must also match. request.hex is unused by
            # the ACTUAL HLS core (unlike the explicitly modeled core); do
            # not permit this exception if any consumed SV references it.
            for name in ['input.hex','records.hex']+(['receive-records.hex']if a.independent_queues else []):
                if (old/name).read_bytes()!=(run/name).read_bytes():raise ValueError('runtime fixture changed: '+name)
            if any('"request.hex"'in x.read_text()for x in rtl):raise ValueError('binary reads changed request fixture')
            shutil.copy2(old/'Vtb',run/'Vtb')
            report.update(compilation_seconds=0,exact_compiled_executable_reused=True,
                previous_compilation_report=str(a.reuse_compiled_report.resolve().relative_to(ROOT)),
                unchanged_compiled_RTL_and_testbench_verified=True)
        elif a.reuse_objects:
            saved={x:(digest(x),x.stat().st_atime_ns,x.stat().st_mtime_ns)for x in obj.iterdir()
                if x.suffix in ['.cpp','.h','.mk']}
            generate=[str(TOOL),'--cc','--exe','--main',*cmd[2:]]
            generate=[x for i,x in enumerate(generate)if not(x=='-j' or i>0 and generate[i-1]=='-j')]
            with(run/'generate.log').open('x')as log:r=subprocess.run(generate,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            if r.returncode:raise RuntimeError('fresh translation failed: '+str(run/'generate.log'))
            identical=[]
            for x,(sha,atime,mtime)in saved.items():
                if x.is_file() and digest(x)==sha:os.utime(x,ns=(atime,mtime));identical.append(x)
            included=[Path(x)for x in __import__('re').findall(r'`include "([^\"]+)"',tb)]
            ignored=list(dict.fromkeys([*rtl,*included,*identical]))
            cmd=['make','-C',str(obj),'-f','Vtb.mk','-j','4',*[v for x in ignored for v in ['-o',str(x)]],'Vtb']
            report.update(fresh_generate_command=generate,compile_command=cmd,
                byte_identical_generated_files_reused=len(identical))
        if not a.reuse_compiled_report:
            with(run/'compile.log').open('x')as log:r=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,
                timeout=max(1,compile_limit-(time.monotonic()-started)))
            report['compilation_seconds']=time.monotonic()-started
            if r.returncode:raise RuntimeError('main retry compile failed: '+str(run/'compile.log'))
        # /dev/shm can be noexec: keep compiler intermediates in RAM, execute
        # only the exact copied executable on the existing normal filesystem.
        if not a.reuse_compiled_report:shutil.copy2(obj/'Vtb',run/'Vtb')
        report['binary_sha256']=digest(run/'Vtb')
        report['tests']={}
        cases=([('READ',[]),('WRITE',['+WRITE']),('SEND',['+SEND'])]if a.request_cq else
            [('posted',[]),('empty_then_post',['+RNR'])]if a.recv else [('timeout',[]),('RNR',['+RNR'])])
        for name,args in cases:
            runtime={}
            if a.request_cq:
                opcode={'READ':2,'WRITE':1,'SEND':3}[name]
                words,records,request=requester.variant(case,opcode)
                (run/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
                (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
                for filename in ['input.hex','records.hex']:
                    shutil.copy2(run/filename,run/(name+'-'+filename));runtime[filename]=digest(run/filename)
            started=time.monotonic()
            with(run/(name+'.log')).open('x')as log:r=subprocess.run([str(run/'Vtb'),*args],cwd=run,
                stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=no_core)
            elapsed=time.monotonic()-started;out=(run/(name+'.log')).read_text()
            if r.returncode:raise RuntimeError('main retry '+name+' failed: '+str(run/(name+'.log')))
            rows=[json.loads(s.split(' ',1)[1])for s in out.splitlines()if s.startswith('NATIVE_RNIC_RESULT ')]
            # The combined two-direction test actually SENDs; its completed
            # sender retains seven history bits. RECV-only never set them.
            expected_flags=127 if a.independent_queues else 0 if a.recv or a.request_cq else 63
            if len(rows)!=1 or rows[0]['proof_flags']!=expected_flags:raise ValueError('missing real placement/lifetime evidence')
            if rows[0]['HLS_model']!= (not bool(evidence)):raise ValueError('incorrect HLS evidence label')
            if a.request_cq:
                if not rows[0].get('CQ_committed') or rows[0].get('opcode')!=opcode:raise ValueError('actual requester CQ event missing')
                snapshot=run/'request-event.hex'
                if len(snapshot.read_text().splitlines())!=25:raise ValueError('missing exact native CQ snapshot')
                shutil.copy2(snapshot,run/(name+'-event.hex'))
                report['tests'][name]=dict(summary=rows[0],simulation_seconds=elapsed,
                    runtime_input_sha256=runtime,CQ_snapshot_sha256=digest(snapshot),actual_coherent_request_WQE=True,
                    actual_shared_MR_and_native_PCIe=True,real_physical_MAC_receipt_delivery_withheld=True,
                    retained_global_drain_gates_zero=True,actual_request_wire=requester.verify(out,request,opcode))
            elif a.recv:
                proofs=[json.loads(s.split(' ',1)[1])for s in out.splitlines()if s.startswith('NATIVE_RECV_CORE_PROOF ')]
                if a.recv_retire and (len(proofs)!=(2 if a.recv_cq else 1) or not all(p['full_owner_match'] for p in proofs)):raise ValueError('missing actual same-HLS receive proof')
                report['tests'][name]=dict(summary=rows[0],simulation_seconds=elapsed,actual_coherent_RECV_WQEs=2 if a.recv_cq else 1,
                    actual_shared_MR_and_native_PCIe_placement=True,full_posted_owner_retained=not a.recv_cq,
                    empty_RQ_before_post_tested=name=='empty_then_post',retained_core_drain_gate_zero=True,
                    actual_RECV_wire=receive.verify(out,request,a.wire_rnr,name=='empty_then_post'),
                    actual_HLS_receive_proofs=proofs,real_receipt_consumer_stall_tested=a.recv_retire and not a.recv_cq,
                    real_physical_MAC_receipt_delivery_withheld=a.recv_cq)
                if a.independent_queues:
                    report['tests'][name]['actual_independent_queues']=split.verify(out,request,name=='empty_then_post')
                    if a.duplex:report['tests'][name]['actual_simultaneous_RC']=duplex.verify(out,request,name=='empty_then_post')
                    report['tests'][name]['actual_coherent_SEND_WQEs']=2
                    for filename in ['send-event1.hex','receive-event1.hex','send-event2.hex','receive-event2.hex']:
                        if len((run/filename).read_text().splitlines())!=25:raise ValueError('missing independent native CQ snapshot')
                        shutil.copy2(run/filename,run/(name+'-'+filename))
                if a.recv_cancel:
                    report['tests'][name]['actual_receive_cancellation']=cancel.verify(out)
                    for filename,count in [('cancel-reply.hex',19),('cancel-record.hex',1)]:
                        if len((run/filename).read_text().splitlines())!=count:raise ValueError('missing exact native cancellation snapshot')
                        shutil.copy2(run/filename,run/(name+'-'+filename))
            else:
                report['tests'][name]=dict(summary=rows[0],simulation_seconds=elapsed,attempts=2,
                    actual_MAC_receipts=2,actual_MAC_proofs=2,actual_DMA_commands=1,actual_RRP_policy_readback=True,
                    authenticated_RNR_packet=name=='RNR',retained_core_drain_gate_zero=True)
            if a.send:report['tests'][name]['actual_SEND_wire']=send.verify(out,request)
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('inputs changed during native retry run')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compilation_seconds','tests']}),flush=True)

if __name__=='__main__':main()
