# SPDX-License-Identifier: BSD-2-Clause-Views
"""Separate late-WRITE notification RQ, retaining the qualified SEND queue.

The new notice input MUST come from a full-message remote-MR guard, not
raw RETH or HLS. Hold its full320-bit identity and the separate posted620
RQ owner through actual final packet/HLS/MAC/whole-CQ retirement. This
component is not a connected native MR guard or HLS/physical qualification.
"""
from pathlib import Path
import derive_segmented_receive_continuation as base

ROOT=base.ROOT;RTL=base.RTL;once=base.once
SOURCE=RTL/'rocev2_receive_message_queue.v'
NAME='rocev2_write_notice_receive_queue'


def derive():
    t=once(SOURCE.read_text(),'module rocev2_receive_message_queue #(','module '+NAME+' #(')
    t=once(t,'    input wire clk,input wire rst,input wire parent_fault,',r'''
    // {QPN24,PD16,epoch64,message_cookie64,key32,baseVA64,total32,firstPSN24}.
    // Already validated remote-MR message identity; NEVER a DMA address grant.
    input wire [319:0] s_write_notice_context,input wire [23:0] s_write_notice_last_psn,
    input wire s_write_notice_valid,output wire s_write_notice_ready,
    output wire [319:0] m_write_retire_context,output wire m_write_retire_valid,
    input wire m_write_retire_ready,
    input wire clk,input wire rst,input wire parent_fault,''')
    t=once(t,'wire protocol_fault;',r'''
reg notice_held=0;reg [319:0] notice_context=0;reg [23:0] notice_last_psn=0;
wire [31:0] notice_total=notice_context[55:24];
wire [31:0] notice_last_length=((notice_total-1)&32'hfff)+1;
wire [31:0] offered_total=s_write_notice_context[55:24];
wire [64:0] offered_end={1'b0,s_write_notice_context[119:56]}+{33'd0,offered_total};
wire [23:0] offered_span=s_write_notice_last_psn-s_write_notice_context[23:0];
wire notice_basic=(^{s_write_notice_context,s_write_notice_last_psn})!==1'bx &&
    s_write_notice_context[319:296]<8 && s_write_notice_context[319:296]===query_qpn &&
    s_write_notice_context[295:280]!=0 && s_write_notice_context[279:216]!=0 &&
    s_write_notice_context[215:152]!=0 && s_write_notice_context[151:120]!=0 &&
    offered_total>4096 && offered_total<=1048576 && offered_end<=65'h10000000000000000 &&
    offered_span==((offered_total-1)>>12);
wire notice_head_present=query_ok && !held && count[query_qpn[2:0]]!=0;
wire notice_RQ_match=s_write_notice_context[295:280]===m_head_context[371:356] &&
    s_write_notice_context[279:216]===m_head_context[459:396];
wire bad_notice=(s_write_notice_valid!==1'b0) &&
    (s_write_notice_valid!==1'b1 || !notice_basic || held || (notice_head_present && !notice_RQ_match));
wire protocol_fault;''')
    t=once(t,'wire [7:0] pf=s_placement_notification_flags;',r'''
assign s_write_notice_ready=s_write_notice_valid===1'b1 && notice_basic && notice_RQ_match &&
    !held && m_head_valid && m_head_ready && !halted && !rst;
assign m_write_retire_context=notice_context;
assign m_write_retire_valid=notice_held && held && committed && s_retire_valid &&
    s_retire_context===owner && !halted && !rst;
wire [7:0] pf=s_placement_notification_flags;''')
    t=once(t,'wire placement_match=placement_shape && placement_sequence;',
        "wire placement_match=placement_shape && placement_sequence && (!notice_held ||\n"
        "    pf==3 && s_placement_psn==notice_last_psn && s_placement_length==notice_last_length);")
    t=once(t,"wire [32:0] whole_bytes=packet_done ?", "wire [32:0] whole_bytes=notice_held ? {1'b0,notice_total}:packet_done ?")
    # Select the ready assignment exactly. The distinct retirement producer's
    # VALID must not depend on READY (stable fanout under backpressure).
    t=once(t,'assign s_retire_ready=held && committed && s_retire_context===owner && !halted && !rst;',
        "assign s_retire_ready=held && committed && s_retire_context===owner &&\n    (!notice_held || m_write_retire_ready===1'b1) && !halted && !rst;")
    t=once(t,'assign protocol_fault=s_post_valid', 'assign protocol_fault=bad_notice || s_post_valid')
    t=once(t,'        held<=0;armed<=0;placed<=0;mac_proved<=0;packet_done<=0;group_active<=0;message_proved<=0;',
        '        notice_held<=0;notice_context<=0;notice_last_psn<=0;\n'
        '        held<=0;armed<=0;placed<=0;mac_proved<=0;packet_done<=0;group_active<=0;message_proved<=0;')
    t=once(t,'    end else begin\n        if(parent_fault',
        "    end else begin\n        if(bad_notice)begin fault<=1;fault_code<=8'hef;end\n        if(parent_fault")
    t=once(t,'        if(m_head_valid && m_head_ready)begin',
        '        if(s_write_notice_valid && s_write_notice_ready)begin\n'
        '            notice_held<=1;notice_context<=s_write_notice_context;notice_last_psn<=s_write_notice_last_psn;\n'
        '        end\n        if(m_head_valid && m_head_ready)begin')
    t=once(t,'packet_psn<=s_placement_psn;if(!group_active)first_psn<=s_placement_psn;',
        'packet_psn<=s_placement_psn;if(!group_active)first_psn<=notice_held ? notice_context[23:0]:s_placement_psn;')
    t=once(t,'        if(release_owner)begin',
        '        if(release_owner)begin\n            notice_held<=0;notice_context<=0;notice_last_psn<=0;')
    return t
