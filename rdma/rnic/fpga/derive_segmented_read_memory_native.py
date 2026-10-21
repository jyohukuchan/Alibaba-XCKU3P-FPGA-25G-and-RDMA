# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual opt-in native READ memory routing, no default or admission widening.

The existing source/legacy executor is unchanged. A retained large-READ role
uses its own real bounded unpad/executor and the SAME physical-nonce/backend
ports; the old external unpad is bypassed ONLY for that stable role. Actual
RX/MSN/lifetime/large admission and runtime qualification remain required.
"""
import re
import derive_segmented_profile as parent
import derive_segmented_executor as executor
import derive_segmented_read_executor as read

ROOT=parent.ROOT;RTL=parent.RTL;once=parent.once
MUX=RTL/'rocev2_segmented_read_executor_mux.v'
UNPAD=RTL/'rocev2_segmented_read_unpad_route.v'
CHILD_UNPAD=RTL/'rocev2_segmented_read_child_unpad.v'
READ=RTL/'rocev2_segmented_read_executor.v'
EXTRA=list(dict.fromkeys([*parent.EXTRA,READ]))


def ports(t):
    return re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?',t[:t.index('\n);')])


def header(t,old,new,extra):
    t=t[:t.index('\n);')+3].replace('output reg ','output wire ')
    t=re.sub(r'=0(?=[,\n])','',t)
    t=once(t,'module '+old+' #(','module '+new+' #(')
    return once(t,'    input wire clk,',extra+'\n    input wire clk,')


def declarations(port_list,mapping,prefix):
    return '\n'.join('wire '+(w+' 'if w else'')+mapping[n]+';'for d,w,n in port_list
        if d=='output'and mapping[n].startswith(prefix))


def instance(name,label,port_list,mapping):
    if {n for _,_,n in port_list}!=set(mapping):raise ValueError('every actual port must be explicit:'+label)
    return name+' #(.MAX_QPS(MAX_QPS)) '+label+'(\n'+',\n'.join('.'+n+'('+mapping[n]+')'for _,_,n in port_list)+'\n);\n'


def mux_source(legacy):
    plist=ports(legacy);h=header(legacy,'rocev2_segmented_executor_mux','rocev2_segmented_read_executor_mux',
        '    output wire large_read_path,')
    counts={'owner_count','command_count','memory_status_count'}
    old={n:(''if n in counts else'l_'+n)if d=='output'else n for d,_,n in plist}
    old.update(halt='halt || local_fault || r_fault',s_owner_valid='role==NONE && !read_offer && s_owner_valid')
    for n in ['s_retire_valid','s_retire_offer_valid','s_read_response_valid','s_hls_read_command_valid',
              's_hls_write_command_valid','s_axis_hls_write_tvalid','s_axis_memory_read_tvalid','s_memory_status_valid',
              'm_axis_hls_read_tready','m_memory_command_ready','m_axis_memory_write_tready','m_memory_event_ready']:
        old[n]='!large_read_path && '+n
    rp=ports(READ.read_text())
    r={n:'r_'+n if d=='output'else n for d,_,n in rp}
    r.update(parent_fault='halt || local_fault || l_fault',s_owner_valid='role==NONE && read_offer && s_owner_valid',
        s_hls_command='s_hls_write_command',s_hls_command_valid='large_read_path && s_hls_write_command_valid',
        s_axis_hls_tdata='s_axis_hls_write_tdata',s_axis_hls_tkeep='s_axis_hls_write_tkeep',
        s_axis_hls_tlast='s_axis_hls_write_tlast',s_axis_hls_tvalid='large_read_path && s_axis_hls_write_tvalid',
        m_axis_memory_tready='large_read_path && m_axis_memory_write_tready',
        s_read_response_valid='large_read_path && s_read_response_valid',
        m_memory_command_ready='large_read_path && m_memory_command_ready',
        s_memory_status_valid='large_read_path && s_memory_status_valid',
        m_memory_event_ready='large_read_path && m_memory_event_ready',
        s_retire_valid="large_read_path && s_retire_valid && s_retire_offer_valid===1'b1 && retire_identity")
    for n in ['tags_exhausted','owner_count','fragment_count','retired_count','discarded_padding_bytes']:r[n]=''
    wires=declarations(plist,old,'l_')+'\n'+declarations(rp,r,'r_')
    select={'s_owner_ready':'s_owner_ready','s_retire_ready':'s_retire_ready','s_read_response_ready':'s_read_response_ready',
        's_hls_write_command_ready':'s_hls_command_ready','s_axis_hls_write_tready':'s_axis_hls_tready',
        's_memory_status_ready':'s_memory_status_ready'}
    select.update({n:n for n in ['m_memory_command_write','m_memory_command_offset','m_memory_command_length',
        'm_memory_command_key','m_memory_command_tag','m_memory_command_valid','m_memory_event_context','m_memory_event_error','m_memory_event_valid']})
    select.update({'m_axis_memory_write_'+n:'m_axis_memory_'+n for n in ['tdata','tkeep','tlast','tvalid']})
    logic='\n'.join('assign '+n+'=large_read_path ? r_'+rn+':l_'+n+';'for n,rn in select.items()if n not in ['s_owner_ready','s_retire_ready'])
    for n,width in [('s_hls_read_command_ready',1),('m_axis_hls_read_tdata',512),('m_axis_hls_read_tkeep',64),
                    ('m_axis_hls_read_tlast',1),('m_axis_hls_read_tvalid',1),('s_axis_memory_read_tready',1)]:
        logic+='\nassign '+n+"=large_read_path ? "+str(width)+"'d0:l_"+n+';'
    return h+r'''
localparam NONE=0,LEGACY=1,READ=2;
reg [1:0] role=NONE;reg [747:0] saved_owner=0;reg local_fault=0;
reg [31:0] accepted=0,commands=0,statuses=0;
wire read_offer=(^{s_owner_context[339:324],s_owner_context[307:276]})!==1'bx &&
 s_owner_context[339:324]==2 && s_owner_context[307:276]>4096;
assign large_read_path=role==READ;
'''+wires+r'''
wire retire_identity=(^s_retire_context)!==1'bx && s_retire_context==saved_owner;
wire retire_bad=large_read_path && ((s_retire_offer_valid!==1'b0 && s_retire_offer_valid!==1'b1) ||
 (s_retire_offer_valid && !retire_identity) || (s_retire_valid && s_retire_offer_valid!==1'b1));
wire extra=retire_bad || (large_read_path && (s_hls_read_command_valid!==1'b0 || s_axis_memory_read_tvalid!==1'b0));
assign fault=local_fault || l_fault || r_fault;
assign fault_code=local_fault ? 8'hd7:r_fault ? r_fault_code:l_fault_code;
assign s_owner_ready=role==NONE && !fault && !extra && (read_offer ? r_s_owner_ready:l_s_owner_ready);
assign s_retire_ready=!fault && !extra && (large_read_path ? r_s_retire_ready && !retire_bad:l_s_retire_ready);
wire [MAX_QPS-1:0] held_guard=role!=NONE ? ({{(MAX_QPS-1){1'b0}},1'b1}<<saved_owner[395:372]):{MAX_QPS{1'b0}};
assign queue_guard=(fault || extra) ? {MAX_QPS{1'b1}}:held_guard|l_queue_guard|r_queue_guard;
assign busy=role!=NONE || l_busy || r_busy || fault || extra;
assign owner_count=accepted;assign command_count=commands;assign memory_status_count=statuses;
'''+logic+'\n'+instance('rocev2_segmented_executor_mux','source_and_legacy',plist,old)+instance(READ.stem,'read_fragments',rp,r)+r'''
always @(posedge clk)begin
 if(rst)begin role<=NONE;saved_owner<=0;local_fault<=0;accepted<=0;commands<=0;statuses<=0;end
 else begin
  if(s_owner_valid && s_owner_ready)begin role<=read_offer ? READ:LEGACY;saved_owner<=s_owner_context;accepted<=accepted+1'b1;end
  if(role==READ && !r_busy && !fault)role<=NONE;
  if(role==LEGACY && !l_busy && !fault)role<=NONE;
  if(m_memory_command_valid && m_memory_command_ready)commands<=commands+1'b1;
  if(s_memory_status_valid && s_memory_status_ready)statuses<=statuses+1'b1;
  if(extra)local_fault<=1;
 end
end
endmodule
`resetall
'''


def unpad_route(legacy):
    plist=ports(legacy);h=header(legacy,'rocev2_wqe_read_unpad','rocev2_segmented_read_unpad_route','    input wire bypass,')
    m={n:'u_'+n if d=='output'else n for d,_,n in plist}
    for n in ['s_context_valid','s_command_valid','s_axis_tvalid','m_command_ready','m_axis_tready']:
        m[n]='!use_bypass && '+n
    decl=declarations(plist,m,'u_')
    selects=dict(s_context_ready="1'b1",s_command_ready='m_command_ready',m_command='s_command',m_command_valid='s_command_valid',
        s_axis_tready='m_axis_tready',m_axis_tdata='s_axis_tdata',m_axis_tkeep='s_axis_tkeep',m_axis_tlast='s_axis_tlast',m_axis_tvalid='s_axis_tvalid')
    logic='\n'.join('assign '+n+'=use_bypass ? '+v+':u_'+n+';'for n,v in selects.items())
    for n in ['context_count','command_count','discarded_padding_bytes']:logic+='\nassign '+n+'=u_'+n+';'
    return h+'\n'+decl+r'''
reg route_fault=0;
wire bad_route=(bypass!==1'b0 && bypass!==1'b1) || (bypass && u_busy);
// Never replace an already-offered legacy beat/event on an illegal route
// change. Keep that real staging owner and quarantine instead.
wire use_bypass=bypass===1'b1 && !u_busy;
assign fault=route_fault || u_fault || bad_route;
assign fault_code=route_fault ? 8'hd8:u_fault_code;
assign queue_guard=(fault || bad_route) ? {MAX_QPS{1'b1}}:u_queue_guard;
assign busy=u_busy || fault || bad_route;
'''+logic+'\n'+instance('rocev2_wqe_read_unpad','legacy_unpad',plist,m)+r'''
always @(posedge clk)begin
 if(rst)route_fault<=0;
 else if(bad_route)route_fault<=1;
end
endmodule
`resetall
'''


def derive():
    out=parent.derive()
    out[MUX]=mux_source(out[executor.MUX])
    out[UNPAD]=unpad_route(out[RTL/'rocev2_wqe_read_unpad.v'])
    out[CHILD_UNPAD]=read.unpad_source()
    p=RTL/'rocev2_native_rnic_endpoint.v';t=out[p]
    t=once(t,'wire segmented_memory_retire_ready;','wire segmented_memory_retire_ready;\nwire segmented_read_memory_path;')
    t=once(t,'rocev2_segmented_executor_mux #(.MAX_QPS(MAX_QPS)) executor (',
        'rocev2_segmented_read_executor_mux #(.MAX_QPS(MAX_QPS)) executor (\n    .large_read_path(segmented_read_memory_path),')
    t=once(t,'rocev2_wqe_read_unpad #(.MAX_QPS(MAX_QPS)) read_unpad (',
        'rocev2_segmented_read_unpad_route #(.MAX_QPS(MAX_QPS)) read_unpad (\n    .bypass(segmented_read_memory_path),')
    out[p]=t
    p=ROOT/'rdma/rtl/rocev2_integrity_transport.v'
    out[p]=once(out[p],'rocev2_native_segmented_request_top transport (','rocev2_native_segmented_read_top transport (')
    return out
