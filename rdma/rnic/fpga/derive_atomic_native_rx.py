# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked actual native Atomic RX/service/MR additions, no original rewrites.

Used only by the complete native integration derivative. All ordinary paths
stay in the same protected graph, HLS, MR/PTE and underlying memory namespace.
"""
from pathlib import Path
import re
import derive_atomic_native_owned_stage as stage

ROOT=stage.ROOT;RTL=ROOT/'rdma/rnic/rtl'
once=stage.once
add_ports=stage.authority.ports
connect=stage.authority.connect
same=stage.authority.same

FLOW=[
 ('input','','atomic_mac_available'),('input','','atomic_parent_fault'),
 ('input','[47:0]','atomic_local_mac'),('input','[47:0]','atomic_peer_mac'),
 ('output','[327:0]','m_atomic_packet_owner'),('output','','m_atomic_packet_owner_valid'),('input','','s_atomic_packet_owner_ready'),
 ('input','[143:0]','s_atomic_hls_owner'),('input','','s_atomic_hls_owner_valid'),('output','','m_atomic_hls_owner_ready'),
 ('output','[391:0]','m_atomic_mac_reply'),('output','','m_atomic_mac_reply_valid'),('input','','s_atomic_mac_reply_ready'),
 ('output','[223:0]','m_atomic_core_done'),('output','','m_atomic_core_done_valid'),('input','','s_atomic_core_done_ready'),
 ('output','[127:0]','m_atomic_ip_data'),('output','[15:0]','m_atomic_ip_keep'),('output','','m_atomic_ip_valid'),
 ('input','','s_atomic_ip_ready'),('output','','m_atomic_ip_last'),
 ('input','[143:0]','s_atomic_retire_owner'),('input','[223:0]','s_atomic_retire_core'),
 ('input','','s_atomic_retire_valid'),('output','','m_atomic_retire_ready'),
 ('output','','atomic_rx_guard')]
CONTEXT=[('input','','atomic_context_valid'),('input','[23:0]','atomic_context_qpn'),
 ('input','[15:0]','atomic_context_pd'),('input','[63:0]','atomic_context_epoch'),
 ('input','[63:0]','atomic_context_cookie'),('input','[23:0]','atomic_context_peer_qpn'),
 ('input','[31:0]','atomic_context_local_ip'),('input','[31:0]','atomic_context_peer_ip')]
HLS=[
 ('input','[143:0]','s_atomic_hls_owner'),('input','','s_atomic_hls_owner_valid'),('output','','m_atomic_hls_owner_ready'),
 ('output','[511:0]','m_atomic_hls_request'),('output','','m_atomic_hls_request_valid'),('input','','s_atomic_hls_request_ready'),
 ('input','[391:0]','s_atomic_hls_reply'),('input','','s_atomic_hls_reply_valid'),('output','','m_atomic_hls_reply_ready'),
 ('output','[223:0]','m_atomic_core_done'),('output','','m_atomic_core_done_valid'),('input','','s_atomic_core_done_ready')]


def module_ports(path):
    header=path.read_text().split('\n);',1)[0]
    return [(d,(w or '').strip().replace('MAX_QPS','8'),n)for d,w,n in
        re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?',header)]


MEM=[(d,w,'a_'+n)for d,w,n in module_ports(RTL/'rocev2_atomic_responder.v')if
     n.startswith(('m_memory_','m_axis_write_','s_axis_read_','s_memory_status_'))or n in ('memory_lock_request','memory_lock_granted')]
MEM.append(('input','','atomic_backend_idle'))


def declarations(items):
    return '\n'.join('wire '+(w+' 'if w else'')+n+';'for _,w,n in items)


def instance(path,name,mapping,parameters=''):
    decl=[];connections=[];known={n for _,_,n in module_ports(path)}
    if set(mapping)-known:raise ValueError('unknown actual port '+str(set(mapping)-known))
    for _,width,port in module_ports(path):
        if port in mapping:value=mapping[port]
        else:
            value=name+'_'+port;decl.append('wire '+(width+' 'if width else'')+value+';')
        connections.append('.'+port+'('+value+')')
    return '\n'.join(decl)+'\n'+path.stem+(' #('+parameters+')'if parameters else'')+' '+name+'(\n'+',\n'.join(connections)+');\n'


def shared(t):
    t=add_ports(t,HLS)
    t=once(t,'wire atomic_unowned_offer=disabled_atomic_request || disabled_atomic_done;',
        "wire atomic_unowned_offer=1'b0;")
    t=once(t,'wire disabled_atomic_request,disabled_atomic_done;','')
    t=once(t,"assign disabled_atomic_request=1'b0;assign disabled_atomic_done=1'b0;",
        "assign m_atomic_hls_owner_ready=1'b0;assign m_atomic_hls_request=512'd0;\n"
        "assign m_atomic_hls_request_valid=1'b0;assign m_atomic_hls_reply_ready=1'b0;\n"
        "assign m_atomic_core_done=224'd0;assign m_atomic_core_done_valid=1'b0;")
    replacements={
      ".s_atomic_owner(144'd0),.s_atomic_owner_valid(1'b0),.s_atomic_owner_ready(),":
      '.s_atomic_owner(s_atomic_hls_owner),.s_atomic_owner_valid(s_atomic_hls_owner_valid),.s_atomic_owner_ready(m_atomic_hls_owner_ready),',
      ".m_atomic_request(),.m_atomic_request_valid(disabled_atomic_request),.m_atomic_request_ready(1'b0),":
      '.m_atomic_request(m_atomic_hls_request),.m_atomic_request_valid(m_atomic_hls_request_valid),.m_atomic_request_ready(s_atomic_hls_request_ready),',
      ".s_atomic_reply(392'd0),.s_atomic_reply_valid(1'b0),.s_atomic_reply_ready(),":
      '.s_atomic_reply(s_atomic_hls_reply),.s_atomic_reply_valid(s_atomic_hls_reply_valid),.s_atomic_reply_ready(m_atomic_hls_reply_ready),',
      ".m_atomic_done(),.m_atomic_done_valid(disabled_atomic_done),.m_atomic_done_ready(1'b0),":
      '.m_atomic_done(m_atomic_core_done),.m_atomic_done_valid(m_atomic_core_done_valid),.m_atomic_done_ready(s_atomic_core_done_ready),'}
    for a,b in replacements.items():t=once(t,a,b)
    return t


def protected(t):
    t=add_ports(t,FLOW+CONTEXT+MEM)
    # Retain original checker and ordinary parser, inserting a classifier
    # AFTER the actual whole-frame integrity outcome, not before it.
    first=t.index('assign checked_ready=')
    t=t[:first]+re.sub(r'\bchecked_(data|keep|valid|ready|last)\b',r'normal_checked_\1',t[first:])
    first=t.index('rocev2_ipv4_icrc #(.TX_MODE(0)) admission_integrity')
    last=t.index(');',first)+2
    block=t[first:last]
    block=once(block,'.s_axis_tdata(s_axis_rx_tdata),.s_axis_tkeep(s_axis_rx_tkeep),',
        '.s_axis_tdata(raw_data),.s_axis_tkeep(raw_keep),')
    block=once(block,'.s_axis_tvalid(s_axis_rx_tvalid),.s_axis_tready(s_axis_rx_tready),',
        '.s_axis_tvalid(raw_valid),.s_axis_tready(raw_ready),')
    block=once(block,'.s_axis_tlast(s_axis_rx_tlast),.s_axis_tuser(s_axis_rx_tuser),',
        '.s_axis_tlast(raw_last),.s_axis_tuser(raw_user),')
    t=t[:first]+block+t[last:]
    first=t.index('assign normal_checked_ready=');last=t.index('\n\nwire [7:0] opcode=',first)
    t=t[:first]+r'''// Accepted raw RX references drain after management pause. Frames not yet
// authorized are discarded in PARSE rather than deadlocking STOP/config.
assign normal_checked_ready=state==COLLECT && qp_ready && !atomic_packet_busy &&
    (!RECV_CQ_ENABLE || !recv_completion_pending) && !fault && !rst;
'''+t[last:]
    t=once(t,'wire startup_done=startup_count==4096;',RX_LOGIC+'\n'+service_logic()+'\nwire startup_done=startup_count==4096;')
    t=once(t,'assign qp_ready=context_valid && !config_busy &&',
        'assign qp_ready=context_valid && !config_busy && !atomic_cfg_pending &&')
    t=once(t,'assign quiescent=state==COLLECT &&',
        'assign quiescent=!atomic_rx_guard && state==COLLECT &&')
    # Actual accepted normal capture/lease as well as Atomic references are
    # exported without depending on parent's local_work_guard/quiescence.
    t=once(t,'                    if(frame_bad || byte_count<',
        '                    if(admission_paused || cfg_qp_valid || cfg_mr_valid || cfg_mr_response_valid)begin\n'
        '                        m_reject_error<=ERR_QP;\n'
        '                    end else if(frame_bad || byte_count<')
    # Shared core remote RX is serialized by real protected owners. Local
    # requester traffic retains its existing independent duplex origin.
    t=once(t,'.s_axis_rx_tdata(replay_data),.s_axis_rx_tkeep(replay_keep),',
        '.s_axis_rx_tdata(atomic_packet_busy ? atomic_hls_data:replay_data),.s_axis_rx_tkeep(atomic_packet_busy ? atomic_hls_keep:replay_keep),')
    t=once(t,'.s_axis_rx_tvalid(replay_valid),.s_axis_rx_tready(core_rx_ready),',
        '.s_axis_rx_tvalid(atomic_packet_busy ? atomic_hls_valid:replay_valid),.s_axis_rx_tready(shared_remote_ready),')
    t=once(t,'.s_axis_rx_tlast(replay_last),.s_axis_rx_tuser(1\'b0),',
        ".s_axis_rx_tlast(atomic_packet_busy ? atomic_hls_last:replay_last),.s_axis_rx_tuser(1'b0),")
    t=once(t,'    .remote_operation_idle(state==COLLECT',
        '    .remote_operation_idle(!atomic_packet_busy && state==COLLECT')
    t=connect(t,'transport',same(HLS))
    # Actual service/reply and core ports were added above; declare only those
    # not already exported by FLOW. Reply fanout is defined in service_logic.
    existing={n for _,_,n in FLOW}
    t=once(t,'wire [127:0] core_tx_data;',
        declarations([p for p in HLS if p[2]not in existing])+'\nwire [127:0] core_tx_data;')
    t=once(t,'assign m_axis_tx_tvalid=core_tx_valid &&',
        'assign m_axis_tx_tvalid=core_tx_valid && !atomic_packet_busy &&')
    t=once(t,'assign core_tx_ready=m_axis_tx_tready && ((lease && committed) || (RNR_ENABLE && state==RNR_WAIT)) && !fault && !rst;',
        'assign core_tx_ready=atomic_packet_busy ? s_atomic_ip_ready : m_axis_tx_tready && ((lease && committed) || (RNR_ENABLE && state==RNR_WAIT)) && !fault && !rst;\n'
        'assign m_atomic_ip_data=core_tx_data;assign m_atomic_ip_keep=core_tx_keep;assign m_atomic_ip_last=core_tx_last;\n'
        'assign m_atomic_ip_valid=core_tx_valid && atomic_packet_busy;')
    # Put the Atomic query at the SAME MR table, below the existing normal/
    # local query arbiter. Returned fields never become another namespace.
    first=t.index('rocev2_mr_table #');last=t.index(');',first)+2
    block=t[first:last]
    block=re.sub(r'\btable_(request|response)_(\w+)\b',r'atomic_table_\1_\2',block)
    t=t[:first]+mr_logic()+block+t[last:]
    t=once(t,'            if(shared_mr_fault) begin fault<=1;',
        '            if(atomic_native_fault)begin fault<=1;fault_code<=8\'he6;end\n'
        '            if(shared_mr_fault) begin fault<=1;')
    t=once(t,'        if(!fault) begin\n',r'''
        if(s_atomic_retire_valid && m_atomic_retire_ready)expected_psn<=s_atomic_retire_core[175:152];
        if(!fault) begin
''')
    return t


RX_LOGIC=r'''
wire [127:0] raw_data,normal_checked_data,routed_atomic_data,atomic_hls_data;
wire [15:0] raw_keep,normal_checked_keep,routed_atomic_keep,atomic_hls_keep;
wire raw_valid,raw_ready,raw_last,raw_user,normal_checked_valid,normal_checked_ready,normal_checked_last;
wire routed_atomic_valid,routed_atomic_ready,routed_atomic_last,atomic_hls_valid,atomic_hls_ready,atomic_hls_last;
wire shared_remote_ready;
assign core_rx_ready=shared_remote_ready && !atomic_packet_busy;
assign atomic_hls_ready=shared_remote_ready && atomic_packet_busy;
wire refs_guard,refs_fault,dispatch_guard,dispatch_fault,atomic_packet_busy,atomic_packet_fault;
wire [15:0] rx_references;wire [351:0] held_rx_context;
wire context_match=atomic_context_qpn==local_qpn && atomic_context_pd==trusted_pd &&
 atomic_context_peer_qpn==peer_qpn && atomic_context_local_ip==local_ip && atomic_context_peer_ip==peer_ip;
wire [351:0] current_rx_context={atomic_peer_mac,atomic_local_mac,atomic_context_peer_ip,atomic_context_local_ip,
 atomic_context_peer_qpn,atomic_context_cookie,atomic_context_epoch,atomic_context_pd,atomic_context_qpn};
rocev2_native_rx_refs input_references(
 .clk(clk),.rst(rst),.enable(qp_ready && !admission_paused && mr_management_idle && !cfg_qp_valid &&
   (!RECV_CQ_ENABLE || !recv_completion_pending)),.parent_fault(atomic_parent_fault),
 .trusted_valid(atomic_context_valid && context_match),.trusted_context(current_rx_context),
 .s_data(s_axis_rx_tdata),.s_keep(s_axis_rx_tkeep),.s_valid(s_axis_rx_tvalid),.s_ready(s_axis_rx_tready),
 .s_last(s_axis_rx_tlast),.s_user(s_axis_rx_tuser),
 .m_data(raw_data),.m_keep(raw_keep),.m_valid(raw_valid),.m_ready(raw_ready),.m_last(raw_last),.m_user(raw_user),
 .checked_eof(checked_valid && checked_ready && checked_last),.checker_drop(rx_bad || rx_overflow),
 .held_context(held_rx_context),.configuration_guard(refs_guard),.queue_guard(),.references(rx_references),.fault(refs_fault));
rocev2_native_atomic_rx_router packet_classification(
 .clk(clk),.rst(rst),.s_data(checked_data),.s_keep(checked_keep),.s_valid(checked_valid),.s_ready(checked_ready),.s_last(checked_last),
 .m_normal_data(normal_checked_data),.m_normal_keep(normal_checked_keep),.m_normal_valid(normal_checked_valid),
 .m_normal_ready(normal_checked_ready),.m_normal_last(normal_checked_last),
 .m_atomic_data(routed_atomic_data),.m_atomic_keep(routed_atomic_keep),.m_atomic_valid(routed_atomic_valid),
 .m_atomic_ready(routed_atomic_ready),.m_atomic_last(routed_atomic_last),.configuration_guard(dispatch_guard),.fault(dispatch_fault));
wire ordinary_idle=state==COLLECT && word_count==0 && !lease && !recv_completion_pending;
wire atomic_new_allowed=ordinary_idle && atomic_mac_available && !admission_paused && qp_ready && !fault && !atomic_parent_fault;
reg atomic_discard=0;
wire discard_now=!atomic_packet_busy && (atomic_discard || admission_paused);
wire atomic_packet_input_ready;
assign routed_atomic_ready=discard_now ? 1'b1:atomic_packet_input_ready && (atomic_packet_busy || atomic_new_allowed);
always @(posedge clk)begin
 if(rst)atomic_discard<=0;
 else if(routed_atomic_valid && routed_atomic_ready && discard_now)atomic_discard<=!routed_atomic_last;
end
wire [23:0] packet_owner_qpn,packet_owner_psn;wire [63:0] packet_owner_epoch;wire [31:0] packet_owner_nonce;
wire packet_owner_valid,packet_retire_ready;
wire retire_core_known=(^s_atomic_retire_core)!==1'bx;
wire retire_core_ok=retire_core_known && s_atomic_retire_core[143:0]==s_atomic_retire_owner &&
 s_atomic_retire_core[223:208]==0 && s_atomic_retire_core[202:200]==7 && s_atomic_retire_core[207:206]==0 &&
 (s_atomic_retire_core[151:144]==8'h13 || s_atomic_retire_core[151:144]==8'h14);
assign m_atomic_retire_ready=packet_retire_ready && retire_core_ok && !fault;
rocev2_atomic_packet_guard atomic_packet(
 .clk(clk),.rst(rst),.enable(atomic_new_allowed),
 .trusted_valid(held_rx_context[23:0]==local_qpn && held_rx_context[39:24]==trusted_pd && held_rx_context[103:40]!=0),
 .trusted_qpn(held_rx_context[23:0]),.trusted_epoch(held_rx_context[103:40]),
 .trusted_local_ip(held_rx_context[223:192]),.trusted_peer_ip(held_rx_context[255:224]),
 .s_axis_tdata(routed_atomic_data),.s_axis_tkeep(routed_atomic_keep),
 .s_axis_tvalid(routed_atomic_valid && !discard_now && (atomic_packet_busy || atomic_new_allowed)),
 .s_axis_tready(atomic_packet_input_ready),.s_axis_tlast(routed_atomic_last),
 .m_axis_tdata(atomic_hls_data),.m_axis_tkeep(atomic_hls_keep),.m_axis_tvalid(atomic_hls_valid),
 .m_axis_tready(atomic_hls_ready),.m_axis_tlast(atomic_hls_last),
 .m_owner_qpn(packet_owner_qpn),.m_owner_epoch(packet_owner_epoch),.m_owner_psn(packet_owner_psn),.m_owner_tag(packet_owner_nonce),
 .m_owner_valid(packet_owner_valid),.m_owner_ready(s_atomic_packet_owner_ready),
 .s_retire_qpn(s_atomic_retire_owner[23:0]),.s_retire_epoch(s_atomic_retire_owner[87:24]),
 .s_retire_psn(s_atomic_retire_owner[111:88]),.s_retire_tag(s_atomic_retire_owner[143:112]),
 .s_retire_valid(s_atomic_retire_valid && retire_core_ok && !fault),.s_retire_ready(packet_retire_ready),
 .busy(atomic_packet_busy),.configuration_guard(),.fault(atomic_packet_fault),.fault_code(),.accepted_count(),.dropped_count());
assign m_atomic_packet_owner={held_rx_context[303:256],held_rx_context[351:304],held_rx_context[223:192],
 held_rx_context[255:224],held_rx_context[191:168],packet_owner_nonce,packet_owner_psn,packet_owner_epoch,packet_owner_qpn};
assign m_atomic_packet_owner_valid=packet_owner_valid;
assign atomic_rx_guard=refs_guard || dispatch_guard || atomic_packet_busy || atomic_discard ||
 state!=COLLECT || word_count!=0 || lease || recv_completion_pending || atomic_cfg_pending ||
 owned_service_configuration_guard || atomic_execution_configuration_guard || atomic_mr_busy || fault;
wire atomic_native_fault=refs_fault || dispatch_fault || atomic_packet_fault || owned_service_fault ||
 atomic_execution_fault || atomic_mr_fault || atomic_parent_fault ||
 (s_atomic_retire_valid && !retire_core_ok) ||
 (m_atomic_hls_request_valid && !atomic_packet_busy) ||
 (atomic_execution_cfg_response_valid && atomic_execution_cfg_error!=0);
reg atomic_cfg_pending=0;
always @(posedge clk)begin
 if(rst)atomic_cfg_pending<=0;
 else begin
  if(cfg_qp_valid && cfg_qp_ready && !cfg_qp_tx_only && cfg_qp_pd!=0)atomic_cfg_pending<=1;
  if(atomic_execution_cfg_response_valid)atomic_cfg_pending<=0;
 end
end
'''


def service_logic():
    mapping=dict(clk='clk',rst='rst',enable="1'b1",cfg_quiescent='!atomic_packet_busy && !owned_service_busy && atomic_backend_idle && !fault',
        cfg_qpn='local_qpn',cfg_peer_qpn='peer_qpn',cfg_pd='trusted_pd',cfg_epoch='atomic_context_epoch',
        cfg_psn='expected_psn',cfg_msn="24'd0",cfg_valid='atomic_cfg_pending',cfg_response_ready="1'b1")
    for _,_,name in MEM:
        if name=='atomic_backend_idle':continue
        mapping[name[2:]]=name
    # The owned adapter is the ONLY source of execution requests; every
    # response feeds a real AXIS broadcast to HLS and its MAC lifetime.
    for n in ['header','bytes','epoch','expected_psn','msn','valid']:mapping['s_request_'+n]='owned_service_m_execute_'+n
    mapping['s_request_ready']='owned_service_m_execute_ready'
    executor=instance(RTL/'rocev2_atomic_responder.v','atomic_execution',mapping,'.SHARED_SEQUENCE_ENABLE(1)')
    mapping=dict(clk='clk',rst='rst',enable='atomic_packet_busy && !fault',
        s_hls_request='m_atomic_hls_request',s_hls_request_valid='m_atomic_hls_request_valid',
        s_hls_request_ready='s_atomic_hls_request_ready')
    for n in ['header','bytes','qpn','epoch','advance','drop','valid']:mapping['s_execute_response_'+n]='atomic_execution_m_response_'+n
    mapping['s_execute_response_ready']='atomic_execution_m_response_ready'
    adapter=instance(RTL/'rocev2_atomic_owned_service_adapter.v','owned_service',mapping)
    fanout=r'''
wire [783:0] atomic_reply_data;wire [1:0] atomic_reply_valid,atomic_reply_ready;
axis_broadcast #(.M_COUNT(2),.DATA_WIDTH(392),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.LAST_ENABLE(0),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1)) atomic_replies(
 .clk(clk),.rst(rst),.s_axis_tdata(owned_service_m_hls_reply),.s_axis_tkeep(1'b1),
 .s_axis_tvalid(owned_service_m_hls_reply_valid),.s_axis_tready(owned_service_m_hls_reply_ready),.s_axis_tlast(1'b1),
 .s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
 .m_axis_tdata(atomic_reply_data),.m_axis_tvalid(atomic_reply_valid),.m_axis_tready(atomic_reply_ready),
 .m_axis_tkeep(),.m_axis_tlast(),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
assign s_atomic_hls_reply=atomic_reply_data[391:0];assign s_atomic_hls_reply_valid=atomic_reply_valid[0];
assign atomic_reply_ready[0]=m_atomic_hls_reply_ready;
assign m_atomic_mac_reply=atomic_reply_data[783:392];assign m_atomic_mac_reply_valid=atomic_reply_valid[1];
assign atomic_reply_ready[1]=s_atomic_mac_reply_ready;
'''
    return executor+adapter+fanout


def mr_logic():
    req=[('pd','[15:0]'),('key','[31:0]'),('address','[63:0]'),('length','[31:0]'),
         ('operation','[2:0]'),('tag','[15:0]'),('valid',''),('ready','')]
    resp=[('tag','[15:0]'),('error','[7:0]'),('offset','[63:0]'),('dma','[63:0]'),
          ('length','[31:0]'),('valid',''),('ready','')]
    decl=declarations([('wire',w,'atomic_table_'+d+'_'+n)for d,items in [('request',req),('response',resp)]for n,w in items])
    decl+='\nwire [31:0] a_query_tags;wire [15:0] a_query_errors;wire [127:0] a_query_offsets,a_query_dmas;\n'
    decl+='wire [63:0] a_query_lengths;wire [1:0] a_query_ready,a_query_valid;\nwire atomic_mr_busy,atomic_mr_fault;\n'
    p=dict(clk='clk',rst='rst',busy='atomic_mr_busy',fault='atomic_mr_fault',fault_code='')
    for n,_ in req:
        if n=='ready':continue
        p['s_request_'+n]='{atomic_execution_m_mr_'+n+',table_request_'+n+'}'
        p['m_request_'+n]='atomic_table_request_'+n
    p['s_request_ready']='a_query_ready';p['m_request_ready']='atomic_table_request_ready'
    p.update(m_response_tag='a_query_tags',m_response_error='a_query_errors',m_response_offset='a_query_offsets',
        m_response_dma_address='a_query_dmas',m_response_length='a_query_lengths',m_response_valid='a_query_valid',
        m_response_ready='{atomic_execution_s_mr_ready,table_response_ready}')
    for n,_ in resp:
        p['s_response_'+('dma_address'if n=='dma'else n)]='atomic_table_response_'+n
    glue=r'''
assign {atomic_execution_m_mr_ready,table_request_ready}=a_query_ready;
assign {atomic_execution_s_mr_tag,table_response_tag}=a_query_tags;
assign {atomic_execution_s_mr_error,table_response_error}=a_query_errors;
assign {atomic_execution_s_mr_offset,table_response_offset}=a_query_offsets;
assign table_response_dma=a_query_dmas[63:0];
assign {atomic_execution_s_mr_length,table_response_length}=a_query_lengths;
assign {atomic_execution_s_mr_valid,table_response_valid}=a_query_valid;
'''
    return decl+instance(RTL/'rocev2_mr_query_arbiter.v','atomic_MR_queries',p)+glue
