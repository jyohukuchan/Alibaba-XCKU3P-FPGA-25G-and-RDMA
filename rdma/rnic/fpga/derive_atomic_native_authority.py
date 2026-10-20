# SPDX-License-Identifier: BSD-2-Clause-Views
"""Atomic QP authority stage in the complete checked Immediate native graph.

Real SQC lookup -> native/dual/control -> accepted privileged RX route binding.
Preserves one actual normal HLS/MR/PTE/backend and default/rollback sources.
Atomic packet dispatch/service/memory/MAC integration is NOT selected yet.
The explicit top lease input must later be driven by the actual Atomic
lifetimes, not software or a constant drain. No Atomic capability advertised.
"""
from pathlib import Path
import re
import derive_immediate_native as base
import derive_atomic_owner_lookup as lookup

ROOT=base.ROOT
RTL=base.RTL
once=base.once
EXTRA=[RTL/'rocev2_atomic_qp_binding.v']
ROOT_PORTS=[
    ('input','','atomic_lease_guard'),
    ('output','','atomic_admission_valid'),('output','','atomic_bound_valid'),
    ('output','[23:0]','atomic_bound_qpn'),('output','[15:0]','atomic_bound_pd'),
    ('output','[63:0]','atomic_bound_cookie'),('output','[63:0]','atomic_bound_epoch'),
    ('output','[23:0]','atomic_bound_peer_qpn'),
    ('output','[31:0]','atomic_bound_local_ip'),('output','[31:0]','atomic_bound_peer_ip'),
    ('output','','atomic_binding_guard'),('output','[7:0]','atomic_binding_queue_guard'),
    ('output','','atomic_binding_fault')]
QUERY_PORTS=[
    ('output','[23:0]','m_atomic_query_qpn'),
    ('input','[63:0]','s_atomic_query_cookie'),('input','[63:0]','s_atomic_query_epoch'),
    ('input','[15:0]','s_atomic_query_pd'),('input','','s_atomic_query_valid')]


def ports(t,items):
    declarations='\n'.join('    '+d+' wire '+(w+' 'if w else'')+n+','for d,w,n in items)
    return once(t,'    input wire clk,',declarations+'\n    input wire clk,')


def connect(t,name,items):
    matches=list(re.finditer(r'(?<!\w)'+re.escape(name)+r'\s*\(',t))
    if len(matches)!=1:raise ValueError('one real child required: '+name)
    i=matches[0].end()
    return t[:i]+'\n'+',\n'.join('.'+n+'('+v+')'for n,v in items)+','+t[i:]


def same(items):return [(n,n)for _,_,n in items]


def controlled(t):
    t=ports(t,ROOT_PORTS+QUERY_PORTS)
    t=once(t,'assign admission_paused=control_pause || control_mmio_error;',BINDING+'\nassign admission_paused=control_pause || control_mmio_error;')
    t=once(t,'assign fault=endpoint_fault || control_fatal || control_mmio_error;',
        'assign fault=endpoint_fault || control_fatal || control_mmio_error || atomic_binding_fault;')
    t=once(t,'assign fault_code=endpoint_fault ? endpoint_fault_code :',
        "assign fault_code=endpoint_fault ? endpoint_fault_code : atomic_binding_fault ? 8'hd6 :")
    t=once(t,'assign quiescent=endpoint_quiescent &&',
        'assign quiescent=endpoint_quiescent && !atomic_binding_guard &&')
    t=once(t,'    .cfg_qp_valid(cfg_qp_valid),\n    .cfg_qp_ready(cfg_qp_ready),',
        '    .cfg_qp_valid(cfg_qp_valid && atomic_cfg_binding_ready),\n    .cfg_qp_ready(atomic_child_qp_ready),')
    t=once(t,'.local_work_guard(local_work_guard),',
        '.local_work_guard(local_work_guard || atomic_binding_guard),')
    return t


