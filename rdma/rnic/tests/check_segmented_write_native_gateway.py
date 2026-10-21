#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compile actual typed-WRITE HLS/native MR gateway; NOT WRITE runtime.

Replace the ENTIRE old generated module/data set, keep all old native
paths, ONE MR table/backend/nonce/HLS domain and both global drains0.
WRITE frontend/packet-memory/shared ACK insertion and runtime still remain;
new ports are real boundary ports, not fake completion/ready/drain tieoffs.
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

ROOT=binding.ROOT;digest=binding.digest;PREFIX=binding.PREFIX
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_native_gateway as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3 or shutil.disk_usage('/dev/shm').free<1024**3:
        raise RuntimeError('unchanged root/RAM1GiB native elaboration guard')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-native-gateway-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-native-gateway-',dir='/dev/shm'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256={
        str(Path(__file__).relative_to(ROOT)):digest(__file__),str(Path(candidate.__file__).relative_to(ROOT)):digest(candidate.__file__)},
        actual_generated_HLS=True,HLS_stub=False,compile_only=True,runtime_test=False,unknown_leaves_ignored=False,
        protected_WRITE_controller_inserted=False,complete_WRITE_native_runtime=False,
        typed_WRITE_native_boundary_ports=True,additional_MR_client_not_namespace=True,
        RNC_features=65535,CQC_features=255,SQC_features=13,RQC_features=31,new_WRITE_software_capability_advertised=False,
        hardware_verified=False,full_board_timing=False,original_HLS_timing_met=False,
        HLS_top=candidate.HLS_TOP,root_and_RAM_guard_bytes=1024**3,compile_limit_seconds=180)
    try:
        old,o_id=binding.bindings('segmented-receive-native-full-004')
        base,b_id=binding.bindings('segmented-receive-native-elaboration-002')
        generated,g_id=binding.bindings('segmented-write-owned-generated-hls-001')
        consumer,c_id=binding.bindings('segmented-write-owned-diagnostics-001')
        memory,m_id=binding.bindings('remote-write-memory-diagnostics-001')
        if not all(r.get('pass_test')for r in [old,base,generated])or not all(r['audit_passed']for r in [consumer,memory])or \
           len(old['tests'])!=34 or any(v['exit']or v['seconds']>30 for v in old['tests'].values()):
            raise ValueError('all34 actual previous native modes and exact new HLS/packet consumers required')
        if (float(generated['target_clock_period']),float(generated['clock_uncertainty']),generated['MAX_QPS'],generated['metadata_entries'])!=(4,1.08,8,2000):
            raise ValueError('original HLS clock/default uncertainty/geometry gates required')
        old_build=json.loads((PREFIX/'rocev2-rnic-segmented-receive-generated-hls-002.json').read_text())
        oldraw=ROOT/old_build['directory']/'project/solution1/syn/verilog'
        newraw=ROOT/generated['directory']/'project/solution1/syn/verilog'
        src=[Path(v)for v in old['bench_elaborate_command']if v.endswith('.v')and Path(v).name!='tb.v']
        if len(src)!=len(set(src)):raise ValueError('one actual selected source per old native leaf required')
        for q in src:
            if digest(q)!=old['source_sha256'][str(q.relative_to(ROOT))]:raise ValueError('actual old native compile selection changed:'+str(q))
        before=dict(result['source_sha256']);before.update({str(q.relative_to(ROOT)):digest(q)for q in src})
        previous=candidate.parent.derive();current=candidate.derive();changed={p for p in current if current[p]!=previous[p]}
        expected={candidate.RTL/(n+'.v')for n in [*candidate.WRAPPERS,'rocev2_protected_responder','rocev2_shared_hls_transport']}
        expected.add(ROOT/'rdma/rtl/rocev2_integrity_transport.v')
        if changed!=expected:raise ValueError('only explicit9 native WRITE boundary/gateway leaves may change')
        for q in sorted(changed):
            alias='rocev2_shared_protected_responder.v'if q.name=='rocev2_protected_responder.v'else q.name
            selected=[n for n in src if n.name==alias]
            if len(selected)!=1 or selected[0].read_text()!=previous[q]:raise ValueError('exact qualified single parent required:'+alias)
            target=run/alias;target.write_text(current[q]);src=[target if n==selected[0]else n for n in src]
        remove={oldraw/n for n in old_build['generated_sha256']if n.endswith('.v')}
        if not remove.issubset(src):raise ValueError('ENTIRE actual old generated HLS selection required')
        src=[q for q in src if q not in remove]
        src +=[newraw/n for n in generated['generated_sha256']if n.endswith('.v')]
        data=[newraw/n for n in generated['generated_sha256']if n.endswith('.dat')]
        if any(q.parent==oldraw for q in src+data):raise ValueError('old/new generated helpers may not mix')
        for q in src+data:before[str(q.relative_to(ROOT))]=digest(q)
        for mod in list(sys.modules.values()):
            q=getattr(mod,'__file__',None)
            if q and Path(q).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'):before[str(Path(q).resolve().relative_to(ROOT))]=digest(q)
        result.update(source_sha256=before,selected_RTL=[str(q.relative_to(ROOT))for q in src],
            selected_HLS_data=[str(q.relative_to(ROOT))for q in data],original_native=o_id,original_elaboration=b_id,
            actual_generated_HLS_provenance=g_id,actual_HLS_consumer_provenance=c_id,actual_packet_memory_provenance=m_id,
            prior_source_bindings_verified=sum(v['bindings_verified']for v in [o_id,b_id,g_id,c_id,m_id]),
            changed_native_leaves=sorted(q.name for q in changed))
        root=(run/'rocev2_native_rnic_endpoint.v').read_text()
        for token in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
            '.s_expect_msn(expected_remote_msn)','.large_read_path(segmented_read_memory_path)',
            'local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;',
            '.s_message_data(rq_message_data)','.s_recv_packet_retire_context(rq_packet_retire_context)']:
            if token not in root:raise ValueError('original complete native protection missing:'+token)
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));result['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);result.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode:raise ValueError('actual new HLS/native gateway compile failed:'+str(run/'compile.log'))
        if any('expects'in line and 'bits'in line for line in c.stderr.splitlines()):raise ValueError('no new native port-width mismatch allowed')
        model=(ram/'native.vvp').read_text();wanted=dict(base['module_counts'])
        oldtop='rocev2_native_segmented_receive_top'
        if wanted.get(oldtop)!=1 or candidate.HLS_TOP in wanted:raise ValueError('exact old single generated root required')
        oldmodel=next(Path(n)for n in base['RAM_artifact_sha256']if Path(n).name=='native.vvp').read_text()
        old_arbiter_count=len(re.findall(r'\.scope module, "[^"]+" "rocev2_mr_query_arbiter"',oldmodel))
        if old_arbiter_count<1:raise ValueError('actual original MR arbitration graph required')
        result['original_actual_MR_arbiter_count']=old_arbiter_count
        wanted[oldtop]=0;wanted[candidate.HLS_TOP]=1;wanted['rocev2_mr_query_arbiter']=old_arbiter_count+1
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('one HLS/MR/backend/nonce and exact old leaves required:'+str(counts))
        domains={n:len(re.findall(r'\.scope module, "'+n+r'" "'+candidate.HLS_TOP+r'_[^"]+"',model))for n in base['HLS_domain_counts']}
        if domains!=base['HLS_domain_counts']:raise ValueError('SAME actual HLS PSN/MSN/parser/service domain must remain')
        write_join=len(re.findall(r'\.scope module, "as02_write_packet_retire_join_0_U0" "'+candidate.HLS_TOP+r'_[^"]+"',model))
        if write_join!=1:raise ValueError('actual typed WRITE completion join missing')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed during native elaboration')
        result.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            HLS_domain_counts=domains,actual_typed_WRITE_join_count=write_join,
            both_global_HLS_drains_zero=True,whole_receive_port776_retained=True,
            protected_WRITE_controller_inserted=False,complete_WRITE_native_runtime=False,
            remaining=['Connect actual checked WRITE classifier/frontend, packet memory/backend/global nonce and ONE shared ACK/late-RQ/CQ through these real ports.',
                'Implement and qualify packet expected-PSN updates and safe partial-message HLS teardown with retained full message leases.',
                'Fresh complete native build/runtime must retain all34 old cases plus new WRITE/Immediate; compile-only is not runtime or DMA proof.',
                'All11 original requirements,1MiB/matched software/multiSGE/live Linux refs/short real-peer recovery/RNR/MSN/congestion/original-clock board/physical qualification remain.'])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],actual_new_HLS=True,native_WRITE_runtime=False,shared_MR_table=1)),flush=True)


if __name__=='__main__':main()
