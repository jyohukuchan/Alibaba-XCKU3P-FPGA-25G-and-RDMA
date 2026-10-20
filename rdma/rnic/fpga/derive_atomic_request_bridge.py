# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched408-bit SQ /748-bit requester integrity bridge, same owned core.

Receive620/680/752 and the owned Atomic responder service ABI stay unchanged.
This is not a complete native profile: actual protected owner/admission/result
DMA/MAC/CQ/lifetimes and matched128-byte SQC/kernel/provider remain required.
No Atomic-only packet guard may replace ordinary native response admission.
"""
import derive_atomic_native_bridge as base
once=base.once


def derive():
    t=base.derive()
    for old,new in [
        ('module rocev2_atomic_native_integrity_transport #','module rocev2_atomic_request_integrity_transport #'),
        ('rocev2_native_atomic_owned_top transport (','rocev2_native_atomic_request_top transport ('),
        ('input wire [619:0] s_request_owner_tdata','input wire [747:0] s_request_owner_tdata'),
        ('output wire [687:0] m_request_done_tdata','output wire [815:0] m_request_done_tdata'),
        ('input wire [279:0] s_axis_sq_tdata','input wire [407:0] s_axis_sq_tdata'),
        ('wire [279:0] keyed_sq_data=s_axis_sq_tdata;','wire [407:0] keyed_sq_data=s_axis_sq_tdata;')]:
        t=once(t,old,new)
    # ap_uint<748> AXIS pads to752. The existing explicit upper4zero bits
    # remain; receive context is NEVER widened by a global substitution.
    if t.count('.s_axis_request_owner_TDATA({4\'d0,s_request_owner_tdata})')!=1:
        raise ValueError('request AXIS padding contract changed')
    return t
