# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same-core zero RQ native candidate; no fabricated memory completion.

Actual posted owner, verified wire, HLS EOF/PSN receipt, ACK MAC and CQ
commit/retire remain independent gates. Zero RX never grants MR/DMA access.
Normal incoming zero WRITE/READ remain refused until their real non-RQ
service ownership is implemented. Default/proof-bound graphs are untouched.
Requires matching rocev2_native_zero_rq_top HLS generation before runtime.
"""
import derive_zero_native as base

ROOT=base.ROOT;RTL=base.RTL;once=base.once;ICRC=base.ICRC
PROTECTED=RTL/'rocev2_protected_responder.v'
RQ=RTL/'rocev2_receive_queue.v'
ACK=RTL/'rocev2_receive_ack_tx.v'
INGRESS=RTL/'rocev2_responder_ethernet_rx.v'
EXTRA=[RTL/'rocev2_zero_rx_padding.v']


def receive_queue(t):
    t=once(t,'length!=0 && length<=4096 &&',
        '(length!=0 || (RECV_RETIRE_ENABLE && RECV_CQ_ENABLE && s_post_context[275:116]==0)) && length<=4096 &&')
    t=once(t,"(^s_placement_length)!==1'bx && s_placement_length!=0 && s_placement_length<=4096",
        "(^s_placement_length)!==1'bx && s_placement_length<=4096")
    return once(t,'s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]!=0 && s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096',
        's_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096')


def protected(t):
    t=once(t,'reg lease=0, write_operation=0, command_done=0, data_done=0, committed=0;',
        'reg lease=0, write_operation=0, command_done=0, data_done=0, committed=0;\n'
        '// Explicit no-data ownership, NEVER a fabricated backend status.\n'
        'reg zero_receive=0;')
    t=once(t,'s_recv_context[307:276]!=0 && s_recv_context[307:276]<=4096',
        '(s_recv_context[307:276]!=0 || s_recv_context[275:116]==0) && s_recv_context[307:276]<=4096')
    t=once(t,'parsed_length==0 || parsed_length>4096',
        '(parsed_length==0 && (!receive_wire || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE)) || parsed_length>4096')
    t=once(t,'byte_count<(send_wire ? send_header_bytes+4 : 60)',
        'byte_count<(send_wire ? send_header_bytes : 60)')
    t=once(t,'request_length<=parsed_length;request_psn<=parsed_psn;',
        'request_length<=parsed_length;request_psn<=parsed_psn;\n'
        '                        zero_receive<=receive_wire && parsed_length==0;')
    t=once(t,'RECV_ARM: if(s_recv_valid && s_recv_ready)state<=LOOKUP;',r'''
                RECV_ARM: if(s_recv_valid && s_recv_ready)begin
                    if(zero_receive)begin
                        // The genuine RQ handshake acquires a no-data lease.
                        // No MR query/response/command/data/status is invented.
                        lease<=1;lease_tag<=lease_tag+16'd1;
                        dma_address<=0;lease_key<=0;lease_offset<=0;
                        command_done<=0;data_done<=0;committed<=0;
                        data_remaining<=0;wire_remaining<=0;
                        accepted_count<=accepted_count+1'b1;forward_index<=0;
                        state<=OWNER_ARM;
                    end else state<=LOOKUP;
                end''')
    t=once(t,'lease<=0;write_operation<=0;command_done<=0;data_done<=0;committed<=0;',
        'lease<=0;write_operation<=0;command_done<=0;data_done<=0;committed<=0;zero_receive<=0;')
    t=once(t,'assign m_memory_command_valid=lease && !command_done',
        'assign m_memory_command_valid=lease && !zero_receive && !command_done')
    t=once(t,'assign s_memory_status_ready=lease && command_done',
        'assign s_memory_status_ready=lease && !zero_receive && command_done')
    if t.count('(lease && committed)')!=2:raise ValueError('both actual ACK gates required')
    t=t.replace('(lease && committed)','(lease && (committed || zero_receive))')
    for old in ['(core_write_valid && (!lease || !write_operation || command_done))',
                '(core_read_valid && (!lease || write_operation || command_done))',
                '(core_write_data_valid && (!lease || !write_operation || data_done))']:
        t=once(t,old,old.replace('(!lease ||','(!lease || zero_receive ||'))
    t=once(t,'if(lease && !command_done && selected_valid && !command_match)',
        'if(lease && zero_receive && (s_memory_status_valid || s_axis_memory_read_tvalid))begin\n'
        '                fault<=1;fault_code<=ERR_UNEXPECTED;\n'
        '            end\n'
        '            if(lease && !command_done && selected_valid && !command_match)')
    # Ethernet padding is outside IPv4/ICRC. Normalize ONLY the legitimate
    # SEND44+two-pad-byte shape, then keep the exact original IP checks.
    first=t.index('rocev2_ipv4_icrc #(.TX_MODE(0)) admission_integrity (')
    last=t.index(');',first)+2;block=t[first:last]
    for name in ['data','keep','valid','ready','last','user']:
        block=once(block,'raw_'+name,'zero_ip_'+name)
    block=once(block,'rocev2_ipv4_icrc #(','rocev2_zero_ipv4_icrc #(')
    adapter=r'''
wire [127:0] zero_ip_data;wire [15:0] zero_ip_keep;
wire zero_ip_valid,zero_ip_ready,zero_ip_last,zero_ip_user;
rocev2_zero_rx_padding zero_ethernet_padding(
 .clk(clk),.rst(rst),.s_axis_tdata(raw_data),.s_axis_tkeep(raw_keep),
 .s_axis_tvalid(raw_valid),.s_axis_tready(raw_ready),.s_axis_tlast(raw_last),.s_axis_tuser(raw_user),
 .m_axis_tdata(zero_ip_data),.m_axis_tkeep(zero_ip_keep),.m_axis_tvalid(zero_ip_valid),
 .m_axis_tready(zero_ip_ready),.m_axis_tlast(zero_ip_last),.m_axis_tuser(zero_ip_user));
'''
    return t[:first]+adapter+block+t[last:]


def ack(t):
    t=once(t,'s_owner_context[307:276]!=0 && s_owner_context[307:276]<=4096',
        '(s_owner_context[307:276]!=0 || s_owner_context[275:116]==0) && s_owner_context[307:276]<=4096')
    return once(t,'s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]!=0 && s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096',
        's_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096')


def ingress(t):
    t=once(t,'reg [15:0] dst_ip_head=0;',
        'reg [15:0] dst_ip_head=0;\nreg zero_ip44=0,zero_short_send=0;')
    t=once(t,'frame_bytes<17\'d62',
        "(frame_bytes<17'd62 && !(zero_short_send && !RESPONSE_MODE && frame_bytes==17'd60))")
    t=once(t,'enabled<=0; ipv4<=0; udp<=0; mac_match<=0; bad<=0;',
        'enabled<=0; ipv4<=0; udp<=0; mac_match<=0; bad<=0;zero_ip44<=0;zero_short_send<=0;')
    t=once(t,'enabled<=enable;saved_run_id<=run_id;',
        'enabled<=enable;saved_run_id<=run_id;zero_ip44<=0;zero_short_send<=0;')
    t=once(t,'if (offset==16) begin',
        "if(offset==32)zero_short_send<=zero_ip44 && s_axis_tdata[87:80]===8'h04 && s_axis_tdata[93:92]===2'd0;\n"
        '            if (offset==16) begin\n'
        "                zero_ip44<=be16(s_axis_tdata,0)===16'd44;")
    return t


def derive():
    out=base.derive()
    p=RTL/'rocev2_wqe_admission.v'
    out[p]=once(out[p],'length==0 && !atomic_opcode && opcode!=4 &&',
        'length==0 && !atomic_opcode &&')
    out[RQ]=receive_queue(out.get(RQ,RQ.read_text()))
    out[ACK]=ack(out.get(ACK,ACK.read_text()))
    out[INGRESS]=ingress(out.get(INGRESS,INGRESS.read_text()))
    out[PROTECTED]=protected(out[PROTECTED])
    p=RTL/'rocev2_cq_mmio.v'
    out[p]=once(out[p],'incoming_opcode==4 ? s_ticket_received_bytes!=0 &&',
        'incoming_opcode==4 ?')
    out[p]=once(out[p],'(s_ticket_context[307:276]!=0 || (incoming_opcode!=4 &&\n     s_ticket_context[275:116]==0))',
        '(s_ticket_context[307:276]!=0 || s_ticket_context[275:116]==0)')
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v'
    out[p]=once(out[p],'rocev2_native_zero_request_top transport (',
        'rocev2_native_zero_rq_top transport (')
    return out
