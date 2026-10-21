# SPDX-License-Identifier: BSD-2-Clause-Views
"""Coordinated large SEND/Immediate RX source graph, not native qualification.

One real full RQ/MR owner, independently checked packet offsets, genuine
per-packet HLS/backend/ACK-MAC release, a distinct whole HLS output and one
whole CQ/retire. Actual new HLS generation/elaboration/runtime and matched
software are required separately. Old/default/raw protected RTL unchanged.
"""
import derive_segmented_immediate as parent
import derive_receive_message_ack as ack

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
EXTRA=[*parent.EXTRA,RTL/'rocev2_receive_message_queue.v']
RNC_FEATURES=65535;CQC_FEATURES=255;RQC_FEATURES=31
FIELDS=[('output','[775:0]','m_recv_message_data'),('output','','m_recv_message_valid'),
    ('input','','m_recv_message_ready'),('input','[619:0]','s_recv_packet_retire_context'),
    ('input','','s_recv_packet_retire_valid'),('output','','s_recv_packet_retire_ready')]


def ports(t,fields=FIELDS):
    return once(t,'    input wire clk,',''.join('    '+d+' wire '+(w+' 'if w else'')+n+',\n'for d,w,n in fields)+'    input wire clk,')


def route(t):
    return once(t,'.m_recv_core_data(m_recv_core_data),',
        '.m_recv_core_data(m_recv_core_data),\n'+''.join('    .'+n+'('+n+'),\n'for _,_,n in FIELDS))


