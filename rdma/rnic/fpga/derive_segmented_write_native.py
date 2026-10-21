# SPDX-License-Identifier: BSD-2-Clause-Views
"""Insert checked WRITE controller into the actual shared native graph.

One actual MR/PTE/backend/physical nonce/HLS and ONE ACK allocator. Old
normal/SQ/Atomic/zero/SEND/READ paths remain. No raw HLS DMA authority or
fake RQ/drain/CQ/PSN success. Source remains private until native execution,
software and original board/physical gates are qualified separately.
"""
import re
import derive_segmented_write_native_gateway as parent
import derive_write_controller_leaves as leaves
import derive_receive_write_ack as ack
import derive_write_notice_binding_queue as rq

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
CTRL=RTL/'rocev2_segmented_write_controller.v'
CTRL_NAME='rocev2_segmented_write_native_controller'
MEMORY=RTL/'rocev2_memory_client_arbiter.v'
HLS_TOP=parent.HLS_TOP
FLOW=[('output','[127:0]','m_write_rx_data'),('output','[15:0]','m_write_rx_keep'),
    ('output','','m_write_rx_valid'),('input','','m_write_rx_ready'),('output','','m_write_rx_last'),
    ('input','[127:0]','s_write_replay_data'),('input','[15:0]','s_write_replay_keep'),
    ('input','','s_write_replay_valid'),('output','','s_write_replay_ready'),('input','','s_write_replay_last'),
    ('output','','m_write_admission_ready'),('output','[95:0]','m_write_hls_command'),
    ('output','','m_write_hls_command_valid'),('input','','m_write_hls_command_ready'),
    ('output','[511:0]','m_write_hls_data'),('output','[63:0]','m_write_hls_keep'),
    ('output','','m_write_hls_valid'),('input','','m_write_hls_ready'),('output','','m_write_hls_last'),
    ('input','[679:0]','s_write_rq_owner'),('input','','s_write_rq_owner_valid'),('output','','s_write_rq_owner_ready'),
    ('input','','s_write_tx_release'),('input','','s_write_message_active'),('input','[423:0]','s_write_commit_token'),
    ('input','[23:0]','s_write_commit_msn'),('input','[7:0]','s_write_commit_proofs'),
    ('input','','s_write_commit_valid'),('output','','s_write_commit_ready'),
    ('input','','s_write_memory_write'),('input','[63:0]','s_write_memory_offset'),
    ('input','[63:0]','s_write_memory_address'),('input','[31:0]','s_write_memory_length'),
    ('input','[31:0]','s_write_memory_key'),('input','[15:0]','s_write_memory_tag'),
    ('input','','s_write_memory_valid'),('output','','s_write_memory_ready'),
    ('input','[511:0]','s_write_data'),('input','[63:0]','s_write_keep'),('input','','s_write_last'),
    ('input','','s_write_valid'),('output','','s_write_ready'),
    ('output','[15:0]','m_write_status_tag'),('output','[7:0]','m_write_status_error'),
    ('output','','m_write_status_valid'),('input','','m_write_status_ready'),
    ('input','[7:0]','s_write_reject_error'),('input','[23:0]','s_write_reject_qpn'),
    ('input','[23:0]','s_write_reject_psn'),('input','','s_write_reject_valid'),('output','','s_write_reject_ready')]


def declarations(fields):return ''.join('wire '+(w+' 'if w else'')+n+';\n'for _,w,n in fields)


def ports(t):
    h=t.split(')(\n',1)[1].split('\n);',1)[0];h=re.sub(r'//[^\n]*','',h)
    out=[];d=None;w=''
    for part in h.split(','):
        part=part.strip();m=re.fullmatch(r'(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s*)?(\w+)(?:\s*=\s*\S+)?',part)
        if m:d,w,n=m.group(1),m.group(2)or'',m.group(3)
        else:
            m=re.fullmatch(r'(\w+)(?:\s*=\s*\S+)?',part)
            if not m or d is None:raise ValueError('unparsed real port:'+part)
            n=m.group(1)
        out.append((d,w.strip(),n))
    return out


