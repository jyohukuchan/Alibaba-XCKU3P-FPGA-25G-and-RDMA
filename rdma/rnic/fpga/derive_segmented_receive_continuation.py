# SPDX-License-Identifier: BSD-2-Clause-Views
"""Allow raw references for a known retained receive MESSAGE continuation.

The old complete graph remains immutable. Only its raw RX reference enable
changes: whole-CQ pending does not close the next packet of a known held
group. Original QP/pause/MR/config/context/reference/fault checks still apply;
pending is NOT cleared and no memory/HLS/MAC/CQ authority is fabricated.
"""
import derive_segmented_receive as base

ROOT=base.ROOT;RTL=base.RTL;once=base.once;EXTRA=base.EXTRA
GUARD=RTL/'rocev2_protected_responder.v'


def __getattr__(name):return getattr(base,name)


def derive():
    out=base.derive()
    out[GUARD]=once(out[GUARD],
        '(!RECV_CQ_ENABLE || !recv_completion_pending)),.parent_fault(atomic_parent_fault),',
        "(!RECV_CQ_ENABLE || !recv_completion_pending ||\n"
        "    (recv_completion_pending===1'b1 && recv_group_active===1'b1))),.parent_fault(atomic_parent_fault),")
    prior=base.derive()
    if {p for p in out if out[p]!=prior[p]}!={GUARD}:raise ValueError('only reviewed raw-reference enable may change')
    return out
