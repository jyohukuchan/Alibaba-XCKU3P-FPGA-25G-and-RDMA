# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit private large-Immediate graph; no old/default capability changes.

Extend the actual READ command-queue graph with whole-WR source authority,
FIRST/MIDDLE/LAST_IMM wire/cache/MAC joins, exact1MiB admission and distinct
RNC32767/CQC127 identity. Incoming RQ remains4096. Runtime/synthesis/native/
Linux/physical/original-clock qualification are separate required evidence.
"""
import derive_segmented_read_command_queue as parent
import derive_segmented_wire as wire

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once;helpers=wire.helpers
PAD=RTL/'rocev2_segmented_tx_padding.v'
EXTRA=parent.EXTRA
RNC_FEATURES=32767;CQC_FEATURES=127


def limit(t,length,op):
    return once(t,length+'<=(('+op+'==1 || '+op+'==2 || '+op+'==3) ? 1048576:4096)',
        length+'<=(('+op+'==1 || '+op+'==2 || '+op+'==3 || '+op+'==5 || '+op+'==6) ? 1048576:4096)')


def padding(t):
    t=once(t,"(s_axis_tdata[103:96]==8'h02 || s_axis_tdata[103:96]==8'h08);",
        "(s_axis_tdata[103:96]==8'h02 || s_axis_tdata[103:96]==8'h08 ||\n"
        "     s_axis_tdata[103:96]==8'h03 || s_axis_tdata[103:96]==8'h09);\n"
        "wire immediate_last=s_axis_tdata[103:96]==8'h03 || s_axis_tdata[103:96]==8'h09;")
    return once(t,"packet_length<=16'd44+{14'd0,declared_pad}",
        "packet_length<=(immediate_last ? 16'd48:16'd44)+{14'd0,declared_pad}")


def derive():
    out=parent.derive()
    for name,length,op in [('rocev2_wqe_admission.v','length','opcode'),
        ('rocev2_wqe_hls_sq.v','in_length','in_opcode'),('rocev2_cq_mmio.v','s_ticket_context[307:276]','incoming_opcode'),
        ('rocev2_wqe_lifetime.v','in_length','in_op'),('rocev2_wqe_mac_tx.v','in_length','in_op'),
        ('rocev2_wqe_response_guard.v','in_length','in_op'),('rocev2_shared_hls_transport.v','length','opcode')]:
        p=RTL/name;out[p]=limit(out[p],length,op)
    p=RTL/'rocev2_wqe_lifetime.v';t=out[p]
    t=once(t,'wire segmented=(opcode==1 || opcode==3) && length>4096;',
        'wire segmented=(opcode==1 || opcode==3 || opcode==5 || opcode==6) && length>4096;')
    t=once(t,"wire [7:0] segmented_wire_opcode=opcode==3 ? (packet_first ? 8'h00:packet_last ? 8'h02:8'h01):\n    (packet_first ? 8'h06:packet_last ? 8'h08:8'h07);",
        "wire [7:0] segmented_wire_opcode=(opcode==3 || opcode==5) ?\n"
        "    (packet_first ? 8'h00:packet_last ? (opcode==5 ? 8'h03:8'h02):8'h01):\n"
        "    (packet_first ? 8'h06:packet_last ? (opcode==6 ? 8'h09:8'h08):8'h07);")
    t=once(t,'request_header_bytes=segmented ? ((opcode==1 && packet_first) ? 60:44):',
        'request_header_bytes=segmented ? (((opcode==1 || opcode==6) && packet_first) ? 60:\n'
        '    (packet_last && (opcode==5 || opcode==6)) ? 48:44):')
    out[p]=once(t,'(!immediate_request || be32(header,opcode==5 ? 40:56)==owner[619:588])',
        '(!immediate_request || (segmented && !packet_last) ||\n'
        '     be32(header,segmented ? 40:opcode==5 ? 40:56)==owner[619:588])')
    for name,field,end in [('rocev2_wqe_tx_lifetime.v','m_cq_context','whole_length'),
                           ('rocev2_shared_hls_transport.v','owner','request_length')]:
        p=RTL/name;out[p]=once(out[p],
            '('+field+'[339:324]==1 || '+field+'[339:324]==2 || '+field+'[339:324]==3) && '+end+'>4096',
            '('+field+'[339:324]==1 || '+field+'[339:324]==2 || '+field+'[339:324]==3 || '+field+'[339:324]==5 || '+field+'[339:324]==6) && '+end+'>4096')
    p=RTL/'rocev2_wqe_replay.v';out[p]=once(out[p],
        '(owner[339:324]==1 || owner[339:324]==3) && owner[307:276]>4096',
        '(owner[339:324]==1 || owner[339:324]==3 || owner[339:324]==5 || owner[339:324]==6) && owner[307:276]>4096')
    p=RTL/'rocev2_segmented_source_executor.v';t=out.get(p,p.read_text())
    t=once(t,'(in_opcode==1 || (in_opcode==3 && s_owner_context[115:20]==0))',
        '(in_opcode==1 || in_opcode==6 || ((in_opcode==3 || in_opcode==5) && s_owner_context[115:20]==0))')
    t=once(t,'s_owner_context[747:588]==0 &&',
        's_owner_context[747:620]==0 && ((in_opcode==5 || in_opcode==6) || s_owner_context[619:588]==0) &&')
    out[p]=once(t,"owner[339:324]==3 ? 64'd0:","(owner[339:324]==3 || owner[339:324]==5) ? 64'd0:")
    p=RTL/'rocev2_segmented_executor_mux.v';out[p]=once(out[p],
        '(s_owner_context[339:324]==1 || s_owner_context[339:324]==3) && s_owner_context[307:276]!=0;',
        '(s_owner_context[339:324]==1 || s_owner_context[339:324]==3 || s_owner_context[339:324]==5 || s_owner_context[339:324]==6) && s_owner_context[307:276]!=0;')
    out[PAD]=padding(out.get(PAD,PAD.read_text()))
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v';out[p]=once(out[p],
        'rocev2_native_segmented_read_top transport (','rocev2_native_segmented_immediate_top transport (')
    p=RTL/'rocev2_control_regs.v';out[p]=once(out[p],
        '| 8192; // distinct private large READ identity',
        '| 8192 | 16384; // distinct private large READ/Immediate identity')
    p=RTL/'rocev2_cq_mmio.v';out[p]=once(out[p],
        '    8:rd=63; // private matched large READ owner/codec profile',
        '    8:rd=127; // private matched large READ/Immediate owner/codec profile')
    return out
