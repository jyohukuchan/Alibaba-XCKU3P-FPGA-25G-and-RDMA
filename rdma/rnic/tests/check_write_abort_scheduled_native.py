#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compile exact prior fatal native wiring with ENTIRE scheduled HLS cohort.

No native leaf changes, HLS stubs, old/new core mixture or error-CQ/drain
qualification. Original180s/root+RAM1GiB/profile8/clocks/drains remain.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
from check_immediate_native_elaboration import FEATURES

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise RuntimeError('unchanged native elaboration root/RAM1GiB guard')
    names=['write-fatal-native-elaboration-001','write-fatal-native-source-diagnostics-001',
        'write-psn-control-native-full-001','write-abort-generated-hls-001',
        'write-abort-scheduled-generated-hls-001','write-abort-scheduled-generated-diagnostics-001',
        'write-abort-scheduled-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    old,oldsource,baseline,oldhls,hls,generated,consumer=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(baseline['tests'])!=38:
        raise ValueError('actual prior native source graph/old38 and new generated/consumer audits required')
    if not all(old.get(k)for k in ['full_native_elaboration','source_unchanged','native_authenticated_fatal61_62_and_selected_abort_cancel_inserted',
        'shared_native_MR_PTE_backend_nonce','one_ACK_allocator','both_global_HLS_drains_zero'])or \
       not generated['all_original_port_contracts_identical']or not generated['actual_same_tested_scheduled_parser']:
        raise ValueError('exact real prior fatal wiring/namespace and all new121 ports/same parser required')
    if (old['RNC_features'],old['CQC_features'],old['SQC_features'],old['RQC_features'],old['software_profile'])!=(131071,511,13,63,8)or \
       old['HLS_top']!=hls['HLS_top']or hls['HLS_top']!='rocev2_native_write_abort_top':
        raise ValueError('unchanged explicit top/profile8 required')
    oldgen=ROOT/oldhls['directory']/'project/solution1/syn/verilog';gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    previous=[ROOT/n for n in old['selected_RTL']];previous_data=[ROOT/n for n in old['selected_HLS_data']]
    if {q.name for q in [*previous,*previous_data]if q.parent==oldgen}!=set(oldhls['generated_sha256']):
        raise ValueError('exact ENTIRE actually consumed old abort core required before replacement')
    src=[q for q in previous if q.parent!=oldgen]+[gen/n for n in sorted(hls['generated_sha256'])if n.endswith('.v')]
    data=[gen/n for n in sorted(hls['generated_sha256'])if not n.endswith('.v')]
    if not data or any(q.suffix!='.dat'for q in data)or len(src)!=len(set(src))or \
       {q.name for q in [*src,*data]if q.parent==gen}!=set(hls['generated_sha256']):
        raise ValueError('whole actual new RTL/data cohort with no duplicates/missing/unreviewed data required')
    # Every non-HLS selected leaf is the same exact already audited source.
    retained=[q for q in previous if q.parent!=oldgen]
    if [q for q in src if q.parent!=gen]!=retained:
        raise ValueError('native wiring/MR/PTE/backend/nonce/ACK/cancel leaves must not change')
    hashes={n:h for n,h in old['source_sha256'].items()if (ROOT/n).parent!=oldgen}
    for q in [*src,*data,Path(__file__).resolve(),*[binding.record(n)for n in names]]:
        hashes[str(q.relative_to(ROOT))]=digest(q)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    run=Path(tempfile.mkdtemp(prefix='write-abort-scheduled-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-abort-scheduled-native-',dir='/dev/shm'))
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        hardware_verified=False,full_board_timing=False,HLS_top=hls['HLS_top'],HLS_stub=False,unknown_leaves_ignored=False,
        actual_generated_HLS=True,compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3,
        RNC_features=131071,CQC_features=511,SQC_features=13,RQC_features=63,software_profile=8,
        evidence=ids,source_sha256=hashes,selected_RTL=[str(q.relative_to(ROOT))for q in src],
        selected_HLS_data=[str(q.relative_to(ROOT))for q in data],complete_HLS_cohort_replaced=True,
        original_non_HLS_native_leaves_unchanged=True,actual_generated_files=len(hls['generated_sha256']),
        complete_native_fatal_runtime=False,both_global_HLS_drains_zero=True)
    try:
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):
            raise ValueError('actual scheduled native hierarchy/width mismatch:'+str(run/'compile.log'))
        model=(ram/'native.vvp').read_text()
        wanted=old['module_counts']
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+re.escape(n)+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('actual sole native/HLS/MR/PTE/backend/nonce/ACK/PSN/MSN/cancel namespaces changed')
        for n,h in hashes.items():
            if digest(ROOT/n)!=h:raise ValueError('actual consumed input changed:'+n)
        r.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            native_authenticated_fatal61_62_and_selected_abort_cancel_inserted=True,shared_native_MR_PTE_backend_nonce=True,
            one_ACK_allocator=True,selected_certificate_is_global_drain_or_unpin=False,native_fatal63_implemented=False,
            error_CQ_STOP_lifetime_implemented=False,
            remaining=['Fresh full actual native40 binary/runtime with all original38 outcomes and genuine fatal61/62 wire/abort/cancel/RQ/quarantine, not just compilation.',
                'All original11/fatal63/error CQ/full QP STOP/reference lifetime/recovery/real-peer/original timing/physical requirements remain.'])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=r['compile_seconds'],native_runtime=False)))


if __name__=='__main__':main()
