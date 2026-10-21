# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE RECV/WRITE/RNR/control allocator, distinct control480/512/MAC528.

The actual HLS header receipt and actual same-tag MAC EOF/SFD/1024-tail
are BOTH necessary. Control ownership never invents RQ/data/PSN/CQ proof.
The enclosing native bridge must authenticate received context and own a
nonwrapping serial; the allocator additionally rejects serial replay/wrap.
"""
import derive_receive_write_rnr_ack as parent

ROOT=parent.ROOT;RTL=parent.RTL;ACK=parent.ACK;once=parent.once
NAME='rocev2_receive_control_ack_tx'


def derive():
    t=once(parent.derive(),'module '+parent.NAME+' #(','module '+NAME+' #(')
    t=once(t,'    input wire [47:0] local_mac,input wire [47:0] peer_mac,',r'''    // Separate control header ownership, NEVER a posted RQ or data grant.
    input wire [479:0] s_control_owner,input wire s_control_owner_valid,output wire s_control_owner_ready,
    input wire [511:0] s_control_core_data,input wire s_control_core_valid,output wire s_control_core_ready,
    output wire [527:0] m_control_done_data,output wire m_control_done_valid,input wire m_control_done_ready,
    input wire [479:0] s_control_retire_owner,input wire s_control_retire_valid,output wire s_control_retire_ready,
    input wire [47:0] local_mac,input wire [47:0] peer_mac,''')
    t=once(t,'reg rnr_mode=0,rnr_proof_sent=0;reg [367:0] rnr_owner=0;',r'''reg rnr_mode=0,rnr_proof_sent=0;reg [367:0] rnr_owner=0;
reg control_mode=0,have_control_core=0,control_proof_sent=0;
reg [479:0] control_owner=0;
reg [511:0] control_proof=0;
// Deliberately retained across every owner retirement and other owner type.
reg [63:0] last_control_serial=0;''')
    for pin in ['s_owner_ready','s_write_owner_ready','s_rnr_owner_ready']:
        t=once(t,'assign '+pin+'=slot_ready &&','assign '+pin+"=slot_ready && s_control_owner_valid===1'b0 &&")
    t=once(t,'wire [64:0] rnr_va_end=',r'''assign s_control_owner_ready=slot_ready && s_owner_valid===1'b0 &&
 s_write_owner_valid===1'b0 && s_rnr_owner_valid===1'b0 && IMMEDIATE_ENABLE==1;
wire [23:0] control_future=s_control_owner[467:444]-s_control_owner[443:420];
wire [23:0] control_duplicate=s_control_owner[443:420]+24'd1-s_control_owner[467:444];
wire control_type_ok=
 s_control_owner[475:468]==8'h1f ? control_duplicate!=0 && !control_duplicate[23]:
 s_control_owner[475:468]==8'h60 ? control_future!=0 && !control_future[23]:
 (s_control_owner[475:468]==8'h61 || s_control_owner[475:468]==8'h62 || s_control_owner[475:468]==8'h63) &&
 s_control_owner[467:444]==s_control_owner[443:420];
wire control_owner_ok=(^{s_control_owner,local_mac,peer_mac,local_ip,peer_ip,peer_qpn})!==1'bx &&
 s_control_owner[479:476]==0 && s_control_owner[419:356]!=0 &&
 s_control_owner[419:356]>last_control_serial &&
 s_control_owner[23:0]<8 && s_control_owner[39:24]!=0 && s_control_owner[103:40]!=0 &&
 s_control_owner[167:104]!=0 && s_control_owner[303:256]==local_mac &&
 s_control_owner[351:304]==peer_mac && s_control_owner[223:192]==local_ip &&
 s_control_owner[255:224]==peer_ip && s_control_owner[191:168]==peer_qpn && control_type_ok;
assign s_control_core_ready=held && control_mode && !have_control_core && state<=CHECK && !halted && !rst;
wire control_core_ok=(^s_control_core_data)!==1'bx &&
 s_control_core_data[479:0]===control_owner && s_control_core_data[511:504]==0;
assign m_control_done_data={active_tag,control_proof};
assign m_control_done_valid=held && control_mode && state==DONE && !control_proof_sent && !halted && !rst;
assign s_control_retire_ready=held && control_mode && state==DONE && control_proof_sent &&
 s_control_retire_owner===control_owner && !halted && !rst;
wire [64:0] rnr_va_end=''')
    for pin in ['m_done_valid','m_write_done_valid','m_rnr_done_valid']:
        t=once(t,'assign '+pin+'=held &&','assign '+pin+'=held && !control_mode &&')
    t=once(t,'wire retire_base=held &&','wire retire_base=held && !control_mode &&')
    t=once(t,"held ? (8'h01<<(rnr_mode ?", "held ? (8'h01<<(control_mode ? control_owner[23:0]:rnr_mode ?")
    t=once(t,'    s_rnr_owner_valid && rnr_owner_ok ?',
        "    s_control_owner_valid && control_owner_ok ? (8'h01<<s_control_owner[23:0]) :\n"
        '    s_rnr_owner_valid && rnr_owner_ok ?')
    t=once(t,'wire [23:0] check_psn=rnr_mode ?',
        'wire [23:0] check_psn=control_mode ? control_owner[443:420]:rnr_mode ?')
    t=once(t,'wire [23:0] check_msn=rnr_mode ?',
        'wire [23:0] check_msn=control_mode ? control_proof[503:480]:rnr_mode ?')
    t=once(t,"octet(packet,54)==(rnr_mode ? 8'h20:8'h00)",
        "octet(packet,54)==(control_mode ? control_owner[475:468]:rnr_mode ? 8'h20:8'h00)")
    t=once(t,"wire check_ready=rnr_mode ? 1'b1:",
        "wire check_ready=control_mode ? have_control_core:rnr_mode ? 1'b1:")
    t=once(t,"wire check_core_ok=rnr_mode ? 1'b1:",
        "wire check_core_ok=control_mode ? have_control_core:rnr_mode ? 1'b1:")
    t=once(t,'else begin proof<=!rnr_mode &&', 'else begin proof<=!control_mode && !rnr_mode &&')
    t=once(t,'        rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;',r'''        rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;
        control_mode<=0;have_control_core<=0;control_proof_sent<=0;
        control_owner<=0;control_proof<=0;last_control_serial<=0;''')
    t=once(t,"        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end",r'''        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end
        if(s_control_owner_valid!==1'b0 && s_control_owner_valid!==1'b1 ||
           !held && s_control_owner_valid===1'b1 &&
           (s_owner_valid!==1'b0 || s_write_owner_valid!==1'b0 || s_rnr_owner_valid!==1'b0))begin
            fault<=1;fault_code<=8'hb0;
        end
        if(s_control_core_valid!==1'b0 && s_control_core_valid!==1'b1 ||
           s_control_core_valid===1'b1 && !s_control_core_ready)begin fault<=1;fault_code<=8'hb1;end
        if(s_control_core_valid && s_control_core_ready)begin
            if(!control_core_ok)begin fault<=1;fault_code<=8'hb2;end
            else begin control_proof<=s_control_core_data;have_control_core<=1;end
        end
        if(s_control_retire_valid!==1'b0 && s_control_retire_valid!==1'b1 ||
           s_control_retire_valid===1'b1 &&
           (!held || !control_mode || s_control_retire_owner!==control_owner) ||
           held && control_mode && s_retire_valid!==1'b0)begin fault<=1;fault_code<=8'hb3;end
        if(s_control_owner_valid && s_control_owner_ready)begin
            if(!control_owner_ok)begin fault<=1;fault_code<=8'hb4;end
            else begin
                held<=1;control_mode<=1;control_owner<=s_control_owner;
                last_control_serial<=s_control_owner[419:356];
                have_control_core<=0;control_proof<=0;control_proof_sent<=0;
                rnr_mode<=0;rnr_owner<=0;rnr_proof_sent<=0;
                write_mode<=0;write_notify<=0;write_owner<=0;write_proof<=0;have_write_core<=0;write_proof_sent<=0;
                owner<=0;proof<=0;state<=WAIT_ACK;packet<=0;
                active_tag<=16'h6000|({{(16-TAG_SEQUENCE_WIDTH){1'b0}},tag_sequence[TAG_SEQUENCE_WIDTH-1:0]}+16'd1);
                tag_sequence<=tag_sequence+1'b1;
                first_sent<=0;eof_sent<=0;receipt_seen<=0;proof_sent<=0;tail_started<=0;tail_count<=0;
                capture_index<=0;send_index<=0;
                saved_local_mac<=local_mac;saved_peer_mac<=peer_mac;saved_local_ip<=local_ip;saved_peer_ip<=peer_ip;saved_peer_qpn<=peer_qpn;
            end
        end''')
    # Only these three genuine old admissions clear the new typed slot. The
    # serial replay guard is NOT reset by old traffic or control retirement.
    for old in ['held<=1;rnr_mode<=1;','held<=1;rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;write_mode<=1;',
                'held<=1;rnr_mode<=0;rnr_proof_sent<=0;rnr_owner<=0;owner<=s_owner_context;']:
        t=once(t,old,'control_mode<=0;have_control_core<=0;control_proof_sent<=0;control_owner<=0;control_proof<=0;\n                '+old)
    t=once(t,'        if(m_rnr_done_valid && m_rnr_done_ready)rnr_proof_sent<=1;',r'''        if(m_control_done_valid && m_control_done_ready)control_proof_sent<=1;
        if(s_control_retire_valid && s_control_retire_ready)begin
            held<=0;control_mode<=0;control_owner<=0;control_proof<=0;
            have_control_core<=0;control_proof_sent<=0;state<=WAIT_ACK;
        end
        if(m_rnr_done_valid && m_rnr_done_ready)rnr_proof_sent<=1;''')
    if t.count("tag_sequence<=tag_sequence+1'b1;")!=4 or t.count('reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;')!=1:
        raise ValueError('ONE shared nonwrapping sequence and four distinct owner alternatives required')
    if t.count('last_control_serial<=0;')!=1:
        raise ValueError('serial replay guard must survive all owner retirements/mode switches')
    return t