BINDING=r'''
wire atomic_cfg_binding_ready,atomic_child_qp_ready;
assign cfg_qp_ready=atomic_child_qp_ready && atomic_cfg_binding_ready;
rocev2_atomic_qp_binding atomic_binding(
 .clk(clk),.rst(rst),.parent_fault(control_fatal || control_mmio_error || endpoint_fault),
 .cfg_valid(cfg_qp_valid),.cfg_fire(cfg_qp_valid && cfg_qp_ready),.cfg_tx_only(cfg_qp_tx_only),
 .cfg_qpn({21'd0,cfg_qp_number}),.cfg_pd(cfg_qp_pd),.cfg_peer_qpn(cfg_peer_qp_number),
 .cfg_local_ip(cfg_local_ip),.cfg_peer_ip(cfg_peer_ip),.cfg_binding_ready(atomic_cfg_binding_ready),
 .m_query_qpn(m_atomic_query_qpn),.s_query_cookie(s_atomic_query_cookie),.s_query_epoch(s_atomic_query_epoch),
 .s_query_pd(s_atomic_query_pd),.s_query_valid(s_atomic_query_valid),.lease_guard(atomic_lease_guard),
 .admission_valid(atomic_admission_valid),.bound_valid(atomic_bound_valid),
 .bound_qpn(atomic_bound_qpn),.bound_pd(atomic_bound_pd),.bound_cookie(atomic_bound_cookie),.bound_epoch(atomic_bound_epoch),
 .bound_peer_qpn(atomic_bound_peer_qpn),.bound_local_ip(atomic_bound_local_ip),.bound_peer_ip(atomic_bound_peer_ip),
 .configuration_guard(atomic_binding_guard),.queue_guard(atomic_binding_queue_guard),.fault(atomic_binding_fault));
'''


def native_sq(t):
    t=ports(t,ROOT_PORTS)
    decl=r'''
wire [23:0] atomic_owner_query_qpn;
wire [63:0] atomic_owner_query_cookie,atomic_owner_query_epoch;
wire [15:0] atomic_owner_query_pd;wire atomic_owner_query_valid;
'''
    t=once(t,'wire [63:0] sq_owner_query_cookie,',decl+'\nwire [63:0] sq_owner_query_cookie,')
    wiring=[('m_atomic_query_qpn','atomic_owner_query_qpn'),('s_atomic_query_cookie','atomic_owner_query_cookie'),
        ('s_atomic_query_epoch','atomic_owner_query_epoch'),('s_atomic_query_pd','atomic_owner_query_pd'),
        ('s_atomic_query_valid','atomic_owner_query_valid')]
    t=connect(t,'network',same(ROOT_PORTS)+wiring)
    lookup_wiring=[('atomic_query_qpn','atomic_owner_query_qpn'),('atomic_query_cookie','atomic_owner_query_cookie'),
        ('atomic_query_epoch','atomic_owner_query_epoch'),('atomic_query_pd','atomic_owner_query_pd'),
        ('atomic_query_valid','atomic_owner_query_valid')]
    t=connect(t,'queue_control',lookup_wiring)
    t=connect(t,'receive_queue_control',[('atomic_query_qpn',"24'd0"),
        ('atomic_query_cookie',''),('atomic_query_epoch',''),('atomic_query_pd',''),('atomic_query_valid','')])
    needle='.wire_queue_guard(wire_queue_guard),'
    if t.count(needle)!=2:raise ValueError('both actual SQ/RQ guards required')
    t=t.replace(needle,'.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard),')
    t=once(t,'assign local_work_guard=rq_admission_configuration_guard ||',
        'assign local_work_guard=atomic_binding_guard || rq_admission_configuration_guard ||')
    return t


def derive():
    out=base.derive()
    out[lookup.SOURCE]=lookup.derive()
    path=RTL/'rocev2_controlled_responder.v';out[path]=controlled(out[path])
    for name,child in [('rocev2_dual_ethernet_endpoint','responder'),('rocev2_native_endpoint','datapath')]:
        path=RTL/(name+'.v')
        out[path]=connect(ports(out[path],ROOT_PORTS+QUERY_PORTS),child,same(ROOT_PORTS+QUERY_PORTS))
    path=RTL/'rocev2_native_sq_endpoint.v';out[path]=native_sq(out[path])
    path=RTL/'rocev2_native_rnic_endpoint.v'
    out[path]=connect(ports(out[path],ROOT_PORTS),'native',same(ROOT_PORTS))
    return out
