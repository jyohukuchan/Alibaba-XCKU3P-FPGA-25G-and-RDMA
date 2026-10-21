#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual NEW profile8 native36, unchanged inputs/data oracles, not hardware.

Only expected CSR identity words differ from previous actual WRITE-native36.
No observed snapshot normalization or borrowed binary/software proof.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous record')
    records={};ids={}
    for name in ['segmented-write-profile-native-full-001','segmented-write-native-full-002','segmented-write-profile-native-elaboration-001',
        'segmented-write-native-runtime-diagnostics-001','segmented-write-owned-generated-hls-001','segmented-write-software-source-diagnostics-001']:
        records[name],ids[name]=binding.bindings(name)
    new=records['segmented-write-profile-native-full-001'];old=records['segmented-write-native-full-002']
    elab=records['segmented-write-profile-native-elaboration-001'];generated=records['segmented-write-owned-generated-hls-001']
    if not all(new.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph','both_global_drains_zero',
        'native_controller_inserted','incoming_segmented_WRITE_runtime','all34_prior_cases_retained','private_WRITE_profile_identity']):
        raise ValueError('actual fresh complete matching profile8 execution required')
    if (new['RNC_features'],new['CQC_features'],new['SQC_features'],new['RQC_features'],new['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('new exact identity required')
    if len(new['tests'])!=36 or set(new['tests'])!=set(old['tests'])or any(v['exit']or v['seconds']>30 for v in new['tests'].values())or \
       new['compile_exit']or new['compilation_seconds']>1200 or new['compile_limit_seconds']!=1200 or new['simulation_limit_seconds']!=30:
        raise ValueError('all36 exact prior bounded cases required')
    for name,v in old['tests'].items():
        current=new['tests'][name]
        if current['runtime_input_sha256']!=v['runtime_input_sha256']or ('summary'in v and current.get('summary')!=v['summary']):
            raise ValueError('original raw input bytes or data/owner/cardinality summary changed:'+name)
    if new['binary_sha256']==old['binary_sha256']or new['compile_directory']==old['compile_directory']:
        raise ValueError('new identity needs fresh executable/object directory')
    vvp=next(Path(q)for q in new['RAM_artifact_sha256']if Path(q).name=='tb.vvp').read_text()
    counts={name:len(re.findall(r'\.scope module, "[^"]+" "'+name+r'"',vvp))for name in elab['module_counts']}
    if counts!=elab['module_counts']:raise ValueError('same actual sole native HLS/MR/PTE/backend/nonce/ACK/RQ/controller required')
    genroot=ROOT/generated['directory']/'project/solution1/syn/verilog'
    selected={Path(q).name for q in new['source_sha256']if(ROOT/q).parent==genroot}
    if selected!=set(generated['generated_sha256']):raise ValueError('all same-generation197 RTL/data files required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected default raw source changed')
    log=(ROOT/new['directory']/'compile.log').read_text()
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_native_cases=36,all36_prior_inputs_and_data_summaries_identical=True,private_identity=[131071,511,13,63,8],
        compilation_seconds=new['compilation_seconds'],maximum_case_seconds=max(v['seconds']for v in new['tests'].values()),
        binary_sha256=new['binary_sha256'],frozen_binary_path=new['frozen_binary_path'],same_generation_RTL_data_files=len(selected),
        actual_executable_native_module_counts=counts,UNOPTFLAT_warnings=log.count('%Warning-UNOPTFLAT:'),warning_waivers=False,
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        kernel_modules_or_callbacks_qualified=False,live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Matching real-header kernel build, standard callbacks/refs, unedited new native WRITE-CQ consumption.',
            'Full1MiB native/multiSGE/live registered refs/recovery/partial-HLS cleanup/original timing/physical and all11 remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,actual_native_cases=36,verified_bindings=result['verified_bindings'])),flush=True)


if __name__=='__main__':main()
