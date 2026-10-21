# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private protected segmented RX and whole-READ lifetime/PSN/cache joins.

One whole READ request, one placement lease, every FIRST/MIDDLE/LAST event,
final HLS ACK/common-state receipt and genuine MAC/cache/CQ joins. No default
or large READ admission change; native runtime/recovery/timing still required.
"""
import derive_expected_remote_msn_native as parent
import derive_segmented_read_response as response
import derive_segmented_wire as wire

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA
helpers=wire.helpers


def read_limit(t,length,op):
    return once(t,length+'<=(('+op+'==1 || '+op+'==3) ? 1048576:4096)',
        length+'<=(('+op+'==1 || '+op+'==2 || '+op+'==3) ? 1048576:4096)')


def lifetime(t):
    t=read_limit(t,'in_length','in_op')
    t=once(t,'wire segmented=(opcode==1 || opcode==3) && length>4096;',r'''
wire segmented_read=opcode==2 && length>4096;
reg [8:0] read_response_index=0;
wire [8:0] read_response_span=(length+32'd4095)>>12;
wire read_response_last=read_response_index+1'b1==read_response_span;
wire [23:0] response_psn=segmented_read ? m_expect_psn+read_response_index:m_expect_psn;
wire [23:0] final_ack_psn=segmented_read ? m_expect_psn+read_response_span-24'd1:m_expect_psn;
wire [7:0] read_response_opcode=read_response_index==0 ? 8'h0d:read_response_last ? 8'h0f:8'h0e;
wire segmented=(opcode==1 || opcode==3) && length>4096;''')
    t=once(t,'s_response_context==owner && s_response_psn==m_expect_psn &&',
        's_response_context==owner && s_response_psn==response_psn &&')
    t=once(t,"s_response_opcode==(atomic_request ? 8'h12 : opcode==2 ? 8'h10 : 8'h11)",
        "s_response_opcode==(atomic_request ? 8'h12 : segmented_read ? read_response_opcode:opcode==2 ? 8'h10 : 8'h11)")
    t=once(t,"s_hls_ack=={5'd0,m_expect_psn,qpn[9:0],(!result_request)}",
        "s_hls_ack=={5'd0,final_ack_psn,qpn[9:0],(!result_request)}")
    old='packet_index<=0;first_psn<=0;advance_pending<=0;'
    if t.count(old)!=2:raise ValueError('both reset and genuine owner capture must reset READ response index')
    t=t.replace(old,'read_response_index<=0;'+old)
    t=once(t,'if(s_response_valid && s_response_ready)response_seen<=1;',r'''
if(s_response_valid && s_response_ready)begin
            if(segmented_read && !read_response_last)read_response_index<=read_response_index+1'b1;
            else response_seen<=1;
        end''')
    return t


def tx_lifetime(t):
    t=once(t,'(m_cq_context[339:324]==1 || m_cq_context[339:324]==3) && whole_length>4096',
        '(m_cq_context[339:324]==1 || m_cq_context[339:324]==2 || m_cq_context[339:324]==3) && whole_length>4096')
    t=once(t,"s_request_done_data[795:772]==(m_expect_psn+24'd1)",
        "s_request_done_data[795:772]==(m_cq_context[339:324]==2 ?\n"
        "        m_expect_psn+whole_packet_span:m_expect_psn+24'd1)")
    # FIRST/MIDDLE prove packet progress, not positive completion of the
    # retained outbound READ request. Only the validated LAST can ACK cache.
    t=once(t,'.s_positive_valid(s_response_valid && s_response_ready)',
        ".s_positive_valid(s_response_valid && s_response_ready &&\n"
        "        (m_cq_context[339:324]!=2 || whole_length<=4096 || s_response_opcode==8'h0f))")
    return t


def derive():
    out=parent.derive()
    p=RTL/'rocev2_wqe_lifetime.v';out[p]=lifetime(out[p])
    p=RTL/'rocev2_wqe_tx_lifetime.v';out[p]=tx_lifetime(out[p])
    p=RTL/'rocev2_wqe_mac_tx.v';out[p]=read_limit(out[p],'in_length','in_op')
    p=RTL/'rocev2_shared_hls_transport.v';t=read_limit(out[p],'length','opcode')
    out[p]=once(t,'(owner[339:324]==1 || owner[339:324]==3) && request_length>4096',
        '(owner[339:324]==1 || owner[339:324]==2 || owner[339:324]==3) && request_length>4096')
    p=RTL/'rocev2_wqe_response_guard.v';out[p]=response.derive()
    p=RTL/'rocev2_native_rnic_endpoint.v';t=out[p]
    t=once(t,'rocev2_wqe_response_guard #(',response.NAME+' #(')
    t=once(t,'.s_expect_psn(tx_m_expect_psn),',
        '.s_expect_psn(tx_m_expect_psn),\n    .s_expect_msn(expected_remote_msn),\n'
        '    .m_read_segment_offset(),.m_read_segment_bytes(),.m_read_segment_last(),.m_response_event_has_aeth(),')
    out[p]=t
    return out
