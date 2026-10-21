#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual native retained-WRITE RNR, not payload/retry/physical proof.

Replace exactly seven native flow leaves and the sole ACK allocator; add one
checked reject controller. SAME HLS/MR/PTE/backend/nonce/PSN/RQ/CQ and tuple.
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
import derive_segmented_write_rnr_native as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise RuntimeError('original root/RAM1GiB elaboration guard')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-rnr-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-write-rnr-native-',dir='/dev/shm'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        hardware_verified=False,full_board_timing=False,actual_generated_HLS=True,HLS_stub=False,unknown_leaves_ignored=False,
        complete_native_RNR_retry_runtime=False,RNC_features=131071,CQC_features=511,SQC_features=13,RQC_features=63,software_profile=8,
        compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3,HLS_top=candidate.native.HLS_TOP)
    try:
        old,old_id=binding.bindings('segmented-write-profile-native-elaboration-001')
        actual,actual_id=binding.bindings('segmented-write-profile-native-full-001')
        ack,ack_id=binding.bindings('receive-write-rnr-ack-002')
        controller,controller_id=binding.bindings('segmented-write-rnr-control-003')
        if not all(v['pass_test']for v in [old,actual,ack,controller])or len(actual['tests'])!=36 or len(ack['tests'])!=78 or len(controller['tests'])!=24:
            raise ValueError('exact actual36 native/78 ACK/24 controller boundaries required')
        previous=candidate.parent.derive();current=candidate.derive()
        changed={q for q in current if q not in previous or current[q]!=previous[q]};removed=set(previous)-set(current)
        old_ack=candidate.RTL/(candidate.native.ack.NAME+'.v');new_ack=candidate.RTL/(candidate.ack.NAME+'.v')
        expected={candidate.RTL/(n+'.v')for n in [*candidate.gateway.WRAPPERS,'rocev2_protected_responder']}
        if changed!=expected|{new_ack,candidate.HELPER}or removed!={old_ack}:
            raise ValueError('exact seven real flow leaves plus sole ACK substitution and controller required')
        src=[ROOT/n for n in old['selected_RTL']]
        matches=[q for q in src if q.name==old_ack.name]
        if len(matches)!=1 or matches[0].read_text()!=previous[old_ack]:raise ValueError('exact one actual old ACK definition required')
        src.remove(matches[0])
        for q in sorted(changed):
            alias='rocev2_shared_protected_responder.v'if q.name=='rocev2_protected_responder.v'else q.name
            matches=[p for p in src if p.name==alias];target=run/alias
            if q in previous:
                if len(matches)!=1 or matches[0].read_text()!=previous[q]:raise ValueError('exact single actual parent leaf required:'+alias)
                src=[target if p==matches[0]else p for p in src]
            else:
                if matches:raise ValueError('new module must not alias another definition:'+alias)
                src.append(target)
            target.write_text(current[q])
        own=[Path(__file__).resolve(),candidate.HELPER,*[Path(m.__file__).resolve()for m in list(sys.modules.values())
            if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]]
        hashes={str(q.relative_to(ROOT)):digest(q)for q in [*src,*own,*[ROOT/n for n in old['selected_HLS_data']]]}
        result.update(source_sha256=hashes,selected_RTL=[str(q.relative_to(ROOT))for q in src],selected_HLS_data=old['selected_HLS_data'],
            parent_elaboration=old_id,parent_actual36_runtime=actual_id,ACK_component=ack_id,controller_component=controller_id,
            changed_flow_leaves=sorted(q.name for q in expected),replaced_ACK=[old_ack.name,new_ack.name])
        root=(run/'rocev2_native_rnic_endpoint.v').read_text();protected=(run/'rocev2_shared_protected_responder.v').read_text()
        for token in ['.local_core_drained(1\'b0)','.hls_transport_drained(1\'b0)',
            '.trusted_identity(m_write_native_context[103:0])','.message_context(write_ctl_message_context)',
            '.s_msn(write_ctl_m_reject_msn)','.m_error_valid(s_write_reject_valid)',
            '.s_valid(write_reject_valid)','.m_reject_valid(write_reject_valid)',
            '.m_rnr_done_data(write_rnr_ack_done)','.m_hls_event(s_write_rnr_event)']:
            if token not in root:raise ValueError('actual native authority/independent handshake missing:'+token)
        if protected.count('(s_write_held && (s_write_tx_release || s_write_rnr_tx_release))')!=2:
            raise ValueError('both actual negative-or-positive TX gates required')
        if '.remote_operation_idle(!atomic_packet_busy && state==COLLECT && word_count==0 && !lease && !config_busy && !legacy_m_reject_valid)'not in protected:
            raise ValueError('original HLS role/drain predicate must remain unchanged')
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));result['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);result.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode or any('expects'in s and 'bits'in s for s in c.stderr.splitlines()):
            raise ValueError('actual RNR native elaboration/width mismatch:'+str(run/'compile.log'))
        model=(ram/'native.vvp').read_text();wanted=dict(old['module_counts'])
        wanted[candidate.native.ack.NAME]=0;wanted[candidate.ack.NAME]=1;wanted['rocev2_segmented_write_rnr_control']=1
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('same actual sole native namespaces and exactly one RNR/ACK required:'+str(counts))
        if any(digest(ROOT/n)!=h for n,h in hashes.items()):raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            native_controller_inserted=True,native_RNR_controller_inserted=True,shared_native_MR_PTE_backend_nonce=True,
            one_ACK_allocator=True,both_global_HLS_drains_zero=True,
            remaining=['Fresh native37: all36 unchanged old inputs/oracles plus actual empty-LAST-RQ RNR/same-PSN retry.',
                'All11/full1MiB/multiSGE/live refs/NAK/recovery/congestion/partial-HLS cleanup/original timing/physical remain.'])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=result['compile_seconds'],native_RNR_runtime=False)),flush=True)


if __name__=='__main__':main()
