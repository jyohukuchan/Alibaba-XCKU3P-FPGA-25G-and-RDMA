# SPDX-License-Identifier: BSD-2-Clause-Views
"""Certified WRITE PSN control on SAME native/HLS/ACK graph, not runtime proof.

Only actual checked-frame trusted/peer/format PSN18 rejects are certified.
Future-PSN NAK and duplicate ACK never replay WRITE or grant RQ/data/CQ/PSN.
Keep every old source/default and real namespace; require fresh native tests.
"""
import derive_segmented_write_rnr_native as parent
import derive_receive_control_ack as ack

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
native=parent.native;gateway=parent.gateway
HLS_TOP='rocev2_native_control_response_top'
HELPER=RTL/'rocev2_write_psn_control.v'
CERT=[('output','','m_control_certified'),('output','[355:0]','m_control_context'),
    ('output','[23:0]','m_control_received_psn'),('output','[23:0]','m_control_expected_psn')]
HLS=[('input','[479:0]','s_control_owner'),('input','','s_control_owner_valid'),('output','','s_control_owner_ready'),
    ('output','[511:0]','m_control_done'),('output','','m_control_done_valid'),('input','','m_control_done_ready'),
    ('output','','m_control_hls_fault')]
GUARDS=[('input','','s_control_held'),('input','[7:0]','s_control_queue_guard'),('input','','s_control_tx_release')]
FIELDS=HLS+GUARDS


def frontend():
    t=native.leaves.frontend()
    t=once(t,'    input wire clk,input wire rst,',
        ''.join('    '+d+' wire '+(w+' 'if w else'')+n+',\n'for d,w,n in CERT)+'    input wire clk,input wire rst,')
    t=once(t,'reg snapshot_valid=0;',r'''reg snapshot_valid=0;
reg control_certified=0;
reg [355:0] control_context=0;
reg [23:0] control_received_psn=0,control_expected_psn=0;
assign m_control_certified=control_certified && state==REJECT && reject_error==18 && !halted && !rst;
assign m_control_context=control_context;
assign m_control_received_psn=control_received_psn;
assign m_control_expected_psn=control_expected_psn;''')
    t=once(t,'reject_error<=0;reject_qpn<=0;reject_psn<=0;frame_context<=0;snapshot_valid<=0;',
        'reject_error<=0;reject_qpn<=0;reject_psn<=0;frame_context<=0;snapshot_valid<=0;\n'
        '  control_certified<=0;control_context<=0;control_received_psn<=0;control_expected_psn<=0;')
    t=once(t,'   PARSE:begin\n', '   PARSE:begin\n    control_certified<=0;\n')
    t=once(t,'    else if(packet_psn!=trusted_expected_psn)reject_error<=18;',r'''    else if(packet_psn!=trusted_expected_psn)begin
     // Reached ONLY after enable/trusted/full-peer/format checks on the
     // genuine upstream checked frame. Local error16/17 is never a NAK grant.
     reject_error<=18;control_certified<=1;control_context<=frame_context;
     control_received_psn<=packet_psn;control_expected_psn<=trusted_expected_psn;
    end''')
    t=once(t,'   REJECT:if(m_reject_valid && m_reject_ready)begin',
        '   REJECT:if(m_reject_valid && m_reject_ready)begin\n    control_certified<=0;')
    return t


def controller():
    t=gateway.ports(native.native_controller(),CERT)
    return once(t,' .m_reject_error(m_reject_error),',
        gateway.connections(CERT)+' .m_reject_error(m_reject_error),')


