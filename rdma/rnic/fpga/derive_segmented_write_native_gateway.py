# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native boundary for typed WRITE HLS and SAME real MR table, source-only.

All original paths and default capabilities remain. This stage exports
real typed ports to the enclosing protected WRITE controller; it DOES NOT
pretend that the raw frontend/backend/ACK/whole CQ insertion is complete.
No default-ready, fake RQ, second HLS/MR or completion/drain is introduced.
"""
import re
import derive_segmented_receive_continuation as parent

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;EXTRA=parent.EXTRA
HLS_TOP='rocev2_native_segmented_write_owned_top'
HLS_FIELDS=[('input','[423:0]','s_write_owner'),('input','','s_write_owner_valid'),
    ('output','','s_write_owner_ready'),('output','[455:0]','m_write_done'),
    ('output','','m_write_done_valid'),('input','','m_write_done_ready'),('output','','m_write_hls_fault')]
GUARDS=[('input','','s_write_held'),('input','','s_write_mr_guard'),('input','[7:0]','s_write_queue_guard')]
QUERY=[('input',w,'s_write_mr_request_'+n)for n,w in [('pd','[15:0]'),('key','[31:0]'),('address','[63:0]'),
    ('length','[31:0]'),('operation','[2:0]'),('tag','[15:0]'),('valid','')]]+[
    ('output','','s_write_mr_request_ready')]+[('output',w,'m_write_mr_response_'+n)for n,w in [
    ('tag','[15:0]'),('error','[7:0]'),('offset','[63:0]'),('dma_address','[63:0]'),('length','[31:0]'),('valid','')]]+[
    ('input','','m_write_mr_response_ready')]
CONTEXT=[('output','[355:0]','m_write_native_context'),('output','','m_write_native_context_valid'),
    ('output','[23:0]','m_write_expected_psn')]
FIELDS=HLS_FIELDS+GUARDS+QUERY+CONTEXT
WRAPPERS=['rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_native_endpoint',
    'rocev2_dual_ethernet_endpoint','rocev2_controlled_responder','rocev2_paged_responder']


def ports(t,fields):
    return once(t,'    input wire clk,',''.join('    '+d+' wire '+(w+' 'if w else'')+n+',\n'for d,w,n in fields)+'    input wire clk,')


def connections(fields,mapping=None):
    mapping=mapping or{}
    return ''.join('    .'+n+'('+mapping.get(n,n)+'),\n'for _,_,n in fields)


def gateway():
    request={n:'write_table_request_'+n for n in ['pd','key','address','length','operation','tag','valid','ready']}
    response={n:'write_table_response_'+n for n in ['tag','error','offset','dma_address','length','valid','ready']}
    text='// One additional CLIENT, never an additional MR namespace.\n'
    widths=dict(pd=16,key=32,address=64,length=32,operation=3,tag=16,valid=1,ready=1,error=8,offset=64,dma_address=64)
    for fields in [request,response]:
        for n,target in fields.items():text+='wire '+('['+str(widths[n]-1)+':0] 'if widths[n]>1 else'')+target+';\n'
    text+='wire [31:0] write_query_tags;wire [15:0] write_query_errors;wire [127:0] write_query_offsets,write_query_dmas;\n'
    text+='wire [63:0] write_query_lengths;wire [1:0] write_query_ready,write_query_valid;wire write_mr_busy,write_mr_fault;\n'
    pin={'clk':'clk','rst':'rst','busy':'write_mr_busy','fault':'write_mr_fault','fault_code':''}
    for n in ['pd','key','address','length','operation','tag','valid']:
        offered='s_write_mr_request_'+n
        if n=='valid':offered='s_write_mr_request_valid && !write_external_bad && !fault'
        pin['s_request_'+n]='{'+offered+',atomic_table_request_'+n+'}'
    pin.update(s_request_ready='write_query_ready',m_response_tag='write_query_tags',m_response_error='write_query_errors',
        m_response_offset='write_query_offsets',m_response_dma_address='write_query_dmas',m_response_length='write_query_lengths',
        m_response_valid='write_query_valid',m_response_ready='{m_write_mr_response_ready,atomic_table_response_ready}')
    for n,target in request.items():pin['m_request_'+n]=target
    for n,target in response.items():pin['s_response_'+n]=target
    text+='rocev2_mr_query_arbiter segmented_write_MR_queries(\n'+',\n'.join(' .'+n+'('+v+')'for n,v in pin.items())+'\n);\n'
    text+='assign atomic_table_request_ready=write_query_ready[0];\n'
    text+='assign s_write_mr_request_ready=write_query_ready[1] && !write_external_bad && !fault;\n'
    for n,vector in [('tag','write_query_tags'),('error','write_query_errors'),('offset','write_query_offsets'),
        ('dma','write_query_dmas'),('length','write_query_lengths'),('valid','write_query_valid')]:
        public='dma_address'if n=='dma'else n
        old='dma'if n=='dma'else n
        text+='assign {m_write_mr_response_'+public+',atomic_table_response_'+old+'}='+vector+';\n'
    return text


def protected(t):
    t=ports(t,FIELDS)
    t=once(t,'    .m_recv_message_data(m_recv_message_data),',connections(HLS_FIELDS+GUARDS,{
        's_write_owner_valid':'s_write_owner_valid && !write_external_bad && !fault',
        's_write_owner_ready':'write_shared_owner_ready'})+'    .m_recv_message_data(m_recv_message_data),')
    # The enclosing WRITE frontend must retain both actual MR and QP guards.
    # Unknown/unprotected owner/query offers quarantine the real native path.
    guard='''wire write_shared_owner_ready;
assign s_write_owner_ready=write_shared_owner_ready && !write_external_bad && !fault;
wire write_external_guard=s_write_held!==1'b0 || s_write_mr_guard!==1'b0 ||
    s_write_owner_valid!==1'b0 || s_write_mr_request_valid!==1'b0 || s_write_queue_guard!==8'd0;
wire write_guard_known=(^{s_write_held,s_write_mr_guard,s_write_queue_guard})!==1'bx;
wire write_native_identity=(^s_write_owner)!==1'bx && s_write_owner[423:400]===local_qpn &&
    s_write_owner[399:384]===trusted_pd && s_write_owner[383:320]===atomic_context_epoch;
wire write_external_bad=!write_guard_known ||
    (s_write_owner_valid!==1'b0 && s_write_owner_valid!==1'b1) ||
    (s_write_mr_request_valid!==1'b0 && s_write_mr_request_valid!==1'b1) ||
    ((s_write_owner_valid || s_write_mr_request_valid) &&
        (s_write_held!==1'b1 || s_write_mr_guard!==1'b1 ||
         local_qpn>=8 || s_write_queue_guard[local_qpn]!==1'b1)) ||
    (s_write_owner_valid && !write_native_identity) ||
    (s_write_mr_request_valid && (s_write_mr_request_pd!==trusted_pd || s_write_mr_request_operation!==3'd3));
assign m_write_native_context=current_rx_context;
assign m_write_native_context_valid=atomic_context_valid && context_match && qp_ready;
assign m_write_expected_psn=expected_psn;
'''
    t=once(t,'wire refs_guard,refs_fault,dispatch_guard,dispatch_fault,atomic_packet_busy,atomic_packet_fault;',
        guard+'wire refs_guard,refs_fault,dispatch_guard,dispatch_fault,atomic_packet_busy,atomic_packet_fault;')
    t=once(t,'assign atomic_rx_guard=refs_guard ||',
        'assign atomic_rx_guard=write_external_guard || write_mr_busy || write_mr_fault || refs_guard ||')
    t=once(t,'wire atomic_native_fault=refs_fault ||',
        'wire atomic_native_fault=write_external_bad || write_mr_fault || m_write_hls_fault || refs_fault ||')
    start=t.index('rocev2_mr_table #');end=t.index(');',start)+2;block=t[start:end]
    # Only actual MR-table pins are rewired. All existing normal/SQ/Atomic
    # arbitration and full-width response routing remain before the new client.
    block=re.sub(r'\batomic_table_request_(\w+)\b',r'write_table_request_\1',block)
    block=re.sub(r'\batomic_table_response_dma\b','write_table_response_dma_address',block)
    block=re.sub(r'\batomic_table_response_(tag|error|offset|length|valid|ready)\b',r'write_table_response_\1',block)
    return t[:start]+gateway()+block+t[end:]


def shared(t):
    t=ports(t,HLS_FIELDS+GUARDS)
    t=once(t,'wire remote_inflight=',"wire remote_inflight=s_write_held===1'b1 || ")
    t=once(t,'wire incoming_fault=',"wire incoming_fault=write_core_fault || write_unowned_offer || ")
    mapping={'s_write_owner_ready':'write_core_owner_ready','m_write_done_valid':'write_core_done_valid',
        'm_write_hls_fault':'write_core_fault',
        's_write_owner_valid':"s_write_owner_valid && s_write_held===1'b1 && !fault",
        'm_write_done_ready':"m_write_done_ready && s_write_held===1'b1 && !fault"}
    logic='''wire write_core_owner_ready,write_core_done_valid,write_core_fault;
wire write_unowned_offer=(s_write_owner_valid && s_write_held!==1'b1) ||
    (write_core_done_valid && s_write_held!==1'b1);
assign s_write_owner_ready=write_core_owner_ready && s_write_held===1'b1 && !fault && !rst;
assign m_write_done_valid=write_core_done_valid && s_write_held===1'b1 && !fault && !rst;
assign m_write_hls_fault=write_core_fault;
'''
    t=once(t,'wire core_recv_owner_ready,core_recv_fault,core_recv_done_valid;',logic+'wire core_recv_owner_ready,core_recv_fault,core_recv_done_valid;')
    return once(t,'.m_recv_message_data(core_recv_message_data),',connections(HLS_FIELDS,mapping)+'.m_recv_message_data(core_recv_message_data),')


def derive():
    out=parent.derive()
    for name in WRAPPERS:
        p=RTL/(name+'.v');t=ports(out[p],FIELDS)
        anchor='    .m_recv_message_data('+('rq_message_data'if name=='rocev2_native_rnic_endpoint'else'm_recv_message_data')+'),'
        out[p]=once(t,anchor,connections(FIELDS)+anchor)
    p=RTL/'rocev2_protected_responder.v';out[p]=protected(out[p])
    p=RTL/'rocev2_shared_hls_transport.v';out[p]=shared(out[p])
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v';t=ports(out[p],HLS_FIELDS)
    t=once(t,'rocev2_native_segmented_receive_top transport (',HLS_TOP+' transport (')
    native={'s_write_owner':'s_axis_write_owner_TDATA','s_write_owner_valid':'s_axis_write_owner_TVALID',
        's_write_owner_ready':'s_axis_write_owner_TREADY','m_write_done':'m_axis_write_done_TDATA',
        'm_write_done_valid':'m_axis_write_done_TVALID','m_write_done_ready':'m_axis_write_done_TREADY','m_write_hls_fault':'regWriteFault'}
    pins=''.join('    .'+native[n]+'('+n+'),\n'for _,_,n in HLS_FIELDS)
    out[p]=once(t,'    .m_axis_recv_message_TDATA(m_recv_message_data),',pins+'    .m_axis_recv_message_TDATA(m_recv_message_data),')
    return out
