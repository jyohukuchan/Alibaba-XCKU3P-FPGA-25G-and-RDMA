#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same profile8 modules ONLY after native38 PSN control and runtime audit.

No kernel ABI/feature/source/default change, install or load. Retain exact
kernel inputs and original180s build/1200s-native/30s-case bounds.
"""
import ast
from pathlib import Path
import build_segmented_write_rnr as parent

ROOT=parent.ROOT;once=parent.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [("prefix='segmented-write-rnr-kernel-frozen-'","prefix='write-psn-control-kernel-frozen-'"),
        ("len(native.get('tests',{}))!=37","len(native.get('tests',{}))!=38"),
        ("'complete_native_RNR_retry_runtime','all36_prior_cases_retained']):",
         "'complete_native_RNR_retry_runtime','all36_prior_cases_retained','complete_native_PSN_control_runtime','all37_prior_cases_retained']):"),
        ('exact matching profile8/native37 RNR/retry plus all36 old cases required',
         'exact matching profile8/native38 PSN control plus all37 old cases required'),
        ("'LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR'}","'LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR','LARGE_RX_WRITE_PSN'}"),
        ('native_RNR_retry_matched=True,','native_RNR_retry_matched=True,native_PSN_control_matched=True,')]:t=once(t,old,new)
    anchor="    parent=ROOT/'external/corundum/modules/mqnic'"
    t=once(t,anchor,'''    import sys
    sys.path.insert(0,str(ROOT/'rdma/rnic/tests'))
    import audit_segmented_receive as actual_binding
    audit,audit_binding=actual_binding.bindings('write-psn-control-native-runtime-diagnostics-001')
    name=a.native_report.name.removeprefix('rocev2-rnic-').removesuffix('.json')
    if not audit['audit_passed']or not audit['actual_NAK_suppression_retry_duplicate_no_second_DMA_RQ_CQ']or \\
       audit['evidence'].get(name,{}).get('report_sha256')!=digest(a.native_report):
        raise ValueError('actual same-source native38 runtime audit required before module build')
'''+anchor)
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
