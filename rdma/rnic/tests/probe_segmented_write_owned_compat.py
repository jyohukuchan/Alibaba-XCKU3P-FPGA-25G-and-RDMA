#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged real owned Atomic service and Immediate consumers on new WRITE core.

Only the typed WRITE harness/signatures are extended. Keep every actual
service/memory/Immediate consumer and30s/600s assertion and bound. No new
native, physical, Linux or original-clock timing qualification is inferred.
"""
from pathlib import Path
import probe_segmented_receive_compat as base
from probe_segmented_write_owned_hls import once


def runner_source():
    t=Path(base.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import probe_segmented_read_hls as read',
        'import probe_segmented_read_hls as read\nfrom probe_segmented_write_owned_hls import write_owned_harness')
    t=once(t,"info.get('HLS_top')!='rocev2_native_segmented_receive_top'",
        "info.get('HLS_top')!='rocev2_native_segmented_write_owned_top'")
    t=once(t,'extra=[Path(__file__).resolve(),',
        "extra=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',")
    t=once(t,"prefix='segmented-receive-compat-'","prefix='segmented-write-owned-compat-'")
    t=once(t,'compat.harness=read.harness','compat.harness=write_owned_harness')
    return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