def protected(t):
    t=ports(t)
    t=once(t,'reg recv_completion_pending=0;',
        'reg recv_completion_pending=0;reg recv_terminal_complete=0;\n'
        'reg recv_group_active=0;reg [619:0] recv_group_context=0;\n'
        'reg [31:0] recv_group_offset=0,recv_packet_offset=0;')
    t=once(t,'s_recv_context[307:276]<=4096','s_recv_context[307:276]<=1048576')
    t=once(t,'(!RECV_CQ_ENABLE || !recv_completion_pending) && !fault && !rst;',
        '(!RECV_CQ_ENABLE || !recv_completion_pending || s_recv_valid) && !fault && !rst;')
    t=once(t,"wire send_wire=RECV_ENABLE && (opcode==8'h04 || opcode==8'h05);",r'''
wire send_first=opcode==8'h00,send_middle=opcode==8'h01;
wire send_last=opcode==8'h02 || opcode==8'h03;
wire send_wire=RECV_ENABLE && (opcode<=8'h05);
wire send_segment=send_first || send_middle || send_last;
wire [31:0] receive_offset=send_first ? 32'd0:send_segment ? recv_group_offset:32'd0;
wire [32:0] receive_end={1'b0,receive_offset}+{1'b0,parsed_length};
wire [64:0] receive_va={1'b0,s_recv_context[243:180]}+{33'd0,receive_offset};
wire receive_sequence_ok=!recv_group_active ? (!send_segment || send_first) :
    send_wire && (send_middle || send_last) && s_recv_context===recv_group_context;
wire receive_extent_ok=!send_segment ||
    (parsed_length!=0 && receive_end<=1048576 && receive_end<={1'b0,s_recv_context[307:276]} &&
     ((send_first || send_middle) ? parsed_length==4096 && pad==0 &&
        receive_end<{1'b0,s_recv_context[307:276]} : 1'b1));
''')
    t=once(t,"wire [31:0] send_header_bytes=opcode==8'h05 ? 48:44;",
        "wire [31:0] send_header_bytes=(opcode==8'h05 || opcode==8'h03) ? 48:44;")
    t=once(t,'|| parsed_length>4096) begin',
        '|| parsed_length>4096 || (send_segment &&\n'
        '                        ((send_first || send_middle) ? parsed_length!=4096 || pad!=0 : parsed_length==0))) begin')
    t=once(t,'else if(receive_wire && (!recv_context_ok || (send_wire && parsed_length>s_recv_context[307:276])))',
        'else if(receive_wire && (!recv_context_ok || !receive_sequence_ok || !receive_extent_ok ||\n'
        '                        (send_wire && (receive_end>{1\'b0,s_recv_context[307:276]} || receive_va>65\'hffffffffffffffff))))')
    # Any different request during a SEND group is a protocol error, not an
    # opportunity to issue legacy WRITE/READ/notification memory commands.
    t=once(t,'else if(zero_service_wire && !zero_context_ok)m_reject_error<=ERR_QP;',
        'else if((send_segment && !recv_group_active && !send_first) ||\n'
        '                        (recv_group_active && (!send_wire || !receive_sequence_ok || !receive_extent_ok)))m_reject_error<=ERR_FORMAT;\n'
        '                    else if(zero_service_wire && !zero_context_ok)m_reject_error<=ERR_QP;')
    t=once(t,"recv_notification<=opcode==8'h05 ? be32(header,40) : opcode==8'h0b ? be32(header,56) : 0;",
        "recv_notification<=(opcode==8'h05 || opcode==8'h03) ? be32(header,40) : opcode==8'h0b ? be32(header,56) : 0;")
    t=once(t,"recv_notification_flags<=opcode==8'h05 ? 1 : opcode==8'h0b ? 3 : 0;",
        "recv_notification_flags<=send_first ? 4:send_middle ? 8:send_last ? (opcode==8'h03 ? 17:16):opcode==8'h05 ? 1:opcode==8'h0b ? 3:0;\n"
        '                        recv_packet_offset<=receive_offset;')
    t=once(t,'request_va<=s_recv_context[243:180];request_key<=s_recv_context[275:244];',
        'request_va<=receive_va[63:0];request_key<=s_recv_context[275:244];')
    t=once(t,"wire [95:0] recv_expected_command={2'd0,local_qpn[9:0],4'd0,1'b0,1'b0,1'b0,1'b1,wire_length[27:0],48'd0};",r'''
wire recv_packet_terminal=recv_notification_flags==0 || recv_notification_flags==1 || recv_notification_flags==3 ||
    recv_notification_flags==16 || recv_notification_flags==17;
wire [95:0] recv_expected_command={2'd0,local_qpn[9:0],4'd0,1'b0,1'b0,1'b0,recv_packet_terminal,
    wire_length[27:0],16'd0,recv_packet_offset};
''')
    t=once(t,'m_recv_placement_context<=recv_context;',r'''
                        if(recv_notification_flags==4 || recv_notification_flags==8)begin
                            recv_group_active<=1;recv_group_context<=recv_context;
                            recv_group_offset<=recv_packet_offset+request_length;
                        end else if(recv_notification_flags==16 || recv_notification_flags==17)begin
                            recv_group_active<=0;recv_group_offset<=0;
                        end
                        m_recv_placement_context<=recv_context;''')
    t=once(t,'if(RECV_CQ_ENABLE && s_recv_retire_valid && s_recv_retire_ready)recv_completion_pending<=0;',r'''
        if(RECV_CQ_ENABLE && s_recv_retire_valid && s_recv_retire_ready)begin
            recv_completion_pending<=0;recv_terminal_complete<=0;
        end
        if(s_recv_packet_retire_valid && s_recv_packet_retire_ready && recv_packet_terminal)recv_terminal_complete<=1;''')
    t=once(t,'recv_operation<=0;recv_completion_pending<=0;recv_context<=0;',
        'recv_operation<=0;recv_completion_pending<=0;recv_context<=0;recv_terminal_complete<=0;\n'
        '        recv_group_active<=0;recv_group_context<=0;recv_group_offset<=0;recv_packet_offset<=0;')
    t=once(t,'.s_recv_retire_context(s_recv_retire_context),.s_recv_retire_valid(s_recv_retire_valid),.s_recv_retire_ready(s_recv_retire_ready),',
        '.s_recv_retire_context(s_recv_packet_retire_context),.s_recv_retire_valid(s_recv_packet_retire_valid),.s_recv_retire_ready(s_recv_packet_retire_ready),\n'
        '    .m_recv_message_data(m_recv_message_data),.m_recv_message_valid(m_recv_message_valid),.m_recv_message_ready(m_recv_message_ready),')
    t=once(t,'assign s_recv_ready=RECV_ENABLE',r'''
assign s_recv_retire_ready=RECV_CQ_ENABLE && recv_completion_pending && recv_terminal_complete &&
    s_recv_retire_context===recv_context && state==COLLECT && word_count==0 && !lease &&
    !m_recv_placement_valid && !fault && !rst;
assign s_recv_ready=RECV_ENABLE''')
    return t


