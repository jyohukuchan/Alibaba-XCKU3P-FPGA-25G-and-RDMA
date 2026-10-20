# SPDX-License-Identifier: BSD-2-Clause-Views
"""One exact private native child executor, never rewrite the default source.

The new outer source controller retains the whole WR; this unchanged bounded
child keeps real data/status/byte-shape guards for each authorized subrange.
Full graph wiring, reserved tag namespace and large wire/CQ remain required.
"""
import derive_zero_service_native as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once


def child_source():
    source=parent.derive()[RTL/'rocev2_wqe_memory_executor.v']
    for anchor in ['input wire [747:0] s_owner_context','in_length<=4096',
                   's_memory_status_tag==tag','downstream_queue_guard[qpn]']:
        if anchor not in source:raise ValueError('actual bounded child invariant missing:'+anchor)
    return once(source,'module rocev2_wqe_memory_executor #(',
        'module rocev2_segmented_child_executor #(')
