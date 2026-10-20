# SPDX-License-Identifier: BSD-2-Clause-Views
"""Coordinated opt-in full-WR segmentation in the actual private native graph.

True FIRST/MIDDLE/LAST, whole-message RETH, per-packet PSN/RX/HLS-ACK/MAC
joins and explicit replay-cache ownership advance, never child WRITE_ONLY
verbs or fake CQ retirement. Defaults and bounded source-DMA child unchanged.
Not selected/qualified until component, actual HLS/native and timing gates.
"""
import derive_segmented_executor as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA
helpers=parent.parent.helpers


def limit(t,length,opcode):
    return once(t,length+'<=4096',length+'<=(('+opcode+'==1 || '+opcode+'==3) ? 1048576:4096)')


LIFE_PORTS=[('input','','packet_drained'),('output','','packet_fault_pending'),
    ('output','[23:0]','m_first_psn'),('output','[8:0]','m_packet_index'),
    ('output','[747:0]','m_packet_advance_context'),('output','[23:0]','m_packet_advance_psn'),
    ('output','','m_packet_advance_valid'),('input','','m_packet_advance_ready')]

LIFE_STATE=r'''
reg [8:0] packet_index=0;
reg [23:0] first_psn=0;
reg advance_pending=0;
wire segmented=(opcode==1 || opcode==3) && length>4096;
wire [31:0] packet_offset={11'd0,packet_index,12'd0};
wire [31:0] packet_bytes=segmented ? (length-packet_offset>4096 ? 4096:length-packet_offset):length;
wire packet_first=packet_index==0;
wire packet_last=!segmented || packet_offset+packet_bytes==length;
wire [23:0] consecutive_psn=first_psn+packet_index;
assign m_first_psn=first_psn;assign m_packet_index=packet_index;
assign m_packet_advance_context=owner;assign m_packet_advance_psn=m_expect_psn;
// Persistent identity-bound offer; a later fault cannot retract it or free WR.
assign m_packet_advance_valid=advance_pending && !rst;
assign packet_fault_pending=fault || incoming_fault;
wire bad_packet_release=advance_pending && packet_drained!==1'b1;
'''


def lifetime(t):
    t=limit(t,'in_length','in_op');t=helpers.add_ports(t,LIFE_PORTS)
    t=once(t,'wire [31:0] padded=(length+3)&32\'hfffffffc;',
        LIFE_STATE+"\nwire [31:0] padded=(packet_bytes+3)&32'hfffffffc;")
    t=once(t,'wire [7:0] request_wire_opcode=',
        "wire [7:0] segmented_wire_opcode=opcode==3 ? (packet_first ? 8'h00:packet_last ? 8'h02:8'h01):\n"
        "    (packet_first ? 8'h06:packet_last ? 8'h08:8'h07);\n"
        'wire [7:0] request_wire_opcode=segmented ? segmented_wire_opcode:')
    t=once(t,'wire [31:0] request_header_bytes=',
        'wire [31:0] request_header_bytes=segmented ? ((opcode==1 && packet_first) ? 60:44):')
    t=once(t,'((-length)&3)','((-packet_bytes)&3)')
    t=once(t,'tx_qpn==peer_qpn &&',
        'tx_qpn==peer_qpn && (!segmented || (header[36*8+7] && (packet_first || tx_psn==consecutive_psn))) &&')
    t=once(t,'(send_request || (be64(header,40)==remote_address',
        '((segmented && !packet_first) || send_request || (be64(header,40)==remote_address')
    t=once(t,'(s_tx_valid && (!active || issue_seen || tx_check))',
        '(s_tx_valid && (!active || ((issue_seen || tx_check || advance_pending) && (!segmented || s_tx_ready))))')
    t=once(t,'wire incoming_fault=bad_owner ||',
        'wire incoming_fault=bad_packet_release || bad_owner ||')
    # Per-packet MAC/cache drain is distinct from full HLS/WR transport drain.
    # Never substitute this for the unchanged final CQ/commit drain gates.
    t=once(t,'if(active && issue_seen && expect_sent && memory_seen && response_seen && ack_seen && mac_seen &&',
        'if(active && packet_last && issue_seen && expect_sent && memory_seen && response_seen && ack_seen && mac_seen &&')
    t=once(t,'    if(rst)begin\n        owner<=0;',
        '    if(rst)begin\n        packet_index<=0;first_psn<=0;advance_pending<=0;\n        owner<=0;')
    t=once(t,'            owner<=s_owner_context;local_ip<=s_owner_local_ip;',
        '            packet_index<=0;first_psn<=0;advance_pending<=0;\n'
        '            owner<=s_owner_context;local_ip<=s_owner_local_ip;')
    t=once(t,'else begin issue_seen<=1;m_expect_psn<=tx_psn;',
        'else begin if(packet_first)first_psn<=tx_psn;issue_seen<=1;m_expect_psn<=tx_psn;')
    t=once(t,'        // Persistent prepared ticket is NOT a CQE or permission to unpin.',r'''
        if(active && segmented && !packet_last && issue_seen && expect_sent && response_seen && ack_seen && mac_seen &&
           packet_drained===1'b1 && !advance_pending && !fault && !incoming_fault)advance_pending<=1;
        if(advance_pending && m_packet_advance_ready && !fault && !incoming_fault)begin
            packet_index<=packet_index+1'b1;advance_pending<=0;
            issue_seen<=0;expect_sent<=0;response_seen<=0;ack_seen<=0;mac_seen<=0;
            header<=0;tx_words<=0;tx_bytes<=0;tx_check<=0;tx_bad<=0;
        end
        // Persistent prepared ticket is NOT a CQE or permission to unpin.''')
    return once(t,'            if(bad_owner)begin fault<=1;',
        "            if(bad_packet_release)begin fault<=1;fault_code<=8'hb8;end\n"
        '            if(bad_owner)begin fault<=1;')


