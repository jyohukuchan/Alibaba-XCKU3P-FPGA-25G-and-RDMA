# SPDX-License-Identifier: BSD-2-Clause-Views
"""Retained segmented WRITE RNR on the SAME native HLS/MR/ACK graph.

Actual reject metadata, native identity and shared fresh-tag negative wire
proof; no invented RQ/DMA/PSN/CQ grant. Preserve ordinary RNR and all positive
visibility fences. Source integration requires fresh complete native runtime.
"""
import derive_segmented_write_profile as parent
import derive_receive_write_rnr_ack as ack

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
native=parent.parent;gateway=native.parent
HELPER=RTL/'rocev2_segmented_write_rnr_control.v'
FLOW=[('input','[55:0]','s_write_rnr_event'),('input','','s_write_rnr_event_valid'),
    ('output','','s_write_rnr_event_ready'),('input','','s_write_rnr_tx_release')]


def rnic(t):
    # Only the actual controller producer is intercepted; keep the original
    # reject mux and local consumer as the downstream, independent handshake.
    t=once(t,'.m_reject_valid(s_write_reject_valid),','.m_reject_valid(write_reject_valid),')
    t=once(t,'.m_reject_ready(s_write_reject_ready),','.m_reject_ready(write_reject_ready),')
    declarations=native.declarations(FLOW)+'''wire write_reject_valid,write_reject_ready;
wire [367:0] write_rnr_ack_owner,write_rnr_ack_retire_owner;
wire [383:0] write_rnr_ack_done;
wire write_rnr_ack_owner_valid,write_rnr_ack_owner_ready,write_rnr_ack_done_valid,write_rnr_ack_done_ready;
wire write_rnr_ack_retire_valid,write_rnr_ack_retire_ready,write_rnr_guard,write_rnr_fault;
wire [7:0] write_rnr_queue_guard,write_rnr_fault_code;
wire [31:0] write_rnr_requests,write_rnr_proofs,write_rnr_retirements,write_rnr_reports;
'''
    pins=dict(clk='clk',rst='rst',enable='RNR_ENABLE!=0',
        parent_fault='parent_fault || fault || write_controller_fault',
        trusted_valid='m_write_native_context_valid',trusted_identity='m_write_native_context[103:0]',
        expected_psn='m_write_expected_psn',message_context='write_ctl_message_context',
        message_active='s_write_message_active',mr_guard='s_write_mr_guard',message_queue_guard='s_write_queue_guard',
        s_error='s_write_reject_error',s_qpn='s_write_reject_qpn',s_psn='s_write_reject_psn',
        s_msn='write_ctl_m_reject_msn',s_keep_message='write_ctl_m_reject_keep_message',
        s_valid='write_reject_valid',s_ready='write_reject_ready',
        m_error_valid='s_write_reject_valid',m_error_ready='s_write_reject_ready',
        m_ack_owner='write_rnr_ack_owner',m_ack_owner_valid='write_rnr_ack_owner_valid',m_ack_owner_ready='write_rnr_ack_owner_ready',
        s_ack_done='write_rnr_ack_done',s_ack_done_valid='write_rnr_ack_done_valid',s_ack_done_ready='write_rnr_ack_done_ready',
        m_ack_retire_owner='write_rnr_ack_retire_owner',m_ack_retire_valid='write_rnr_ack_retire_valid',m_ack_retire_ready='write_rnr_ack_retire_ready',
        m_hls_event='s_write_rnr_event',m_hls_event_valid='s_write_rnr_event_valid',m_hls_event_ready='s_write_rnr_event_ready',
        tx_release='s_write_rnr_tx_release',configuration_guard='write_rnr_guard',queue_guard='write_rnr_queue_guard',
        fault='write_rnr_fault',fault_code='write_rnr_fault_code',requests='write_rnr_requests',
        wire_proofs='write_rnr_proofs',retirements='write_rnr_retirements',reports='write_rnr_reports')
    logic=declarations+'rocev2_segmented_write_rnr_control write_rnr_control(\n'+',\n'.join(
        '.'+n+'('+v+')'for n,v in pins.items())+'\n);\n'
    t=once(t,'reg write_fault_latched=0;',logic+'reg write_fault_latched=0;')
    t=once(t,'else if(write_controller_fault)write_fault_latched<=1;',
        'else if(write_controller_fault || write_rnr_fault)write_fault_latched<=1;')
    t=once(t,'assign atomic_lease_guard=zero_wire_guard ||',
        'assign atomic_lease_guard=write_rnr_guard || zero_wire_guard ||')
    t=once(t,'assign local_execution_guard=zero_wire_queue_guard |',
        'assign local_execution_guard=write_rnr_queue_guard | zero_wire_queue_guard |')
    t=once(t,'    .m_recv_message_data(rq_message_data),',
        gateway.connections(FLOW)+'    .m_recv_message_data(rq_message_data),')
    t=once(t,native.ack.NAME+' #(',ack.NAME+' #(')
    pins=dict(s_rnr_owner='write_rnr_ack_owner',s_rnr_owner_valid='write_rnr_ack_owner_valid',
        s_rnr_owner_ready='write_rnr_ack_owner_ready',m_rnr_done_data='write_rnr_ack_done',
        m_rnr_done_valid='write_rnr_ack_done_valid',m_rnr_done_ready='write_rnr_ack_done_ready',
        s_rnr_retire_owner='write_rnr_ack_retire_owner',s_rnr_retire_valid='write_rnr_ack_retire_valid',
        s_rnr_retire_ready='write_rnr_ack_retire_ready')
    a=t.index(ack.NAME+' #(');b=t.index(');',a)+2;block=t[a:b]
    block=once(block,'    .prior_response_drained(response_tx_quiescent),',
        ''.join('    .'+n+'('+v+'),\n'for n,v in pins.items())+'    .prior_response_drained(response_tx_quiescent),')
    return t[:a]+block+t[b:]


