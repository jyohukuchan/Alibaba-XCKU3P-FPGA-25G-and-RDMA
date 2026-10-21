#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual complete native/HLS compile with the known held-group ingress fix.

Retain all original complete-profile/module/domain/width/drain/clock gates.
No payload runtime, installed API, original timing or physical proof inferred.
"""
from pathlib import Path
import check_segmented_receive_native_elaboration as base


def runner_source():
    t=Path(base.__file__).read_text()
    from derive_segmented_receive_continuation import once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_receive_native_sources as source','import segmented_receive_continuation_native_sources as source')
    t=once(t,"prefix='segmented-receive-native-'","prefix='segmented-receive-continuation-native-'")
    t=once(t,"prefix='as02-segmented-receive-native-'","prefix='as02-segmented-receive-continuation-native-'")
    t=once(t,'unknown_leaves_ignored=False,actual_generated_HLS=True,',
        'unknown_leaves_ignored=False,receive_continuation_gate_fixed=True,actual_generated_HLS=True,')
    t=once(t,"        bridge=(run/'rocev2_integrity_transport.v').read_text()",
        "        guard=(run/'rocev2_shared_protected_responder.v').read_text()\n"
        "        if \"(recv_completion_pending===1'b1 && recv_group_active===1'b1)\"not in guard:raise ValueError('exact known held-group raw-reference gate required')\n"
        "        bridge=(run/'rocev2_integrity_transport.v').read_text()")
    return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
