# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in SEND receive path on the SAME protected parser/MR/HLS/backend.

This extends the shared derivative only; the original protected responder,
HLS delivery and rollback bytes remain unchanged. Placement/ACK submission
is NOT core retirement or permission to publish a CQE/unpin a receive WQE.
"""
PORTS=[('input','[587:0]','s_recv_context'),('input','','s_recv_valid'),
    ('output','','s_recv_ready'),('output','[23:0]','m_recv_query_qpn'),
    ('output','[587:0]','m_recv_placement_context'),('output','[31:0]','m_recv_placement_length'),
    ('output','','m_recv_placement_valid'),('input','','m_recv_placement_ready'),
    ('input','','recv_owned_guard'),('output','[23:0]','m_recv_placement_psn'),
    ('output','[679:0]','m_recv_core_data'),('output','','m_recv_core_valid'),('input','','m_recv_core_ready'),
    ('input','','recv_ack_admission_ready'),('input','[587:0]','s_recv_retire_context'),
    ('input','','s_recv_retire_valid'),('output','','s_recv_retire_ready'),
    ('output','[655:0]','m_request_done_data'),('output','','m_request_done_valid'),('input','','m_request_done_ready')]

def once(s,a,b):
    if s.count(a)!=1:raise ValueError('receive shared-responder anchor changed: '+a)
    return s.replace(a,b,1)

def derive(text):
    text=once(text,'    parameter EXTERNAL_REPLAY_ENABLE=0,',
        '    parameter EXTERNAL_REPLAY_ENABLE=0,\n    parameter RECV_ENABLE=0,\n    parameter RNR_ENABLE=0,\n    parameter RECV_RETIRE_ENABLE=0,\n    parameter RECV_CQ_ENABLE=0,\n    parameter REQUEST_CQ_ENABLE=0,')
    lines='\n'.join('    '+d+' wire '+(w+' 'if w else'')+n+',' for d,w,n in PORTS)
    text=once(text,'    input wire clk,',lines+'\n    input wire clk,')
    for width,name in [('[587:0]','m_recv_placement_context'),('[31:0]','m_recv_placement_length'),('', 'm_recv_placement_valid'),('[23:0]','m_recv_placement_psn')]:
        text=once(text,'output wire '+(width+' 'if width else'')+name+',',
            'output reg '+(width+' 'if width else'')+name+'=0,')
    text=once(text,'    ACTIVE=5, REJECT=6;','    ACTIVE=5, REJECT=6, RECV_ARM=7, RNR_ARM=8, RNR_WAIT=9, OWNER_ARM=10;')
    text=once(text,'reg [2:0] state=COLLECT;','reg [3:0] state=COLLECT;')
    text=once(text,'    ERR_TAG_EXHAUSTED=36, ERR_MR_PROTOCOL=37;',
        '    ERR_TAG_EXHAUSTED=36, ERR_MR_PROTOCOL=37, ERR_RQ_EMPTY=38, ERR_RQ_LENGTH=39;')
    text=once(text,'reg [15:0] lease_tag=0;',r'''
reg [15:0] lease_tag=0;
reg recv_operation=0;
reg recv_completion_pending=0;
reg [587:0] recv_context=0;
reg [31:0] rnr_sent_count=0;
wire [55:0] rnr_event_data={8'h20,request_psn,local_qpn};
wire rnr_event_valid=RNR_ENABLE && state==RNR_ARM && !fault && !rst;
wire rnr_event_ready;
wire [647:0] recv_owner_data={4'd0,request_psn,request_length,recv_context};
wire recv_owner_valid=RECV_RETIRE_ENABLE && state==OWNER_ARM && !fault && !rst;
wire recv_owner_ready;
assign m_recv_query_qpn=RECV_ENABLE ? local_qpn : 0;
wire recv_context_ok=(^s_recv_context)!==1'bx && s_recv_context[395:372]==local_qpn &&
    s_recv_context[371:356]==trusted_pd && s_recv_context[459:396]!=0 &&
    s_recv_context[523:460]!=0 && s_recv_context[355:340]!=0 &&
    s_recv_context[339:324]==4 && s_recv_context[323:308]==1 &&
    s_recv_context[307:276]!=0 && s_recv_context[307:276]<=4096 &&
    s_recv_context[115:20]==0 && s_recv_context[19:0]==20'd3;
assign s_recv_ready=RECV_ENABLE && state==RECV_ARM && s_recv_valid &&
    s_recv_context===recv_context && (!RECV_CQ_ENABLE || recv_ack_admission_ready) && !fault && !rst;
''')
    text=once(text,'assign checked_ready=state==COLLECT && qp_ready &&',
        'assign checked_ready=state==COLLECT && qp_ready && (!RECV_CQ_ENABLE || !recv_completion_pending) &&')
    text=once(text,'wire [31:0] parsed_length=be32(header,52);',
        "wire [31:0] parsed_length=(RECV_ENABLE && opcode==8'h04) ? {16'd0,byte_count}-32'd44-{30'd0,pad} : be32(header,52);")
    text=text.replace("write_operation ? 3'd3 : 3'd2", "recv_operation ? 3'd1 : write_operation ? 3'd3 : 3'd2")
    text=once(text,'wire command_match=selected_command[93:0]==expected_command;',r'''
// SEND's native HLS command intentionally has address0/host0. Check ALL
// fields against that exact raw shape, then use ONLY the saved authorized
// receive WQE's MR key/offset for real placement; raw0 is never a DMA address.
wire [95:0] recv_expected_command={2'd0,local_qpn[9:0],4'd0,1'b0,1'b0,1'b0,1'b1,wire_length[27:0],48'd0};
wire command_match=recv_operation ? (selected_command===recv_expected_command) : selected_command[93:0]==expected_command;
''')
    text=once(text,'        request_va<=0;dma_address<=0;',
        '        recv_operation<=0;recv_completion_pending<=0;recv_context<=0;rnr_sent_count<=0;m_recv_placement_context<=0;m_recv_placement_length<=0;m_recv_placement_valid<=0;m_recv_placement_psn<=0;\n        request_va<=0;dma_address<=0;')
    text=once(text,'        if(!startup_done) startup_count<=startup_count+1\'b1;',
        "        if(m_recv_placement_valid && m_recv_placement_ready)m_recv_placement_valid<=0;\n"
        "        if(RECV_CQ_ENABLE && s_recv_valid && s_recv_ready)recv_completion_pending<=1;\n"
        "        if(RECV_CQ_ENABLE && s_recv_retire_valid && s_recv_retire_ready)recv_completion_pending<=0;\n"
        "        if(!startup_done) startup_count<=startup_count+1'b1;")
    text=once(text,'            if(shared_mr_fault) begin fault<=1;fault_code<=ERR_MR_PROTOCOL;end',r'''
            if(RECV_ENABLE && state==RECV_ARM && (!s_recv_valid || s_recv_context!==recv_context))begin
                fault<=1;fault_code<=ERR_UNEXPECTED;
            end
            if(shared_mr_fault) begin fault<=1;fault_code<=ERR_MR_PROTOCOL;end''')
    text=once(text,'if(frame_bad || byte_count<60 || header[0+:8]!=8\'h45 ||',
        "if(frame_bad || byte_count<((RECV_ENABLE && opcode==8'h04) ? 48 : 60) || header[0+:8]!=8'h45 ||")
    text=once(text,"else if(opcode!=8'h0a && opcode!=8'h0c) m_reject_error<=ERR_OPCODE;",
        "else if(opcode!=8'h0a && opcode!=8'h0c && !(RECV_ENABLE && opcode==8'h04)) m_reject_error<=ERR_OPCODE;")
    text=once(text,"(opcode==8'h0c && (byte_count!=60 || pad!=0))) m_reject_error<=ERR_FORMAT;",
        "(opcode==8'h0c && (byte_count!=60 || pad!=0)) ||\n"
        "                        (opcode==8'h04 && (byte_count!=44+padded_length || pad!=((-parsed_length)&3)))) m_reject_error<=ERR_FORMAT;")
    text=once(text,"                    else if(lease_tag==16'hffff) m_reject_error<=ERR_TAG_EXHAUSTED;",r'''
                    else if(RECV_ENABLE && opcode==8'h04 && !s_recv_valid)begin
                        m_reject_error<=ERR_RQ_EMPTY;
                        if(RNR_ENABLE)begin
                            // Header/ICRC/peer/full-QPN/expected-PSN/length
                            // already authenticated above. NEVER forward RX
                            // to HLS, take a receive WQE or advance its PSN.
                            request_psn<=parsed_psn;recv_operation<=0;
                            m_reject_valid<=1;rejected_count<=rejected_count+1'b1;
                            state<=RNR_ARM;
                        end
                    end
                    else if(RECV_ENABLE && opcode==8'h04 && (!recv_context_ok || parsed_length>s_recv_context[307:276]))
                        m_reject_error<=ERR_RQ_LENGTH;
                    else if(lease_tag==16'hffff) m_reject_error<=ERR_TAG_EXHAUSTED;''')
    text=once(text,'''                        request_va<=be64(header,40);request_key<=be32(header,48);request_length<=parsed_length;request_psn<=parsed_psn;
                        write_operation<=opcode==8'h0a;wire_length<=opcode==8'h0a ? padded_length : parsed_length;
                        state<=LOOKUP;''',r'''
                        request_length<=parsed_length;request_psn<=parsed_psn;
                        recv_operation<=RECV_ENABLE && opcode==8'h04;
                        if(RECV_ENABLE && opcode==8'h04)begin
                            recv_context<=s_recv_context;
                            request_va<=s_recv_context[243:180];request_key<=s_recv_context[275:244];
                            write_operation<=1;wire_length<=padded_length;state<=RECV_ARM;
                        end else begin
                            request_va<=be64(header,40);request_key<=be32(header,48);
                            write_operation<=opcode==8'h0a;wire_length<=opcode==8'h0a ? padded_length : parsed_length;
                            state<=LOOKUP;
                        end''')
    text=once(text,'                LOOKUP: if(mr_request_ready) state<=MR_WAIT;',
        '                RNR_ARM: if(rnr_event_valid && rnr_event_ready)state<=RNR_WAIT;\n'
        '                RNR_WAIT: if(m_axis_tx_tvalid && m_axis_tx_tready && m_axis_tx_tlast)begin\n'
        '                    rnr_sent_count<=rnr_sent_count+1\'b1;state<=REJECT;\n'
        '                end\n'
        '                RECV_ARM: if(s_recv_valid && s_recv_ready)state<=LOOKUP;\n'
        '                OWNER_ARM: if(recv_owner_valid && recv_owner_ready)state<=FORWARD;\n'
        '                LOOKUP: if(mr_request_ready) state<=MR_WAIT;')
    text=once(text,"accepted_count<=accepted_count+1'b1;forward_index<=0;state<=FORWARD;",
        "accepted_count<=accepted_count+1'b1;forward_index<=0;state<=RECV_RETIRE_ENABLE && recv_operation ? OWNER_ARM : FORWARD;")
    text=once(text,"                    lease<=0;completed_count<=completed_count+1'b1;expected_psn<=expected_psn+1'b1;",r'''
                    // Real memory visibility and IP ACK handoff, NOT actual
                    // MAC receipt/core retirement. Full RQ owner stays held.
                    if(recv_operation)begin
                        m_recv_placement_context<=recv_context;
                        m_recv_placement_length<=request_length;m_recv_placement_psn<=request_psn;m_recv_placement_valid<=1;
                    end
                    lease<=0;completed_count<=completed_count+1'b1;expected_psn<=expected_psn+1'b1;''')
    text=once(text,'assign m_axis_tx_tvalid=core_tx_valid && lease && committed && !fault && !rst;',
        'assign m_axis_tx_tvalid=core_tx_valid && ((lease && committed) || (RNR_ENABLE && state==RNR_WAIT)) && !fault && !rst;')
    text=once(text,'assign core_tx_ready=m_axis_tx_tready && lease && committed && !fault && !rst;',
        'assign core_tx_ready=m_axis_tx_tready && ((lease && committed) || (RNR_ENABLE && state==RNR_WAIT)) && !fault && !rst;')
    text=once(text,'rocev2_shared_hls_transport #(.QP_TX_ENABLE(QP_TX_ENABLE),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE)) transport (',
        'rocev2_shared_hls_transport #(.QP_TX_ENABLE(QP_TX_ENABLE),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE),.RECV_ENABLE(RECV_ENABLE),.RNR_ENABLE(RNR_ENABLE),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.RECV_CQ_ENABLE(RECV_CQ_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE)) transport (\n'
        '    .m_request_done_data(m_request_done_data),.m_request_done_valid(m_request_done_valid),.m_request_done_ready(m_request_done_ready),\n'
        '    .s_recv_retire_context(s_recv_retire_context),.s_recv_retire_valid(s_recv_retire_valid),.s_recv_retire_ready(s_recv_retire_ready),\n'
        '    .s_recv_owner_tdata(recv_owner_data),.s_recv_owner_tvalid(recv_owner_valid),.s_recv_owner_tready(recv_owner_ready),\n'
        '    .m_recv_done_tdata(m_recv_core_data),.m_recv_done_tvalid(m_recv_core_valid),.m_recv_done_tready(m_recv_core_ready),\n'
        '    .s_rnr_event_tdata(rnr_event_data),.s_rnr_event_tvalid(rnr_event_valid),.s_rnr_event_tready(rnr_event_ready),\n'
        '    .remote_receive_held(recv_owned_guard),')
    return text
