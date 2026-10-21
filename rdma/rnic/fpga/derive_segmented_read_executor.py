# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact bounded native executor and READ-unpad children for a new controller.

Only the unpad module name changes. The whole748-bit READ controller must
derive each bounded context from its saved authorized WR and retain the
original placement/CQ lease. No default graph or old length limit changes.
"""
import derive_segmented_source as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
child_source=parent.child_source


def unpad_source():
    t=parent.parent.derive()[RTL/'rocev2_wqe_read_unpad.v']
    for anchor in ['input wire [747:0] s_context','in_length<=4096',
                   's_command==expected_raw','downstream_queue_guard[qpn]',
                   's_axis_tkeep==mask64(wire_remaining)']:
        if anchor not in t:raise ValueError('actual bounded unpad invariant missing:'+anchor)
    return once(t,'module rocev2_wqe_read_unpad #(',
        'module rocev2_segmented_read_child_unpad #(')
