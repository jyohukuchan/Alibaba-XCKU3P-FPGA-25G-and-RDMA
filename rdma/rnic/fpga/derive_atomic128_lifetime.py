# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched Atomic requester wire/MAC/replay/result-unpad lifetime leaves.

Same actual native proof join, not quiet/ready-based WR completion. Full748
owners,816-bit HLS receipts and all64-bit wire operands are checked. Real
MR/DMA/MAC/CQ/kernel parents must join their genuine operation-owned events.
Original/default sources and clock/drain gates are never modified here.
"""
import re
import derive_atomic128_response as geometry

ROOT=geometry.ROOT;RTL=geometry.RTL;once=geometry.once
NAMES=['rocev2_wqe_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_tx_lifetime',
       'rocev2_wqe_replay','rocev2_wqe_read_unpad']


def operand_policy(t):
    t=once(t,'wire owner_ok=',
        'wire in_atomic=in_op==7 || in_op==8;\n'
        'wire operand_shape=in_atomic ? (in_length==8 && in_remote[2:0]==0 &&\n'
        '    (in_op!=8 || s_owner_context[683:620]==0)) : s_owner_context[747:620]==0;\n'
        'wire owner_ok=operand_shape &&')
    return once(t,'(in_op==1 || in_op==2 || in_op==6 || ((in_op==3 || in_op==5) && in_remote==0 && in_rkey==0))',
        '(in_atomic || in_op==1 || in_op==2 || in_op==6 || ((in_op==3 || in_op==5) && in_remote==0 && in_rkey==0))')


def leaf(name):
    t=geometry.base.leaf(name,(RTL/(name+'.v')).read_text())
    if '[619:0]'not in t:raise ValueError('missing full requester owner '+name)
    t=t.replace('[619:0]','[747:0]')
    if name in ['rocev2_wqe_lifetime','rocev2_wqe_mac_tx']:t=operand_policy(t)
    if name=='rocev2_wqe_lifetime':
        # Atomic compare occupies wire bytes60..67, beyond the old64-byte
        # header window. Capture FIVE complete words and compare all64 bits.
        if t.count('[511:0]')!=4:raise ValueError('lifetime header geometry changed')
        t=t.replace('[511:0]','[639:0]')
        t=once(t,'if(tx_words<4)for','if(tx_words<5)for')
        t=once(t,'wire send_request=opcode==3 || opcode==5;',
            'wire atomic_request=opcode==7 || opcode==8;\n'
            'wire result_request=opcode==2 || atomic_request;\n'
            'wire send_request=opcode==3 || opcode==5;')
        t=once(t,"wire [7:0] request_wire_opcode=opcode==1 ? 8'h0a :",
            "wire [7:0] request_wire_opcode=opcode==7 ? 8'h13 : opcode==8 ? 8'h14 : opcode==1 ? 8'h0a :")
        t=once(t,'wire [31:0] request_header_bytes=send_request ?',
            'wire [31:0] request_header_bytes=atomic_request ? 72:send_request ?')
        t=once(t,'header[29*8+4+:2]==(opcode==2 ? 0 : ((-length)&3))',
            'header[29*8+4+:2]==(result_request ? 0 : ((-length)&3))')
        t=once(t,'be32(header,48)==remote_key && be32(header,52)==length)',
            'be32(header,48)==remote_key &&\n'
            '     (atomic_request ? (be64(header,52)==owner[747:684] && be64(header,60)==owner[683:620]):be32(header,52)==length))')
        t=once(t,'request_header_bytes+(opcode==2 ? 0:padded)',
            'request_header_bytes+(result_request ? 0:padded)')
        t=once(t,"s_response_opcode==(opcode==2 ? 8'h10 : 8'h11)",
            "s_response_opcode==(atomic_request ? 8'h12 : opcode==2 ? 8'h10 : 8'h11)")
        t=once(t,'qpn[9:0],(opcode!=2)}','qpn[9:0],(!result_request)}')
        t=once(t,'(opcode==2 && !issue_seen)','(result_request && !issue_seen)')
        t=once(t,'(opcode!=2 || issue_seen)','(!result_request || issue_seen)')
    if name=='rocev2_wqe_tx_lifetime':
        t=once(t,'input wire [687:0] s_request_done_data,','input wire [815:0] s_request_done_data,')
        for old,new in [('643:620','771:748'),('667:644','795:772'),('675:668','803:796'),('687:676','815:804')]:
            t=once(t,'s_request_done_data['+old+']','s_request_done_data['+new+']')
        t=once(t,"wire [7:0] request_opcode=m_cq_context[339:324]==1 ? 8'h0a :",
            "wire [7:0] request_opcode=m_cq_context[339:324]==7 ? 8'h13 : m_cq_context[339:324]==8 ? 8'h14 : m_cq_context[339:324]==1 ? 8'h0a :")
    if name=='rocev2_wqe_read_unpad':
        t=once(t,'in_op==2 && s_context[619:588]==0 &&',
            '(in_op==2 || in_op==7 || in_op==8) && s_context[619:588]==0 &&\n'
            '    ((in_op==7 || in_op==8) ? (in_length==8 && in_remote[2:0]==0 &&\n'
            '     (in_op!=8 || s_context[683:620]==0)):s_context[747:620]==0) &&')
    # Replace the matched children only within this new opt-in leaf family.
    for child in NAMES:
        t=re.sub(r'\b'+child+r'\b','rocev2_atomic128_'+child.removeprefix('rocev2_'),t)
    return t


def derive():return {RTL/(n+'.v'):leaf(n)for n in NAMES}
