# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual legacy/retained-source executor dispatch and atomic CQ fanout.

Both paths use the same actual MR/page/backend physical-nonce domain. No
large admission or per-packet wire/whole-WR CQ qualification is implied by
connecting the source controller; those validators remain independently shut.
"""
import re
import derive_segmented_native as parent
import derive_segmented_source as source

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
EXTRA=parent.EXTRA+[RTL/'rocev2_segmented_source_executor.v']
MUX=RTL/'rocev2_segmented_executor_mux.v'
CHILD=RTL/'rocev2_segmented_child_executor.v'


def mux_source(legacy):
    header=legacy[:legacy.index('\n);')+3]
    header=once(header,'module rocev2_wqe_memory_executor #(', 'module rocev2_segmented_executor_mux #(')
    header=re.sub(r'=0(?=[,\n])','',header.replace('output reg ','output wire '))
    header=once(header,'    input wire clk,',
        '    input wire [747:0] s_retire_context,\n    input wire s_retire_valid,\n'
        '    input wire s_retire_offer_valid,\n'
        '    output wire s_retire_ready,\n    input wire clk,')
    # Use the exact private native executor ports, including Atomic/zero
    # extensions. No hand-copied narrower ABI or dropped default output.
    ports=parent.helpers.module_ports(RTL/'rocev2_wqe_memory_executor.v')
    # The original file has588-bit contexts. Widen only exactly those ports
    # already widened in the checked private native source above.
    ports=[(d,'[747:0]'if n in ['s_owner_context','s_read_response_context','m_memory_event_context']else
        '[MAX_QPS-1:0]'if n in ['queue_guard','downstream_queue_guard']else w,n)for d,w,n in ports]
    names={n for _,_,n in ports}
    outputs={n:w for d,w,n in ports if d=='output'}
    counts={'owner_count','command_count','memory_status_count'}
    decl='\n'.join('wire '+(w+' 'if w else'')+'l_'+n+';'for n,w in outputs.items()if n not in counts)
    mapping={n:(''if n in counts else 'l_'+n)if d=='output'else n for d,w,n in ports}
    mapping.update(halt='halt || local_fault || b_fault',s_owner_valid='s_owner_valid && role==NONE && !source_offer')
    for n in ['s_read_response_valid','s_hls_read_command_valid','s_hls_write_command_valid',
              's_axis_hls_write_tvalid','s_axis_memory_read_tvalid','s_memory_status_valid',
              'm_axis_hls_read_tready','m_memory_command_ready','m_axis_memory_write_tready','m_memory_event_ready']:
        mapping[n]='!big_route && '+n
    legacy_instance='rocev2_wqe_memory_executor #(.MAX_QPS(MAX_QPS)) legacy(\n'+',\n'.join('.'+n+'('+mapping[n]+')'for _,_,n in ports)+'\n);\n'
    big=dict(clk='clk',rst='rst',enable='enable',parent_fault='halt || local_fault || l_fault',
        s_owner_context='s_owner_context',s_owner_valid='s_owner_valid && role==NONE && source_offer',s_owner_ready='b_s_owner_ready',
        s_hls_command='s_hls_read_command',s_hls_command_valid='big_route && s_hls_read_command_valid',s_hls_command_ready='b_s_hls_read_command_ready',
        m_axis_hls_tdata='b_m_axis_hls_read_tdata',m_axis_hls_tkeep='b_m_axis_hls_read_tkeep',
        m_axis_hls_tlast='b_m_axis_hls_read_tlast',m_axis_hls_tvalid='b_m_axis_hls_read_tvalid',m_axis_hls_tready='big_route && m_axis_hls_read_tready',
        s_axis_memory_tdata='s_axis_memory_read_tdata',s_axis_memory_tkeep='s_axis_memory_read_tkeep',
        s_axis_memory_tlast='s_axis_memory_read_tlast',s_axis_memory_tvalid='big_route && s_axis_memory_read_tvalid',s_axis_memory_tready='b_s_axis_memory_read_tready',
        s_retire_context='s_retire_context',
        s_retire_valid="big_route && s_retire_valid && s_retire_offer_valid===1'b1 && retire_identity",s_retire_ready='b_s_retire_ready',
        queue_guard='b_queue_guard',busy='b_busy',fault='b_fault',fault_code='b_fault_code',tags_exhausted='',
        owner_count='',fragment_count='',replay_count='',retired_count='')
    for n in ['write','offset','length','key','tag','valid']:
        big['m_memory_command_'+n]='b_m_memory_command_'+n
    big['m_memory_command_ready']='big_route && m_memory_command_ready'
    for n in ['tag','error','valid']:big['s_memory_status_'+n]=('big_route && 'if n=='valid'else'')+'s_memory_status_'+n
    big['s_memory_status_ready']='b_s_memory_status_ready'
    for n in ['context','error','valid']:big['m_memory_event_'+n]='b_m_memory_event_'+n
    big['m_memory_event_ready']='big_route && m_memory_event_ready'
    bports=parent.helpers.module_ports(RTL/'rocev2_segmented_source_executor.v')
    if set(big)!={n for _,_,n in bports}:raise ValueError('every actual large-source port must be explicit')
    declarations={}
    for _,w,n in bports:
        v=big[n]
        if v.startswith('b_') and re.fullmatch(r'\w+',v):declarations[v]='[MAX_QPS-1:0]'if n=='queue_guard'else w
    decl+='\n'+'\n'.join('wire '+(w+' 'if w else'')+n+';'for n,w in declarations.items())
    big_instance=parent.helpers.instance(RTL/'rocev2_segmented_source_executor.v','segmented',big,'.MAX_QPS(MAX_QPS)')
    muxed=['s_hls_read_command_ready','m_axis_hls_read_tdata','m_axis_hls_read_tkeep','m_axis_hls_read_tlast','m_axis_hls_read_tvalid',
        'm_memory_command_write','m_memory_command_offset','m_memory_command_length','m_memory_command_key','m_memory_command_tag','m_memory_command_valid',
        's_axis_memory_read_tready','s_memory_status_ready','m_memory_event_context','m_memory_event_error','m_memory_event_valid']
    passthrough=['s_read_response_ready','s_hls_write_command_ready','s_axis_hls_write_tready',
        'm_axis_memory_write_tdata','m_axis_memory_write_tkeep','m_axis_memory_write_tlast','m_axis_memory_write_tvalid']
    logic='\n'.join('assign '+n+'=big_route ? b_'+n+':l_'+n+';'for n in muxed)
    logic+='\n'+'\n'.join('assign '+n+'=big_route ? '+('512\'d0'if n.endswith('tdata')else'64\'d0'if n.endswith('tkeep')else'1\'b0')+':l_'+n+';'for n in passthrough)
    return header+r'''
localparam NONE=0,LEGACY=1,LARGE=2;
reg [1:0] role=NONE;reg [747:0] saved_owner=0;reg local_fault=0;
reg [31:0] accepted=0,commands=0,statuses=0;
// All ordinary nonzero source WRs retain memory/replay authority to CQ, not
// just large WRs. READ/Atomic placement, Immediate and zero keep legacy logic.
wire source_offer=(^{s_owner_context[339:324],s_owner_context[307:276]})!==1'bx &&
 (s_owner_context[339:324]==1 || s_owner_context[339:324]==3) && s_owner_context[307:276]!=0;
wire big_route=role==LARGE;
'''+decl+'\n'+r'''
wire retire_identity=(^s_retire_context)!==1'bx && s_retire_context==saved_owner;
wire retire_bad=big_route && ((s_retire_offer_valid!==1'b0 && s_retire_offer_valid!==1'b1) ||
 (s_retire_offer_valid && !retire_identity) || (s_retire_valid && s_retire_offer_valid!==1'b1));
wire extra_offer=retire_bad || (big_route && (s_read_response_valid!==1'b0 || s_hls_write_command_valid!==1'b0 || s_axis_hls_write_tvalid!==1'b0));
assign fault=local_fault || l_fault || b_fault;
assign fault_code=local_fault ? 8'hd6:b_fault ? b_fault_code:l_fault_code;
assign s_owner_ready=role==NONE && !fault && (source_offer ? b_s_owner_ready:l_s_owner_ready);
assign s_retire_ready=big_route ? b_s_retire_ready && !retire_bad:1'b1;
wire [MAX_QPS-1:0] owned_guard=role!=NONE ? ({{(MAX_QPS-1){1'b0}},1'b1}<<saved_owner[395:372]):{MAX_QPS{1'b0}};
assign queue_guard=(fault || extra_offer) ? {MAX_QPS{1'b1}}:owned_guard|l_queue_guard|b_queue_guard;
assign busy=role!=NONE || l_busy || b_busy || fault || extra_offer;
assign owner_count=accepted;assign command_count=commands;assign memory_status_count=statuses;
'''+logic+'\n'+legacy_instance+big_instance+r'''
always @(posedge clk)begin
 if(rst)begin role<=NONE;saved_owner<=0;local_fault<=0;accepted<=0;commands<=0;statuses<=0;end
 else begin
  if(s_owner_valid && s_owner_ready)begin role<=source_offer ? LARGE:LEGACY;saved_owner<=s_owner_context;accepted<=accepted+1'b1;end
  if(role==LEGACY && !l_busy && !fault)role<=NONE;
  if(role==LARGE && !b_busy && !fault)role<=NONE;
  if(m_memory_command_valid && m_memory_command_ready)commands<=commands+1'b1;
  if(s_memory_status_valid && s_memory_status_ready)statuses<=statuses+1'b1;
  if(extra_offer)local_fault<=1;
 end
end
endmodule
`resetall
'''


def derive():
    out=parent.derive();legacy=out[RTL/'rocev2_wqe_memory_executor.v']
    child=source.child_source()
    if child!=once(legacy,'module rocev2_wqe_memory_executor #(', 'module rocev2_segmented_child_executor #('):
        raise ValueError('unchanged bounded child must match actual selected native executor')
    out[CHILD]=child;out[MUX]=mux_source(legacy)
    p=RTL/'rocev2_native_rnic_endpoint.v';t=out[p]
    t=once(t,'rocev2_wqe_memory_executor #(.MAX_QPS(MAX_QPS)) executor (',
        'wire segmented_memory_retire_ready;\n'
        'rocev2_segmented_executor_mux #(.MAX_QPS(MAX_QPS)) executor (\n'
        '    .s_retire_context(cq_retire_context),\n'
        '    .s_retire_offer_valid(cq_retire_valid && !receive_retire),\n'
        '    .s_retire_valid(cq_retire_valid && !receive_retire && local_retire_ready),\n'
        '    .s_retire_ready(segmented_memory_retire_ready),')
    t=once(t,'recv_hls_retire_ready : local_retire_ready;',
        'recv_hls_retire_ready : local_retire_ready && segmented_memory_retire_ready;')
    t=once(t,'.s_local_retire_valid(cq_retire_valid && !receive_retire),',
        '.s_local_retire_valid(cq_retire_valid && !receive_retire && segmented_memory_retire_ready),')
    out[p]=t
    return out