def native_controller():
    t=once(CTRL.read_text(),'module rocev2_segmented_write_controller #(','module '+CTRL_NAME+' #(')
    t=once(t,'    output wire m_command_write,output wire [63:0] m_command_offset,',
        '    output wire [63:0] m_command_address,\n    output wire m_command_write,output wire [63:0] m_command_offset,')
    return once(t,'assign fault=halted;',
        'assign fault=halted;\n// Same actual per-packet MR response; not narrowed HLS address authority.\nassign m_command_address=packet_mr_address;')


def native_router():
    t=once(leaves.router(),'input wire force_write,','input wire force_write,input wire allow_header,')
    return once(t,'assign s_ready=!rst && (state<=SECOND ? !fault:(state==BODY && ready));',
        "assign s_ready=!rst && (state==FIRST ? allow_header===1'b1 && !fault:\n"
        "    state==SECOND ? !fault:(state==BODY && ready));")


def memory_mux(t):
    fields=[('output','','m_memory_command_write'),('output','[63:0]','m_memory_command_address'),
        ('output','[31:0]','m_memory_command_length'),('output','[15:0]','m_memory_command_tag'),
        ('output','[31:0]','m_memory_command_key'),('output','[63:0]','m_memory_command_offset'),
        ('output','','m_memory_command_valid'),('input','','m_memory_command_ready'),
        ('output','[511:0]','m_axis_memory_write_tdata'),('output','[63:0]','m_axis_memory_write_tkeep'),
        ('output','','m_axis_memory_write_tvalid'),('input','','m_axis_memory_write_tready'),('output','','m_axis_memory_write_tlast'),
        ('input','[511:0]','s_axis_memory_read_tdata'),('input','[63:0]','s_axis_memory_read_tkeep'),
        ('input','','s_axis_memory_read_tvalid'),('output','','s_axis_memory_read_tready'),('input','','s_axis_memory_read_tlast'),
        ('input','[15:0]','s_memory_status_tag'),('input','[7:0]','s_memory_status_error'),('input','','s_memory_status_valid'),('output','','s_memory_status_ready')]
    a=t.index('\n);')+4;head=t[:a];body=t[a:]
    for _,_,n in fields:body=re.sub(r'(?<!\.)\b'+n+r'\b','legacy_'+n,body)
    logic=declarations([(d,w,'legacy_'+n)for d,w,n in fields])
    logic+='wire [1:0] write_memory_clients,write_memory_command_ready,write_memory_status_valid,write_memory_data_ready;\n'
    logic+='wire [31:0] write_memory_status_tags;wire [15:0] write_memory_status_errors;\n'
    logic+='wire [1023:0] write_memory_read_data;wire [127:0] write_memory_read_keep;wire [1:0] write_memory_read_valid,write_memory_read_last;\n'
    logic+='wire write_memory_busy,write_memory_guard,write_memory_fault;\n'
    p=dict(clk='clk',rst='rst',enable='!fault && !write_external_bad',
        s_command_write='{s_write_memory_write,legacy_m_memory_command_write}',
        s_command_offset='{s_write_memory_offset,legacy_m_memory_command_offset}',
        s_command_length='{s_write_memory_length,legacy_m_memory_command_length}',
        s_command_key='{s_write_memory_key,legacy_m_memory_command_key}',s_command_tag='{s_write_memory_tag,legacy_m_memory_command_tag}',
        s_command_valid='{s_write_memory_valid,legacy_m_memory_command_valid}',s_command_ready='write_memory_command_ready',
        s_axis_write_tdata='{s_write_data,legacy_m_axis_memory_write_tdata}',s_axis_write_tkeep='{s_write_keep,legacy_m_axis_memory_write_tkeep}',
        s_axis_write_tlast='{s_write_last,legacy_m_axis_memory_write_tlast}',s_axis_write_tvalid='{s_write_valid,legacy_m_axis_memory_write_tvalid}',
        s_axis_write_tready='write_memory_data_ready',m_axis_read_tdata='write_memory_read_data',m_axis_read_tkeep='write_memory_read_keep',
        m_axis_read_tlast='write_memory_read_last',m_axis_read_tvalid='write_memory_read_valid',
        m_axis_read_tready="{1'b0,legacy_s_axis_memory_read_tready}",
        m_status_tag='write_memory_status_tags',m_status_error='write_memory_status_errors',m_status_valid='write_memory_status_valid',
        m_status_ready='{m_write_status_ready,legacy_s_memory_status_ready}',
        m_command_write='m_memory_command_write',m_command_offset='m_memory_command_offset',m_command_length='m_memory_command_length',
        m_command_key='m_memory_command_key',m_command_tag='m_memory_command_tag',m_command_valid='m_memory_command_valid',m_command_ready='m_memory_command_ready',
        m_axis_write_tdata='m_axis_memory_write_tdata',m_axis_write_tkeep='m_axis_memory_write_tkeep',
        m_axis_write_tlast='m_axis_memory_write_tlast',m_axis_write_tvalid='m_axis_memory_write_tvalid',m_axis_write_tready='m_axis_memory_write_tready',
        s_axis_read_tdata='s_axis_memory_read_tdata',s_axis_read_tkeep='s_axis_memory_read_tkeep',
        s_axis_read_tlast='s_axis_memory_read_tlast',s_axis_read_tvalid='s_axis_memory_read_tvalid',s_axis_read_tready='s_axis_memory_read_tready',
        s_status_tag='s_memory_status_tag',s_status_error='s_memory_status_error',s_status_valid='s_memory_status_valid',s_status_ready='s_memory_status_ready',
        client_guard='write_memory_clients',busy='write_memory_busy',configuration_guard='write_memory_guard',fault='write_memory_fault',fault_code='')
    logic+='rocev2_memory_client_arbiter write_and_ordinary_memory(\n'+',\n'.join('.'+n+'('+v+')'for n,v in p.items())+'\n);\n'
    logic+='assign {s_write_memory_ready,legacy_m_memory_command_ready}=write_memory_command_ready;\n'
    logic+='assign {s_write_ready,legacy_m_axis_memory_write_tready}=write_memory_data_ready;\n'
    logic+='assign {m_write_status_tag,legacy_s_memory_status_tag}=write_memory_status_tags;\n'
    logic+='assign {m_write_status_error,legacy_s_memory_status_error}=write_memory_status_errors;\n'
    logic+='assign {m_write_status_valid,legacy_s_memory_status_valid}=write_memory_status_valid;\n'
    logic+='assign legacy_s_axis_memory_read_tdata=write_memory_read_data[511:0];assign legacy_s_axis_memory_read_tkeep=write_memory_read_keep[63:0];\n'
    logic+='assign legacy_s_axis_memory_read_tlast=write_memory_read_last[0];assign legacy_s_axis_memory_read_tvalid=write_memory_read_valid[0];\n'
    logic+='assign m_memory_command_address=write_memory_clients[1] ? s_write_memory_address:legacy_m_memory_command_address;\n'
    return head+logic+body


