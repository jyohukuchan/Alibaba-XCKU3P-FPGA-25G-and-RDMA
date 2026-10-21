#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual native fatal61/62/quarantine/abort/cancel graph, not runtime.

Entire SAME generated abort HLS208 files, actual original MR/PTE/backend/
nonce/ACK and genuine controller handshake wiring. Original180s/root+RAM1GiB/
profile8/clocks/both global drains0 remain. No error CQ/STOP/unpin claim.
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
import derive_write_fatal_native as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:raise RuntimeError('original root/RAM1GiB elaboration guard')
    run=Path(tempfile.mkdtemp(prefix='write-fatal-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-fatal-native-',dir='/dev/shm'))
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        hardware_verified=False,full_board_timing=False,HLS_top=candidate.HLS_TOP,HLS_stub=False,unknown_leaves_ignored=False,
        actual_generated_HLS=True,complete_native_fatal_runtime=False,compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3,
        RNC_features=131071,CQC_features=511,SQC_features=13,RQC_features=63,software_profile=8)
    try:
        names=['write-psn-control-native-elaboration-001','write-psn-control-native-full-001','write-psn-control-native-runtime-diagnostics-001',
            'control-response-generated-hls-001','write-abort-generated-hls-001','write-abort-generated-diagnostics-001',
            'write-abort-control-004','write-abort-control-diagnostics-001','write-error-control-001']
        records={};ids={}
        for n in names:records[n],ids[n]=binding.bindings(n)
        old,actual,runtime,oldhls,hls,generated,bridge,bridge_audit,control=[records[n]for n in names]
        if not all(v.get('pass_test',v.get('audit_passed'))for v in records.values())or len(actual['tests'])!=38 or \
           len(bridge['tests'])!=66 or len(control['tests'])!=81 or not control['all46_old_summaries_identical']or hls['HLS_top']!=candidate.HLS_TOP:
            raise ValueError('actual native38/abort66/merged81/entire generated abort HLS required')
        previous=candidate.parent.derive();current=candidate.derive()
        changed={q for q in current if q not in previous or current[q]!=previous[q]};removed=set(previous)-set(current)
        oldctrl=candidate.parent.HELPER;newctrl=candidate.RTL/(candidate.error.NAME+'.v');newguard=candidate.RTL/(candidate.GUARD_NAME+'.v')
        flow={candidate.RTL/(n+'.v')for n in [*candidate.gateway.WRAPPERS,'rocev2_protected_responder','rocev2_shared_hls_transport',
            candidate.native.leaves.FRONT_NAME,candidate.native.CTRL_NAME]}|{ROOT/'rdma/rtl/rocev2_integrity_transport.v'}
        if changed!=flow|{newctrl,newguard,candidate.BRIDGE}or removed!={oldctrl}:
            raise ValueError('only actual11 flow/parser/controller leaves, one merged control, selected abort bridge/guard required')
        oldgen=ROOT/oldhls['directory']/'project/solution1/syn/verilog';newgen=ROOT/hls['directory']/'project/solution1/syn/verilog'
        src=[ROOT/n for n in old['selected_RTL']];data=[ROOT/n for n in old['selected_HLS_data']]
        if {q.name for q in [*src,*data]if q.parent==oldgen}!=set(oldhls['generated_sha256']):raise ValueError('entire actual old HLS cohort replacement required')
        src=[q for q in src if q.parent!=oldgen];src+=[newgen/n for n in sorted(hls['generated_sha256'])if n.endswith('.v')]
        data=[newgen/n for n in sorted(hls['generated_sha256'])if not n.endswith('.v')]
        if len(hls['generated_sha256'])!=208 or any(q.parent!=newgen for q in data):raise ValueError('entire actual new208 HLS cohort required')
        matches=[q for q in src if q.name==oldctrl.name]
        if len(matches)!=1 or matches[0].read_text()!=previous[oldctrl]:raise ValueError('one exact old PSN helper definition required')
        src.remove(matches[0])
        for q in sorted(changed):
            alias='rocev2_shared_protected_responder.v'if q.name=='rocev2_protected_responder.v'else q.name
            matches=[p for p in src if p.name==alias];target=run/alias
            if q in previous:
                if len(matches)!=1 or matches[0].read_text()!=previous[q]:raise ValueError('one exact consumed parent leaf required:'+alias)
                src=[target if p==matches[0]else p for p in src]
            else:
                if matches:raise ValueError('new definition collision:'+alias)
                src.append(target)
            target.write_text(current[q])
        inputs=[Path(__file__).resolve(),candidate.BRIDGE,candidate.GUARD,candidate.error.SOURCE,*[Path(m.__file__).resolve()for m in list(sys.modules.values())
            if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]]
        hashes={str(q.relative_to(ROOT)):digest(q)for q in [*src,*data,*inputs]}
        r.update(source_sha256=hashes,evidence=ids,selected_RTL=[str(q.relative_to(ROOT))for q in src],selected_HLS_data=[str(q.relative_to(ROOT))for q in data],
            changed_flow_leaves=sorted(str(q.relative_to(ROOT))for q in flow),merged_control_replacement=[oldctrl.name,newctrl.name],complete_HLS_cohort_replaced=True)
        root=(run/'rocev2_native_rnic_endpoint.v').read_text();protected=(run/'rocev2_shared_protected_responder.v').read_text()
        required=[".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
            '.positive_wire_taken(write_ack_done_valid && write_ack_done_ready)',
            '.positive_commit_taken(s_write_commit_valid && s_write_commit_ready)',
            '.positive_retire_taken(write_ack_retire_valid && write_ack_retire_ready)',
            '.error_wire(error_fatal_wire)','.error_retire_taken(error_fatal_retire_taken)',
            '.local_report_taken(error_report_taken)','.m_done_ready(m_write_fatal_selected_ready)',
            '.s_fatal_cert_valid(write_ctl_m_fatal_certified)','.s_error_cancel_valid(s_error_cancel_valid)']
        if any(n not in root for n in required):raise ValueError('actual native owner/fanout/terminal-consumer wiring missing')
        if "assign m_write_admission_ready=(s_write_abort_guard[local_qpn]===1'b0) && ordinary_idle"not in protected:
            raise ValueError('actual native ingress quarantine gate required')
        idle='.remote_operation_idle(!atomic_packet_busy && state==COLLECT && word_count==0 && !lease && !config_busy && !legacy_m_reject_valid)'
        if idle not in protected:raise ValueError('original HLS role/drain predicate must remain')
        ctrl=(run/(candidate.native.CTRL_NAME+'.v')).read_text()
        if '.cancel_drained(s_error_cancel_certified)'not in ctrl or '.s_cancel_valid(s_error_cancel_valid)'not in ctrl:
            raise ValueError('actual native message cancellation must not remain tied0 or be made default-ready')
        for n,h in binding.PROTECTED.items():
            if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode or any('expects'in s and 'bits'in s for s in c.stderr.splitlines()):raise ValueError('actual native hierarchy/width mismatch:'+str(run/'compile.log'))
        wanted={n:(0 if n.startswith(oldhls['HLS_top'])else v)for n,v in old['module_counts'].items()}
        wanted.update({candidate.HLS_TOP:1,'rocev2_write_psn_control':0,candidate.error.NAME:1,'rocev2_write_abort_control':1,
            'rocev2_remote_write_message_guard':0,candidate.GUARD_NAME:1})
        for suffix in ['as02_native_control_merger_0_s','rx_exh_fsm_512_0_s','as02_write_packet_retire_join_0_s','generate_exh_512_0_s','msn_table_0_s','state_table_0_s']:
            defs=[Path(n).stem for n in hls['generated_sha256']if n.endswith('_'+suffix+'.v')]
            if len(defs)!=1:raise ValueError('single actual generated domain required:'+suffix)
            wanted[defs[0]]=1
        model=(ram/'native.vvp').read_text();counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('actual native namespaces/HLS/control/MSN/state counts changed:'+str(counts))
        if any(digest(ROOT/n)!=h for n,h in hashes.items()):raise ValueError('actual consumed source changed')
        r.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            native_authenticated_fatal61_62_and_selected_abort_cancel_inserted=True,shared_native_MR_PTE_backend_nonce=True,one_ACK_allocator=True,
            both_global_HLS_drains_zero=True,selected_certificate_is_global_drain_or_unpin=False,native_fatal63_implemented=False,error_CQ_STOP_lifetime_implemented=False,
            remaining=['Actual full new graph all38 old cases plus authenticated fatal61/62/wire/HLS abort/native cancel/retained quarantine, not just compilation.',
                'Full QP fatal63/error CQ/STOP/pinned refs and all11/native1MiB/multiSGE/live Linux-provider/real-peer recovery/congestion/original timing/physical remain.'])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=r['compile_seconds'],native_runtime=False)))


if __name__=='__main__':main()
