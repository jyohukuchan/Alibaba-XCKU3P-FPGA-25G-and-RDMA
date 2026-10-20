# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked128-byte WQE/MR admission and immutable Atomic requester staging.

Default/proven64-byte sources are unchanged. Replace the original hierarchy
in a future MATCHED128-byte profile, never add another MR/QP namespace.
Owner748 = original Immediate620 + compare64 + swap/add64; SQ408 retains
the complete lower280-bit ABI. This stage is NOT the actual HLS Atomic
requester/ACK/result/replay/CQ/kernel/provider implementation.
"""
import derive_atomic128_fetch as fetch

ROOT=fetch.ROOT;RTL=fetch.RTL;once=fetch.once
WQE=RTL/'rocev2_wqe_admission.v';SQ=RTL/'rocev2_sq_wqe_admission.v';HLS=RTL/'rocev2_wqe_hls_sq.v'


def operand_ports(t):
    return once(t,'    output wire [31:0] m_work_immediate,',
        '    output wire [31:0] m_work_immediate,\n'
        '    output wire [63:0] m_work_compare,\n'
        '    output wire [63:0] m_work_swap_add,')


def wqe(t):
    t=once(t,'module rocev2_wqe_admission #(','module rocev2_atomic128_wqe_admission #(')
    t=once(t,'input wire [511:0] s_wqe_data,','input wire [1023:0] s_wqe_data,')
    t=once(t,'input wire [63:0] s_wqe_keep,','input wire [127:0] s_wqe_keep,')
    t=once(t,'reg [511:0] record=0;','reg [1023:0] record=0;')
    t=once(t,'reg [63:0] record_keep=0;','reg [127:0] record_keep=0;')
    t=operand_ports(t)
    t=once(t,'wire immediate_opcode=opcode==5 || opcode==6;',
        'wire immediate_opcode=opcode==5 || opcode==6;\nwire atomic_opcode=opcode==7 || opcode==8;\n'
        "wire record_known=(^record)!==1'bx;\n"
        "wire trusted_known=(^{context_valid,qpn,pd,tag,expected_sequence,epoch})!==1'bx;")
    t=once(t,"wire shape_ok=record_keep==64'hffffffffffffffff && record_last && record[447:416]==0 &&",
        "wire shape_ok=record_known && record_keep==128'hffffffffffffffffffffffffffffffff && record_last &&\n"
        "    record[1023:640]==0 && (atomic_opcode ? (opcode!=8 || record[575:512]==0):record[639:512]==0) &&\n"
        "    record[447:416]==0 &&")
    t=once(t,'wire context_ok=context_valid && qpn<MAX_QPS && expected_sequence!=0 && epoch!=0;',
        'wire context_ok=trusted_known && context_valid && qpn<MAX_QPS && tag!=0 && expected_sequence!=0 && epoch!=0;')
    t=once(t,'    opcode==1 || opcode==2 || (SEND_ENABLE && opcode==3)',
        '    atomic_opcode || opcode==1 || opcode==2 || (SEND_ENABLE && opcode==3)')
    t=once(t,'wire length_ok=length!=0 && length<=4096;',
        "wire length_ok=atomic_opcode ? length==8:length!=0 && length<=4096;\n"
        "wire address_ok=!atomic_opcode || record[194:192]==0;")
    t=once(t,"assign m_mr_request_operation=(opcode==2 || opcode==4) ? 3'd1 : 3'd0;",
        "assign m_mr_request_operation=(atomic_opcode || opcode==2 || opcode==4) ? 3'd1 : 3'd0;")
    t=once(t,'assign m_work_immediate=error==0 && IMMEDIATE_ENABLE ? record[415:384] : 32\'d0;',
        'assign m_work_immediate=error==0 && IMMEDIATE_ENABLE ? record[415:384] : 32\'d0;\n'
        "assign m_work_compare=error==0 && atomic_opcode ? record[575:512]:64'd0;\n"
        "assign m_work_swap_add=error==0 && atomic_opcode ? record[639:576]:64'd0;")
    t=once(t,"case({local_last[64],remote_last[64]})\n        2'b00: state<=QUERY;",
        "case({local_last[64],remote_last[64],address_ok})\n        3'b001: state<=QUERY;")
    return t


def sq(t):
    t=once(t,'module rocev2_sq_wqe_admission #(','module rocev2_atomic128_sq_wqe_admission #(')
    t=once(t,'input wire [511:0] s_fetch_data,','input wire [1023:0] s_fetch_data,')
    t=operand_ports(t)
    t=once(t,'wire [31:0] frontend_immediate;',
        'wire [31:0] frontend_immediate;\nwire [63:0] frontend_compare,frontend_swap_add;')
    t=once(t,"assign m_work_immediate=m_work_authorized ? frontend_immediate : 32'd0;",
        "assign m_work_immediate=m_work_authorized ? frontend_immediate : 32'd0;\n"
        "assign m_work_compare=m_work_authorized ? frontend_compare:64'd0;\n"
        "assign m_work_swap_add=m_work_authorized ? frontend_swap_add:64'd0;")
    t=once(t,'rocev2_wqe_admission #(','rocev2_atomic128_wqe_admission #(')
    t=once(t,".s_wqe_keep(data_known ? 64'hffffffffffffffff : 64'd0),",
        ".s_wqe_keep(data_known ? 128'hffffffffffffffffffffffffffffffff : 128'd0),")
    t=once(t,'.m_work_immediate(frontend_immediate),',
        '.m_work_immediate(frontend_immediate),.m_work_compare(frontend_compare),.m_work_swap_add(frontend_swap_add),')
    return t


def hls(t):
    t=once(t,'module rocev2_wqe_hls_sq #(','module rocev2_atomic128_wqe_hls_sq #(')
    t=t.replace('[587+32*IMMEDIATE_ENABLE:0]','[747:0]').replace('[247+32*IMMEDIATE_ENABLE:0]','[407:0]')
    t=once(t,'wire [31:0] in_immediate=s_work_context>>588;',
        'wire [31:0] in_immediate=s_work_context[619:588];\n'
        'wire [63:0] in_compare=s_work_context[683:620],in_swap_add=s_work_context[747:684];\n'
        'wire in_atomic=in_opcode==7 || in_opcode==8;')
    t=once(t,'wire [31:0] immediate=m_owner_context>>588;',
        'wire [31:0] immediate=m_owner_context[619:588];\n'
        'wire [63:0] compare=m_owner_context[683:620],swap_add=m_owner_context[747:684];')
    t=once(t,'(IMMEDIATE_ENABLE && in_opcode==6)) &&',
        '(IMMEDIATE_ENABLE && in_opcode==6) || in_atomic) &&\n'
        '    (in_atomic ? (in_length==8 && in_remote_address[2:0]==0 && (in_opcode!=8 || in_compare==0)):\n'
        '     (in_compare==0 && in_swap_add==0)) &&')
    t=once(t,'{in_opcode,in_flags,in_length,in_local_key,in_local_address,in_local_offset,in_remote_address,in_remote_key,in_immediate}==0;',
        '{in_opcode,in_flags,in_length,in_local_key,in_local_address,in_local_offset,in_remote_address,in_remote_key,in_immediate,in_compare,in_swap_add}==0;')
    t=once(t,"wire [31:0] wire_opcode=opcode==1 ? 32'd10 :",
        "wire [31:0] wire_opcode=opcode==7 ? 32'd19 : opcode==8 ? 32'd20 : opcode==1 ? 32'd10 :")
    t=once(t,"assign m_axis_sq_tdata=IMMEDIATE_ENABLE ? {7'd0,immediate,sq_payload} : {7'd0,sq_payload};",
        "assign m_axis_sq_tdata={swap_add,compare,7'd0,immediate,sq_payload};")
    return t


def derive():
    return {WQE:wqe(WQE.read_text()),SQ:sq(SQ.read_text()),HLS:hls(HLS.read_text())}
