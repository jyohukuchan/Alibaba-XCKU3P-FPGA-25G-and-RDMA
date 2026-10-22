#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Re-execute all220 unchanged callbacks on actual full75-input parent cohort.

This is the existing callback fixture, not the separate new parent-worker
execution proof. Linux/MMIO/certificate/pins/DMA/workqueue remain models.
"""
import ast
from pathlib import Path
import tempfile
import probe_fatal_verbs_callbacks as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    old="'fatal-verbs-kernel-build-001'"
    if t.count(old)!=2:raise ValueError('both exact new kernel build bindings required')
    t=t.replace(old,"'fatal-parent-kernel-build-001'")
    for before,after in [("evidence['actual_total_inputs']!=73","evidence['actual_total_inputs']!=75"),
        ("prefix='fatal-verbs-callbacks-'","prefix='fatal-parent-callbacks-'")]:t=once(t,before,after)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-parent-callback-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
