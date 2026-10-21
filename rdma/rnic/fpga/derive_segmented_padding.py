# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select pre-padded LAST handling ONLY around the new segmented HLS.

Preserve the legacy padding module/old initiator paths and every owner,
clock, lifetime, checksum/ICRC and default capability gate.
"""
import derive_segmented_wire as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
PAD=RTL/'rocev2_segmented_tx_padding.v'
TRANSPORT=ROOT/'rdma/rtl/rocev2_integrity_transport.v'
EXTRA=[*parent.EXTRA,PAD]


def derive():
    out=parent.derive()
    t=out[TRANSPORT]
    if 'module rocev2_atomic_request_integrity_transport #'not in t or \
       'rocev2_native_segmented_request_top transport ('not in t:
        raise ValueError('only matched new native requester integrity wrapper may select segmented padding')
    out[TRANSPORT]=once(t,'rocev2_tx_padding tx_padding (','rocev2_segmented_tx_padding tx_padding (')
    return out
