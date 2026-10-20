# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked Atomic128 cohort with genuine per-QP remote-Atomic authority.

RNC bit1024 is NEW; default and prior proof-bound cohorts stay unchanged.
Privileged accepted QP access is bound to the actual SQC cookie/epoch/PD,
then retained with raw RX references and captured by the actual executor.
General RX admission remains valid for READ/WRITE-only QPs. Atomic denial
returns real RemoteAccess NAK0x62 BEFORE replay, lock, MR query or memory.
The existing actual MR op4 permission is STILL separately required.
No HLS ABI, global drain, clock, default driver or capability relaxation.
"""
import derive_atomic128_native as base

ROOT=base.ROOT;RTL=base.RTL;once=base.once
authority=base.base.rx.stage.authority
ports=authority.ports;connect=authority.connect
BINDING=RTL/'rocev2_atomic_qp_binding.v'
CONTROL=RTL/'rocev2_mr_control.v'
REGS=RTL/'rocev2_control_regs.v'
REFS=RTL/'rocev2_native_rx_refs.v'
EXECUTOR=RTL/'rocev2_atomic_responder.v'
ACCESS=[('output','[3:0]','atomic_bound_access')]
CONTEXT=[('input','[3:0]','atomic_context_access')]


def binding():
    t=BINDING.read_text()
    t=once(t,'    input wire [23:0] cfg_qpn,input wire [15:0] cfg_pd,',
        '    input wire [3:0] cfg_access,\n    input wire [23:0] cfg_qpn,input wire [15:0] cfg_pd,')
    t=once(t,'    output reg [23:0] bound_qpn=0,',
        '    output reg [3:0] bound_access=0,\n    output reg [23:0] bound_qpn=0,')
    t=once(t,'{cfg_valid,cfg_tx_only,cfg_qpn,cfg_pd,',
        '{cfg_access,cfg_valid,cfg_tx_only,cfg_qpn,cfg_pd,')
    t=once(t,'assign cfg_binding_ready=cfg_known &&',
        "wire access_ok=cfg_tx_only || cfg_pd==0 ? cfg_access==0 :\n"
        "    (cfg_access==4'h6 || cfg_access==4'he);\n"
        'assign cfg_binding_ready=access_ok && cfg_known &&')
    t=once(t,'        bound_valid<=0;bound_qpn<=0;',
        '        bound_access<=0;bound_valid<=0;bound_qpn<=0;')
    t=once(t,'            bound_valid<=cfg_pd!=0;',
        "            bound_access<=cfg_pd!=0 ? cfg_access:4'd0;\n            bound_valid<=cfg_pd!=0;")
    # Do NOT gate the general trusted RX binding with Atomic permission.
    if t.count("assign admission_valid=bound_valid && live_owner_ok && cfg_valid===1'b0 && !halted && !rst;")!=1:
        raise ValueError('ordinary RX admission must be preserved')
    return t


def control():
    t=once(CONTROL.read_text(),'    output wire [15:0] cfg_qp_pd,',
        '    output wire [15:0] cfg_qp_pd,\n    output wire [3:0] cfg_qp_access,')
    t=once(t,'assign cfg_qp_pd=pd;', 'assign cfg_qp_pd=pd;\nassign cfg_qp_access=access;')
    return once(t,'                else if((command==RUN || command==QP || command==QP_TX)',
        "                else if(command==QP && ((^{pd,access})===1'bx ||\n"
        "                    (pd==0 ? access!=0 : (access!=4'h6 && access!=4'he)))) reply_error(ERR_SHAPE);\n"
        '                else if((command==RUN || command==QP || command==QP_TX)')


def executor():
    t=once(EXECUTOR.read_text(),'    input wire [63:0] s_request_epoch,',
        '    input wire [3:0] s_request_access,\n    input wire [63:0] s_request_epoch,')
    t=once(t,'reg [319:0] request=0;', 'reg [319:0] request=0;\nreg [3:0] request_access=0;')
    t=once(t,'        state<=IDLE;request<=0;', '        request_access<=0;state<=IDLE;request<=0;')
    t=once(t,'                request<=s_request_header;',
        '                request_access<=s_request_access;request<=s_request_header;')
    return once(t,'                else if(cache_valid[qi] &&',
        "                // Immutable accepted raw-RX QP permission, not a live head/lookup.\n"
        "                // Denial has an owned NAK completion, never synthetic MR success.\n"
        "                else if(request_access!==4'he)begin qp_error[qi]<=1;nak(8'h62,psn);end\n"
        '                else if(cache_valid[qi] &&')


def derive():
    out=base.derive()
    out[BINDING]=binding();out[CONTROL]=control();out[EXECUTOR]=executor()
    out[REGS]=once(REGS.read_text(),'(IMMEDIATE_ENABLE ? 512 : 0);',
        '(IMMEDIATE_ENABLE ? 512 : 0) | 1024;')
    t=REFS.read_text()
    if t.count('[351:0]')!=2:raise ValueError('raw RX context geometry changed')
    out[REFS]=t.replace('[351:0]','[355:0]')
    p=RTL/'rocev2_controlled_responder.v';t=ports(out[p],ACCESS)
    t=once(t,'wire atomic_cfg_binding_ready,atomic_child_qp_ready;',
        'wire [3:0] cfg_qp_access;\nwire atomic_cfg_binding_ready,atomic_child_qp_ready;')
    t=connect(t,'controller',[('cfg_qp_access','cfg_qp_access')])
    t=connect(t,'atomic_binding',[('cfg_access','cfg_qp_access'),('bound_access','atomic_bound_access')])
    out[p]=connect(t,'endpoint',[('atomic_context_access','atomic_bound_access')])
    for name,child in [('rocev2_dual_ethernet_endpoint','responder'),
                       ('rocev2_native_endpoint','datapath'),
                       ('rocev2_native_sq_endpoint','network'),
                       ('rocev2_native_rnic_endpoint','native')]:
        p=RTL/(name+'.v');out[p]=connect(ports(out[p],ACCESS),child,
            [('atomic_bound_access','atomic_bound_access')])
    p=RTL/'rocev2_paged_responder.v'
    out[p]=base.base.guard_connections(ports(out[p],CONTEXT),
        [('atomic_context_access','atomic_context_access')])
    p=authority.base.responder.ORIGINAL;t=ports(out[p],CONTEXT)
    t=once(t,'wire [351:0] held_rx_context;', 'wire [355:0] held_rx_context;')
    t=once(t,'wire [351:0] current_rx_context={atomic_peer_mac,',
        'wire [355:0] current_rx_context={atomic_context_access,atomic_peer_mac,')
    out[p]=connect(t,'atomic_execution',[('s_request_access','held_rx_context[355:352]')])
    return out
