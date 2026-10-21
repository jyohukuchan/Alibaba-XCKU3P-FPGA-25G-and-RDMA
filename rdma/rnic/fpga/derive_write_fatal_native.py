# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual fatal61/62 admission/quarantine/abort/cancel source graph.

Source derivation is NOT native runtime or full fatal-QP recovery. Selected
certificate output is not error CQ/STOP/global drain/unpin; quarantine stays.
No63 classification, packet-MR internal failure recovery or default changes
are invented. Full same-generation abort HLS and fresh native cases required.
"""
import derive_write_psn_control_native as parent
import derive_write_error_control as error
ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;gateway=parent.gateway;native=parent.native
HLS_TOP='rocev2_native_write_abort_top'
CERT=[('output','','m_fatal_certified'),('output','[355:0]','m_fatal_context'),
    ('output','[23:0]','m_fatal_received_psn'),('output','[23:0]','m_fatal_expected_psn'),
    ('output','[7:0]','m_fatal_syndrome')]
CANCEL=[('input','[319:0]','s_error_cancel_context'),('input','','s_error_cancel_valid'),
    ('input','','s_error_cancel_certified'),('output','','s_error_cancel_ready')]
HLS=[('input','[959:0]','s_write_abort_owner'),('input','','s_write_abort_owner_valid'),('output','','s_write_abort_owner_ready'),
    ('output','[991:0]','m_write_abort_done'),('output','','m_write_abort_done_valid'),('input','','m_write_abort_done_ready'),
    ('output','','m_write_abort_hls_fault')]
FIELDS=HLS+[('input','[7:0]','s_write_abort_guard')]
TERMINAL=[('output','[999:0]','m_write_fatal_selected'),('output','','m_write_fatal_selected_valid'),('input','','m_write_fatal_selected_ready')]
BRIDGE=RTL/'rocev2_write_abort_control.v'
GUARD=RTL/'rocev2_remote_write_message_guard.v'
GUARD_NAME='rocev2_fatal_write_message_guard'


def guard():
    t=once(GUARD.read_text(),'module rocev2_remote_write_message_guard #(','module '+GUARD_NAME+' #(')
    # Invalid keys/addresses must be classified by the SAME actual WHOLE MR
    # lookup before any packet owner/DMA grant, not mislabeled semantic16.
    t=once(t,'!message_active && reth_known && s_packet_reth_key!=0 &&',
        '!message_active && reth_known &&')
    return once(t,"s_packet_reth_length<=1048576 &&\n    input_reth_end<=65'h10000000000000000 :",
        's_packet_reth_length<=1048576 :')


def frontend():
    t=gateway.ports(parent.frontend(),CERT)
    t=once(t,'reg snapshot_valid=0;',r'''reg snapshot_valid=0;
reg fatal_request_qualified=0;reg [23:0] fatal_expected_psn=0;
// Only actual metadata-path rejects AFTER the complete checked-frame peer,
// format and native expected-PSN chain are authority. Local REJECT16/17,
// bad ICRC, unknown response fields or internal packet-MR faults are NOT.
assign m_fatal_certified=state==ADMIT && guard_reject_valid && fatal_request_qualified &&
 (guard_reject_error==16 || guard_reject_error>=1 && guard_reject_error<=4) && !halted && !rst;
assign m_fatal_context=frame_context;
assign m_fatal_received_psn=packet_psn;
assign m_fatal_expected_psn=fatal_expected_psn;
assign m_fatal_syndrome=m_fatal_certified ? (guard_reject_error==16 ? 8'h61:8'h62):8'd0;''')
    t=once(t,'control_certified<=0;control_context<=0;control_received_psn<=0;control_expected_psn<=0;',
        'control_certified<=0;control_context<=0;control_received_psn<=0;control_expected_psn<=0;\n  fatal_request_qualified<=0;fatal_expected_psn<=0;')
    t=once(t,'   PARSE:begin\n', '   PARSE:begin\n    fatal_request_qualified<=0;\n')
    t=once(t,'    else state<=METADATA;',
        '    else begin fatal_request_qualified<=1;fatal_expected_psn<=trusted_expected_psn;state<=METADATA;end')
    t=once(t,'if(m_reject_valid && m_reject_ready)begin state<=COLLECT;',
        'if(m_reject_valid && m_reject_ready)begin fatal_request_qualified<=0;state<=COLLECT;')
    return once(t,'rocev2_remote_write_message_guard #(',GUARD_NAME+' #(')


def controller():
    t=gateway.ports(parent.controller(),CERT+CANCEL)
    t=once(t,' .m_reject_error(m_reject_error),',gateway.connections(CERT)+' .m_reject_error(m_reject_error),')
    t=once(t,".s_cancel_context(320'd0),.s_cancel_valid(1'b0),.cancel_drained(1'b0),.s_cancel_ready(),",
        '.s_cancel_context(s_error_cancel_context),.s_cancel_valid(s_error_cancel_valid),.cancel_drained(s_error_cancel_certified),.s_cancel_ready(s_error_cancel_ready),')
    return once(t,'// Partial-message HLS teardown is NOT proved: cancellation stays disabled,\n// and reset is never a safe drain/unpin certificate.',
        '// Selected cancellation requires actual abort992/native proof; NOT a\n// global drain/STOP/unpin certificate. Reset is never a drain certificate.')


def rnic(t):
    t=gateway.ports(t,TERMINAL)
    t=once(t,'rocev2_write_psn_control write_psn_control(',error.NAME+' write_psn_control(')
    extra=native.declarations(FIELDS+[(d,w,'write_ctl_'+n)for d,w,n in CERT]+CANCEL)+r'''
wire error_control_guard,error_fatal_held,error_fatal_wire_valid,error_fatal_wire_ready;
wire [7:0] error_control_queue_guard,abort_control_queue_guard,write_abort_quarantined;
wire [355:0] error_fatal_context;
wire [527:0] error_fatal_wire;
wire [479:0] error_fatal_retire_owner,error_report_owner;
wire error_fatal_retire_taken,error_report_taken,abort_report_release,abort_control_guard,write_abort_fault;
wire [7:0] write_abort_fault_code;
wire [31:0] write_abort_requests,write_abort_HLS_completions,write_abort_cancels,write_abort_completions;
assign s_control_held=error_control_guard || abort_control_guard;
assign s_control_queue_guard=error_control_queue_guard | abort_control_queue_guard;
assign s_write_abort_guard=abort_control_queue_guard |
 (error_fatal_held && error_fatal_context[23:0]<8 ? 8'h01<<error_fatal_context[23:0]:8'd0);
'''
    t=once(t,'reg write_fault_latched=0;',extra+'reg write_fault_latched=0;')
    t=once(t,'else if(write_controller_fault || write_rnr_fault || write_control_fault)',
        'else if(write_controller_fault || write_rnr_fault || write_control_fault || write_abort_fault)')
    t=once(t,'.configuration_guard(s_control_held),','.configuration_guard(error_control_guard),')
    t=once(t,'.queue_guard(s_control_queue_guard),','.queue_guard(error_control_queue_guard),')
    pins={n:'write_ctl_'+n.replace('s_fatal_cert_valid','m_fatal_certified').replace('s_fatal_','m_fatal_')
        for _,_,n in error.FATAL if n.startswith('s_fatal_')}
    pins.update(fatal_report_release='abort_report_release',m_fatal_held='error_fatal_held',m_fatal_context='error_fatal_context',
        m_fatal_wire='error_fatal_wire',m_fatal_wire_valid='error_fatal_wire_valid',m_fatal_wire_ready='error_fatal_wire_ready',
        m_fatal_retire_owner='error_fatal_retire_owner',m_fatal_retire_taken='error_fatal_retire_taken',
        m_report_owner='error_report_owner',m_report_taken='error_report_taken')
    a=t.index(error.NAME+' write_psn_control(');b=t.index(');',a)
    t=t[:b]+',\n'+',\n'.join('.'+n+'('+v+')'for n,v in pins.items())+t[b:]
    t=once(t,' .m_reject_error(s_write_reject_error),',
        gateway.connections(CERT,{n:'write_ctl_'+n for _,_,n in CERT})+' .m_reject_error(s_write_reject_error),') if ' .m_reject_error(s_write_reject_error),'in t else once(t,
        '.m_reject_error(s_write_reject_error),',gateway.connections(CERT,{n:'write_ctl_'+n for _,_,n in CERT})+'.m_reject_error(s_write_reject_error),')
    t=once(t,'.m_packet_commit_token(s_write_commit_token),',gateway.connections(CANCEL)+'.m_packet_commit_token(s_write_commit_token),')
    pins=dict(clk='clk',rst='rst',enable='RECV_ENABLE!=0 && DUPLEX_ENABLE!=0',parent_fault='parent_fault || fault || write_controller_fault || write_control_fault || write_rnr_fault',
        trusted_valid='m_write_native_context_valid',trusted_context='m_write_native_context',trusted_expected_psn='m_write_expected_psn',
        message_context='write_ctl_message_context',message_active='s_write_message_active',
        quarantine_context='m_write_native_context',quarantine_valid="m_write_native_context_valid && (s_write_abort_guard[m_write_native_context[23:0]]===1'b1)",
        positive_wire='write_ack_done',positive_wire_taken='write_ack_done_valid && write_ack_done_ready',
        positive_commit_token='s_write_commit_token',positive_commit_msn='s_write_commit_msn',positive_commit_proofs='s_write_commit_proofs',
        positive_commit_taken='s_write_commit_valid && s_write_commit_ready',positive_retire_token='write_ack_retire_token',positive_retire_taken='write_ack_retire_valid && write_ack_retire_ready',
        error_wire='error_fatal_wire',error_wire_valid='error_fatal_wire_valid',error_wire_ready='error_fatal_wire_ready',
        error_retire_owner='error_fatal_retire_owner',error_retire_taken='error_fatal_retire_taken',
        m_hls_owner='s_write_abort_owner',m_hls_owner_valid='s_write_abort_owner_valid',m_hls_owner_ready='s_write_abort_owner_ready',
        s_hls_done='m_write_abort_done',s_hls_done_valid='m_write_abort_done_valid',s_hls_done_ready='m_write_abort_done_ready',
        m_report_release='abort_report_release',local_report_owner='error_report_owner',local_report_taken='error_report_taken',
        m_cancel_context='s_error_cancel_context',m_cancel_valid='s_error_cancel_valid',m_cancel_certified='s_error_cancel_certified',m_cancel_ready='s_error_cancel_ready',
        m_done='m_write_fatal_selected',m_done_valid='m_write_fatal_selected_valid',m_done_ready='m_write_fatal_selected_ready',
        configuration_guard='abort_control_guard',queue_guard='abort_control_queue_guard',quarantined='write_abort_quarantined',
        fault='write_abort_fault',fault_code='write_abort_fault_code',requests='write_abort_requests',hls_completions='write_abort_HLS_completions',cancels='write_abort_cancels',completions='write_abort_completions')
    logic='rocev2_write_abort_control write_abort_control(\n'+',\n'.join('.'+n+'('+v+')'for n,v in pins.items())+'\n);\n'
    t=once(t,'reg write_fault_latched=0;',logic+'reg write_fault_latched=0;')
    return once(t,'    .m_recv_message_data(rq_message_data),',gateway.connections(FIELDS)+'    .m_recv_message_data(rq_message_data),')


def protected(t):
    t=gateway.ports(t,FIELDS)
    logic=r'''
wire abort_external_bad=(^s_write_abort_guard)===1'bx ||
 (s_write_abort_owner_valid!==1'b0 && s_write_abort_owner_valid!==1'b1) ||
 (s_write_abort_owner_valid && (s_control_held!==1'b1 || local_qpn>=8 ||
 s_write_abort_guard[local_qpn]!==1'b1 || m_write_native_context_valid!==1'b1 ||
 s_write_abort_owner[779:424]!==current_rx_context));
'''
    t=once(t,'wire control_shared_owner_ready;',logic+'wire control_shared_owner_ready;')
    t=once(t,'wire atomic_native_fault=',
        'wire atomic_native_fault=abort_external_bad || m_write_abort_hls_fault || ')
    t=once(t,'assign m_write_admission_ready=ordinary_idle',
        "assign m_write_admission_ready=(s_write_abort_guard[local_qpn]===1'b0) && ordinary_idle")
    return once(t,'    .m_recv_message_data(m_recv_message_data),',gateway.connections(FIELDS,{
        's_write_abort_owner_valid':'s_write_abort_owner_valid && !abort_external_bad && !fault'})+'    .m_recv_message_data(m_recv_message_data),')


def shared(t):
    t=gateway.ports(t,FIELDS)
    logic=r'''
wire abort_core_owner_ready,abort_core_done_valid,abort_core_fault;
wire abort_unowned_offer=(s_write_abort_owner_valid && (s_control_held!==1'b1 || s_write_abort_guard==0)) ||
 (abort_core_done_valid && s_control_held!==1'b1);
assign s_write_abort_owner_ready=abort_core_owner_ready && s_control_held===1'b1 && !fault && !rst;
assign m_write_abort_done_valid=abort_core_done_valid && s_control_held===1'b1 && !fault && !rst;
assign m_write_abort_hls_fault=abort_core_fault;
'''
    t=once(t,'wire control_core_owner_ready,control_core_done_valid,control_core_fault;',
        logic+'wire control_core_owner_ready,control_core_done_valid,control_core_fault;')
    t=once(t,'wire incoming_fault=','wire incoming_fault=abort_core_fault || abort_unowned_offer || ')
    return once(t,'.m_recv_message_data(core_recv_message_data),',gateway.connections(HLS,{
        's_write_abort_owner_ready':'abort_core_owner_ready','m_write_abort_done_valid':'abort_core_done_valid',
        'm_write_abort_hls_fault':'abort_core_fault',
        's_write_abort_owner_valid':"s_write_abort_owner_valid && s_control_held===1'b1 && !fault",
        'm_write_abort_done_ready':"m_write_abort_done_ready && s_control_held===1'b1 && !fault"})+'.m_recv_message_data(core_recv_message_data),')


def derive():
    out=parent.derive()
    for name in gateway.WRAPPERS:
        path=RTL/(name+'.v')
        if name=='rocev2_native_rnic_endpoint':out[path]=rnic(out[path]);continue
        t=gateway.ports(out[path],FIELDS)
        out[path]=once(t,'    .m_recv_message_data(m_recv_message_data),',gateway.connections(FIELDS)+'    .m_recv_message_data(m_recv_message_data),')
    path=RTL/'rocev2_protected_responder.v';out[path]=protected(out[path])
    path=RTL/'rocev2_shared_hls_transport.v';out[path]=shared(out[path])
    path=ROOT/'rdma/rtl/rocev2_integrity_transport.v';t=gateway.ports(out[path],HLS)
    t=once(t,parent.HLS_TOP+' transport (',HLS_TOP+' transport (')
    mapping=dict(s_write_abort_owner='s_axis_write_abort_owner_TDATA',s_write_abort_owner_valid='s_axis_write_abort_owner_TVALID',
        s_write_abort_owner_ready='s_axis_write_abort_owner_TREADY',m_write_abort_done='m_axis_write_abort_done_TDATA',
        m_write_abort_done_valid='m_axis_write_abort_done_TVALID',m_write_abort_done_ready='m_axis_write_abort_done_TREADY',m_write_abort_hls_fault='regWriteAbortFault')
    out[path]=once(t,'    .m_axis_recv_message_TDATA(m_recv_message_data),',
        ''.join('    .'+mapping[n]+'('+n+'),\n'for _,_,n in HLS)+'    .m_axis_recv_message_TDATA(m_recv_message_data),')
    out[RTL/(native.leaves.FRONT_NAME+'.v')]=frontend()
    out[RTL/(native.CTRL_NAME+'.v')]=controller()
    del out[parent.HELPER];out[RTL/(error.NAME+'.v')]=error.derive()
    out[BRIDGE]=BRIDGE.read_text();out[RTL/(GUARD_NAME+'.v')]=guard()
    return out
