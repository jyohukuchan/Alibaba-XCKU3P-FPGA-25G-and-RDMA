# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE shared RECV/WRITE/RNR tag allocator; typed negative RNR ownership.

RNR owner={certified MSN24,rejected LAST PSN24,retained WRITE message320}.
No fake posted RQ, WRITE data/HLS receipt or CQ proof. Capture/check the
actual negative ACK before TX; same real MAC EOF/SFD/1024-tail and fresh
nonwrapping class6000 sequence. Original two owner paths remain unchanged.
"""
import derive_receive_write_ack as parent

ROOT=parent.ROOT;RTL=parent.RTL;ACK=parent.ACK;once=parent.once
NAME='rocev2_receive_write_rnr_ack_tx'


def derive():
    t=once(parent.derive(),'module '+parent.NAME+' #(','module '+NAME+' #(')
    t=once(t,'    input wire [47:0] local_mac,input wire [47:0] peer_mac,',r'''    // Privileged RNR-only owner, NOT a posted RQ or a positive WRITE grant.
    input wire [367:0] s_rnr_owner,input wire s_rnr_owner_valid,output wire s_rnr_owner_ready,
    output wire [383:0] m_rnr_done_data,output wire m_rnr_done_valid,input wire m_rnr_done_ready,
    input wire [367:0] s_rnr_retire_owner,input wire s_rnr_retire_valid,output wire s_rnr_retire_ready,
    input wire [47:0] local_mac,input wire [47:0] peer_mac,''')
    t=once(t,'reg [455:0] write_proof=0;','reg [455:0] write_proof=0;\nreg rnr_mode=0,rnr_proof_sent=0;reg [367:0] rnr_owner=0;')
    t=once(t,"assign s_owner_ready=slot_ready && s_write_owner_valid===1'b0;",
        "assign s_owner_ready=slot_ready && s_write_owner_valid===1'b0 && s_rnr_owner_valid===1'b0;")
    t=once(t,"assign s_write_owner_ready=slot_ready && s_owner_valid===1'b0 && IMMEDIATE_ENABLE==1;",r'''assign s_write_owner_ready=slot_ready && s_owner_valid===1'b0 && s_rnr_owner_valid===1'b0 && IMMEDIATE_ENABLE==1;
assign s_rnr_owner_ready=slot_ready && s_owner_valid===1'b0 && s_write_owner_valid===1'b0 && IMMEDIATE_ENABLE==1;
wire [64:0] rnr_va_end={1'b0,s_rnr_owner[119:56]}+{33'd0,s_rnr_owner[55:24]};
wire [23:0] rnr_last_delta=(s_rnr_owner[55:24]-32'd1)>>12;
wire [23:0] rnr_last_psn=s_rnr_owner[23:0]+rnr_last_delta;
wire rnr_owner_ok=(^{s_rnr_owner,local_mac,peer_mac,local_ip,peer_ip,peer_qpn})!==1'bx &&
 s_rnr_owner[319:296]<8 && s_rnr_owner[295:280]!=0 && s_rnr_owner[279:216]!=0 &&
 s_rnr_owner[215:152]!=0 && s_rnr_owner[151:120]!=0 && s_rnr_owner[55:24]>4096 &&
 s_rnr_owner[55:24]<=1048576 && rnr_va_end<=65'h10000000000000000 && s_rnr_owner[343:320]==rnr_last_psn;
assign m_rnr_done_data={active_tag,rnr_owner};
assign m_rnr_done_valid=held && rnr_mode && state==DONE && !rnr_proof_sent && !halted && !rst;
assign s_rnr_retire_ready=held && rnr_mode && state==DONE && rnr_proof_sent &&
 s_rnr_retire_owner===rnr_owner && !halted && !rst;''')
    t=once(t,'assign m_done_valid=held && (!write_mode || write_notify)',
        'assign m_done_valid=held && !rnr_mode && (!write_mode || write_notify)')
    t=once(t,'assign m_write_done_valid=held && write_mode',
        'assign m_write_done_valid=held && !rnr_mode && write_mode')
    t=once(t,'wire retire_base=held && state==DONE','wire retire_base=held && !rnr_mode && state==DONE')
    t=once(t,"held ? (8'h01<<(write_mode ? write_owner[423:400]:owner[395:372])) :",
        "held ? (8'h01<<(rnr_mode ? rnr_owner[319:296]:write_mode ? write_owner[423:400]:owner[395:372])) :\n"
        "    s_rnr_owner_valid && rnr_owner_ok ? (8'h01<<s_rnr_owner[319:296]) :")
    t=once(t,'wire [23:0] check_psn=write_mode ?',
        'wire [23:0] check_psn=rnr_mode ? rnr_owner[343:320]:write_mode ?')
    t=once(t,'wire [23:0] check_msn=write_mode ?',
        'wire [23:0] check_msn=rnr_mode ? rnr_owner[367:344]:write_mode ?')
    t=once(t,'octet(packet,50)==0 && octet(packet,54)==0 &&',
        "octet(packet,50)==0 && octet(packet,54)==(rnr_mode ? 8'h20:8'h00) &&")
    t=once(t,'wire check_ready=write_mode ?','wire check_ready=rnr_mode ? 1\'b1:write_mode ?')
    t=once(t,'wire check_core_ok=write_mode ?','wire check_core_ok=rnr_mode ? 1\'b1:write_mode ?')
    t=once(t,'else begin proof<=(!write_mode || write_notify) ? s_core_data:0;',
        'else begin proof<=!rnr_mode && (!write_mode || write_notify) ? s_core_data:0;')
    t=once(t,'        held<=0;pass_frame<=0;state<=WAIT_ACK;owner<=0;proof<=0;packet<=0;',
        '        held<=0;pass_frame<=0;state<=WAIT_ACK;owner<=0;proof<=0;packet<=0;\n'
        '        rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;')
    t=once(t,"        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end",r'''        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end
        if(s_rnr_owner_valid!==1'b0 && s_rnr_owner_valid!==1'b1 ||
           !held && s_rnr_owner_valid===1'b1 && (s_owner_valid!==1'b0 || s_write_owner_valid!==1'b0))begin fault<=1;fault_code<=8'hd9;end
        if(s_rnr_retire_valid && (!held || !rnr_mode || s_rnr_retire_owner!==rnr_owner))begin fault<=1;fault_code<=8'hda;end
        if(s_rnr_owner_valid && s_rnr_owner_ready)begin
            if(!rnr_owner_ok)begin fault<=1;fault_code<=8'hdb;end
            else begin
                held<=1;rnr_mode<=1;rnr_owner<=s_rnr_owner;rnr_proof_sent<=0;
                write_mode<=0;write_notify<=0;write_owner<=0;write_proof<=0;have_write_core<=0;write_proof_sent<=0;
                owner<=0;proof<=0;state<=WAIT_ACK;packet<=0;
                active_tag<=16'h6000|({{(16-TAG_SEQUENCE_WIDTH){1'b0}},tag_sequence[TAG_SEQUENCE_WIDTH-1:0]}+16'd1);
                tag_sequence<=tag_sequence+1'b1;
                first_sent<=0;eof_sent<=0;receipt_seen<=0;proof_sent<=0;tail_started<=0;tail_count<=0;
                capture_index<=0;send_index<=0;
                saved_local_mac<=local_mac;saved_peer_mac<=peer_mac;saved_local_ip<=local_ip;saved_peer_ip<=peer_ip;saved_peer_qpn<=peer_qpn;
            end
        end''')
    t=once(t,'                held<=1;write_mode<=1;','                held<=1;rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;write_mode<=1;')
    t=once(t,'                held<=1;owner<=s_owner_context;','                held<=1;rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;owner<=s_owner_context;')
    t=once(t,'        if(m_done_valid && m_done_ready)proof_sent<=1;',r'''        if(m_rnr_done_valid && m_rnr_done_ready)rnr_proof_sent<=1;
        if(s_rnr_retire_valid && s_rnr_retire_ready)begin
            held<=0;rnr_mode<=0;rnr_owner<=0;rnr_proof_sent<=0;state<=WAIT_ACK;
        end
        if(m_done_valid && m_done_ready)proof_sent<=1;''')
    if t.count("tag_sequence<=tag_sequence+1'b1;")!=3 or t.count('reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;')!=1:
        raise ValueError('ONE shared nonwrapping sequence, exactly three typed owner alternatives required')
    return t
