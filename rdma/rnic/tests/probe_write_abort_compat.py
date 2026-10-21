#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged real owned Atomic/Immediate services on the WRITE-abort HLS.

Only internal signatures/harness change. The new abort input is empty in
these legacy tests; all actual consumers/assertions and600s/30s remain.
This is not native abort/quarantine/error CQ/global drain/physical proof.
"""
from pathlib import Path
import probe_control_response_compat as parent
from probe_control_response_hls import once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('from probe_control_response_hls import control_harness','from probe_write_abort_hls import abort_harness'),
        ("info.get('HLS_top')!='rocev2_native_control_response_top'","info.get('HLS_top')!='rocev2_native_write_abort_top'"),
        ("extra=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_control_response_hls.py',",
         "extra=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_write_abort_hls.py',ROOT/'rdma/rnic/tests/probe_control_response_compat.py',ROOT/'rdma/rnic/tests/probe_control_response_hls.py',"),
        ("prefix='control-response-compat-'","prefix='write-abort-compat-'"),
        ('compat.harness=control_harness','compat.harness=abort_harness')]:t=once(t,old,new)
    return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
