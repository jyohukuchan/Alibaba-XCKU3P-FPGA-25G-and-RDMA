# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE class6000 ACK allocator, separate real RQ620 and WRITE424 identities.

Derived only for the new cohort. Original receive gates/tag allocator/MAC
EOF/receipt/1024-tail remain. WRITE Immediate publishes TWO independently
backpressured packet proofs and requires BOTH exact retire handshakes.
This leaf supplies no DMA/fence/HLS/CQ/partial-message teardown proof.
"""
import derive_receive_message_ack as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;ACK=parent.ACK
NAME='rocev2_receive_write_ack_tx'


def derive():
    t=parent.derive()
    t=once(t,'module rocev2_receive_ack_tx #(', 'module '+NAME+' #(')
    t=once(t,'    input wire [47:0] local_mac,input wire [47:0] peer_mac,', '''    // Privileged remote packet owner; a plain WRITE has NO posted RQ.
    input wire [423:0] s_write_owner,input wire s_write_owner_notify,
    input wire [619:0] s_write_owner_rq_context,
    input wire s_write_owner_valid,output wire s_write_owner_ready,
    input wire [455:0] s_write_core_data,input wire s_write_core_valid,output wire s_write_core_ready,
    output wire [471:0] m_write_done_data,output wire m_write_done_valid,input wire m_write_done_ready,
    input wire [423:0] s_write_retire_token,input wire s_write_retire_valid,output wire s_write_retire_ready,
    input wire [47:0] local_mac,input wire [47:0] peer_mac,''')
    t=once(t,'reg [CORE_WIDTH-1:0] proof=0;', '''reg [CORE_WIDTH-1:0] proof=0;
reg write_mode=0,write_notify=0,have_write_core=0,write_proof_sent=0;
reg [423:0] write_owner=0;
reg [455:0] write_proof=0;''')
    t=once(t,"assign s_owner_ready=!held && !pass_frame && !s_axis_tvalid && prior_response_drained===1'b1 &&\n    !tags_exhausted && !halted && !rst;", '''wire slot_ready=!held && !pass_frame && !s_axis_tvalid && prior_response_drained===1'b1 &&
    !tags_exhausted && !halted && !rst;
assign s_owner_ready=slot_ready && s_write_owner_valid===1'b0;
assign s_write_owner_ready=slot_ready && s_owner_valid===1'b0 && IMMEDIATE_ENABLE==1;
wire [32:0] write_input_end={1'b0,s_write_owner[103:72]}+{1'b0,s_write_owner[71:40]};
wire [64:0] write_va_end={1'b0,s_write_owner[223:160]}+{33'd0,s_write_owner[159:128]};
wire [31:0] write_psn_delta=s_write_owner[103:72]>>12;
wire [23:0] write_expected_psn=s_write_owner[127:104]+write_psn_delta[23:0];
wire [31:0] rq_capacity=s_write_owner_rq_context[307:276];
wire [64:0] rq_va_end={1'b0,s_write_owner_rq_context[243:180]}+{33'd0,rq_capacity};
wire [64:0] rq_offset_end={1'b0,s_write_owner_rq_context[179:116]}+{33'd0,rq_capacity};
wire write_rq_ok=(^s_write_owner_rq_context)!==1'bx &&
    s_write_owner_rq_context[395:372]===s_write_owner[423:400] &&
    s_write_owner_rq_context[371:356]===s_write_owner[399:384] &&
    s_write_owner_rq_context[459:396]===s_write_owner[383:320] &&
    s_write_owner_rq_context[523:460]!=0 && s_write_owner_rq_context[355:340]!=0 &&
    s_write_owner_rq_context[339:324]==4 && s_write_owner_rq_context[323:308]==1 &&
    s_write_owner_rq_context[619:588]==0 && s_write_owner_rq_context[115:20]==0 &&
    s_write_owner_rq_context[19:0]==3 && rq_capacity<=1048576 &&
    (rq_capacity==0 ? s_write_owner_rq_context[275:116]==0:
     s_write_owner_rq_context[275:244]!=0 && rq_va_end<=65'h10000000000000000 &&
     rq_offset_end<=65'h10000000000000000);
wire write_owner_ok=(^{s_write_owner,s_write_owner_notify,local_mac,peer_mac,local_ip,peer_ip,peer_qpn})!==1'bx &&
    s_write_owner[423:400]<8 && s_write_owner[399:384]!=0 && s_write_owner[383:320]!=0 &&
    s_write_owner[319:256]!=0 && s_write_owner[255:224]!=0 && s_write_owner[15:0]!=0 &&
    s_write_owner[159:128]>4096 && s_write_owner[159:128]<=1048576 &&
    write_va_end<=65'h10000000000000000 && s_write_owner[83:72]==0 &&
    s_write_owner[71:40]!=0 && s_write_owner[71:40]<=4096 &&
    write_input_end<={1'b0,s_write_owner[159:128]} &&
    (write_input_end=={1'b0,s_write_owner[159:128]} || s_write_owner[71:40]==4096) &&
    s_write_owner[39:16]==write_expected_psn &&
    (s_write_owner_notify ? write_input_end=={1'b0,s_write_owner[159:128]} && write_rq_ok:
     s_write_owner_rq_context===620'd0);
assign s_write_core_ready=held && write_mode && !have_write_core && state<=CHECK && !halted && !rst;
wire write_core_ok=(^s_write_core_data)!==1'bx && s_write_core_data[423:0]===write_owner &&
    s_write_core_data[455:448]==0;''')
    t=once(t,'assign m_done_valid=held && state==DONE && !proof_sent && !halted && !rst;\nassign s_retire_ready=held && state==DONE && proof_sent && s_retire_context===owner && !halted && !rst;', '''assign m_done_valid=held && (!write_mode || write_notify) && state==DONE && !proof_sent && !halted && !rst;
assign m_write_done_data={active_tag,write_proof};
assign m_write_done_valid=held && write_mode && state==DONE && !write_proof_sent && !halted && !rst;
wire retire_base=held && state==DONE && !halted && !rst;
wire write_retire_match=s_write_retire_token===write_owner;
// Paired READY depends on the OTHER VALID, never the OTHER READY. A
// compliant producer asserts VALID independently; neither identity retires alone.
assign s_retire_ready=retire_base && proof_sent && s_retire_context===owner &&
    (!write_mode || write_notify && write_proof_sent && s_write_retire_valid===1'b1 && write_retire_match);
assign s_write_retire_ready=retire_base && write_mode && write_proof_sent && write_retire_match &&
    (!write_notify || proof_sent && s_retire_valid===1'b1 && s_retire_context===owner);''')
    t=once(t,"assign queue_guard=halted ? 8'hff : held ? (8'h01<<owner[395:372]) :\n    s_owner_valid && owner_ok ? (8'h01<<s_owner_context[395:372]) : 0;", '''assign queue_guard=halted ? 8'hff : held ? (8'h01<<(write_mode ? write_owner[423:400]:owner[395:372])) :
    s_write_owner_valid && write_owner_ok ? (8'h01<<s_write_owner[423:400]) :
    s_owner_valid && owner_ok ? (8'h01<<s_owner_context[395:372]) : 0;''')
    t=once(t,'wire header_ok=', '''wire [23:0] check_psn=write_mode ? write_owner[39:16]:s_core_data[OWNER_WIDTH+55:OWNER_WIDTH+32];
wire [23:0] check_msn=write_mode ? write_proof[447:424]:s_core_data[OWNER_WIDTH+83:OWNER_WIDTH+60];
wire header_ok=''')
    t=once(t,'be24(packet,51)==s_core_data[OWNER_WIDTH+55:OWNER_WIDTH+32] &&\n    be24(packet,55)==s_core_data[OWNER_WIDTH+83:OWNER_WIDTH+60];',
        'be24(packet,51)==check_psn &&\n    be24(packet,55)==check_msn;')
    t=once(t,'always @(posedge clk)begin', '''wire write_notify_core_ok=core_ok && core_notification_flags==3 &&
    s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]==write_owner[71:40] &&
    s_core_data[OWNER_WIDTH+55:OWNER_WIDTH+32]==write_owner[39:16] &&
    s_core_data[OWNER_WIDTH+83:OWNER_WIDTH+60]==write_proof[447:424];
wire check_ready=write_mode ? have_write_core && (!write_notify || s_core_valid):s_core_valid;
wire check_core_ok=write_mode ? (!write_notify || write_notify_core_ok):core_ok;
always @(posedge clk)begin''')
    t=once(t,'        held<=0;pass_frame<=0;state<=WAIT_ACK;owner<=0;proof<=0;packet<=0;', '''        held<=0;pass_frame<=0;state<=WAIT_ACK;owner<=0;proof<=0;packet<=0;
        write_mode<=0;write_notify<=0;have_write_core<=0;write_proof_sent<=0;write_owner<=0;write_proof<=0;''')
    t=once(t,"        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end", '''        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end
        if(!held && s_owner_valid===1'b1 && s_write_owner_valid===1'b1)begin fault<=1;fault_code<=8'hd6;end
        if(s_write_owner_valid!==1'b0 && s_write_owner_valid!==1'b1)begin fault<=1;fault_code<=8'hd6;end
        if(s_write_core_valid && s_write_core_ready)begin
            if(!write_core_ok)begin fault<=1;fault_code<=8'hd7;end
            else begin write_proof<=s_write_core_data;have_write_core<=1;end
        end
        if(s_write_retire_valid && (!held || !write_mode || !write_retire_match) ||
           held && write_mode && write_notify && s_retire_valid && s_retire_context!==owner)begin
            fault<=1;fault_code<=8'hd8;
        end
        if(s_write_owner_valid && s_write_owner_ready)begin
            if(!write_owner_ok)begin fault<=1;fault_code<=8'hd2;end
            else begin
                held<=1;write_mode<=1;write_notify<=s_write_owner_notify;write_owner<=s_write_owner;
                owner<=s_write_owner_notify ? s_write_owner_rq_context:620'd0;
                have_write_core<=0;write_proof<=0;write_proof_sent<=0;proof<=0;state<=WAIT_ACK;packet<=0;
                active_tag<=16'h6000|({{(16-TAG_SEQUENCE_WIDTH){1'b0}},tag_sequence[TAG_SEQUENCE_WIDTH-1:0]}+16'd1);
                tag_sequence<=tag_sequence+1'b1;
                first_sent<=0;eof_sent<=0;receipt_seen<=0;proof_sent<=0;tail_started<=0;tail_count<=0;
                capture_index<=0;send_index<=0;
                saved_local_mac<=local_mac;saved_peer_mac<=peer_mac;saved_local_ip<=local_ip;saved_peer_ip<=peer_ip;saved_peer_qpn<=peer_qpn;
            end
        end''')
    t=once(t,'                held<=1;owner<=s_owner_context;state<=WAIT_ACK;packet<=0;', '''                held<=1;owner<=s_owner_context;state<=WAIT_ACK;packet<=0;
                write_mode<=0;write_notify<=0;have_write_core<=0;write_proof_sent<=0;write_owner<=0;write_proof<=0;''')
    t=once(t,'        if(state==CHECK && s_core_valid && !halted)begin\n            if(!core_ok || !header_ok)',
        '        if(state==CHECK && check_ready && !halted)begin\n            if(!check_core_ok || !header_ok)')
    t=once(t,'            else begin proof<=s_core_data;state<=SEND;send_index<=0;end',
        '            else begin proof<=(!write_mode || write_notify) ? s_core_data:0;state<=SEND;send_index<=0;end')
    t=once(t,'        if(s_retire_valid && s_retire_ready)begin held<=0;owner<=0;state<=WAIT_ACK;end', '''        if(m_write_done_valid && m_write_done_ready)write_proof_sent<=1;
        if(s_retire_valid && s_retire_ready || s_write_retire_valid && s_write_retire_ready)begin
            held<=0;owner<=0;state<=WAIT_ACK;write_mode<=0;write_notify<=0;write_owner<=0;
            have_write_core<=0;write_proof<=0;write_proof_sent<=0;
        end''')
    # Both alternatives contain the SAME class6000 sequence register. There
    # must never be another instantiated allocator or tag-domain substitution.
    if t.count('tag_sequence<=tag_sequence+1\'b1;')!=2 or t.count('reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;')!=1:
        raise ValueError('one shared class6000 sequence required')
    return t
