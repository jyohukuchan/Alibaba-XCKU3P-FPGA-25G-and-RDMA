#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh exact8191/31 native29, unchanged large data/owner and all regressions.

Same generated HLS/MR/PTE/DMA/nonce/MAC/CQ, only two RTL identity leaves and
explicit expected identity fields change. All29 cases/30s, compile1200s.
No actual Linux, standard API, physical hardware or timing qualification.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_padding_native_full as parent
import segmented_profile_native_sources as source
import segmented_profile_native_fixture as fixture

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_padding_native_sources as source','import segmented_profile_native_sources as source')
    t=once(t,'import segmented_wire_native_fixture as service','import segmented_profile_native_fixture as service')
    t=once(t,'verify_zero=legacy.verify_zero','verify_zero=service.verify_zero')
    t=once(t,'fixture.verify(output,rx_records,opcode,capacity,','service.verify_rq(output,rx_records,opcode,capacity,')
    t=once(t,'prior.verify(output,records,request,opcode,immediate,run)',
        'service.verify_atomic(output,records,request,opcode,immediate,run)')
    t=once(t,"prefix='segmented-padding-native-full-'","prefix='segmented-profile-native-full-'")
    t=once(t,"prefix='as02-segmented-padding-obj-'","prefix='as02-segmented-profile-obj-'")
    t=once(t,"prefix='as02-segmented-padding-artifacts-'","prefix='as02-segmented-profile-artifacts-'")
    t=once(t,'RNC_features=4095,','RNC_features=8191,CQC_features=31,matching_kernel_software_profile=4,')
    marker="    for n,h in evidence['source_sha256'].items():"
    t=once(t,marker,"    if(evidence.get('RNC_features'),evidence.get('CQC_features'),evidence.get('software_profile'))!=(8191,31,4):\n"
        "        raise ValueError('exact matched8191/31 native elaboration required')\n"+marker)
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-profile-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