REPLAY_PORTS=[('input','','packet_parent_fault'),('input','[747:0]','s_packet_advance_context'),
    ('input','[23:0]','s_packet_advance_psn'),('input','[8:0]','s_packet_advance_index'),
    ('input','','s_packet_advance_valid'),('output','','s_packet_advance_ready')]

REPLAY_ADVANCE=r'''
reg [8:0] packet_index=0;
wire segmented=(owner[339:324]==1 || owner[339:324]==3) && owner[307:276]>4096;
wire [31:0] packet_end=({23'd0,packet_index}+1'b1)<<12;
wire advance_identity=(^{s_packet_advance_context,s_packet_advance_psn,s_packet_advance_index,issued_psn})!==1'bx &&
    active && segmented && s_packet_advance_context==owner &&
    s_packet_advance_psn==issued_psn && s_packet_advance_index==packet_index && packet_end<owner[307:276];
wire bad_advance=(s_packet_advance_valid!==1'b0 && s_packet_advance_valid!==1'b1) ||
    (s_packet_advance_valid && !advance_identity);
assign s_packet_advance_ready=advance_identity && state==HOLD && acked && done_sent && !m_done_valid &&
    !m_axis_ip_tvalid && !fault && !failed && !bad_advance && packet_parent_fault===1'b0 && !rst;
'''


def replay(t):
    t=helpers.add_ports(t,REPLAY_PORTS)
    t=once(t,'HOLD=5,FAILED=6;','HOLD=5,FAILED=6,NEXTOWNER=7;')
    t=once(t,'reg [2:0] state=CAPTURE;', 'reg [2:0] state=CAPTURE;\n'+REPLAY_ADVANCE)
    t=once(t,'state==REOWNER && !rst','(state==REOWNER || state==NEXTOWNER) && !rst')
    t=once(t,'        active<=0;acked<=0;done_sent<=0;','        packet_index<=0;active<=0;acked<=0;done_sent<=0;')
    t=once(t,'            active<=1;owner<=s_owner_context;',
        '            packet_index<=0;active<=1;owner<=s_owner_context;')
    t=once(t,'if(m_replay_valid && m_replay_ready)begin state<=SEND;send_index<=0;retry_kind<=0;end',
        'if(m_replay_valid && m_replay_ready)begin state<=state==NEXTOWNER ? CAPTURE:SEND;send_index<=0;retry_kind<=0;end')
    t=once(t,'        if(s_retire_valid)begin',r'''
        if(s_packet_advance_valid && s_packet_advance_ready)begin
            packet_index<=packet_index+1'b1;words<=0;bytes<=0;send_index<=0;
            acked<=0;done_sent<=0;send_committed<=0;deadline_enabled<=0;retry_kind<=0;state<=NEXTOWNER;
            // ACK resets retry counters (behavioral reference, not copied code):
            // https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_comp.c
            retries_left<=policy_retry[held_qpn[2:0]];rnr_left<=policy_rnr[held_qpn[2:0]];
        end
        if(bad_advance || packet_parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd4;end
        if(s_retire_valid)begin''')
    return t


