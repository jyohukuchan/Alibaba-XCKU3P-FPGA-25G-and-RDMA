# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual existing protected memory executor extended to Atomic8-byte results.

Full748-bit immutable owner/placement identity, SAME full local key/MR offset
and protected backend contract. READ/CAS/FADD are result writes, not source
reads. Raw96-bit commands still require exact post-origin-router metadata;
no physical address is accepted from HLS. Real native parent/MR/PTE/backend/
DMA visibility/CQ/provider binding is required beyond this component.
"""
import derive_atomic128_response as geometry

ROOT=geometry.ROOT;RTL=geometry.RTL;SOURCE=RTL/'rocev2_wqe_memory_executor.v'
once=geometry.once


def derive():
    t=geometry.base.leaf('rocev2_wqe_memory_executor',SOURCE.read_text())
    t=once(t,'module rocev2_wqe_memory_executor #(','module rocev2_atomic128_wqe_memory_executor #(')
    if t.count('[619:0]')!=3:raise ValueError('memory executor owner geometry changed')
    t=t.replace('[619:0]','[747:0]')
    t=once(t,'wire good_work=in_error==0 &&',
        'wire in_atomic=in_opcode==7 || in_opcode==8;\n'
        'wire operands_ok=in_atomic ? (in_length==8 && in_remote[2:0]==0 &&\n'
        '    (in_opcode!=8 || s_owner_context[683:620]==0)) : s_owner_context[747:620]==0;\n'
        'wire good_work=operands_ok && in_error==0 &&')
    t=once(t,'(in_opcode==1 || in_opcode==2 || in_opcode==6 || ((in_opcode==3 || in_opcode==5) && in_remote==0 && in_rkey==0))',
        '(in_atomic || in_opcode==1 || in_opcode==2 || in_opcode==6 || ((in_opcode==3 || in_opcode==5) && in_remote==0 && in_rkey==0))')
    t=once(t,'wire denied_work=in_error!=0 && !in_authorized && s_owner_context[619:588]==0 &&',
        'wire denied_work=in_error!=0 && !in_authorized && s_owner_context[747:588]==0 &&')
    return once(t,'wire placement=opcode==2;','wire placement=opcode==2 || opcode==7 || opcode==8;')
