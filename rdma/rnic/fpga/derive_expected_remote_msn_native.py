# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual accepted outgoing-QP route/SQC identity -> expected remote MSN.

TX-only setup is observed too, without repurposing incoming Atomic binding.
Dedicated SQC lookup, genuine owner/CQ fanouts and a separate configuration
guard retain all old semantics. RX/lifetime/large READ admission stay closed.
"""
import derive_segmented_read_memory_native as parent
import derive_atomic_access_native as access

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;ports=access.ports;connect=access.connect
PRED=RTL/'rocev2_expected_remote_msn.v'
EXTRA=list(dict.fromkeys([*parent.EXTRA,PRED]))
ROUTE=[('output','','msn_route_valid'),('output','[23:0]','msn_route_qpn'),('output','[23:0]','msn_route_peer_qpn'),
       ('output','[31:0]','msn_route_local_ip'),('output','[31:0]','msn_route_peer_ip')]
QUERY=[('input','[23:0]','msn_query_qpn'),('output','[63:0]','msn_query_cookie'),('output','[63:0]','msn_query_epoch'),
       ('output','[15:0]','msn_query_pd'),('output','','msn_query_valid')]


def derive():
    out=parent.derive()
    p=RTL/'rocev2_controlled_responder.v';t=ports(out[p],[('input','','msn_cfg_guard'),*ROUTE])
    t=once(t,'assign cfg_qp_ready=atomic_child_qp_ready && atomic_cfg_binding_ready;',
        "assign cfg_qp_ready=atomic_child_qp_ready && atomic_cfg_binding_ready && msn_cfg_guard===1'b0;\n"+r'''
reg tx_route_valid=0;reg [23:0] tx_route_qpn=0,tx_route_peer=0;
reg [31:0] tx_route_local_ip=0,tx_route_peer_ip=0;
assign msn_route_valid=tx_route_valid;assign msn_route_qpn=tx_route_qpn;assign msn_route_peer_qpn=tx_route_peer;
assign msn_route_local_ip=tx_route_local_ip;assign msn_route_peer_ip=tx_route_peer_ip;
always @(posedge clk)begin
 if(rst)begin tx_route_valid<=0;tx_route_qpn<=0;tx_route_peer<=0;tx_route_local_ip<=0;tx_route_peer_ip<=0;end
 else if(cfg_qp_valid && cfg_qp_ready)begin
  tx_route_valid<=cfg_qp_tx_only || cfg_qp_pd!=0;tx_route_qpn<={21'd0,cfg_qp_number};
  tx_route_peer<=cfg_peer_qp_number;tx_route_local_ip<=cfg_local_ip;tx_route_peer_ip<=cfg_peer_ip;
 end
end
''')
    t=once(t,'.cfg_qp_valid(cfg_qp_valid && atomic_cfg_binding_ready),',
        ".cfg_qp_valid(cfg_qp_valid && atomic_cfg_binding_ready && msn_cfg_guard===1'b0),")
    out[p]=t
    for name,child in [('rocev2_dual_ethernet_endpoint','responder'),('rocev2_native_endpoint','datapath'),('rocev2_native_sq_endpoint','network')]:
        p=RTL/(name+'.v');t=ports(out[p],[('input','','msn_cfg_guard'),*ROUTE])
        out[p]=connect(t,child,[('msn_cfg_guard','msn_cfg_guard'),*[(n,n)for _,_,n in ROUTE]])
    p=RTL/'rocev2_sq_control_regs.v';t=ports(out.get(p,p.read_text()),QUERY)
    t=once(t,'reg [7:0] reply_error=0;',r'''
wire msn_query_known=(^msn_query_qpn)!==1'bx && msn_query_qpn<MAX_QPS;
wire [2:0] msn_query_index=msn_query_qpn[2:0];
// Dedicated combinational read-only owner port, not retry-policy state or
// producer head. No mailbox-busy gap can invalidate an already owned WR.
assign msn_query_valid=msn_query_known && owner_active[msn_query_index] &&
 !owner_tainted[msn_query_index] && !fatal && !endpoint_fault;
assign msn_query_cookie=msn_query_valid ? owner_cookie[msn_query_index]:0;
assign msn_query_epoch=msn_query_valid ? owner_epoch[msn_query_index]:0;
assign msn_query_pd=msn_query_valid ? owner_pd[msn_query_index]:0;
reg [7:0] reply_error=0;''')
    out[p]=t
    p=RTL/'rocev2_native_sq_endpoint.v';t=ports(out[p],QUERY)
    t=connect(t,'queue_control',[(n,n)for _,_,n in QUERY])
    t=connect(t,'receive_queue_control',[(n,"24'd0"if n=='msn_query_qpn'else'')for _,_,n in QUERY])
    out[p]=t
    p=RTL/'rocev2_native_rnic_endpoint.v';t=ports(out[p],ROUTE)
    decl=r'''
wire msn_owner_eligible,msn_expect_eligible,msn_retire_eligible,msn_cfg_guard,msn_fault,msn_busy,msn_guard_expect_ready;
wire [7:0] msn_fault_code;wire [7:0] msn_queue_guard;wire [23:0] expected_remote_msn,msn_query_qpn;
wire [63:0] msn_query_cookie,msn_query_epoch;wire [15:0] msn_query_pd;wire msn_query_valid;
wire msn_retire_fire=cq_retire_valid && !receive_retire && local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;
rocev2_expected_remote_msn #(.MAX_QPS(MAX_QPS)) remote_msn(
 .clk(clk),.rst(rst),.parent_fault(ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault || rrp_fault || rq_fault || recv_ack_fault),
 .route_valid(msn_route_valid),.route_qpn(msn_route_qpn),.route_peer_qpn(msn_route_peer_qpn),.route_local_ip(msn_route_local_ip),.route_peer_ip(msn_route_peer_ip),
 .m_query_qpn(msn_query_qpn),.s_query_valid(msn_query_valid),.s_query_cookie(msn_query_cookie),.s_query_epoch(msn_query_epoch),.s_query_pd(msn_query_pd),
 .s_owner_context(sq_m_executor_context),.s_owner_fire(owner_take),.owner_eligible(msn_owner_eligible),
 .s_expect_context(tx_m_expect_context),.s_expect_valid(tx_m_expect_valid),.expect_eligible(msn_expect_eligible),.expected_msn(expected_remote_msn),
 .s_retire_context(cq_retire_context),.s_retire_offer_valid(cq_retire_valid && !receive_retire),.s_retire_fire(msn_retire_fire),.retire_eligible(msn_retire_eligible),
 .configuration_guard(msn_cfg_guard),.queue_guard(msn_queue_guard),.busy(msn_busy),.fault(msn_fault),.fault_code(msn_fault_code),.message_count(),.retired_count());
'''
    t=once(t,'assign owner_ready=',decl+'\nassign owner_ready=msn_owner_eligible && ')
    t=once(t,'assign pipeline_fault=ex_fault ||','assign pipeline_fault=msn_fault || ex_fault ||')
    t=once(t,'assign fault_code=zero_wire_fault ?', 'assign fault_code=msn_fault ? msn_fault_code:zero_wire_fault ?')
    t=once(t,'.s_expect_valid(tx_m_expect_valid),\n    .s_expect_ready(tx_m_expect_ready),',
        '.s_expect_valid(tx_m_expect_valid && msn_expect_eligible),\n    .s_expect_ready(msn_guard_expect_ready),')
    t=once(t,'assign read_token_ready=',
        'assign tx_m_expect_ready=msn_guard_expect_ready && msn_expect_eligible;\nassign read_token_ready=')
    t=once(t,'local_retire_ready && segmented_memory_retire_ready;',
        'local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;')
    t=once(t,'.s_local_retire_valid(cq_retire_valid && !receive_retire && segmented_memory_retire_ready),',
        '.s_local_retire_valid(cq_retire_valid && !receive_retire && segmented_memory_retire_ready && msn_retire_eligible),')
    t=once(t,'.s_retire_valid(cq_retire_valid && !receive_retire && local_retire_ready),',
        '.s_retire_valid(cq_retire_valid && !receive_retire && local_retire_ready && msn_retire_eligible),')
    t=once(t,'.wire_queue_guard(rx_queue_guard | {8{!response_router_quiescent}}),',
        '.wire_queue_guard(rx_queue_guard | msn_queue_guard | {8{!response_router_quiescent}}),')
    t=connect(t,'native',[('msn_cfg_guard','msn_cfg_guard'),*[(n,n)for _,_,n in ROUTE],*[(n,n)for _,_,n in QUERY]])
    out[p]=t
    return out