def protected(t):
    t=parent.ports(t,FLOW)
    # Insert WRITE classification BEFORE Atomic, keeping its exact old path
    # on normal output. Message force routes out-of-sequence ops to the real
    # WRITE parser for local rejection, never into another active HLS owner.
    a=t.index('rocev2_native_atomic_rx_router packet_classification(');b=t.index(');',a)+2;old=t[a:b]
    mapping={'checked_data':'write_other_data','checked_keep':'write_other_keep','checked_valid':'write_other_valid',
        'checked_ready':'write_other_ready','checked_last':'write_other_last'}
    for n,v in mapping.items():old=re.sub(r'\b'+n+r'\b',v,old)
    logic='''wire [127:0] write_other_data;wire [15:0] write_other_keep;
wire write_other_valid,write_other_ready,write_other_last,write_dispatch_guard,write_dispatch_fault;
rocev2_native_write_rx_router write_classification(
 .clk(clk),.rst(rst),.force_write(s_write_message_active),.allow_header(!s_write_held || m_write_rx_ready),
 .s_data(checked_data),.s_keep(checked_keep),.s_valid(checked_valid),.s_ready(checked_ready),.s_last(checked_last),
 .m_normal_data(write_other_data),.m_normal_keep(write_other_keep),.m_normal_valid(write_other_valid),.m_normal_ready(write_other_ready),.m_normal_last(write_other_last),
 .m_atomic_data(m_write_rx_data),.m_atomic_keep(m_write_rx_keep),.m_atomic_valid(m_write_rx_valid),.m_atomic_ready(m_write_rx_ready),.m_atomic_last(m_write_rx_last),
 .configuration_guard(write_dispatch_guard),.fault(write_dispatch_fault));
'''
    t=t[:a]+logic+old+t[b:]
    t=once(t,'assign atomic_rx_guard=write_external_guard ||',
        'assign atomic_rx_guard=write_dispatch_guard || write_memory_guard || write_external_guard ||')
    t=once(t,'wire atomic_native_fault=write_external_bad ||',
        'wire atomic_native_fault=write_dispatch_fault || write_memory_fault || write_commit_bad || write_external_bad ||')
    # Native shadow PSN receives EXACT actual controller full-DONE. The
    # native header/QP/epoch and PSN are never supplied by an untrusted peer.
    logic='''assign m_write_admission_ready=ordinary_idle && !atomic_packet_busy && !atomic_cfg_pending && qp_ready && !fault &&
    (write_dispatch_guard || (!admission_paused && mr_management_idle && !cfg_qp_valid));
wire write_commit_known=(^{s_write_commit_token,s_write_commit_msn,s_write_commit_proofs})!==1'bx;
wire write_commit_match=write_commit_known && s_write_held===1'b1 && s_write_mr_guard===1'b1 &&
    s_write_commit_token[423:400]===local_qpn && s_write_commit_token[399:384]===trusted_pd &&
    s_write_commit_token[383:320]===atomic_context_epoch && s_write_commit_token[39:16]===expected_psn &&
    s_write_commit_proofs==8'h0f && s_write_queue_guard[local_qpn]===1'b1;
assign s_write_commit_ready=write_commit_match && !fault && !rst;
wire write_commit_bad=(s_write_commit_valid!==1'b0 && s_write_commit_valid!==1'b1) ||
    (s_write_commit_valid && !write_commit_match);
wire new_write_rq_fire=s_write_rq_owner_valid && s_write_rq_owner_ready;
wire shared_recv_owner_ready;
assign s_write_rq_owner_ready=s_write_held && shared_recv_owner_ready;
assign recv_owner_ready=!s_write_held && shared_recv_owner_ready;
'''
    t=once(t,'wire ordinary_idle=state==COLLECT && word_count==0 && !lease && !recv_completion_pending;',
        'wire ordinary_idle=state==COLLECT && word_count==0 && !lease && !recv_completion_pending;\n'+logic)
    t=once(t,'.s_recv_owner_tdata(recv_owner_data),.s_recv_owner_tvalid(recv_owner_valid),.s_recv_owner_tready(recv_owner_ready),',
        '.s_recv_owner_tdata(s_write_held ? s_write_rq_owner:recv_owner_data),.s_recv_owner_tvalid(s_write_held ? s_write_rq_owner_valid:recv_owner_valid),.s_recv_owner_tready(shared_recv_owner_ready),')
    # Switch only the selected remote RX/WRITE channels. Existing local
    # command provenance/router remains unchanged in the real shared core.
    t=once(t,'assign core_rx_ready=shared_remote_ready && !atomic_packet_busy;',
        'assign core_rx_ready=shared_remote_ready && !atomic_packet_busy && !s_write_held;\nassign s_write_replay_ready=shared_remote_ready && s_write_held && !atomic_packet_busy;')
    t=once(t,'assign atomic_hls_ready=shared_remote_ready && atomic_packet_busy;',
        'assign atomic_hls_ready=shared_remote_ready && atomic_packet_busy && !s_write_held;')
    for n,normal,atomic in [('tdata','replay_data','atomic_hls_data'),('tkeep','replay_keep','atomic_hls_keep'),
        ('tvalid','replay_valid','atomic_hls_valid'),('tlast','replay_last','atomic_hls_last')]:
        # Actual parent's selection is a ternary; retain it verbatim as the
        # ordinary alternative, not another independently active producer.
        old='.s_axis_rx_'+n+'(atomic_packet_busy ? '+atomic+':'+normal+')'
        new='.s_axis_rx_'+n+'(s_write_held ? s_write_replay_'+{'tdata':'data','tkeep':'keep','tvalid':'valid','tlast':'last'}[n]+':(atomic_packet_busy ? '+atomic+':'+normal+'))'
        t=once(t,old,new)
    names={'core_write_command':('m_write_hls_command','wire [95:0] write_shared_command;'),
        'core_write_valid':('m_write_hls_command_valid','wire write_shared_command_valid;'),
        'core_write_ready':('m_write_hls_command_ready','wire write_shared_command_ready;'),
        'core_write_data':('m_write_hls_data','wire [511:0] write_shared_data;'),
        'core_write_keep':('m_write_hls_keep','wire [63:0] write_shared_keep;'),
        'core_write_data_valid':('m_write_hls_valid','wire write_shared_valid;'),
        'core_write_data_ready':('m_write_hls_ready','wire write_shared_ready;'),
        'core_write_last':('m_write_hls_last','wire write_shared_last;')}
    shared_names=dict(core_write_command='write_shared_command',core_write_valid='write_shared_command_valid',core_write_ready='write_shared_command_ready',
        core_write_data='write_shared_data',core_write_keep='write_shared_keep',core_write_data_valid='write_shared_valid',core_write_data_ready='write_shared_ready',core_write_last='write_shared_last')
    a=t.index('rocev2_shared_hls_transport #');b=t.index(');',a)+2;block=t[a:b]
    for n,v in shared_names.items():block=re.sub(r'\b'+n+r'\b',v,block)
    t=t[:a]+block+t[b:]
    logic=''.join(v[1]+'\n'for v in names.values())
    for n,(public,_)in names.items():
        shared=shared_names[n]
        if n in ['core_write_ready','core_write_data_ready']:
            logic+='assign '+shared+'=s_write_held ? '+public+':'+n+';\n'
        elif n in ['core_write_valid','core_write_data_valid']:
            logic+='assign '+n+'='+shared+' && !s_write_held;assign '+public+'='+shared+' && s_write_held;\n'
        else:logic+='assign '+n+'='+shared+';assign '+public+'='+shared+';\n'
    t=once(t,'wire [127:0] core_tx_data;',logic+'wire [127:0] core_tx_data;')
    gate='((lease && (committed || zero_receive || zero_service)) || (RNR_ENABLE && state==RNR_WAIT))'
    if t.count(gate)!=2:raise ValueError('both original TX visibility gates required')
    t=t.replace(gate,'('+gate+' || (s_write_held && s_write_tx_release))')
    # Shared HLS remote_operation_idle intentionally remains the original
    # COLLECT/!lease predicate: waiting on WRITE ACK-retire would make a cycle.
    t=once(t,'        if(m_recv_placement_valid && m_recv_placement_ready)m_recv_placement_valid<=0;',
        '''        if(s_write_commit_valid && s_write_commit_ready)expected_psn<=s_write_commit_token[39:16]+24'd1;
        if(new_write_rq_fire)begin
            recv_context<=s_write_rq_owner[619:0];recv_completion_pending<=1;
            recv_terminal_complete<=0;recv_notification_flags<=3;
        end
        if(m_recv_placement_valid && m_recv_placement_ready)m_recv_placement_valid<=0;''')
    # One actual local reject-event interface, not a fake positive ACK/RNR.
    # Real wire NAK/RNR recovery remains a separate unqualified requirement.
    reject=[('output','[7:0]','m_reject_error'),('output','[23:0]','m_reject_qpn'),('output','[23:0]','m_reject_psn'),('output','','m_reject_valid')]
    a=t.index('\n);')+4;head=t[:a];body=t[a:]
    for _,_,n in reject:
        head=re.sub(r'output reg (\[[^]]+\] )?'+n+r'=0',lambda m:'output wire '+(m[1]or'')+n,head)
        body=re.sub(r'(?<!\.)\b'+n+r'\b','legacy_'+n,body)
    body=re.sub(r'(?<!\.)\bm_reject_ready\b','legacy_m_reject_ready',body)
    logic=''.join('reg '+(w+' 'if w else'')+'legacy_'+n+'=0;\n'for _,w,n in reject)+'wire legacy_m_reject_ready;\n'
    for _,_,n in reject:
        field=n.removeprefix('m_reject_')
        logic+='assign '+n+'=legacy_m_reject_valid ? legacy_'+n+':s_write_reject_'+field+';\n'if field!='valid'else'assign m_reject_valid=legacy_m_reject_valid || s_write_reject_valid;\n'
    logic+='assign legacy_m_reject_ready=m_reject_ready;assign s_write_reject_ready=m_reject_ready && !legacy_m_reject_valid;\n'
    t=head+logic+body
    t=memory_mux(t)
    return t


