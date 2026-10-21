#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actually inserted WRITE controller in complete real native graph.

Actual native PSN/MR/HLS/memory/global nonce/ACK/RQ/CQ wires, no test models
or new namespaces. This is ELABORATION only: fresh all34+WRITE runtime,
software, recovery/partial-message teardown and original timing still remain.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding
from check_immediate_native_elaboration import FEATURES

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_native as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every earlier report')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise RuntimeError('original root/RAM1GiB native elaboration guard')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-write-native-',dir='/dev/shm'))
    own=[Path(__file__).resolve(),Path(candidate.__file__).resolve()]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256={str(q.relative_to(ROOT)):digest(q)for q in own},
        actual_generated_HLS=True,HLS_stub=False,unknown_leaves_ignored=False,compile_only=True,runtime_test=False,
        native_controller_inserted=True,real_native_PSN_commit=True,shared_native_MR_PTE_backend_nonce=True,one_ACK_allocator=True,
        native_boundary_models=False,complete_native_WRITE_runtime=False,hardware_verified=False,full_board_timing=False,
        RNC_features=65535,CQC_features=255,SQC_features=13,RQC_features=31,new_software_capability_advertised=False,
        HLS_top=candidate.HLS_TOP,compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3)
    try:
        base,b_id=binding.bindings('segmented-write-native-gateway-003')
        controller,c_id=binding.bindings('segmented-write-controller-diagnostics-001')
        if not base['pass_test']or not base['source_unchanged']or not controller['audit_passed']:
            raise ValueError('actual qualified native gateway/controller required')
        src=[ROOT/n for n in base['selected_RTL']]
        for q in src:
            if digest(q)!=base['source_sha256'][str(q.relative_to(ROOT))]:raise ValueError('actual parent source selection changed:'+str(q))
        previous=candidate.parent.derive();current=candidate.derive()
        changed={q for q in current if q not in previous or current[q]!=previous[q]}
        old_expected={candidate.RTL/(n+'.v')for n in [*candidate.parent.WRAPPERS,'rocev2_protected_responder']}
        extra={candidate.RTL/(n+'.v')for n in [candidate.CTRL_NAME,candidate.leaves.FRONT_NAME,candidate.leaves.ROUTER_NAME,candidate.ack.NAME,candidate.rq.NAME]}
        if changed!=old_expected|extra:raise ValueError('only7 native leaves and5 qualified new controller leaves may change')
        before=dict(result['source_sha256']);before.update({str(q.relative_to(ROOT)):digest(q)for q in src})
        for q in sorted(changed):
            alias='rocev2_shared_protected_responder.v'if q.name=='rocev2_protected_responder.v'else q.name
            matches=[p for p in src if p.name==alias];target=run/alias
            if q in previous:
                if len(matches)!=1 or matches[0].read_text()!=previous[q]:raise ValueError('exact actual single parent required:'+alias)
                src=[target if p==matches[0]else p for p in src]
            else:
                if matches:raise ValueError('new controller module cannot alias parent:'+alias)
                src.append(target)
            target.write_text(current[q])
        for q in [candidate.RTL/'rocev2_remote_write_memory.v',candidate.RTL/'rocev2_remote_write_message_guard.v']:
            if any(p.name==q.name for p in src):raise ValueError('new memory/guard must be a single instance definition')
            src.append(q)
        before.update({str(q.relative_to(ROOT)):digest(q)for q in src})
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]
        before.update({str(q.relative_to(ROOT)):digest(q)for q in helpers})
        result.update(source_sha256=before,selected_RTL=[str(q.relative_to(ROOT))for q in src],selected_HLS_data=base['selected_HLS_data'],
            parent_native=b_id,qualified_controller=c_id,changed_native_leaves=sorted(q.name for q in changed),original_module_counts=base['module_counts'])
        protected=(run/'rocev2_shared_protected_responder.v').read_text();root=(run/'rocev2_native_rnic_endpoint.v').read_text()
        for token in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",'.s_expect_msn(expected_remote_msn)',
            '.large_read_path(segmented_read_memory_path)','local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;']:
            if token not in root:raise ValueError('original complete native protection missing:'+token)
        for token in ['write_controller(','.m_packet_commit_ready(s_write_commit_ready)',
            '.s_hls_done(m_write_done)',candidate.ack.NAME+' #(',candidate.rq.NAME+' #(',
            '.m_write_retire_ready(write_notice_retire_ready)',
            '.s_owner_valid(rq_head_valid && rq_head_ready && !write_notice_valid)']:
            if token not in root:raise ValueError('actual inserted controller/sole ACK/late RQ wire missing:'+token)
        for token in ['rocev2_native_write_rx_router write_classification(','.allow_header(!s_write_held || m_write_rx_ready)',
            '.force_write(s_write_message_active)','rocev2_memory_client_arbiter write_and_ordinary_memory(',
            'expected_psn<=s_write_commit_token[39:16]+24\'d1;','(s_write_held && s_write_tx_release)',
            'recv_context<=s_write_rq_owner[619:0];recv_completion_pending<=1;']:
            if token not in protected:raise ValueError('actual native RX/memory/PSN/visibility gate missing:'+token)
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+name+'_ENABLE=1'for name in FEATURES];cmd+=list(map(str,src));result['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);result.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode:raise ValueError('actual inserted native WRITE elaboration failed:'+str(run/'compile.log'))
        if any('expects'in s and 'bits'in s for s in c.stderr.splitlines()):raise ValueError('no native port-width waiver')
        model=(ram/'native.vvp').read_text();oldmodel=next(Path(n)for n in base['RAM_artifact_sha256']if Path(n).name=='native.vvp').read_text()
        wanted=dict(base['module_counts']);wanted['rocev2_receive_ack_tx']=0;wanted[candidate.ack.NAME]=1
        wanted['rocev2_receive_message_queue']=0;wanted[candidate.rq.NAME]=1
        for name in [candidate.CTRL_NAME,candidate.leaves.FRONT_NAME,candidate.leaves.ROUTER_NAME,'rocev2_remote_write_memory','rocev2_remote_write_message_guard']:
            wanted[name]=1
        old_memory_arbiters=len(re.findall(r'\.scope module, "[^"]+" "rocev2_memory_client_arbiter"',oldmodel))
        if old_memory_arbiters<1:raise ValueError('actual original shared memory arbitration required')
        wanted['rocev2_memory_client_arbiter']=old_memory_arbiters+1
        counts={name:len(re.findall(r'\.scope module, "[^"]+" "'+name+r'"',model))for name in wanted}
        if counts!=wanted:raise ValueError('actual sole native MR/HLS/backend/nonce/ACK/RQ multiplicity mismatch:'+str(counts))
        domains={name:len(re.findall(r'\.scope module, "'+name+r'" "'+candidate.HLS_TOP+r'_[^"]+"',model))for name in base['HLS_domain_counts']}
        if domains!=base['HLS_domain_counts']:raise ValueError('same actual generated HLS PSN/MSN/parser/service domain required')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed during compile')
        result.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,HLS_domain_counts=domains,
            original_memory_arbiters=old_memory_arbiters,both_global_HLS_drains_zero=True,
            native_WRITE_payload_runtime=False,all34_old_native_cases_rerun=False,
            remaining=['Fresh complete native compile/runtime: all34 unchanged old cases PLUS new segmented WRITE/Immediate with actual generated HLS/PCIe/global nonce/ACK/CQ/native PSN.',
                'Actual native completion must retain full1MiB/matched software/multiSGE/live Linux refs and real-peer recovery/RNR/MSN/congestion.',
                'Real wire NAK/RNR behavior for new reject events and privileged partial-HLS-message cleanup remain; no cancellation/drain/reset substitute.',
                'All11 original requirements and original4ns/default1.08ns board/physical proof remain; estimate15.571ns still fails.'])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=result['compile_seconds'],controller_inserted=True,native_runtime=False)),flush=True)


if __name__=='__main__':main()
