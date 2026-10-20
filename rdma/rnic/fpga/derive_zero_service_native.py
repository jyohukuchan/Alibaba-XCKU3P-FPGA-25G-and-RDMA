# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked ordinary zero WRITE/READ in the SAME actual native HLS graph.

Real privileged QP/peer/PD/epoch/cookie authority, distinct ordinary service
owner, actual HLS core receipt and fresh genuine MAC/SFD/EOF/tail retirement.
No fake RQ/Atomic alias/MR/DMA/status completion or global drain certificate.
Default and previous proof-bound sources are never rewritten.
"""
import derive_zero_rq_native as base
import derive_atomic_native as helpers

ROOT=base.ROOT;RTL=base.RTL;once=base.once;ICRC=base.ICRC;PROTECTED=base.PROTECTED
ports=helpers.ports;connect=helpers.connect;same=helpers.same
HLS=[('input','[343:0]','s_zero_hls_owner'),('input','','s_zero_hls_owner_valid'),
 ('output','','m_zero_hls_owner_ready'),('output','[399:0]','m_zero_core_done'),
 ('output','','m_zero_core_done_valid'),('input','','s_zero_core_done_ready')]
FLOW=HLS+[('input','','zero_mac_available'),('output','[527:0]','m_zero_packet_owner'),
 ('output','','m_zero_packet_owner_valid'),('input','','s_zero_packet_owner_ready'),
 ('input','[343:0]','s_zero_retire_owner'),('input','[399:0]','s_zero_retire_core'),
 ('input','','s_zero_retire_valid'),('output','','m_zero_retire_ready')]
EXTRA=base.EXTRA+[RTL/'rocev2_zero_service_owner.v',RTL/'rocev2_zero_service_mac.v']


def protected(t):
    t=ports(t,FLOW)
    t=connect(t,'transport',same(HLS))
    t=once(t,'RNR_WAIT=9, OWNER_ARM=10;','RNR_WAIT=9, OWNER_ARM=10, ZERO_ARM=11, ZERO_WAIT=12;')
    t=once(t,'reg zero_receive=0;',r'''
reg zero_receive=0,zero_service=0;
reg [343:0] zero_owner=0;reg [183:0] zero_route=0;
assign m_zero_packet_owner={zero_route,zero_owner};
assign m_zero_packet_owner_valid=state==ZERO_ARM && !rst;
wire zero_retire_ok=(^{s_zero_retire_owner,s_zero_retire_core})!==1'bx &&
 s_zero_retire_owner===zero_owner && s_zero_retire_core[343:0]===zero_owner &&
 s_zero_retire_core[367:344]==request_psn+24'd1 && s_zero_retire_core[399:392]==8'h0f;
assign m_zero_retire_ready=zero_service && state==ZERO_WAIT && zero_retire_ok && !fault && !rst;
''')
    t=once(t,'wire receive_wire=RECV_ENABLE && (send_wire || opcode==8\'h0b);',r'''
wire receive_wire=RECV_ENABLE && (send_wire || opcode==8'h0b);
wire zero_service_wire=REQUEST_CQ_ENABLE && parsed_length==0 && (opcode==8'h0a || opcode==8'h0c);
wire zero_context_ok=(^held_rx_context)!==1'bx && held_rx_context[23:0]==local_qpn &&
 held_rx_context[39:24]==trusted_pd && held_rx_context[103:40]!=0 && held_rx_context[167:104]!=0 &&
 held_rx_context[191:168]==peer_qpn && held_rx_context[223:192]==local_ip && held_rx_context[255:224]==peer_ip &&
 (write_wire ? held_rx_context[353]:held_rx_context[354]);
''')
    t=once(t,'(parsed_length==0 && (!receive_wire || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE))',
        '(parsed_length==0 && !zero_service_wire && (!receive_wire || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE))')
    t=once(t,'                    else if(receive_wire && !s_recv_valid)begin',
        '                    else if(zero_service_wire && !zero_context_ok)m_reject_error<=ERR_QP;\n'
        '                    else if(zero_service_wire && !zero_mac_available)state<=PARSE;\n'
        '                    else if(receive_wire && !s_recv_valid)begin')
    t=once(t,'                        state<=receive_wire ? RECV_ARM : LOOKUP;',r'''
                        if(zero_service_wire)begin
                            // The snapshotted privileged context grants NO
                            // memory transaction. Retain the real packet lease
                            // until its OWN HLS+MAC/SFD/EOF/tail retirement.
                            zero_service<=1;lease<=1;lease_tag<=lease_tag+16'd1;
                            zero_owner<={32'd0,be32(header,48),be64(header,40),opcode,parsed_psn,
                                lease_tag+16'd1,held_rx_context[167:104],held_rx_context[103:40],trusted_pd,local_qpn};
                            zero_route<={held_rx_context[303:256],held_rx_context[351:304],
                                local_ip,peer_ip,peer_qpn};
                            dma_address<=0;lease_key<=0;lease_offset<=0;
                            command_done<=0;data_done<=0;committed<=0;data_remaining<=0;wire_remaining<=0;
                            accepted_count<=accepted_count+1'b1;forward_index<=0;state<=ZERO_ARM;
                        end else state<=receive_wire ? RECV_ARM : LOOKUP;
''')
    t=once(t,'                OWNER_ARM: if(recv_owner_valid && recv_owner_ready)state<=FORWARD;',r'''
                ZERO_ARM: if(m_zero_packet_owner_valid && s_zero_packet_owner_ready)state<=FORWARD;
                ZERO_WAIT: if(s_zero_retire_valid && m_zero_retire_ready)begin
                    zero_service<=0;lease<=0;completed_count<=completed_count+1'b1;
                    expected_psn<=s_zero_retire_core[367:344];state<=COLLECT;
                    word_count<=0;byte_count<=0;frame_bad<=0;header<=0;
                end
                OWNER_ARM: if(recv_owner_valid && recv_owner_ready)state<=FORWARD;
''')
    first=t.index('                ACTIVE: if(m_axis_tx_tvalid');end=t.index('                REJECT: begin',first)
    block=t[first:end]
    block=once(block,'                    lease<=0;completed_count<=completed_count+1\'b1;',
        '                    if(zero_service)state<=ZERO_WAIT;\n                    else begin\n'
        '                    lease<=0;completed_count<=completed_count+1\'b1;')
    tail='                end\n'
    if not block.endswith(tail):raise ValueError('actual ACTIVE boundary changed')
    block=block[:-len(tail)]+'                    end\n'+tail
    t=t[:first]+block+t[end:]
    t=once(t,'committed<=0;zero_receive<=0;',
        'committed<=0;zero_receive<=0;zero_service<=0;zero_owner<=0;zero_route<=0;')
    t=once(t,'assign m_memory_command_valid=lease && !zero_receive',
        'assign m_memory_command_valid=lease && !zero_service && !zero_receive')
    t=once(t,'assign s_memory_status_ready=lease && !zero_receive',
        'assign s_memory_status_ready=lease && !zero_service && !zero_receive')
    if t.count('(committed || zero_receive)')!=2:raise ValueError('retain both actual TX gates')
    t=t.replace('(committed || zero_receive)','(committed || zero_receive || zero_service)')
    if t.count('(!lease || zero_receive ||')!=3:raise ValueError('all actual memory offer guards required')
    t=t.replace('(!lease || zero_receive ||','(!lease || zero_receive || zero_service ||')
    t=once(t,'if(lease && zero_receive && (s_memory_status_valid || s_axis_memory_read_tvalid))',
        'if(lease && (zero_receive || zero_service) && (s_memory_status_valid || s_axis_memory_read_tvalid))')
    return once(t,'            if(atomic_native_fault)begin',r'''
            if((s_zero_hls_owner_valid && (!zero_service || s_zero_hls_owner!==zero_owner)) ||
               (m_zero_core_done_valid && !zero_service) || (s_zero_retire_valid && !zero_retire_ok))begin
                fault<=1;fault_code<=ERR_UNEXPECTED;
            end
            if(atomic_native_fault)begin''')


def shared(t):
    t=ports(t,HLS)
    first=t.index('generate if(QP_TX_ENABLE)begin : qptx_core');last=t.index('end else begin : legacy_core',first)
    block=connect(t[first:last],'core',[
        ('s_zero_owner','s_zero_hls_owner'),('s_zero_owner_valid','s_zero_hls_owner_valid'),
        ('s_zero_owner_ready','m_zero_hls_owner_ready'),('m_zero_done','m_zero_core_done'),
        ('m_zero_done_valid','m_zero_core_done_valid'),('m_zero_done_ready','s_zero_core_done_ready')])
    t=t[:first]+block+t[last:]
    return once(t,'end else begin : legacy_core',
        "end else begin : legacy_core\nassign m_zero_hls_owner_ready=0;assign m_zero_core_done=0;assign m_zero_core_done_valid=0;")


def bridge(t):
    items=[('input','[343:0]','s_zero_owner'),('input','','s_zero_owner_valid'),('output','','s_zero_owner_ready'),
        ('output','[399:0]','m_zero_done'),('output','','m_zero_done_valid'),('input','','m_zero_done_ready')]
    t=ports(t,items)
    t=once(t,'rocev2_native_zero_rq_top transport (','rocev2_native_zero_service_top transport (')
    return connect(t,'transport',[(port,signal)for prefix,signal in [
        ('s_axis_zero_owner','s_zero_owner'),('m_axis_zero_done','m_zero_done')]
        for port,signal in [(prefix+'_TDATA',signal),(prefix+'_TVALID',signal+'_valid'),(prefix+'_TREADY',signal+'_ready')]])


def root(t):
    t=connect(t,'native',same(FLOW))
    # OUTSIDE existing Atomic/native tag policies, so no inner validator is
    # weakened to accept a foreign namespace. Translate only real owned SFD.
    for n in ['tdata','tkeep','tvalid','tready','tlast','tuser']:
        t=once(t,'.m_axis_mac_'+n+'(m_axis_mac_tx_'+n+'),','.m_axis_mac_'+n+'(zero_native_'+n+'),')
    for n in ['tag','ts','valid','ready']:
        t=once(t,'.s_mac_cpl_'+n+'(s_axis_mac_cpl_'+n+'),','.s_mac_cpl_'+n+'(zero_native_cpl_'+n+'),')
    t=once(t,'assign atomic_lease_guard=atomic_rx_guard ||',
        'assign atomic_lease_guard=zero_wire_guard || zero_reservation_guard || zero_wire_fault || zero_reservation_fault || atomic_rx_guard ||')
    t=once(t,'assign fault=native_fault || pipeline_fault ||',
        'assign fault=zero_wire_fault || zero_reservation_fault || native_fault || pipeline_fault ||')
    t=once(t,'assign fault_code=native_fault ?',
        "assign fault_code=zero_wire_fault ? 8'hde : zero_reservation_fault ? 8'hdf : native_fault ?")
    t=once(t,'assign local_execution_guard=ex_queue_guard |',
        'assign local_execution_guard=zero_wire_queue_guard | zero_reservation_queue_guard | ex_queue_guard |')
    logic=helpers.rx.declarations(FLOW)+r'''
wire zero_wire_guard,zero_wire_fault,zero_wire_busy,zero_tags_exhausted;
wire zero_reservation_guard,zero_reservation_fault;
wire [7:0] zero_wire_queue_guard,zero_reservation_queue_guard;
wire [527:0] zero_reserved_owner;wire zero_reserved_valid,zero_reserved_ready;
wire [127:0] zero_native_tdata;wire [15:0] zero_native_tkeep;
wire zero_native_tvalid,zero_native_tready,zero_native_tlast;wire [16:0] zero_native_tuser;
wire [15:0] zero_native_cpl_tag;wire [95:0] zero_native_cpl_ts;
wire zero_native_cpl_valid,zero_native_cpl_ready;
assign zero_mac_available=!zero_wire_busy && !zero_tags_exhausted && !zero_reservation_guard &&
 !zero_wire_fault && !zero_reservation_fault && response_tx_quiescent===1'b1 && !fault;
'''
    logic+=helpers.rx.instance(RTL/'rocev2_zero_service_owner.v','zero_reservation',dict(
        clk='clk',rst='rst',parent_fault='parent_fault || fault',s_owner='m_zero_packet_owner',
        s_valid='m_zero_packet_owner_valid',s_ready='s_zero_packet_owner_ready',
        m_mac_owner='zero_reserved_owner',m_mac_valid='zero_reserved_valid',m_mac_ready='zero_reserved_ready',
        m_hls_owner='s_zero_hls_owner',m_hls_valid='s_zero_hls_owner_valid',m_hls_ready='m_zero_hls_owner_ready',
        configuration_guard='zero_reservation_guard',queue_guard='zero_reservation_queue_guard',
        fault='zero_reservation_fault',reserved_count='',delivered_count=''))
    p=dict(clk='clk',rst='rst',enable="1'b1",parent_fault='parent_fault || fault',
        s_owner='zero_reserved_owner',s_owner_valid='zero_reserved_valid',s_owner_ready='zero_reserved_ready',
        s_core_done='m_zero_core_done',s_core_valid='m_zero_core_done_valid',s_core_ready='s_zero_core_done_ready',
        m_retire_owner='s_zero_retire_owner',m_retire_core='s_zero_retire_core',
        m_retire_tag='',m_retire_timestamp='',m_retire_valid='s_zero_retire_valid',m_retire_ready='m_zero_retire_ready',
        queue_guard='zero_wire_queue_guard',configuration_guard='zero_wire_guard',busy='zero_wire_busy',
        fault='zero_wire_fault',fault_code='',active_tag='',tags_exhausted='zero_tags_exhausted',
        frame_count='',receipt_count='',retired_count='')
    for n in ['tdata','tkeep','tvalid','tready','tlast','tuser']:
        p['s_axis_native_'+n]='zero_native_'+n;p['m_axis_mac_'+n]='m_axis_mac_tx_'+n
    for n in ['tag','ts','valid','ready']:
        p['s_mac_cpl_'+n]='s_axis_mac_cpl_'+n;p['m_native_cpl_'+n]='zero_native_cpl_'+n
    logic+=helpers.rx.instance(RTL/'rocev2_zero_service_mac.v','zero_wire_lifetime',p)
    return once(t,'assign fault=zero_wire_fault ||',logic+'\nassign fault=zero_wire_fault ||')


def derive():
    out=base.derive();out[PROTECTED]=protected(out[PROTECTED])
    p=RTL/'rocev2_shared_hls_transport.v';out[p]=shared(out[p])
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v';out[p]=bridge(out[p])
    p=RTL/'rocev2_paged_responder.v'
    out[p]=helpers.guard_connections(ports(out[p],FLOW),same(FLOW))
    for name,child in [('rocev2_controlled_responder','endpoint'),
                      ('rocev2_dual_ethernet_endpoint','responder'),('rocev2_native_endpoint','datapath'),
                      ('rocev2_native_sq_endpoint','network')]:
        p=RTL/(name+'.v');out[p]=connect(ports(out[p],FLOW),child,same(FLOW))
    p=RTL/'rocev2_native_rnic_endpoint.v';out[p]=root(out[p])
    return out
