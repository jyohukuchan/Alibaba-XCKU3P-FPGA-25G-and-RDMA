#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh real native8193 READ plus ALL29 prior bounded native cases.

Actual SQ/MR/PTE/CRC/MSN/generated-HLS/DMA/nonce/fence/MAC/CQ; physical
host/root/peer/PHY/PTP modeled. Original1200s build/30s runtime bounds,
clocks/geometry/global drains/tails/oracles retained. No Linux/hardware proof.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_profile_native_full as parent
import segmented_read_native_fixture as fixture

ROOT=fixture.ROOT;once=fixture.once


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_profile_native_sources as source','import segmented_read_profile_native_sources as source')
    t=once(t,'import segmented_profile_native_fixture as service','import segmented_read_native_fixture as service')
    a=t.index("    if not evidence.get('pass_test')")
    b=t.index("    for n,h in evidence['source_sha256'].items():",a)
    t=t[:a]+'''    if not evidence.get('pass_test')or evidence.get('HLS_top')!='rocev2_native_segmented_read_top'or \\
       (evidence.get('requester_owner_bits'),evidence.get('SQ_bits'),evidence.get('READ_admission_limit'))!=(748,408,1048576):
        raise ValueError('exact actual full READ profile graph required')
    if(evidence.get('RNC_features'),evidence.get('CQC_features'))!=(16383,63)or not all(evidence.get(n)for n in
        ['large_READ_admission_open','protected_segmented_RX_selected','expected_MSN_connected_to_RX','whole_READ_lifetime_wired']):
        raise ValueError('distinct16383/63 admission/RX/MSN/lifetime graph required')
    expected_modules={'rocev2_segmented_read_executor_mux':1,'rocev2_segmented_read_executor':1,
        'rocev2_segmented_executor_mux':1,'rocev2_segmented_source_executor':1,'rocev2_segmented_child_executor':2,
        'rocev2_memory_command_nonce':1,'rocev2_segmented_read_response_guard':1,'rocev2_expected_remote_msn':1}
    if any(evidence['module_counts'].get(n)!=count for n,count in expected_modules.items())or not evidence.get('both_global_HLS_drains_zero'):
        raise ValueError('actual unique READ/source/shared physical-nonce/MSN/drain graph required')
'''+t[b:]
    for old,new in [("prefix='segmented-profile-native-full-'","prefix='segmented-read-native-full-'"),
        ("prefix='as02-segmented-profile-obj-'","prefix='as02-segmented-read-native-obj-'"),
        ("prefix='as02-segmented-profile-artifacts-'","prefix='as02-segmented-read-native-artifacts-'")]:t=once(t,old,new)
    t=once(t,'RNC_features=8191,CQC_features=31,matching_kernel_software_profile=4,',
        'RNC_features=16383,CQC_features=63,kernel_profile_matched=False,')
    t=once(t,'large_native_wire_CQ=False,planned_cases=29,large_source_runtime_verified=False',
        'large_native_wire_CQ=False,planned_cases=30,large_source_runtime_verified=False,large_READ_native_runtime=False')
    t=once(t,"'wqe_segmented.c','wqe_segmented.h']]",
        "'wqe_segmented.c','wqe_segmented.h','wqe_segmented_read.c','wqe_segmented_read.h']]")
    t=once(t,"        cases=[('LARGE_WRITE',1,0,['+WRITE','+SEGMENTED'],False,None),",
        "        cases=[('LARGE_READ',2,0,['+LARGE_READ'],False,None),\n"
        "            ('LARGE_WRITE',1,0,['+WRITE','+SEGMENTED'],False,None),")
    t=once(t,"if len(cases)!=29:raise ValueError('all27 prior cases plus actual8193 WRITE/SEND required')",
        "if len(cases)!=30:raise ValueError('all29 prior cases plus actual8193 READ required')")
    t=once(t,"            is_large=name.startswith('LARGE_')\n            if is_large:",
        "            is_large_read=name=='LARGE_READ'\n            is_large=name in ['LARGE_WRITE','LARGE_SEND']\n"
        "            if is_large_read:words,records,request,read_frames=service.large_read_variant()\n            elif is_large:")
    t=once(t,"            if is_large:inputs['large-acks.hex']=",
        "            if is_large_read:inputs['large-read-input.hex']=''.join(f'{w:037x}\\n'for w in read_frames)\n"
        "            if is_large:inputs['large-acks.hex']=")
    t=once(t,'result.update(service.verify_large(output,records,request,opcode,run)if is_large else',
        'result.update(service.verify_large_read(output,records,request,run)if is_large_read else\n'
        '                service.verify_large(output,records,request,opcode,run)if is_large else')
    t=once(t,"            if not is_large:result['actual_source_and_atomic_CQ']=",
        "            if not is_large and not is_large_read:result['actual_source_and_atomic_CQ']=")
    t=once(t,"            result['actual_common_nonce_backend']=service.verify_nonce(output)",
        "            if is_large_read:report['large_READ_native_runtime']=True\n"
        "            result['actual_common_nonce_backend']=service.verify_nonce(output)")
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-read-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
