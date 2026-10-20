# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked zero-requester extension of the SAME Atomic-access native graph.

Zero bytes require canonical no-local-memory fields, not an invented MR grant
or DMA status. READ still waits for the actual protected identical response
token. Wire/HLS/MAC/CQ owners and all drain/timing gates remain independent.
RNC4095 is a PRIVATE integration candidate: incoming zero/RQ and matched
provider/runtime/physical qualification remain separate, unfinished work.
Default and prior proof-bound sources are never rewritten.
"""
import derive_atomic_access_native as base

ROOT=base.ROOT;RTL=base.RTL;once=base.once
ICRC=ROOT/'rdma/rtl/rocev2_ipv4_icrc.v'


def integrity():
    # SEND_ONLY has no RETH/AETH/Immediate: IPv4+UDP+BTH+ICRC =44 bytes.
    # Keep the original integrity module for every legacy/default caller.
    # This new named native-only clone admits44 ONLY for that exact shape;
    # all original checksum/ICRC/UDP/dense-mask/full-frame checks stay intact.
    t=once(ICRC.read_text(),'module rocev2_ipv4_icrc #(',
        'module rocev2_zero_ipv4_icrc #(')
    t=once(t,'packet_length < 48 ||','packet_length < 44 ||')
    return once(t,'    if (!first_reg && offset_reg == 16) begin',
        '    if (!first_reg && offset_reg == 16) begin\n'
        "        if (ip_length_reg == 44 && (s_axis_tdata[103:96] != 8'h04 ||\n"
        "                s_axis_tdata[109:108] != 2'd0)) bad_current = 1;")


def length_policy(t,old,fields):
    return once(t,old+'!=0 && '+old+'<=4096',
        '('+old+'!=0 || {'+fields+'}==0) && '+old+'<=4096')


def admission(t):
    t=once(t,'wire length_ok=atomic_opcode ? length==8:length!=0 && length<=4096;',
        'wire zero_request=length==0 && !atomic_opcode && opcode!=4 &&\n'
        '    record[191:128]==0 && record[319:288]==0;\n'
        'wire length_ok=atomic_opcode ? length==8:(zero_request || (length!=0 && length<=4096));')
    return once(t,"        else begin\n            local_last<={1'b0,record[191:128]}",
        '        // The real accepted queue/descriptor owns zero work, but no MR\n'
        '        // or data address is consulted and no MR response is invented.\n'
        '        else if(zero_request)begin authorized_offset<=0;state<=RESULT;end\n'
        "        else begin\n            local_last<={1'b0,record[191:128]}")


def executor(t):
    t=length_policy(t,'in_length','in_key,in_address,in_offset')
    t=once(t,'m_memory_event_valid<=!in_authorized;',
        'm_memory_event_valid<=!in_authorized || (in_length==0 && in_opcode!=2);')
    t=once(t,'if(s_read_response_valid && s_read_response_ready)placement_seen<=1;',
        'if(s_read_response_valid && s_read_response_ready)begin\n'
        '            placement_seen<=1;\n'
        '            // No-data READ is proven only by the genuine protected\n'
        '            // full-owner response token, not an idle data interface.\n'
        '            if(length==0)m_memory_event_valid<=1;\n'
        '        end')
    t=once(t,'(!active || !authorized || opposite_valid || raw_seen || !raw_match)',
        '(!active || !authorized || length==0 || opposite_valid || raw_seen || !raw_match)')
    t=once(t,'wire take_raw=active && authorized && !raw_seen',
        'wire take_raw=active && authorized && length!=0 && !raw_seen')
    return once(t,'(!active || !authorized || (placement ? s_axis_memory_read_tvalid',
        '(!active || !authorized || length==0 || (placement ? s_axis_memory_read_tvalid')


def unpad(t):
    t=length_policy(t,'in_length','in_key,in_va,in_offset')
    t=once(t,'(s_command_valid && (!active || command_seen || !command_match))',
        '(s_command_valid && (!active || length==0 || command_seen || !command_match))')
    t=once(t,'assign s_command_ready=active && !command_seen',
        'assign s_command_ready=active && length!=0 && !command_seen')
    t=once(t,'        if(s_command_valid && s_command_ready)',
        '        // Only this empty pad-staging lease ends. The executor took\n'
        '        // the SAME protected token atomically and retains the WR.\n'
        '        if(active && length==0 && held_guard && !fault && !command_bad &&\n'
        "           s_axis_tvalid===1'b0 && !m_command_valid && !m_axis_tvalid)active<=0;\n"
        '        if(s_command_valid && s_command_ready)')
    return once(t,'(s_axis_tvalid && (!active || (issued &&',
        '(s_axis_tvalid && (!active || length==0 || (issued &&')


def derive():
    out=base.derive()
    p=RTL/'rocev2_wqe_admission.v';out[p]=admission(out[p])
    p=RTL/'rocev2_wqe_hls_sq.v'
    out[p]=length_policy(out[p],'in_length','in_local_key,in_local_address,in_local_offset')
    p=RTL/'rocev2_wqe_memory_executor.v';out[p]=executor(out[p])
    p=RTL/'rocev2_wqe_read_unpad.v';out[p]=unpad(out[p])
    for name in ['rocev2_wqe_response_guard','rocev2_wqe_lifetime','rocev2_wqe_mac_tx']:
        p=RTL/(name+'.v');out[p]=length_policy(out[p],'in_length','in_key,in_va,in_offset')
    p=RTL/'rocev2_shared_hls_transport.v'
    out[p]=length_policy(out[p],'length','key,va,offset')
    p=RTL/'rocev2_cq_mmio.v'
    out[p]=once(out[p],"s_ticket_context[307:276]!=0 &&\n    s_ticket_context[307:276]<=4096",
        '(s_ticket_context[307:276]!=0 || (incoming_opcode!=4 &&\n'
        '     s_ticket_context[275:116]==0)) &&\n    s_ticket_context[307:276]<=4096')
    p=RTL/'rocev2_control_regs.v'
    out[p]=once(out[p],'(IMMEDIATE_ENABLE ? 512 : 0) | 1024;',
        '(IMMEDIATE_ENABLE ? 512 : 0) | 1024 | 2048;')
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v'
    out[p]=once(out[p],'rocev2_native_atomic_request_top transport (',
        'rocev2_native_zero_request_top transport (')
    if out[p].count('rocev2_ipv4_icrc #(')!=2:raise ValueError('both actual native integrity instances required')
    out[p]=out[p].replace('rocev2_ipv4_icrc #(','rocev2_zero_ipv4_icrc #(')
    out[ICRC]=integrity()
    return out
