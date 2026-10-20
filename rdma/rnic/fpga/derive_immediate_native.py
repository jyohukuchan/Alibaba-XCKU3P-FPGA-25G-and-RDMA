# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched opt-in Immediate native graph, retaining the default/rollback graph.

This complete opt-in source substitution set advertises the matched native
Immediate controller tuple, NOT a programmed image/default capability.
One shared native core/MR/PTE/backend remains. Upper32
immutable request bits are never a remote-key alias or RX notification.
The original protected responder is only read, never modified.
"""
from pathlib import Path
import re
import derive_shared_responder as responder
import derive_duplex_transport as duplex
import derive_immediate_bridge as bridge

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl'
PARENTS=['rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint',
    'rocev2_native_endpoint','rocev2_dual_ethernet_endpoint',
    'rocev2_controlled_responder','rocev2_paged_responder']
LEAVES=['rocev2_wqe_memory_executor','rocev2_wqe_lifetime',
    'rocev2_wqe_mac_tx','rocev2_wqe_tx_lifetime','rocev2_wqe_response_guard',
    'rocev2_wqe_replay','rocev2_wqe_read_unpad']
once=responder.once


def widths(text):
    # Simultaneous replacement: old receive-owner648 and receive-proof680
    # have DIFFERENT new widths. Never run cascading string substitutions.
    values={587:619,247:279,647:679,655:687,679:751,695:767}
    return re.sub(r'\[(587|247|647|655|679|695):0\]',
        lambda m:'['+str(values[int(m[1])])+':0]',text)


def unpack_lower(text):
    # Existing field offsets remain lower588. Storage/whole-owner comparisons
    # retain620; explicitly slice ONLY legacy field unpacking assignments.
    return re.sub(r'(assign\s*\{[^;]+?\}\s*=\s*)(\w+)(;)',
        lambda m:m[1]+m[2]+'[587:0]'+m[3],text)


def request_fields(text):
    fields={'611:588':'643:620','635:612':'667:644',
        '643:636':'675:668','655:644':'687:676'}
    return re.sub(r'\[(611:588|635:612|643:636|655:644)\]',
        lambda m:'['+fields[m[1]]+']',text)


def allow_ops(text,context):
    # Preserve all original MR/range/proof checks, adding only the two new
    # operations. Non-Immediate WQEs MUST have canonical upper bits0.
    patterns=[('in_opcode','in_remote','in_rkey'),('in_op','in_remote','in_rkey'),
        ('opcode','remote_address','remote_key')]
    changed=0
    for op,va,key in patterns:
        old=f'({op}==1 || {op}==2 || ({op}==3 && {va}==0 && {key}==0))'
        if old in text:
            text=once(text,old,
                f'({op}==1 || {op}==2 || {op}==6 || (({op}==3 || {op}==5) && {va}==0 && {key}==0)) &&\n'
                f'    (({op}==5 || {op}==6) || {context}[619:588]==0)')
            changed+=1
    if changed!=1:raise ValueError('expected one native opcode policy: '+context)
    return text


def request_opcode(text,expression):
    old=expression+"==1 ? 8'h0a : "+expression+"==2 ? 8'h0c : 8'h04"
    return once(text,old,expression+"==1 ? 8'h0a : "+expression+"==2 ? 8'h0c : "+
        expression+"==5 ? 8'h05 : "+expression+"==6 ? 8'h0b : 8'h04")


def leaf(name,text):
    text=unpack_lower(widths(text))
    if name in ['rocev2_wqe_memory_executor','rocev2_wqe_lifetime','rocev2_wqe_mac_tx']:
        text=allow_ops(text,'s_owner_context')
    if name=='rocev2_wqe_response_guard':text=allow_ops(text,'s_expect_context')
    if name=='rocev2_wqe_memory_executor':
        text=once(text,'wire denied_work=in_error!=0 && !in_authorized &&',
            'wire denied_work=in_error!=0 && !in_authorized && s_owner_context[619:588]==0 &&')
    if name=='rocev2_wqe_read_unpad':
        text=once(text,'in_op==2 && in_available',
            'in_op==2 && s_context[619:588]==0 && in_available')
    if name=='rocev2_wqe_tx_lifetime':
        text=request_fields(text)
        text=request_opcode(text,'m_cq_context[339:324]')
    if name=='rocev2_wqe_lifetime':
        text=once(text,'wire header_ok=',r'''wire send_request=opcode==3 || opcode==5;
wire immediate_request=opcode==5 || opcode==6;
wire [7:0] request_wire_opcode=opcode==1 ? 8'h0a : opcode==2 ? 8'h0c : opcode==5 ? 8'h05 : opcode==6 ? 8'h0b : 8'h04;
wire [31:0] request_header_bytes=send_request ? (immediate_request ? 48:44) : (immediate_request ? 64:60);
wire header_ok=''')
        text=once(text,'tx_bytes>=(opcode==3 ? 44 : 60)','tx_bytes>=request_header_bytes')
        text=once(text,"(opcode==1 ? 8'h0a : opcode==3 ? 8'h04 : 8'h0c)",'request_wire_opcode')
        text=once(text,'(opcode==3 || (be64(header,40)==remote_address',
            '(send_request || (be64(header,40)==remote_address')
        text=once(text,'tx_bytes==(opcode==1 ? 60+padded : opcode==3 ? 44+padded : 60);',
            '(!immediate_request || be32(header,opcode==5 ? 40:56)==owner[619:588]) &&\n'
            '    tx_bytes==request_header_bytes+(opcode==2 ? 0:padded);')
    return text


def sidecars(text):
    text=once(text,'    output wire [31:0] m_recv_placement_length,',
        '    output wire [31:0] m_recv_placement_length,\n'
        '    output wire [31:0] m_recv_placement_notification,\n'
        '    output wire [7:0] m_recv_placement_notification_flags,')
    return once(text,'.m_recv_placement_length(m_recv_placement_length),',
        '.m_recv_placement_length(m_recv_placement_length),\n'
        '    .m_recv_placement_notification(m_recv_placement_notification),\n'
        '    .m_recv_placement_notification_flags(m_recv_placement_notification_flags),')


def parent(name,text):
    text=widths(text)
    if name!='rocev2_native_rnic_endpoint':text=sidecars(text)
    if name=='rocev2_controlled_responder':
        text=once(text,'.SEPARATE_RQ_ENABLE(SEPARATE_RQ_ENABLE)) registers (',
            '.SEPARATE_RQ_ENABLE(SEPARATE_RQ_ENABLE),.IMMEDIATE_ENABLE(1)) registers (')
    if name=='rocev2_native_sq_endpoint':
        text=once(text,'rocev2_sq_control_regs #(.MAX_QPS(MAX_QPS)) queue_control(',
            'rocev2_sq_control_regs #(.MAX_QPS(MAX_QPS),.IMMEDIATE_ENABLE(1)) queue_control(')
        text=once(text,".RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE)) receive_queue_control(",
            ".RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE),.IMMEDIATE_ENABLE(1)) receive_queue_control(")
        text=once(text,'    output wire [31:0] m_work_remote_key,',
            '    output wire [31:0] m_work_remote_key,\n    output wire [31:0] m_work_immediate,')
        text=once(text,'wire [31:0] rq_work_remote_key;',
            'wire [31:0] rq_work_remote_key;\nwire [31:0] rq_work_immediate;')
        text=once(text,'rq_work_context={rq_work_wr_id,','rq_work_context={rq_work_immediate,rq_work_wr_id,')
        text=once(text,'bridge_work_context={m_work_wr_id,','bridge_work_context={m_work_immediate,m_work_wr_id,')
        text=once(text,'rocev2_wqe_hls_sq #(.MAX_QPS(MAX_QPS))',
            'rocev2_wqe_hls_sq #(.MAX_QPS(MAX_QPS),.IMMEDIATE_ENABLE(1))')
        text=once(text,'rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.SEND_ENABLE(SEND_ENABLE)',
            'rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.IMMEDIATE_ENABLE(1),.SEND_ENABLE(SEND_ENABLE)')
        text=once(text,' .m_work_remote_key(m_work_remote_key),',
            ' .m_work_remote_key(m_work_remote_key),\n .m_work_immediate(m_work_immediate),')
        # Receive WQEs also use the canonical Immediate descriptor format;
        # their notification field must remain0. RQ upper bits are NOT wire.
        text=once(text,'rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.SEND_ENABLE(0)',
            'rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.IMMEDIATE_ENABLE(1),.SEND_ENABLE(0)')
        text=once(text,' .m_work_remote_key(rq_work_remote_key),',
            ' .m_work_remote_key(rq_work_remote_key),\n .m_work_immediate(rq_work_immediate),')
        text=once(text,'assign rq_work_remote_key=0;',
            'assign rq_work_remote_key=0;assign rq_work_immediate=0;')
    if name=='rocev2_native_rnic_endpoint':
        text=once(text,'    output wire [31:0] m_work_remote_key,',
            '    output wire [31:0] m_work_remote_key,\n    output wire [31:0] m_work_immediate,')
        text=once(text,'    .m_work_remote_key(m_work_remote_key),',
            '    .m_work_remote_key(m_work_remote_key),.m_work_immediate(m_work_immediate),')
        text=once(text,'wire [31:0] rq_ticket_received_bytes;',
            'wire [31:0] rq_ticket_received_bytes;\nwire [31:0] rq_ticket_notification,rq_placement_notification;\n'
            'wire [7:0] rq_ticket_notification_flags,rq_placement_notification_flags;')
        text=once(text,'.m_recv_placement_length(rq_placement_length),',
            '.m_recv_placement_length(rq_placement_length),\n'
            '    .m_recv_placement_notification(rq_placement_notification),\n'
            '    .m_recv_placement_notification_flags(rq_placement_notification_flags),')
        text=once(text,'rocev2_receive_queue #(.MAX_QPS(MAX_QPS),',
            'rocev2_receive_queue #(.IMMEDIATE_ENABLE(1),.MAX_QPS(MAX_QPS),')
        text=once(text,'.s_placement_context(rq_placement_context),',
            '.s_placement_notification(rq_placement_notification),.s_placement_notification_flags(rq_placement_notification_flags),\n'
            '    .s_placement_context(rq_placement_context),')
        text=once(text,'.m_ticket_context(rq_ticket_context),',
            '.m_ticket_notification(rq_ticket_notification),.m_ticket_notification_flags(rq_ticket_notification_flags),\n'
            '    .m_ticket_context(rq_ticket_context),')
        text=once(text,'assign rq_ticket_context=0;',
            'assign rq_ticket_notification=0;assign rq_ticket_notification_flags=0;assign rq_ticket_context=0;')
        text=once(text,'rocev2_receive_ack_tx ack_owner(',
            'rocev2_receive_ack_tx #(.IMMEDIATE_ENABLE(1)) ack_owner(')
        text=once(text,'rocev2_cq_mmio #(.MESSAGE_ENABLE(RECV_CQ_ENABLE))',
            'rocev2_cq_mmio #(.IMMEDIATE_ENABLE(1),.MESSAGE_ENABLE(RECV_CQ_ENABLE))')
        text=once(text,'.s_ticket_received_bytes(rq_ticket_valid ? rq_ticket_received_bytes : 32\'d0),',
            '.s_ticket_received_bytes(rq_ticket_valid ? rq_ticket_received_bytes : 32\'d0),\n'
            '    .s_ticket_notification(rq_ticket_valid ? rq_ticket_notification : 32\'d0),\n'
            '    .s_ticket_notification_flags(rq_ticket_valid ? rq_ticket_notification_flags : 8\'d0),')
        text=once(text,'initial if(MAX_QPS!=8)',
            'initial if(!DUPLEX_ENABLE || !REQUEST_CQ_ENABLE || !SEPARATE_RQ_ENABLE || !RECV_CANCEL_ENABLE)\n'
            '    $fatal(1,"Immediate native derivative requires complete matched independent/duplex profile");\n'
            'initial if(MAX_QPS!=8)')
    return text


def shared_transport():
    text=request_fields(unpack_lower(widths(duplex.derive())))
    text=allow_ops(text,'s_local_owner_context')
    text=request_opcode(text,'owner[339:324]')
    text=once(text,"wire [279:0] expected_sq={7'd0,1'b1,saved_rkey,",
        "wire [279:0] expected_sq={7'd0,owner[619:588],1'b1,saved_rkey,")
    text=once(text,"(saved_opcode==1 ? 32'd10 : saved_opcode==3 ? 32'd4 : 32'd12)",
        "(saved_opcode==1 ? 32'd10 : saved_opcode==2 ? 32'd12 : saved_opcode==5 ? 32'd5 : saved_opcode==6 ? 32'd11 : 32'd4)")
    text=once(text,'m_recv_done_tdata[679:0]!==recv_owner || m_recv_done_tdata[679:672]!=0',
        'm_recv_done_tdata[679:0]!==recv_owner || m_recv_done_tdata[751:744]!=0')
    text=once(text,'rocev2_qptx_integrity_transport #(',
        'rocev2_immediate_integrity_transport #(')
    start=text.index('generate if(QP_TX_ENABLE)');end=text.index('end else begin : legacy_core',start)
    selected=text[start:end]
    selected=once(selected,'.s_axis_sq_tdata(s_local_sq_tdata[239:0]),',
        '.s_axis_sq_tdata(s_local_sq_tdata),')
    selected=once(selected,".integrity_overflow_count(integrity_overflow_count),\n.s_axis_sq_rkey(s_local_sq_tdata[239:208]));",
        '.integrity_overflow_count(integrity_overflow_count));')
    return text[:start]+selected+text[end:]


def protected_responder():
    text=widths(responder.derive(responder.ORIGINAL.read_text()))
    text=once(text,'reg recv_operation=0;',r'''// RQ notification ownership and DATA authority are independent for WRITE_IMM.
reg recv_operation=0,recv_data_operation=0;
reg [31:0] recv_notification=0;
reg [7:0] recv_notification_flags=0;''')
    text=once(text,'    output reg [31:0] m_recv_placement_length=0,',
        '    output reg [31:0] m_recv_placement_length=0,\n'
        '    output reg [31:0] m_recv_placement_notification=0,\n'
        '    output reg [7:0] m_recv_placement_notification_flags=0,')
    text=once(text,"wire [7:0] opcode=header[28*8+:8];",r'''wire [7:0] opcode=header[28*8+:8];
wire send_wire=RECV_ENABLE && (opcode==8'h04 || opcode==8'h05);
wire write_wire=opcode==8'h0a || opcode==8'h0b;
wire receive_wire=RECV_ENABLE && (send_wire || opcode==8'h0b);
wire [31:0] send_header_bytes=opcode==8'h05 ? 48:44;''')
    text=once(text,"(RECV_ENABLE && opcode==8'h04) ? {16'd0,byte_count}-32'd44-{30'd0,pad}",
        "send_wire ? {16'd0,byte_count}-send_header_bytes-{30'd0,pad}")
    mr_operation="recv_operation ? 3'd1 : write_operation"
    if text.count(mr_operation)!=2:raise ValueError('both actual MR clients must be checked')
    text=text.replace(mr_operation,"recv_data_operation ? 3'd1 : write_operation")
    text=once(text,'wire command_match=recv_operation ?',
        'wire command_match=recv_data_operation ?')
    text=once(text,'s_recv_context[115:20]==0 &&',
        's_recv_context[619:588]==0 && s_recv_context[115:20]==0 &&')
    text=once(text,'recv_operation<=0;recv_completion_pending<=0;',
        'recv_data_operation<=0;recv_notification<=0;recv_notification_flags<=0;\n'
        '        m_recv_placement_notification<=0;m_recv_placement_notification_flags<=0;\n'
        '        recv_operation<=0;recv_completion_pending<=0;')
    text=once(text,"byte_count<((RECV_ENABLE && opcode==8'h04) ? 48 : 60)",
        'byte_count<(send_wire ? send_header_bytes+4 : 60)')
    text=once(text,"opcode!=8'h0a && opcode!=8'h0c && !(RECV_ENABLE && opcode==8'h04)",
        "!write_wire && opcode!=8'h0c && !send_wire")
    text=once(text,"(opcode==8'h0a && (byte_count!=60+padded_length || pad!=((-parsed_length)&3)))",
        "(write_wire && (byte_count!=(opcode==8'h0b ? 64:60)+padded_length || pad!=((-parsed_length)&3)))")
    text=once(text,"(opcode==8'h04 && (byte_count!=44+padded_length || pad!=((-parsed_length)&3)))",
        '(send_wire && (byte_count!=send_header_bytes+padded_length || pad!=((-parsed_length)&3)))')
    text=once(text,"RECV_ENABLE && opcode==8'h04 && !s_recv_valid",
        'receive_wire && !s_recv_valid')
    text=once(text,"RECV_ENABLE && opcode==8'h04 && (!recv_context_ok || parsed_length>s_recv_context[307:276])",
        'receive_wire && (!recv_context_ok || (send_wire && parsed_length>s_recv_context[307:276]))')
    a=text.index('                        recv_operation<=RECV_ENABLE && opcode==8\'h04;')
    b=text.index('\n                end\n                RNR_ARM:',a)
    text=text[:a]+r'''                        recv_operation<=receive_wire;recv_data_operation<=send_wire;
                        recv_notification<=opcode==8'h05 ? be32(header,40) : opcode==8'h0b ? be32(header,56) : 0;
                        recv_notification_flags<=opcode==8'h05 ? 1 : opcode==8'h0b ? 3 : 0;
                        if(receive_wire)recv_context<=s_recv_context;
                        if(send_wire)begin
                            request_va<=s_recv_context[243:180];request_key<=s_recv_context[275:244];
                            write_operation<=1;wire_length<=padded_length;
                        end else begin
                            // FULL RETH/key/PD goes through the SAME genuine
                            // remote-MR check, never the notification RQ key.
                            request_va<=be64(header,40);request_key<=be32(header,48);
                            write_operation<=write_wire;wire_length<=write_wire ? padded_length : parsed_length;
                        end
                        state<=receive_wire ? RECV_ARM : LOOKUP;
                    end'''+text[b:]
    text=once(text,'m_recv_placement_context<=recv_context;',
        'm_recv_placement_context<=recv_context;\n'
        '                        m_recv_placement_notification<=recv_notification;\n'
        '                        m_recv_placement_notification_flags<=recv_notification_flags;')
    return text


def derive():
    """Return original-path -> generated text; callers must substitute ALL."""
    out={RTL/(n+'.v'):parent(n,(RTL/(n+'.v')).read_text())for n in PARENTS}
    out.update({RTL/(n+'.v'):leaf(n,(RTL/(n+'.v')).read_text())for n in LEAVES})
    out[duplex.ORIGINAL]=shared_transport()
    # This entry represents the existing checked protected derivative, not
    # editing or selecting a weakened replacement of the immutable original.
    out[responder.ORIGINAL]=protected_responder()
    out[duplex.bridge.legacy.BRIDGE]=bridge.derive()
    return out


def inputs():
    paths=[RTL/(n+'.v')for n in PARENTS+LEAVES]+[duplex.ORIGINAL,
        responder.ORIGINAL,duplex.bridge.legacy.BRIDGE,Path(__file__).resolve(),
        Path(responder.__file__),Path(responder.recv.__file__),Path(duplex.__file__),
        Path(bridge.__file__),Path(duplex.bridge.__file__),Path(duplex.bridge.legacy.__file__)]
    return list(dict.fromkeys(paths))