def rnic(t):
    header=''.join('    '+d+' wire '+(w+' 'if w else'')+n+',\n'for d,w,n in parent.FIELDS)
    t=once(t,header,'')
    a=t.index('\n);')+4;t=t[:a]+declarations(parent.FIELDS+FLOW)+t[a:]
    t=once(t,'    .m_recv_message_data(rq_message_data),',parent.connections(FLOW)+'    .m_recv_message_data(rq_message_data),')
    p=dict(clk='clk',rst='rst',enable='m_write_admission_ready',
        parent_fault='parent_fault || native_fault || ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault || rrp_fault || rq_fault || recv_ack_fault',
        trusted_valid='m_write_native_context_valid',trusted_context='m_write_native_context',trusted_expected_psn='m_write_expected_psn',
        s_rx_data='m_write_rx_data',s_rx_keep='m_write_rx_keep',s_rx_valid='m_write_rx_valid',s_rx_ready='m_write_rx_ready',s_rx_last='m_write_rx_last',
        m_hls_rx_data='s_write_replay_data',m_hls_rx_keep='s_write_replay_keep',m_hls_rx_valid='s_write_replay_valid',m_hls_rx_ready='s_write_replay_ready',m_hls_rx_last='s_write_replay_last',
        m_hls_owner='s_write_owner',m_hls_owner_valid='s_write_owner_valid',m_hls_owner_ready='s_write_owner_ready',
        s_hls_done='m_write_done',s_hls_done_valid='m_write_done_valid',s_hls_done_ready='m_write_done_ready',
        m_hls_rq_owner='s_write_rq_owner',m_hls_rq_owner_valid='s_write_rq_owner_valid',m_hls_rq_owner_ready='s_write_rq_owner_ready',
        s_rq_context='write_rq_head_context',s_rq_valid='write_rq_head_valid',
        m_notice_context='write_notice_context',m_notice_last_psn='write_notice_psn',m_notice_valid='write_notice_valid',m_notice_ready='write_notice_ready',
        s_notice_retire_context='write_notice_retire_context',s_notice_retire_valid='write_notice_retire_valid',s_notice_retire_ready='write_notice_retire_ready',
        m_rq_placement_context='write_placement_context',m_rq_placement_length='write_placement_length',m_rq_placement_notification='write_placement_notification',
        m_rq_placement_psn='write_placement_psn',m_rq_placement_valid='write_placement_valid',m_rq_placement_ready='write_placement_ready',
        s_hls_command='m_write_hls_command',s_hls_command_valid='m_write_hls_command_valid',s_hls_command_ready='m_write_hls_command_ready',
        s_hls_data='m_write_hls_data',s_hls_keep='m_write_hls_keep',s_hls_last='m_write_hls_last',s_hls_valid='m_write_hls_valid',s_hls_ready='m_write_hls_ready',
        m_command_write='s_write_memory_write',m_command_address='s_write_memory_address',m_command_offset='s_write_memory_offset',m_command_length='s_write_memory_length',
        m_command_key='s_write_memory_key',m_command_tag='s_write_memory_tag',m_command_valid='s_write_memory_valid',m_command_ready='s_write_memory_ready',
        m_data='s_write_data',m_keep='s_write_keep',m_last='s_write_last',m_valid='s_write_valid',m_ready='s_write_ready',
        m_tx_release='s_write_tx_release',m_packet_commit_token='s_write_commit_token',m_packet_commit_msn='s_write_commit_msn',
        m_packet_commit_proofs='s_write_commit_proofs',m_packet_commit_valid='s_write_commit_valid',m_packet_commit_ready='s_write_commit_ready',
        m_reject_error='s_write_reject_error',m_reject_qpn='s_write_reject_qpn',m_reject_psn='s_write_reject_psn',m_reject_valid='s_write_reject_valid',m_reject_ready='s_write_reject_ready',
        message_active='s_write_message_active',configuration_guard='s_write_held',queue_guard='s_write_queue_guard',fault='write_controller_fault')
    for n in ['pd','key','address','length','operation','tag','valid','ready']:p['m_mr_'+n]='s_write_mr_request_'+n
    for n in ['tag','error','offset','length','valid','ready']:p['s_mr_'+n]='m_write_mr_response_'+n
    p['s_mr_address']='m_write_mr_response_dma_address'
    for n in ['tag','error','valid','ready']:p['s_status_'+n]='m_write_status_'+n
    for n in ['owner','owner_notify','owner_rq_context','owner_valid','owner_ready','core','core_valid','core_ready','retire_token','retire_valid','retire_ready']:
        p['m_ack_'+n]='write_ack_'+n
    for n in ['done','done_valid','done_ready']:p['s_ack_'+n]='write_ack_'+n
    logic='''initial if(!DUPLEX_ENABLE || !RECV_ENABLE || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE)
 $fatal(1,"private segmented WRITE native requires full real receive/ACK/CQ profile");
assign s_write_mr_guard=s_write_held;
reg write_fault_latched=0;
always @(posedge clk)begin if(rst)write_fault_latched<=0;else if(write_controller_fault)write_fault_latched<=1;end
'''
    existing={n for _,_,n in parent.FIELDS+FLOW};fields=ports(native_controller())
    for d,w,n in fields:
        if n not in p:
            if d=='input':raise ValueError('no modeled/tied controller input allowed:'+n)
            p[n]='write_ctl_'+n
        v=p[n]
        if re.fullmatch(r'\w+',v)and v not in existing and v not in ['clk','rst']:
            logic+='wire '+(w+' 'if w else'')+v+';\n';existing.add(v)
    logic+=CTRL_NAME+' write_controller(\n'+',\n'.join('.'+n+'('+p[n]+')'for _,_,n in fields)+'\n);\n'
    t=once(t,'wire [619:0] rq_post_context,rq_head_context,rq_placement_context;',logic+'wire [619:0] rq_post_context,rq_head_context,rq_placement_context;')
    t=once(t,'assign fault=zero_wire_fault ||','assign fault=write_fault_latched || zero_wire_fault ||')
    t=once(t,'    .s_recv_context(rq_head_context),.s_recv_valid(rq_head_valid),.s_recv_ready(rq_head_ready),',
        '    .s_recv_context(rq_head_context),.s_recv_valid(rq_head_valid),.s_recv_ready(write_legacy_head_ready),')
    t=once(t,'rocev2_receive_message_queue #(',rq.NAME+' #(')
    t=once(t,'    .query_qpn(rq_query_qpn),',
        '''    .m_notice_head_context(write_rq_head_context),.m_notice_head_valid(write_rq_head_valid),
    .s_write_notice_context(write_notice_context),.s_write_notice_last_psn(write_notice_psn),
    .s_write_notice_valid(write_notice_valid),.s_write_notice_ready(write_notice_ready),
    .m_write_retire_context(write_notice_retire_context),.m_write_retire_valid(write_notice_retire_valid),.m_write_retire_ready(write_notice_retire_ready),
    .query_qpn(rq_query_qpn),''')
    t=once(t,'wire rq_post_valid,rq_post_ready,rq_head_valid,rq_head_ready,rq_placement_valid,rq_placement_ready;',
        '''wire rq_post_valid,rq_post_ready,rq_head_valid,rq_head_ready,rq_placement_valid,rq_placement_ready;
wire write_legacy_head_ready;
assign rq_head_ready=write_legacy_head_ready || write_notice_valid;
assign write_placement_ready=rq_placement_ready;
''')
    # Only actual queue-side placement pins are selected. Old protected
    # placement remains the ordinary alternative with unchanged backpressure.
    a=t.index(rq.NAME+' #(');b=t.index(');',a)+2;block=t[a:b]
    for name,new in [('rq_placement_context','write_placement_context'),('rq_placement_length','write_placement_length'),
        ('rq_placement_notification','write_placement_notification'),('rq_placement_psn','write_placement_psn')]:
        block=re.sub(r'\b'+name+r'\b','(s_write_held ? '+new+':'+name+')',block)
    block=once(block,'.s_placement_notification_flags(rq_placement_notification_flags)',
        ".s_placement_notification_flags(s_write_held ? 8'd3:rq_placement_notification_flags)")
    block=once(block,'.s_placement_valid(rq_placement_valid)',
        '.s_placement_valid(s_write_held ? write_placement_valid:rq_placement_valid)')
    t=t[:a]+block+t[b:]
    t=once(t,'rocev2_receive_ack_tx #(',ack.NAME+' #(')
    t=once(t,'.s_owner_valid(rq_head_valid && rq_head_ready)',
        '.s_owner_valid(rq_head_valid && rq_head_ready && !write_notice_valid)')
    pins={n:'write_ack_'+n.removeprefix('s_write_')for n in ['s_write_owner','s_write_owner_notify','s_write_owner_rq_context','s_write_owner_valid','s_write_owner_ready']}
    pins.update(s_write_core_data='write_ack_core',s_write_core_valid='write_ack_core_valid',s_write_core_ready='write_ack_core_ready',
        m_write_done_data='write_ack_done',m_write_done_valid='write_ack_done_valid',m_write_done_ready='write_ack_done_ready',
        s_write_retire_token='write_ack_retire_token',s_write_retire_valid='write_ack_retire_valid',s_write_retire_ready='write_ack_retire_ready')
    a=t.index(ack.NAME+' #(');b=t.index(');',a)+2;block=t[a:b]
    block=once(block,'    .prior_response_drained(response_tx_quiescent),',
        ''.join('    .'+n+'('+v+'),\n'for n,v in pins.items())+'    .prior_response_drained(response_tx_quiescent),')
    return t[:a]+block+t[b:]


def derive():
    out=parent.derive()
    for name in parent.WRAPPERS:
        p=RTL/(name+'.v')
        if name=='rocev2_native_rnic_endpoint':out[p]=rnic(out[p]);continue
        t=parent.ports(out[p],FLOW)
        out[p]=once(t,'    .m_recv_message_data(m_recv_message_data),',parent.connections(FLOW)+'    .m_recv_message_data(m_recv_message_data),')
    p=RTL/'rocev2_protected_responder.v';out[p]=protected(out[p])
    out[RTL/(leaves.FRONT_NAME+'.v')]=leaves.frontend()
    out[RTL/(leaves.ROUTER_NAME+'.v')]=native_router()
    out[RTL/(CTRL_NAME+'.v')]=native_controller()
    out[RTL/(ack.NAME+'.v')]=ack.derive();out[RTL/(rq.NAME+'.v')]=rq.derive()
    return out