def rnic(t):
    t=once(t,'.m_reject_valid(write_reject_valid),','.m_reject_valid(control_reject_valid),')
    t=once(t,'.m_reject_ready(write_reject_ready),','.m_reject_ready(control_reject_ready),')
    t=once(t,'.m_reject_error(s_write_reject_error),',
        gateway.connections(CERT,{n:'write_ctl_'+n for _,_,n in CERT})+'.m_reject_error(s_write_reject_error),')
    logic=native.declarations(FIELDS+[(d,w,'write_ctl_'+n)for d,w,n in CERT])+'''wire control_reject_valid,control_reject_ready;
wire [479:0] write_control_ack_owner,write_control_ack_retire_owner;
wire [527:0] write_control_ack_done;
wire write_control_ack_owner_valid,write_control_ack_owner_ready,write_control_ack_done_valid,write_control_ack_done_ready;
wire write_control_ack_retire_valid,write_control_ack_retire_ready,write_control_fault;
wire [7:0] write_control_fault_code;
wire [31:0] write_control_requests,write_control_proofs,write_control_retirements,write_control_reports,write_control_suppressed;
'''
    pins=dict(clk='clk',rst='rst',enable='RECV_ENABLE!=0 && DUPLEX_ENABLE!=0',
        parent_fault='parent_fault || fault || write_controller_fault || write_rnr_fault',
        trusted_valid='m_write_native_context_valid',trusted_context='m_write_native_context',trusted_expected_psn='m_write_expected_psn',
        s_error='s_write_reject_error',s_qpn='s_write_reject_qpn',s_psn='s_write_reject_psn',
        s_msn='write_ctl_m_reject_msn',s_keep_message='write_ctl_m_reject_keep_message',
        s_valid='control_reject_valid',s_ready='control_reject_ready',
        s_cert_valid='write_ctl_m_control_certified',s_cert_context='write_ctl_m_control_context',
        s_cert_received_psn='write_ctl_m_control_received_psn',s_cert_expected_psn='write_ctl_m_control_expected_psn',
        m_error_valid='write_reject_valid',m_error_ready='write_reject_ready',
        m_ack_owner='write_control_ack_owner',m_ack_owner_valid='write_control_ack_owner_valid',m_ack_owner_ready='write_control_ack_owner_ready',
        s_ack_done='write_control_ack_done',s_ack_done_valid='write_control_ack_done_valid',s_ack_done_ready='write_control_ack_done_ready',
        m_ack_retire_owner='write_control_ack_retire_owner',m_ack_retire_valid='write_control_ack_retire_valid',m_ack_retire_ready='write_control_ack_retire_ready',
        m_hls_owner='s_control_owner',m_hls_owner_valid='s_control_owner_valid',m_hls_owner_ready='s_control_owner_ready',
        tx_release='s_control_tx_release',configuration_guard='s_control_held',queue_guard='s_control_queue_guard',
        fault='write_control_fault',fault_code='write_control_fault_code',requests='write_control_requests',
        wire_proofs='write_control_proofs',retirements='write_control_retirements',reports='write_control_reports',suppressed='write_control_suppressed')
    logic+='rocev2_write_psn_control write_psn_control(\n'+',\n'.join('.'+n+'('+v+')'for n,v in pins.items())+'\n);\n'
    t=once(t,'reg write_fault_latched=0;',logic+'reg write_fault_latched=0;')
    t=once(t,'else if(write_controller_fault || write_rnr_fault)',
        'else if(write_controller_fault || write_rnr_fault || write_control_fault)')
    t=once(t,'assign atomic_lease_guard=write_rnr_guard ||','assign atomic_lease_guard=s_control_held || write_rnr_guard ||')
    t=once(t,'assign local_execution_guard=write_rnr_queue_guard |','assign local_execution_guard=s_control_queue_guard | write_rnr_queue_guard |')
    t=once(t,'    .m_recv_message_data(rq_message_data),',gateway.connections(FIELDS)+'    .m_recv_message_data(rq_message_data),')
    t=once(t,parent.ack.NAME+' #(',ack.NAME+' #(')
    pins=dict(s_control_owner='write_control_ack_owner',s_control_owner_valid='write_control_ack_owner_valid',
        s_control_owner_ready='write_control_ack_owner_ready',s_control_core_data='m_control_done',
        s_control_core_valid='m_control_done_valid',s_control_core_ready='m_control_done_ready',
        m_control_done_data='write_control_ack_done',m_control_done_valid='write_control_ack_done_valid',m_control_done_ready='write_control_ack_done_ready',
        s_control_retire_owner='write_control_ack_retire_owner',s_control_retire_valid='write_control_ack_retire_valid',s_control_retire_ready='write_control_ack_retire_ready')
    a=t.index(ack.NAME+' #(');b=t.index(');',a)+2;block=t[a:b]
    block=once(block,'    .prior_response_drained(response_tx_quiescent),',
        ''.join('    .'+n+'('+v+'),\n'for n,v in pins.items())+'    .prior_response_drained(response_tx_quiescent),')
    return t[:a]+block+t[b:]


