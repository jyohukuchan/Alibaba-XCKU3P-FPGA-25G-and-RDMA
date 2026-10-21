# SPDX-License-Identifier: BSD-2-Clause-Views
"""New private protected multi-packet READ-response leaf, no default change.

One full748-bit WR/placement lease, strict per-packet CRC/peer/QPN/PSN/class/
length/AETH, trusted whole-request MSN, and explicit offset/bytes/last metadata.
The new packet events are NOT whole-WR CQ or DMA-visibility certificates.
Native HLS/executor/lifetime/kernel/provider integration is still required.
"""
import derive_segmented_profile as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
SOURCE=RTL/'rocev2_wqe_response_guard.v'
NAME='rocev2_segmented_read_response_guard'


def derive():
    t=parent.derive()[SOURCE]
    t=once(t,'module rocev2_wqe_response_guard #(','module '+NAME+' #(')
    t=once(t,'// One WR/one <=4096B response is a prototype, not full RC/retry/CQ support.',
        '// Private READ up to1MiB; all original ordinary/zero/Atomic policies remain.\n'
        '// Per-packet response events are NOT whole-WR completion or DMA authority.')
    t=once(t,'    input wire [23:0] s_expect_psn,',
        '    input wire [23:0] s_expect_psn,\n'
        '    // MUST come from trusted issued/common-QP state, never from RX.\n'
        '    input wire [23:0] s_expect_msn,\n'
        '    output wire [31:0] m_read_segment_offset,\n'
        '    output wire [31:0] m_read_segment_bytes,\n'
        '    output wire m_read_segment_last,\n'
        '    output wire m_response_event_has_aeth,')
    t=once(t,'reg downstream_lease=0;',
        'reg downstream_lease=0;\n'
        'reg [31:0] read_offset=0;reg [23:0] read_expected_msn=0;\n'
        'reg read_token_given=0;')
    t=once(t,"wire known=(^{s_expect_context,s_expect_local_ip,s_expect_peer_ip,s_expect_psn})!==1'bx;",
        "wire known=(^{s_expect_context,s_expect_local_ip,s_expect_peer_ip,s_expect_psn})!==1'bx &&\n"
        "    (!(in_op==2 && in_length>4096) || (^s_expect_msn)!==1'bx);")
    t=once(t,'in_length<=((in_op==1 || in_op==3) ? 1048576:4096)',
        'in_length<=((in_op==1 || in_op==2 || in_op==3) ? 1048576:4096)')
    t=once(t,"wire [31:0] padded_length=(length+3)&32'hfffffffc;",r'''
wire [31:0] padded_length=(length+3)&32'hfffffffc;
wire segmented_read=opcode==2 && length>4096;
wire [31:0] read_remaining=length-read_offset;
wire [31:0] segment_bytes=read_remaining>4096 ? 32'd4096:read_remaining;
wire segment_last=read_remaining<=4096;
wire [7:0] required_read_opcode=read_offset==0 ? 8'h0d:segment_last ? 8'h0f:8'h0e;
wire segment_aeth=required_read_opcode!=8'h0e;
wire [31:0] segment_padded=(segment_bytes+3)&32'hfffffffc;
wire [23:0] parsed_msn={header[41*8+:8],header[42*8+:8],header[43*8+:8]};
assign m_read_segment_offset=segmented_read ? read_offset:0;
assign m_read_segment_bytes=segmented_read ? segment_bytes:length;
assign m_read_segment_last=!segmented_read || segment_last;
assign m_response_event_has_aeth=!segmented_read || segment_aeth;
''')
    t=once(t,"wire op_ok=control_packet || parsed_opcode==(atomic_request ? 8'h12 : opcode==2 ? 8'h10 : 8'h11);",
        "wire op_ok=control_packet || parsed_opcode==(atomic_request ? 8'h12 :\n"
        "    segmented_read ? required_read_opcode:opcode==2 ? 8'h10 : 8'h11);")
    t=once(t,"wire syndrome_ok=(header[40*8+:8]&8'he0)==0;",
        "wire syndrome_ok=(segmented_read && parsed_opcode==8'h0e) || (header[40*8+:8]&8'he0)==0;")
    t=once(t,'    atomic_request ? (bytes_received==56 && pad==0) :',
        '    atomic_request ? (bytes_received==56 && pad==0) :\n'
        '    segmented_read ? (bytes_received==(segment_aeth ? 48:44)+segment_padded &&\n'
        '        pad==((-segment_bytes)&3)) :')
    t=once(t,'local_ip<=0;peer_ip<=0;expected_psn<=0;downstream_lease<=0;',
        'local_ip<=0;peer_ip<=0;expected_psn<=0;downstream_lease<=0;\n'
        '        read_offset<=0;read_expected_msn<=0;read_token_given<=0;')
    t=once(t,'words<=0;header<=0;bytes_received<=0;frame_bad<=0;downstream_lease<=0;',
        'words<=0;header<=0;bytes_received<=0;frame_bad<=0;downstream_lease<=0;\n'
        '            read_offset<=0;read_expected_msn<=s_expect_msn;read_token_given<=0;')
    t=once(t,"            else if(!syndrome_ok && !control_packet)m_reject_error<=8'h95;",
        "            else if(!syndrome_ok && !control_packet)m_reject_error<=8'h95;\n"
        "            else if(segmented_read && !control_packet && segment_aeth && parsed_msn!=read_expected_msn)\n"
        "                m_reject_error<=8'h99;")
    t=once(t,'m_response_event_opcode<=parsed_opcode;m_response_event_syndrome<=header[40*8+:8];',
        "m_response_event_opcode<=parsed_opcode;\n"
        "                m_response_event_syndrome<=(segmented_read && !segment_aeth && !control_packet) ? 8'd0:header[40*8+:8];")
    t=once(t,'state<=control_packet ? CONTROL : result_request ? TOKEN : FORWARD;',
        'state<=control_packet ? CONTROL : (result_request && (!segmented_read || !read_token_given)) ? TOKEN : FORWARD;')
    t=once(t,'if(token_transfer)begin downstream_lease<=1;state<=FORWARD;end',
        'if(token_transfer)begin downstream_lease<=1;read_token_given<=1;state<=FORWARD;end')
    t=once(t,'            if(!fault)begin active<=0;downstream_lease<=0;state<=COLLECT;words<=0;header<=0;bytes_received<=0;frame_bad<=0;end',
        '            if(!fault)begin\n'
        '                state<=COLLECT;words<=0;header<=0;bytes_received<=0;frame_bad<=0;\n'
        '                if(segmented_read && !segment_last)begin\n'
        '                    read_offset<=read_offset+segment_bytes;expected_psn<=expected_psn+1\'b1;\n'
        '                    // SAME whole owner and external placement lease remain held.\n'
        '                end else begin active<=0;downstream_lease<=0;read_offset<=0;read_token_given<=0;end\n'
        '            end')
    return t