def shared(t):
    t=ports(t,FIELDS[:3])
    t=once(t,'reg recv_held=0,recv_proved=0;',
        'reg recv_held=0,recv_proved=0,recv_message_seen=0,recv_terminal=0;reg [751:0] recv_core_receipt=0;')
    t=once(t,'wire core_recv_owner_ready,core_recv_fault,core_recv_done_valid;',r'''
wire core_recv_owner_ready,core_recv_fault,core_recv_done_valid;
wire [775:0] core_recv_message_data;wire core_recv_message_valid,core_recv_message_ready;
wire recv_message_basic=(^core_recv_message_data)!==1'bx && recv_held &&
    core_recv_message_data[619:0]===recv_owner[619:0] && core_recv_message_data[775:764]==0;
wire recv_message_shape=recv_message_basic && recv_terminal &&
    core_recv_message_data[699:676]==recv_owner[675:652] &&
    core_recv_message_data[723:700]==recv_core_receipt[703:680] &&
    core_recv_message_data[755:724]==recv_core_receipt[735:704] &&
    core_recv_message_data[763:756]==(recv_core_receipt[743:736]&8'h03);
wire bad_recv_message=core_recv_message_valid && (!recv_message_basic || recv_message_seen ||
    (recv_proved && !recv_message_shape));
assign m_recv_message_data=core_recv_message_data;
assign m_recv_message_valid=core_recv_message_valid && recv_proved && recv_message_shape && !fault && !rst;
assign core_recv_message_ready=m_recv_message_ready && recv_proved && recv_message_shape && !fault && !rst;
''')
    t=once(t,'wire incoming_fault=atomic_unowned_offer ||routing_fault',
        'wire incoming_fault=bad_recv_message || atomic_unowned_offer ||routing_fault')
    t=once(t,'s_recv_retire_context===recv_owner[619:0] && remote_operation_idle===1\'b1 &&',
        's_recv_retire_context===recv_owner[619:0] && (!recv_terminal || recv_message_seen) && remote_operation_idle===1\'b1 &&')
    t=once(t,'.m_recv_done_tvalid(core_recv_done_valid),',
        '.m_recv_message_data(core_recv_message_data),.m_recv_message_valid(core_recv_message_valid),.m_recv_message_ready(core_recv_message_ready),\n'
        '.m_recv_done_tvalid(core_recv_done_valid),')
    t=once(t,'recv_held<=0;recv_proved<=0;recv_owner<=0;request_proved<=0;',
        'recv_held<=0;recv_proved<=0;recv_owner<=0;recv_message_seen<=0;recv_terminal<=0;recv_core_receipt<=0;request_proved<=0;')
    t=once(t,'recv_held<=1;recv_proved<=0;recv_owner<=s_recv_owner_tdata;',
        'recv_held<=1;recv_proved<=0;recv_owner<=s_recv_owner_tdata;recv_message_seen<=0;recv_terminal<=0;recv_core_receipt<=0;')
    t=once(t,'            end else recv_proved<=1;',r'''
            end else begin
                recv_proved<=1;recv_core_receipt<=m_recv_done_tdata;
                recv_terminal<=m_recv_done_tdata[743:736]==0 || m_recv_done_tdata[743:736]==1 ||
                    m_recv_done_tdata[743:736]==3 || m_recv_done_tdata[743:736]==16 || m_recv_done_tdata[743:736]==17;
            end''')
    t=once(t,'recv_held<=0;recv_proved<=0;recv_owner<=0;\n        end',
        'recv_held<=0;recv_proved<=0;recv_owner<=0;recv_message_seen<=0;recv_terminal<=0;recv_core_receipt<=0;\n        end\n'
        '        if(m_recv_message_valid && m_recv_message_ready)recv_message_seen<=1;')
    return t


