# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE PSN/fatal serial allocator and real control wire/local-report fanout.

Native fatal certificates are separate from ordinary PSN18 certification.
Only authenticated semantic16 ->61 and actual remote MR1..4 ->62 are sourced
here. No63 classification is invented; full QP/error CQ/STOP is separate.
"""
from pathlib import Path
import derive_write_psn_control_native as parent
ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
NAME='rocev2_write_error_control'
SOURCE=RTL/'rocev2_write_psn_control.v'
FATAL=[('input','','s_fatal_cert_valid'),('input','[355:0]','s_fatal_context'),
    ('input','[23:0]','s_fatal_received_psn'),('input','[23:0]','s_fatal_expected_psn'),
    ('input','[7:0]','s_fatal_syndrome'),('input','','fatal_report_release'),
    ('output','','m_fatal_held'),('output','[355:0]','m_fatal_context'),
    ('output','[527:0]','m_fatal_wire'),('output','','m_fatal_wire_valid'),('input','','m_fatal_wire_ready'),
    ('output','[479:0]','m_fatal_retire_owner'),('output','','m_fatal_retire_taken'),
    ('output','[479:0]','m_report_owner'),('output','','m_report_taken')]


def derive():
    t=once(SOURCE.read_text(),'module rocev2_write_psn_control #(','module '+NAME+' #(')
    t=once(t,' input wire clk,rst,enable,parent_fault,',
        ''.join(' '+d+' wire '+(w+' 'if w else'')+n+',\n'for d,w,n in FATAL)+' input wire clk,rst,enable,parent_fault,')
    t=once(t,'reg [2:0] state=IDLE;', 'reg [2:0] state=IDLE;\nreg fatal_pending=0;')
    t=once(t,'wire request=enable===', 'wire psn_request=enable===')
    t=once(t,'wire context_ok=current_ok', 'wire psn_context_ok=current_ok')
    at=t.index('wire [23:0] delta=')
    t=t[:at]+r'''
wire fatal_request=enable===1'b1 && s_valid===1'b1 && s_fatal_cert_valid===1'b1;
wire fatal_context_ok=current_ok && error_known &&
 (^{s_fatal_context,s_fatal_received_psn,s_fatal_expected_psn,s_fatal_syndrome})!==1'bx &&
 s_fatal_context===trusted_context && s_qpn===s_fatal_context[23:0] &&
 s_psn===s_fatal_received_psn && s_fatal_received_psn===trusted_expected_psn &&
 s_fatal_expected_psn===trusted_expected_psn &&
 (s_error==16 && s_fatal_syndrome==8'h61 || s_error>=1 && s_error<=4 && s_fatal_syndrome==8'h62);
wire request=psn_request || fatal_request;
wire context_ok=fatal_request ? fatal_context_ok:psn_context_ok;
'''+t[at:]
    t=once(t,'wire wire_request=request && (future || duplicate) && !repeat_nak;',
        'wire wire_request=fatal_request || psn_request && (future || duplicate) && !repeat_nak;')
    t=once(t,'wire input_ok=error_known &&',
        "wire input_ok=(s_fatal_cert_valid===1'b0 || s_fatal_cert_valid===1'b1) && !(psn_request && fatal_request) && error_known &&")
    a=t.index('wire stable_reject=');b=t.index('wire done_match=',a)
    old=t[a:b].replace('wire stable_reject=','wire psn_stable_reject=',1)
    t=t[:a]+old+r'''
wire fatal_stable_reject=s_valid===1'b1 && s_fatal_cert_valid===1'b1 && fatal_context_ok &&
 {s_error,s_qpn,s_psn,s_msn,s_keep_message}===reject_snapshot && s_fatal_context===owner[355:0] &&
 s_fatal_received_psn===owner[467:444] && s_fatal_expected_psn===owner[443:420] && s_fatal_syndrome===owner[475:468];
wire stable_reject=fatal_pending ? fatal_stable_reject:psn_stable_reject;
'''+t[b:]
    t=once(t,'assign s_ack_done_ready=state==PROOF && done_match && !halted && !rst;',
        "assign s_ack_done_ready=state==PROOF && done_match && (!fatal_pending || m_fatal_wire_ready===1'b1) && !halted && !rst;")
    anchor='(state==IDLE && !wire_request) || state==REPORT'
    if t.count(anchor)!=2:raise ValueError('both original independent local handshake gates required')
    t=t.replace(anchor,anchor+" && (!fatal_pending || fatal_report_release===1'b1)")
    # Both old handshakes get the same fatal release condition; no ready-only
    # certificate or independent one-sided local/error-owner consumption.
    t=once(t,'always @(posedge clk)begin',r'''
assign m_fatal_held=(retained && fatal_pending) || (state==IDLE && fatal_request);
assign m_fatal_context=retained ? owner[355:0]:s_fatal_context;
assign m_fatal_wire=s_ack_done;
assign m_fatal_wire_valid=state==PROOF && fatal_pending && s_ack_done_valid && done_match && !halted && !rst;
assign m_fatal_retire_owner=owner;
assign m_fatal_retire_taken=m_ack_retire_valid && m_ack_retire_ready && fatal_pending;
assign m_report_owner=owner;
assign m_report_taken=state==REPORT && fatal_pending && s_valid && s_ready;
always @(posedge clk)begin''')
    t=once(t,'state<=IDLE;owner<=0;reject_snapshot<=0;last_serial<=INITIAL_SERIAL;',
        'state<=IDLE;fatal_pending<=0;owner<=0;reject_snapshot<=0;last_serial<=INITIAL_SERIAL;')
    t=once(t,'if(parent_fault!==1\'b0 || s_valid',
        "if(s_valid===1'b1 && (s_fatal_cert_valid!==1'b0 && s_fatal_cert_valid!==1'b1 || psn_request && fatal_request) || parent_fault!==1'b0 || s_valid")
    anchor='''owner<={4'd0,future ? 8'h60:8'h1f,s_cert_received_psn,
      future ? s_cert_expected_psn:s_cert_expected_psn-24'd1,last_serial+64'd1,s_cert_context};'''
    t=once(t,anchor,"fatal_pending<=fatal_request;\n     owner<=fatal_request ? {4'd0,s_fatal_syndrome,s_fatal_received_psn,s_fatal_expected_psn,last_serial+64'd1,s_fatal_context}:"+anchor[len('owner<='):])
    return once(t,'state<=IDLE;owner<=0;reject_snapshot<=0;end',
        'state<=IDLE;fatal_pending<=0;owner<=0;reject_snapshot<=0;end')
