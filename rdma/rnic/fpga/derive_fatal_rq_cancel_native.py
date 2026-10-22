# SPDX-License-Identifier: BSD-2-Clause-Views
"""Optional real fatal-join-authorized RQC cancellation, never global STOP.

Only completed native selected1000/current full SQC context may distinguish
the permanent quarantine bit from an active wire lease for RQC command4.
All allocation/retire/posting/admission/SQC guards remain, and actual RQ
cancel, fetch/parent/work/wire/CQ drain and full owner/nonce proof are required.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from segmented_write_payload_native_fixture import once

ROOT=Path(__file__).resolve().parents[3]
AUTHORITY=ROOT/'rdma/rnic/rtl/rocev2_fatal_rq_cancel_authority.v'


def derive(top,sq,control,fec):
    logic='''wire [7:0] fatal_rq_cancel_authorized;
wire fatal_rq_cancel_fault,fatal_cancel_other_lease_guard;
wire [7:0] fatal_rq_cancel_fault_code;
rocev2_fatal_rq_cancel_authority fatal_rq_cancel_authority(
 .clk(clk),.rst(rst),.parent_fault(parent_fault || fault),
 .event_data(fatal_join_selected),.event_taken(fatal_join_valid && fatal_join_ready),
 .trusted_valid(m_write_native_context_valid),.trusted_context(m_write_native_context),.trusted_psn(m_write_expected_psn),
 .quarantined(write_abort_quarantined),.noncontrol_lease_guard(fatal_cancel_other_lease_guard),
 .cancel_only_authorized(fatal_rq_cancel_authorized),.fault(fatal_rq_cancel_fault),.fault_code(fatal_rq_cancel_fault_code));
'''
    top=once(top,'reg write_fault_latched=0;',logic+'reg write_fault_latched=0;')
    top=once(top,'write_control_fault || write_abort_fault)write_fault_latched<=1;',
        'write_control_fault || write_abort_fault || fatal_rq_cancel_fault)write_fault_latched<=1;')
    top=once(top,'assign fault_code=msn_fault ?',"assign fault_code=fatal_rq_cancel_fault ? 8'he7 : msn_fault ?")
    a=top.index('assign atomic_lease_guard=s_control_held || ');b=top.index(';',a)+1
    original=top[a:b];other=original[len('assign atomic_lease_guard=s_control_held || '):-1]
    top=top[:a]+'assign fatal_cancel_other_lease_guard='+other+';\nassign atomic_lease_guard=s_control_held || fatal_cancel_other_lease_guard;'+top[b:]
    top=once(top,'.s_fatal_selected(fatal_mailbox_selected),',
        '.s_fatal_rq_cancel_authorized(fatal_rq_cancel_authorized),\n.s_fatal_selected(fatal_mailbox_selected),')
    sq=once(sq,'    input wire clk,','    input wire [7:0] s_fatal_rq_cancel_authorized,\n    input wire clk,')
    old='rocev2_sq_control_regs #(.MAX_QPS(MAX_QPS),.CONTROL_ID(32\'h52514331),.RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE),.IMMEDIATE_ENABLE(1)) receive_queue_control('
    sq=once(sq,old,old.replace('rocev2_sq_control_regs','rocev2_fatal_rq_control_regs',1)+
        '\n.s_fatal_cancel_authorized(s_fatal_rq_cancel_authorized),\n.s_fatal_cancel_wire_guard(wire_queue_guard | fatal_event_queue_guard),')
    # Leave BOTH original full quarantine configuration guards byte-identical.
    control=once(control,'module rocev2_sq_control_regs #(','module rocev2_fatal_rq_control_regs #(')
    control=once(control,'    input wire clk,',
        '    input wire [7:0] s_fatal_cancel_authorized,s_fatal_cancel_wire_guard,\n    input wire clk,')
    old='!wire_queue_guard[qi] && !completion_queue_guard[qi] && !endpoint_fault;'
    new="((snapshot[1]==4 && s_fatal_cancel_authorized[qi]===1'b1) ?\n    s_fatal_cancel_wire_guard[qi]===1'b0:!wire_queue_guard[qi]) && !completion_queue_guard[qi] && !endpoint_fault;"
    control=once(control,old,new)
    # New explicit bit4: private native RQC command4 can use the completed
    # fatal-join/current-context distinction. Old feature15 readers refuse it.
    fec=once(fec,"8:rd=32'h0000000f;","8:rd=32'h0000001f;")
    return top,sq,control,fec
