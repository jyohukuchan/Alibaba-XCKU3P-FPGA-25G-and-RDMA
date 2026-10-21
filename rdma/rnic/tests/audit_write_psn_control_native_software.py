#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native38 PSN control, same-source kernel and unedited-CQ105 audit.

Require all68 frozen kernel inputs identical and every100 prior CQ outcome.
Linux/MMIO/pins/DMA primitives remain MODELS, not installed/live hardware.
"""
import ast
from pathlib import Path
import audit_segmented_write_rnr_native_software as parent
from segmented_write_kernel_models import once


def runner_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    old="""    names=['segmented-write-rnr-native-full-002','segmented-write-rnr-native-runtime-diagnostics-001',
        'segmented-write-rnr-kernel-build-001','segmented-write-rnr-kernel-native-cq-001',
        'segmented-write-kernel-build-001','segmented-write-kernel-native-cq-001',
        'segmented-write-native-software-diagnostics-001']"""
    new="""    names=['write-psn-control-native-full-001','write-psn-control-native-runtime-diagnostics-001',
        'write-psn-control-kernel-build-001','write-psn-control-kernel-native-cq-001',
        'segmented-write-rnr-kernel-build-001','segmented-write-rnr-kernel-native-cq-001',
        'segmented-write-rnr-native-software-diagnostics-001']"""
    t=once(t,old,new)
    for old,new in [
        ("len(native['tests'])!=37 or len(cq['tests'])!=100 or len(oldcq['tests'])!=95 or not kernel['native_RNR_retry_matched']",
         "len(native['tests'])!=38 or len(cq['tests'])!=105 or len(oldcq['tests'])!=100 or not kernel['native_PSN_control_matched']"),
        ('exact new37 and matched kernel/all100 CQ cases required','exact new38 and matched kernel/all105 CQ cases required'),
        ('every95 original CQ case name required','every100 original CQ case name required'),
        ("snapshot=run/'LARGE_RX_WRITE_RNR-event.hex';rq=run/'LARGE_RX_WRITE_RNR-receive-records.hex'",
         "snapshot=run/'LARGE_RX_WRITE_PSN-event.hex';rq=run/'LARGE_RX_WRITE_PSN-receive-records.hex'"),
        ("positive=cq['tests']['LARGE_RX_WRITE_RNR-0']['summary']","positive=cq['tests']['LARGE_RX_WRITE_PSN-0']['summary']"),
        ("cq['tests']['LARGE_RX_WRITE_RNR-'+str(mutation)]","cq['tests']['LARGE_RX_WRITE_PSN-'+str(mutation)]"),
        ('actual new native37 raw report','actual new native38 raw report'),
        ('actual_native_cases=37,actual_standard_C_native_CQ_cases=100,all95_previous_CQ_outcomes_identical=True,',
         'actual_native_cases=38,actual_standard_C_native_CQ_cases=105,all100_previous_CQ_outcomes_identical=True,'),
        ('new_RNR_CQ_summary=positive','new_PSN_CQ_summary=positive'),
        ('native37=True,actual_CQ100=True','native38=True,actual_CQ105=True')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