def native(t):
    t=once(t,'wire rq_ticket_valid,rq_ticket_ready,rq_commit_ready,rq_retire_ready;',r'''
wire rq_ticket_valid,rq_ticket_ready,rq_commit_ready,rq_retire_ready;
wire [775:0] rq_message_data;wire rq_message_valid,rq_message_ready;
wire [619:0] rq_packet_retire_context;wire rq_packet_retire_valid,rq_packet_retire_ready;
wire recv_packet_hls_retire_ready;
assign rq_packet_retire_ready=recv_ack_retire_ready && recv_packet_hls_retire_ready;
''')
    t=once(t,'rq_retire_ready && recv_ack_retire_ready && recv_hls_retire_ready :',
        'rq_retire_ready && recv_hls_retire_ready :')
    t=once(t,'assign recv_ack_retire_valid=cq_retire_valid && receive_retire && rq_retire_ready && recv_hls_retire_ready;',
        'assign recv_ack_retire_valid=rq_packet_retire_valid && recv_packet_hls_retire_ready;')
    t=once(t,'assign recv_hls_retire_valid=cq_retire_valid && receive_retire && rq_retire_ready && recv_ack_retire_ready;',
        'assign recv_hls_retire_valid=cq_retire_valid && receive_retire && rq_retire_ready;')
    t=once(t,'.s_recv_retire_context(cq_retire_context[619:0]),',r'''
    .m_recv_message_data(rq_message_data),.m_recv_message_valid(rq_message_valid),.m_recv_message_ready(rq_message_ready),
    .s_recv_packet_retire_context(rq_packet_retire_context),
    .s_recv_packet_retire_valid(rq_packet_retire_valid && recv_ack_retire_ready),.s_recv_packet_retire_ready(recv_packet_hls_retire_ready),
    .s_recv_retire_context(cq_retire_context[619:0]),''')
    t=once(t,'rocev2_receive_queue #(', 'rocev2_receive_message_queue #(')
    t=once(t,'    .s_placement_context(rq_placement_context),',r'''
    .s_message_data(rq_message_data),.s_message_valid(rq_message_valid),.s_message_ready(rq_message_ready),
    .m_packet_retire_context(rq_packet_retire_context),.m_packet_retire_valid(rq_packet_retire_valid),.m_packet_retire_ready(rq_packet_retire_ready),
    .s_placement_context(rq_placement_context),''')
    t=once(t,'.s_retire_valid(cq_retire_valid && receive_retire && recv_ack_retire_ready && recv_hls_retire_ready)',
        '.s_retire_valid(cq_retire_valid && receive_retire && recv_hls_retire_ready)')
    t=once(t,'.s_retire_context(cq_retire_context[619:0]),.s_retire_valid(recv_ack_retire_valid)',
        '.s_retire_context(rq_packet_retire_context),.s_retire_valid(recv_ack_retire_valid)')
    return t


def derive():
    out=parent.derive()
    for name in ['rocev2_native_sq_endpoint','rocev2_native_endpoint','rocev2_dual_ethernet_endpoint',
                 'rocev2_controlled_responder','rocev2_paged_responder']:
        p=RTL/(name+'.v');out[p]=route(ports(out[p]))
    p=RTL/'rocev2_native_rnic_endpoint.v';out[p]=native(out[p])
    p=RTL/'rocev2_protected_responder.v';out[p]=protected(out[p])
    p=RTL/'rocev2_shared_hls_transport.v';out[p]=shared(out[p])
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v';t=ports(out[p],FIELDS[:3])
    t=once(t,'rocev2_native_segmented_immediate_top transport (','rocev2_native_segmented_receive_top transport (')
    out[p]=once(t,'    .m_axis_recv_done_TDATA(m_recv_done_tdata),',
        '    .m_axis_recv_message_TDATA(m_recv_message_data),.m_axis_recv_message_TVALID(m_recv_message_valid),.m_axis_recv_message_TREADY(m_recv_message_ready),\n'
        '    .m_axis_recv_done_TDATA(m_recv_done_tdata),')
    out[ack.ACK]=ack.derive()
    # The distinct cohort admits whole posted RQ capacity via the SAME full
    # MR checker. No physical placement authority is added to raw HLS ports.
    for name,op in [('rocev2_wqe_admission.v','opcode'),('rocev2_wqe_hls_sq.v','in_opcode'),('rocev2_cq_mmio.v','incoming_opcode')]:
        p=RTL/name;out[p]=once(out[p],op+'==3 || '+op+'==5 || '+op+'==6) ? 1048576:4096)',
            op+'==3 || '+op+'==4 || '+op+'==5 || '+op+'==6) ? 1048576:4096)')
    p=RTL/'rocev2_cq_mmio.v';out[p]=once(out[p],'s_ticket_received_bytes<=4096','s_ticket_received_bytes<=1048576')
    out[p]=once(out[p],'8:rd=127; // private matched large READ/Immediate owner/codec profile',
        '8:rd=255; // separate large SEND receive cohort, source only until qualified')
    p=RTL/'rocev2_control_regs.v';out[p]=once(out[p],'| 8192 | 16384; // distinct private large READ/Immediate identity',
        '| 8192 | 16384 | 32768; // distinct private large SEND receive identity')
    p=RTL/'rocev2_sq_control_regs.v';out[p]=once(out[p],"8:rd=(RECV_CANCEL_ENABLE ? 32'h3:32'h1) | 32'hc;",
        "8:rd=(RECV_CANCEL_ENABLE ? 32'h13:32'h1) | 32'hc;")
    return out