def protected(t):
    t=gateway.ports(t,FIELDS)
    logic='''wire control_shared_owner_ready;
assign s_control_owner_ready=control_shared_owner_ready && !control_external_bad && !fault;
wire control_external_guard=s_control_held!==1'b0 || s_control_owner_valid!==1'b0;
wire control_external_bad=(^{s_control_held,s_control_queue_guard,s_control_tx_release})===1'bx ||
 (s_control_owner_valid!==1'b0 && s_control_owner_valid!==1'b1) ||
 (s_control_owner_valid && (s_control_held!==1'b1 || local_qpn>=8 ||
 s_control_queue_guard[local_qpn]!==1'b1 || m_write_native_context_valid!==1'b1 ||
 s_control_owner[355:0]!==current_rx_context));
'''
    t=once(t,'wire write_shared_owner_ready;',logic+'wire write_shared_owner_ready;')
    t=once(t,'assign atomic_rx_guard=','assign atomic_rx_guard=control_external_guard || ')
    t=once(t,'wire atomic_native_fault=write_rnr_bad ||','wire atomic_native_fault=control_external_bad || m_control_hls_fault || write_rnr_bad ||')
    t=once(t,'    .m_recv_message_data(m_recv_message_data),',
        gateway.connections(FIELDS,{'s_control_owner_valid':'s_control_owner_valid && !control_external_bad && !fault',
        's_control_owner_ready':'control_shared_owner_ready'})+'    .m_recv_message_data(m_recv_message_data),')
    gate='(s_write_held && (s_write_tx_release || s_write_rnr_tx_release))'
    if t.count(gate)!=2:raise ValueError('both real old positive/RNR visibility gates required')
    return t.replace(gate,'('+gate+' || (s_control_held && s_control_tx_release))')


def shared(t):
    t=gateway.ports(t,FIELDS)
    t=once(t,'wire remote_inflight=',"wire remote_inflight=s_control_held===1'b1 || ")
    t=once(t,'wire incoming_fault=','wire incoming_fault=control_core_fault || control_unowned_offer || ')
    logic='''wire control_core_owner_ready,control_core_done_valid,control_core_fault;
wire control_unowned_offer=(s_control_owner_valid && s_control_held!==1'b1) ||
 (control_core_done_valid && s_control_held!==1'b1);
assign s_control_owner_ready=control_core_owner_ready && s_control_held===1'b1 && !fault && !rst;
assign m_control_done_valid=control_core_done_valid && s_control_held===1'b1 && !fault && !rst;
assign m_control_hls_fault=control_core_fault;
'''
    t=once(t,'wire write_core_owner_ready,write_core_done_valid,write_core_fault;',logic+'wire write_core_owner_ready,write_core_done_valid,write_core_fault;')
    mapping=dict(s_control_owner_ready='control_core_owner_ready',m_control_done_valid='control_core_done_valid',m_control_hls_fault='control_core_fault',
        s_control_owner_valid="s_control_owner_valid && s_control_held===1'b1 && !fault",
        m_control_done_ready="m_control_done_ready && s_control_held===1'b1 && !fault")
    return once(t,'.m_recv_message_data(core_recv_message_data),',gateway.connections(HLS,mapping)+'.m_recv_message_data(core_recv_message_data),')


def derive():
    out=parent.derive()
    for name in gateway.WRAPPERS:
        p=RTL/(name+'.v')
        if name=='rocev2_native_rnic_endpoint':out[p]=rnic(out[p]);continue
        t=gateway.ports(out[p],FIELDS)
        out[p]=once(t,'    .m_recv_message_data(m_recv_message_data),',gateway.connections(FIELDS)+'    .m_recv_message_data(m_recv_message_data),')
    p=RTL/'rocev2_protected_responder.v';out[p]=protected(out[p])
    p=RTL/'rocev2_shared_hls_transport.v';out[p]=shared(out[p])
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v';t=gateway.ports(out[p],HLS)
    t=once(t,gateway.HLS_TOP+' transport (',HLS_TOP+' transport (')
    mapping=dict(s_control_owner='s_axis_control_owner_TDATA',s_control_owner_valid='s_axis_control_owner_TVALID',
        s_control_owner_ready='s_axis_control_owner_TREADY',m_control_done='m_axis_control_done_TDATA',
        m_control_done_valid='m_axis_control_done_TVALID',m_control_done_ready='m_axis_control_done_TREADY',m_control_hls_fault='regControlFault')
    out[p]=once(t,'    .m_axis_recv_message_TDATA(m_recv_message_data),',
        ''.join('    .'+mapping[n]+'('+n+'),\n'for _,_,n in HLS)+'    .m_axis_recv_message_TDATA(m_recv_message_data),')
    out[RTL/(native.leaves.FRONT_NAME+'.v')]=frontend()
    out[RTL/(native.CTRL_NAME+'.v')]=controller()
    del out[RTL/(parent.ack.NAME+'.v')];out[RTL/(ack.NAME+'.v')]=ack.derive()
    out[HELPER]=HELPER.read_text()
    return out
