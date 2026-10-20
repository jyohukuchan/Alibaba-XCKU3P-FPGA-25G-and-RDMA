# SPDX-License-Identifier: BSD-2-Clause-Views
"""Stage the real owned HLS in the complete native authority graph.

Ordinary READ/WRITE/SEND/Immediate use the SAME owned core required by Atomic.
Atomic RX dispatch/service/exclusive memory/MAC is still NOT selected: normal
protected admission rejects Atomic opcodes and all Atomic inputs are inactive.
Unexpected Atomic service/done output faults the native HLS wrapper. This is
staging toward full integration, not an Atomic capability/completion claim.
"""
import derive_atomic_native_authority as authority
import derive_atomic_native_bridge as bridge

ROOT=authority.ROOT
once=authority.once
EXTRA=authority.EXTRA


def derive():
    out=authority.derive()
    path=authority.base.duplex.ORIGINAL
    t=out[path]
    t=once(t,'rocev2_immediate_integrity_transport #(','rocev2_atomic_native_integrity_transport #(')
    t=once(t,'wire incoming_fault=','wire atomic_unowned_offer=disabled_atomic_request || disabled_atomic_done;\nwire incoming_fault=atomic_unowned_offer ||')
    t=once(t,'generate if(QP_TX_ENABLE)begin : qptx_core',
        'wire disabled_atomic_request,disabled_atomic_done;\n'
        'generate if(QP_TX_ENABLE)begin : qptx_core')
    t=once(t,'.s_request_owner_tdata(s_local_owner_context),',
        ".s_atomic_owner(144'd0),.s_atomic_owner_valid(1'b0),.s_atomic_owner_ready(),\n"
        ".m_atomic_request(),.m_atomic_request_valid(disabled_atomic_request),.m_atomic_request_ready(1'b0),\n"
        ".s_atomic_reply(392'd0),.s_atomic_reply_valid(1'b0),.s_atomic_reply_ready(),\n"
        ".m_atomic_done(),.m_atomic_done_valid(disabled_atomic_done),.m_atomic_done_ready(1'b0),\n"
        '.s_request_owner_tdata(s_local_owner_context),')
    t=once(t,'end else begin : legacy_core',
        "end else begin : legacy_core\nassign disabled_atomic_request=1'b0;assign disabled_atomic_done=1'b0;")
    out[path]=t
    out[authority.base.duplex.bridge.legacy.BRIDGE]=bridge.derive()
    return out
