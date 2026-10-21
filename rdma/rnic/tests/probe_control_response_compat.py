#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged real owned Atomic service and Immediate consumers on control HLS.

Only new internal signatures/harness are adapted. Real old service/consumer
assertions and600s/30s remain; no native/control-MAC or physical claim.
"""
from pathlib import Path
import probe_segmented_write_owned_compat as parent
from probe_control_response_hls import once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('from probe_segmented_write_owned_hls import write_owned_harness',
        'from probe_control_response_hls import control_harness'),
        ("info.get('HLS_top')!='rocev2_native_segmented_write_owned_top'","info.get('HLS_top')!='rocev2_native_control_response_top'"),
        ("extra=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',",
         "extra=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_control_response_hls.py',ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',"),
        ("prefix='segmented-write-owned-compat-'","prefix='control-response-compat-'"),
        ('compat.harness=write_owned_harness','compat.harness=control_harness')]:t=once(t,old,new)
    return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