def tx_lifetime(t):
    t=once(t,'wire life_owner_ready,',
        'wire [747:0] packet_advance_context;wire [23:0] packet_advance_psn,whole_first_psn;\n'
        'wire [8:0] packet_index;wire packet_advance_valid,packet_advance_ready,packet_fault_pending;\n'
        'wire life_owner_ready,')
    t=once(t,'s_request_done_data[771:748]===m_expect_psn',
        's_request_done_data[771:748]===whole_first_psn')
    # BOTH observed last PSN and full first->next span remain mandatory.
    t=once(t,'s_request_done_data[795:772]==(m_expect_psn+24\'d1) &&',
        "s_request_done_data[795:772]==(m_expect_psn+24'd1) &&\n"
        "    s_request_done_data[795:772]==(whole_first_psn+whole_packet_span) &&")
    t=once(t,'wire request_match=',
        'wire [31:0] whole_length=m_cq_context[307:276];\n'
        'wire [23:0] whole_packet_span=(m_cq_context[339:324]==1 || m_cq_context[339:324]==3) && whole_length>4096 ?\n'
        "    (whole_length+32'd4095)>>12:24'd1;\nwire request_match=")
    t=once(t,'assign s_owner_ready=life_owner_ready',
        'wire segmented_profile_ok=s_owner_context[307:276]<=4096 || (RETRY_ENABLE && REQUEST_CQ_ENABLE);\n'
        'assign s_owner_ready=segmented_profile_ok && life_owner_ready')
    t=once(t,'(!life_owner_ready || !mac_owner_ready)',
        '(!segmented_profile_ok || !life_owner_ready || !mac_owner_ready)')
    t=helpers.connect(t,'lifetime',[
        ('packet_drained','local_tx_drained'),('packet_fault_pending','packet_fault_pending'),
        ('m_first_psn','whole_first_psn'),('m_packet_index','packet_index'),
        ('m_packet_advance_context','packet_advance_context'),('m_packet_advance_psn','packet_advance_psn'),
        ('m_packet_advance_valid','packet_advance_valid'),('m_packet_advance_ready','packet_advance_ready')])
    t=helpers.connect(t,'replay',dict(packet_parent_fault='outer_fault || packet_fault_pending',
        s_packet_advance_context='packet_advance_context',s_packet_advance_psn='packet_advance_psn',
        s_packet_advance_index='packet_index',s_packet_advance_valid='packet_advance_valid',
        s_packet_advance_ready='packet_advance_ready').items())
    return once(t,'assign replay_owner_ready=1;',
        'assign packet_advance_ready=0;\nassign replay_owner_ready=1;')


def derive():
    out=parent.derive()
    p=RTL/'rocev2_wqe_admission.v';out[p]=limit(out[p],'length','opcode')
    p=RTL/'rocev2_wqe_hls_sq.v';out[p]=limit(out[p],'in_length','in_opcode')
    p=RTL/'rocev2_shared_hls_transport.v';t=limit(out[p],'length','opcode')
    t=once(t,"m_request_done_data[795:772]==(m_request_done_data[771:748]+24'd1)",
        "m_request_done_data[795:772]==(m_request_done_data[771:748]+request_packet_span)")
    t=once(t,'wire request_shape=',
        'wire [31:0] request_length=owner[307:276];\n'
        'wire [23:0] request_packet_span=(owner[339:324]==1 || owner[339:324]==3) && request_length>4096 ?\n'
        "    (request_length+32'd4095)>>12:24'd1;\nwire request_shape=")
    out[p]=t
    p=RTL/'rocev2_wqe_lifetime.v';out[p]=lifetime(out[p])
    p=RTL/'rocev2_wqe_mac_tx.v';out[p]=limit(out[p],'in_length','in_op')
    p=RTL/'rocev2_wqe_response_guard.v';out[p]=limit(out[p],'in_length','in_op')
    p=RTL/'rocev2_wqe_replay.v';out[p]=replay(out[p])
    p=RTL/'rocev2_wqe_tx_lifetime.v';out[p]=tx_lifetime(out[p])
    p=RTL/'rocev2_cq_mmio.v';out[p]=limit(out[p],'s_ticket_context[307:276]','incoming_opcode')
    return out
