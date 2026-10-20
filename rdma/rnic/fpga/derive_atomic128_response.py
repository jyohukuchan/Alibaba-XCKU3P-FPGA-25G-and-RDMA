# SPDX-License-Identifier: BSD-2-Clause-Views
"""Atomic requester response protection in the existing native guard domain.

Checked748-bit derivative: full immutable operands/owner, actual complete
IPv4/UDP/ICRC/peer/QPN/issued-PSN/AETH/length validation and result-placement
token BEFORE any HLS beat. No separate MR or sequence namespace; native
parents must supply real saved MR/issued-WR authority and retain its lease.
This component alone is NOT result DMA/WR/CQ/unpin or standard-API proof.
"""
import derive_immediate_native as base

ROOT=base.ROOT;RTL=ROOT/'rdma/rnic/rtl';SOURCE=RTL/'rocev2_wqe_response_guard.v'
once=base.once


def derive():
    t=base.leaf('rocev2_wqe_response_guard',SOURCE.read_text())
    t=once(t,'module rocev2_wqe_response_guard #(','module rocev2_atomic128_wqe_response_guard #(')
    # Immediate derivative already slices only the lower588 field unpacking.
    # Widen WHOLE requester owners, not the header, field offsets or MR table.
    if t.count('[619:0]')!=4:raise ValueError('response owner geometry changed')
    t=t.replace('[619:0]','[747:0]')
    t=once(t,'wire expect_ok=known &&',
        'wire in_atomic=in_op==7 || in_op==8;\n'
        'wire operands_ok=in_atomic ? (in_length==8 && in_remote[2:0]==0 &&\n'
        '    (in_op!=8 || s_expect_context[683:620]==0)) : s_expect_context[747:620]==0;\n'
        'wire expect_ok=known && operands_ok &&')
    t=once(t,'(in_op==1 || in_op==2 || in_op==6 || ((in_op==3 || in_op==5) && in_remote==0 && in_rkey==0))',
        '(in_atomic || in_op==1 || in_op==2 || in_op==6 || ((in_op==3 || in_op==5) && in_remote==0 && in_rkey==0))')
    t=once(t,"wire op_ok=control_packet || parsed_opcode==(opcode==2 ? 8'h10 : 8'h11);",
        "wire atomic_request=opcode==7 || opcode==8;\n"
        "wire result_request=opcode==2 || atomic_request;\n"
        "wire op_ok=control_packet || parsed_opcode==(atomic_request ? 8'h12 : opcode==2 ? 8'h10 : 8'h11);")
    t=once(t,"wire size_ok=(opcode!=2 || control_packet) ? (bytes_received==48 && pad==0) :\n"
        "    (bytes_received==48+padded_length && pad==((-length)&3));",
        "wire size_ok=(!result_request || control_packet) ? (bytes_received==48 && pad==0) :\n"
        "    atomic_request ? (bytes_received==56 && pad==0) :\n"
        "    (bytes_received==48+padded_length && pad==((-length)&3));")
    return once(t,'state<=control_packet ? CONTROL : opcode==2 ? TOKEN : FORWARD;',
        'state<=control_packet ? CONTROL : result_request ? TOKEN : FORWARD;')
