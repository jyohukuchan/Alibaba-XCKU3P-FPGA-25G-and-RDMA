#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual certified PSN-control native/HLS hierarchy, elaboration ONLY.

Entire actual new197-file HLS generation, no mixed old core, and SAME
MR/PTE/backend/nonce/ACK/RQ/CQ namespaces. Not native packet runtime proof.
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
import derive_write_psn_control_native as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise RuntimeError('original root/RAM1GiB elaboration gate')
    run=Path(tempfile.mkdtemp(prefix='write-psn-control-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-psn-control-native-',dir='/dev/shm'))
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        hardware_verified=False,full_board_timing=False,HLS_top=candidate.HLS_TOP,HLS_stub=False,unknown_leaves_ignored=False,
        actual_generated_HLS=True,complete_native_control_runtime=False,compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3,
        RNC_features=131071,CQC_features=511,SQC_features=13,RQC_features=63,software_profile=8)
    try:
        names=['segmented-write-rnr-native-elaboration-001','segmented-write-rnr-native-full-002',
            'control-response-generated-hls-001','segmented-write-owned-generated-hls-001',
            'receive-control-ack-003','receive-control-ack-diagnostics-001','write-psn-control-001']
        records={};ids={}
        for n in names:records[n],ids[n]=binding.bindings(n)
        old,actual,hls,oldhls,ack,audit,ctrl=[records[n]for n in names]
        if not all(v.get('pass_test',v.get('audit_passed'))for v in records.values())or len(actual['tests'])!=37 or \
           len(ack['tests'])!=144 or len(ctrl['tests'])!=46 or hls['HLS_top']!=candidate.HLS_TOP:
            raise ValueError('exact native37/control144+2/helper46/actual generated control HLS required')
        previous=candidate.parent.derive();current=candidate.derive()
        changed={q for q in current if q not in previous or current[q]!=previous[q]};removed=set(previous)-set(current)
        oldack=candidate.RTL/(candidate.parent.ack.NAME+'.v');newack=candidate.RTL/(candidate.ack.NAME+'.v')
        flow={candidate.RTL/(n+'.v')for n in [*candidate.gateway.WRAPPERS,'rocev2_protected_responder','rocev2_shared_hls_transport',
            candidate.native.leaves.FRONT_NAME,candidate.native.CTRL_NAME]}|{ROOT/'rdma/rtl/rocev2_integrity_transport.v'}
        if changed!=flow|{newack,candidate.HELPER}or removed!={oldack}:
            raise ValueError('only11 real flow/parser leaves, sole ACK replacement and PSN controller required')
        oldgen=ROOT/oldhls['directory']/'project/solution1/syn/verilog';newgen=ROOT/hls['directory']/'project/solution1/syn/verilog'
        src=[ROOT/n for n in old['selected_RTL']];data=[ROOT/n for n in old['selected_HLS_data']]
        consumed={q.name for q in [*src,*data]if q.parent==oldgen}
        if consumed!=set(oldhls['generated_sha256']):raise ValueError('exact entire old197-file cohort must be replaced')
        src=[q for q in src if q.parent!=oldgen]
        src +=[newgen/n for n in sorted(hls['generated_sha256'])if n.endswith('.v')]
        data=[newgen/n for n in sorted(hls['generated_sha256'])if not n.endswith('.v')]
        if len(hls['generated_sha256'])!=197 or any(q.parent!=newgen for q in data):raise ValueError('complete actual new197 RTL/data required')
        matches=[q for q in src if q.name==oldack.name]
        if len(matches)!=1 or matches[0].read_text()!=previous[oldack]:raise ValueError('one exact actual old ACK definition required')
        src.remove(matches[0])
        for q in sorted(changed):
            alias='rocev2_shared_protected_responder.v'if q.name=='rocev2_protected_responder.v'else q.name
            matches=[p for p in src if p.name==alias];target=run/alias
            if q in previous:
                if len(matches)!=1 or matches[0].read_text()!=previous[q]:raise ValueError('one exact consumed parent leaf required:'+alias)
                src=[target if p==matches[0]else p for p in src]
            else:
                if matches:raise ValueError('new definition collides:'+alias)
                src.append(target)
            target.write_text(current[q])
        inputs=[Path(__file__).resolve(),candidate.HELPER,*[Path(m.__file__).resolve()for m in list(sys.modules.values())
            if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]]
        hashes={str(q.relative_to(ROOT)):digest(q)for q in [*src,*data,*inputs]}
        r.update(source_sha256=hashes,evidence=ids,selected_RTL=[str(q.relative_to(ROOT))for q in src],
            selected_HLS_data=[str(q.relative_to(ROOT))for q in data],changed_flow_leaves=sorted(str(q.relative_to(ROOT))for q in flow),
            replaced_ACK=[oldack.name,newack.name],complete_HLS_cohort_replaced=True)
        root=(run/'rocev2_native_rnic_endpoint.v').read_text();protected=(run/'rocev2_shared_protected_responder.v').read_text()
        for token in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
            '.s_cert_valid(write_ctl_m_control_certified)','.s_cert_context(write_ctl_m_control_context)',
            '.trusted_context(m_write_native_context)','.trusted_expected_psn(m_write_expected_psn)',
            '.s_control_core_data(m_control_done)','.s_ack_done(write_control_ack_done)',
            '.m_error_valid(write_reject_valid)','.m_reject_valid(control_reject_valid)']:
            if token not in root:raise ValueError('actual native authority/typed ownership/independent consumer missing:'+token)
        gate='((s_write_held && (s_write_tx_release || s_write_rnr_tx_release)) || (s_control_held && s_control_tx_release))'
        if protected.count(gate)!=2:raise ValueError('both actual old positive/RNR and new control TX gates required')
        idle='.remote_operation_idle(!atomic_packet_busy && state==COLLECT && word_count==0 && !lease && !config_busy && !legacy_m_reject_valid)'
        if idle not in protected:raise ValueError('original real HLS role/drain predicate must remain')
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode or any('expects'in s and 'bits'in s for s in c.stderr.splitlines()):
            raise ValueError('actual native hierarchy/width mismatch:'+str(run/'compile.log'))
        wanted=dict(old['module_counts']);wanted.update({oldhls['HLS_top']:0,candidate.HLS_TOP:1,candidate.parent.ack.NAME:0,
            candidate.ack.NAME:1,'rocev2_write_psn_control':1})
        for suffix in ['as02_native_control_merger_0_s','generate_exh_512_0_s','msn_table_0_s','state_table_0_s']:
            defs=[Path(n).stem for n in hls['generated_sha256']if n.endswith('_'+suffix+'.v')]
            if len(defs)!=1:raise ValueError('single actual HLS domain definition required:'+suffix)
            wanted[defs[0]]=1
        model=(ram/'native.vvp').read_text()
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('same actual native namespaces and one ACK/control/HLS domains required:'+str(counts))
        if any(digest(ROOT/n)!=h for n,h in hashes.items()):raise ValueError('consumed source changed')
        r.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            native_certified_PSN_controller_inserted=True,shared_native_MR_PTE_backend_nonce=True,one_ACK_allocator=True,
            both_global_HLS_drains_zero=True,remaining=['Fresh native execution of all37 old cases and certified future-PSN suppression/retry/duplicate-no-second-data-CQ.',
                'Proper fatal-QP quarantine/teardown, full1MiB/multiSGE/live registered refs/real-peer recovery/congestion/original timing/physical/all11 remain.'])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=r['compile_seconds'],native_control_runtime=False)))


if __name__=='__main__':main()