def protected(t):
    t=gateway.ports(t,FLOW)
    logic='''// One actual HLS RNR event input, with mutually exclusive producers.
wire [55:0] shared_rnr_event_data=s_write_rnr_event_valid ? s_write_rnr_event:rnr_event_data;
wire shared_rnr_event_valid=RNR_ENABLE && (rnr_event_valid || s_write_rnr_event_valid) && !write_rnr_collision;
wire shared_rnr_event_ready;
wire write_rnr_collision=(s_write_rnr_event_valid!==1'b0 && s_write_rnr_event_valid!==1'b1) ||
    (s_write_rnr_event_valid && (rnr_event_valid!==1'b0 || s_write_held!==1'b1 || s_write_mr_guard!==1'b1));
reg write_rnr_bad=0;
always @(posedge clk)begin if(rst)write_rnr_bad<=0;else if(write_rnr_collision)write_rnr_bad<=1;end
assign rnr_event_ready=shared_rnr_event_ready && s_write_rnr_event_valid===1'b0 && !write_rnr_bad;
assign s_write_rnr_event_ready=RNR_ENABLE && shared_rnr_event_ready && rnr_event_valid===1'b0 && !write_rnr_bad;
'''
    t=once(t,'wire rnr_event_ready;','wire rnr_event_ready;\n'+logic)
    t=once(t,'wire atomic_native_fault=write_dispatch_fault ||',
        'wire atomic_native_fault=write_rnr_bad || write_dispatch_fault ||')
    t=once(t,'.s_rnr_event_tdata(rnr_event_data),.s_rnr_event_tvalid(rnr_event_valid),.s_rnr_event_tready(rnr_event_ready),',
        '.s_rnr_event_tdata(shared_rnr_event_data),.s_rnr_event_tvalid(shared_rnr_event_valid),.s_rnr_event_tready(shared_rnr_event_ready),')
    gate='(s_write_held && s_write_tx_release)'
    if t.count(gate)!=2:raise ValueError('both original positive visibility gates must remain')
    return t.replace(gate,'(s_write_held && (s_write_tx_release || s_write_rnr_tx_release))')


def derive():
    out=parent.derive()
    for name in gateway.WRAPPERS:
        p=RTL/(name+'.v')
        if name=='rocev2_native_rnic_endpoint':out[p]=rnic(out[p]);continue
        t=gateway.ports(out[p],FLOW)
        out[p]=once(t,'    .m_recv_message_data(m_recv_message_data),',
            gateway.connections(FLOW)+'    .m_recv_message_data(m_recv_message_data),')
    p=RTL/'rocev2_protected_responder.v';out[p]=protected(out[p])
    del out[RTL/(native.ack.NAME+'.v')]
    out[RTL/(ack.NAME+'.v')]=ack.derive()
    out[HELPER]=HELPER.read_text()
    return out
