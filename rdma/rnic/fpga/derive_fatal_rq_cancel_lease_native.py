# SPDX-License-Identifier: BSD-2-Clause-Views
"""Separate real RX/reference/memory leases from the permanent control alias.

Original aggregate atomic/configuration/admission/queue guards stay byte-
identical. A new output carries every original term except control-held,
retaining control-owner VALID and all actual RX/write/Atomic/reference work.
Only fatal RQC authority consumes the distinction; no STOP/drain/unpin.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from segmented_write_payload_native_fixture import once

CORE='rocev2_shared_protected_responder.v'
PAGED='rocev2_paged_responder.v'
MIDDLE=['rocev2_controlled_responder.v','rocev2_dual_ethernet_endpoint.v',
    'rocev2_native_endpoint.v','rocev2_native_sq_endpoint.v']
TOP='rocev2_native_rnic_endpoint.v'
LEAVES=[CORE,PAGED,*MIDDLE,TOP]


def derive(files,original_top):
    out={n:files[n]for n in LEAVES}
    for n in [CORE,PAGED,*MIDDLE]:
        out[n]=once(out[n],'    output wire atomic_rx_guard,',
            '    output wire atomic_rx_guard,\n    output wire fatal_rx_noncontrol_guard,')
    original=files[CORE];a=original.index('assign atomic_rx_guard=control_external_guard || ');b=original.index(';',a)+1
    rest=original[a+len('assign atomic_rx_guard=control_external_guard || '):b-1]
    out[CORE]=once(out[CORE],original[a:b],original[a:b]+\
        "\nassign fatal_rx_noncontrol_guard=(s_control_owner_valid!==1'b0) || "+rest+';')
    out[PAGED]=once(out[PAGED],'wire guard_atomic_rx_guard;',
        'wire guard_atomic_rx_guard,guard_fatal_rx_noncontrol_guard;')
    out[PAGED]=once(out[PAGED],'.atomic_rx_guard(guard_atomic_rx_guard),',
        '.atomic_rx_guard(guard_atomic_rx_guard),\n.fatal_rx_noncontrol_guard(guard_fatal_rx_noncontrol_guard),')
    anchor='assign atomic_rx_guard=guard_atomic_rx_guard || atomic_memory_guard || atomic_memory_fault;'
    out[PAGED]=once(out[PAGED],anchor,anchor+\
        '\nassign fatal_rx_noncontrol_guard=guard_fatal_rx_noncontrol_guard || atomic_memory_guard || atomic_memory_fault;')
    for n in [*MIDDLE,TOP]:
        out[n]=once(out[n],'.atomic_rx_guard(atomic_rx_guard),',
            '.atomic_rx_guard(atomic_rx_guard),\n.fatal_rx_noncontrol_guard(fatal_rx_noncontrol_guard),')
    out[TOP]=once(out[TOP],'wire atomic_rx_guard;','wire atomic_rx_guard,fatal_rx_noncontrol_guard;')
    a=original_top.index('assign atomic_lease_guard=s_control_held || ');b=original_top.index(';',a)+1
    aggregate=original_top[a:b];rest=aggregate[len('assign atomic_lease_guard=s_control_held || '):-1]
    if rest.count('atomic_rx_guard')!=1:raise ValueError('exact sole original RX aggregate term required')
    a=out[TOP].index('assign fatal_cancel_other_lease_guard=');b=out[TOP].index(';',a)+1
    out[TOP]=out[TOP][:a]+'assign fatal_cancel_other_lease_guard='+rest.replace('atomic_rx_guard','fatal_rx_noncontrol_guard')+';'+out[TOP][b:]
    out[TOP]=once(out[TOP],'assign atomic_lease_guard=s_control_held || fatal_cancel_other_lease_guard;',aggregate)
    return out
