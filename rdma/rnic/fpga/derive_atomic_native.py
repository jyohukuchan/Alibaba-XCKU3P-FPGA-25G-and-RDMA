# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete checked normal+Atomic native graph, candidate until verified.

Same native owned HLS, SQC route epoch/PD, MR/PTE and actual memory backend.
Atomic private tags/lifetime sit OUTSIDE the existing WQE MAC policy. All
retirement sources are hardware owners, never test/CPU quiet or global drain.
Original/default/rollback sources and all timing gates remain unchanged.
"""
import re
import derive_atomic_native_rx as rx

ROOT=rx.ROOT;RTL=rx.RTL
once=rx.once;ports=rx.add_ports;connect=rx.connect;same=rx.same
EXTRA=rx.stage.EXTRA+[RTL/n for n in [
 'rocev2_native_rx_refs.v','rocev2_native_atomic_rx_router.v','rocev2_atomic_packet_guard.v',
 'rocev2_atomic_owned_service_adapter.v','rocev2_atomic_responder.v','rocev2_atomic_memory_bridge.v',
 'rocev2_atomic_owner_reservation.v','rocev2_atomic_mac_tx.v']]


def guard_connections(t,items):
    i=t.index('rocev2_shared_protected_responder #(')
    j=t.index(' guard (',i)+len(' guard (')
    return t[:j]+'\n'+',\n'.join('.'+n+'('+v+')'for n,v in items)+','+t[j:]


BACKEND=[('command_write',''),('command_offset','[63:0]'),('command_length','[31:0]'),
 ('command_key','[31:0]'),('command_tag','[15:0]'),('command_valid',''),('command_ready',''),
 ('write_data','[511:0]'),('write_keep','[63:0]'),('write_last',''),('write_valid',''),('write_ready',''),
 ('read_data','[511:0]'),('read_keep','[63:0]'),('read_last',''),('read_valid',''),('read_ready',''),
 ('status_tag','[15:0]'),('status_error','[7:0]'),('status_valid',''),('status_ready','')]


def memory(t):
    t=ports(t,rx.FLOW+rx.CONTEXT)
    t=once(t,'wire guard_fault,guard_quiescent,guard_mr_ready,guard_qp_ready;',
        rx.declarations(rx.MEM)+'\nwire guard_atomic_rx_guard;\n'
        'wire atomic_memory_guard,atomic_memory_fault,atomic_memory_busy;\n'
        'assign atomic_rx_guard=guard_atomic_rx_guard || atomic_memory_guard || atomic_memory_fault;\n'
        'wire guard_fault,guard_quiescent,guard_mr_ready,guard_qp_ready;')
    p=same(rx.FLOW+rx.CONTEXT+rx.MEM)
    p=[(n,'guard_atomic_rx_guard'if n=='atomic_rx_guard'else v)for n,v in p]
    t=guard_connections(t,p)
    t=once(t,'wire effective_local_work_guard=local_work_guard ||',
        'wire effective_local_work_guard=atomic_memory_guard || local_work_guard ||')
    first=t.index('generate if(LOCAL_MEMORY_ENABLE)begin : shared_payload_memory')
    last=t.index('end endgenerate',first)+len('end endgenerate')
    block=t[first:last]
    block=re.sub(r'\bbackend_('+'|'.join(n for n,_ in BACKEND)+r')\b',r'normal_backend_\1',block)
    block=once(block,'.enable(!guard_fault && !backend_fault),',
        '.enable(!guard_fault && !backend_fault && !a_memory_lock_request),')
    t=t[:first]+block+t[last:]
    t=once(t,'assign memory_drained=backend_drained && backend_idle && !local_memory_busy &&',
        'assign memory_drained=backend_drained && backend_idle && !local_memory_busy && !atomic_memory_guard &&')
    t=once(t,'assign fault=guard_fault || backend_fault || memory_mux_fault;',
        'assign fault=guard_fault || backend_fault || memory_mux_fault || atomic_memory_fault;')
    first=t.index('assign fault_code=');last=t.index(';',first)
    statement=t[first:last]
    statement=once(statement,'memory_mux_fault ?', "atomic_memory_fault ? 8'hed : memory_mux_fault ?")
    t=t[:first]+statement+t[last:]
    decl=rx.declarations([('wire',w,'normal_backend_'+n)for n,w in BACKEND])
    m=dict(clk='clk',rst='rst',enable='!guard_fault && !backend_fault',
        # Stop NEW ordinary admissions, but drain an already-owned normal
        # command BEFORE reserving. Once reserved keep the request asserted
        # across backend busy phases until the real executor releases it.
        atomic_lock_request='a_memory_lock_request && (a_memory_lock_granted || (!local_memory_busy && backend_idle && backend_drained))',
        atomic_lock_granted='a_memory_lock_granted',configuration_guard='atomic_memory_guard',
        fault='atomic_memory_fault',fault_code='',busy='atomic_memory_busy',client_guard='')
    for port,signal in {
      's_command_write':'{a_m_memory_write,normal_backend_command_write}',
      's_command_offset':'{a_m_memory_offset,normal_backend_command_offset}',
      's_command_length':'{a_m_memory_length,normal_backend_command_length}',
      's_command_key':'{a_m_memory_key,normal_backend_command_key}',
      's_command_tag':'{a_m_memory_tag,normal_backend_command_tag}',
      's_command_valid':'{a_m_memory_valid,normal_backend_command_valid}',
      's_command_ready':'{a_m_memory_ready,normal_backend_command_ready}',
      's_axis_write_tdata':'{a_m_axis_write_tdata,normal_backend_write_data}',
      's_axis_write_tkeep':'{a_m_axis_write_tkeep,normal_backend_write_keep}',
      's_axis_write_tlast':'{a_m_axis_write_tlast,normal_backend_write_last}',
      's_axis_write_tvalid':'{a_m_axis_write_tvalid,normal_backend_write_valid}',
      's_axis_write_tready':'{a_m_axis_write_tready,normal_backend_write_ready}',
      'm_axis_read_tdata':'{a_s_axis_read_tdata,normal_backend_read_data}',
      'm_axis_read_tkeep':'{a_s_axis_read_tkeep,normal_backend_read_keep}',
      'm_axis_read_tlast':'{a_s_axis_read_tlast,normal_backend_read_last}',
      'm_axis_read_tvalid':'{a_s_axis_read_tvalid,normal_backend_read_valid}',
      'm_axis_read_tready':'{a_s_axis_read_tready,normal_backend_read_ready}',
      'm_status_tag':'{a_s_memory_status_tag,normal_backend_status_tag}',
      'm_status_error':'{a_s_memory_status_error,normal_backend_status_error}',
      'm_status_valid':'{a_s_memory_status_valid,normal_backend_status_valid}',
      'm_status_ready':'{a_s_memory_status_ready,normal_backend_status_ready}'}.items():m[port]=signal
    for n in ['write','offset','length','key','tag','valid','ready']:m['m_command_'+n]='backend_command_'+n
    for n,suffix in [('tdata','data'),('tkeep','keep'),('tlast','last'),('tvalid','valid'),('tready','ready')]:
        m['m_axis_write_'+n]='backend_write_'+suffix;m['s_axis_read_'+n]='backend_read_'+suffix
    for n in ['tag','error','valid','ready']:m['s_status_'+n]='backend_status_'+n
    logic=decl+'\nassign atomic_backend_idle=backend_drained && backend_idle && !local_memory_busy && !atomic_memory_busy && !fault;\n'
    logic+=rx.instance(RTL/'rocev2_atomic_memory_bridge.v','atomic_memory_domain',m)
    return once(t,'generate if(LOCAL_MEMORY_ENABLE)begin : shared_payload_memory',
        logic+'\ngenerate if(LOCAL_MEMORY_ENABLE)begin : shared_payload_memory')


def root(t):
    # This is now a real hardware guard, not an external API/drain knob.
    t=once(t,'    input wire atomic_lease_guard,\n','')
    t=once(t,'assign fault=native_fault || pipeline_fault;',
        'assign fault=native_fault || pipeline_fault || atomic_mac_fault || atomic_reservation_fault;')
    t=once(t,'assign fault_code=native_fault ? native_fault_code :',
        "assign fault_code=native_fault ? native_fault_code : atomic_mac_fault ? 8'hdc : atomic_reservation_fault ? 8'hdd :")
    for n in ['tdata','tkeep','tvalid','tready','tlast','tuser']:
        t=once(t,'.m_axis_mac_'+n+'(m_axis_mac_tx_'+n+'),',
            '.m_axis_mac_'+n+'(atomic_normal_mac_'+n+'),')
    for n in ['tag','ts','valid','ready']:
        t=once(t,'.s_mac_cpl_'+n+'(s_axis_mac_cpl_'+n+'),',
            '.s_mac_cpl_'+n+'(atomic_normal_cpl_'+n+'),')
    logic=rx.declarations(rx.FLOW)+r'''
wire atomic_lease_guard;
wire atomic_mac_guard,atomic_mac_fault,atomic_mac_busy,atomic_tags_exhausted;
wire atomic_reservation_guard,atomic_reservation_fault;
wire [7:0] atomic_mac_queue_guard,atomic_reservation_queue_guard;
assign atomic_lease_guard=atomic_rx_guard || atomic_mac_guard || atomic_reservation_guard ||
 (|atomic_mac_queue_guard) || (|atomic_reservation_queue_guard);
assign atomic_parent_fault=fault || parent_fault;
assign atomic_local_mac=active_local_mac;assign atomic_peer_mac=active_peer_mac;
assign atomic_mac_available=!atomic_mac_busy && !atomic_tags_exhausted && !atomic_mac_fault &&
 !(|atomic_mac_queue_guard) && !atomic_reservation_guard && !atomic_reservation_fault && !fault;
wire [127:0] atomic_normal_mac_tdata;wire [15:0] atomic_normal_mac_tkeep;
wire atomic_normal_mac_tvalid,atomic_normal_mac_tready,atomic_normal_mac_tlast;
wire [16:0] atomic_normal_mac_tuser;
wire [15:0] atomic_normal_cpl_tag;wire [95:0] atomic_normal_cpl_ts;
wire atomic_normal_cpl_valid,atomic_normal_cpl_ready;
wire [327:0] reserved_mac_owner;wire reserved_mac_valid,reserved_mac_ready;
initial if(TX_TAG_WIDTH!=16 || TS_WIDTH!=96 || CLOCK_PERIOD_PS!=4000)
 $fatal(1,"native Atomic requires reviewed16-bit genuineMAC tags/96-bitSFD/250MHz core");
'''
    reserve=rx.instance(RTL/'rocev2_atomic_owner_reservation.v','atomic_reservation',dict(
        clk='clk',rst='rst',parent_fault='atomic_parent_fault',
        s_owner='m_atomic_packet_owner',s_valid='m_atomic_packet_owner_valid',s_ready='s_atomic_packet_owner_ready',
        m_mac_owner='reserved_mac_owner',m_mac_valid='reserved_mac_valid',m_mac_ready='reserved_mac_ready',
        m_hls_owner='s_atomic_hls_owner',m_hls_valid='s_atomic_hls_owner_valid',m_hls_ready='m_atomic_hls_owner_ready',
        configuration_guard='atomic_reservation_guard',queue_guard='atomic_reservation_queue_guard',
        fault='atomic_reservation_fault',reserved_count='',delivered_count=''))
    p=dict(clk='clk',rst='rst',enable="1'b1",parent_fault='atomic_parent_fault',
        s_owner='reserved_mac_owner[143:0]',s_owner_valid='reserved_mac_valid',s_owner_ready='reserved_mac_ready',
        s_owner_local_mac='reserved_mac_owner[327:280]',s_owner_peer_mac='reserved_mac_owner[279:232]',
        s_owner_local_ip='reserved_mac_owner[231:200]',s_owner_peer_ip='reserved_mac_owner[199:168]',
        s_owner_peer_qpn='reserved_mac_owner[167:144]',s_service_reply='m_atomic_mac_reply',
        s_service_valid='m_atomic_mac_reply_valid',s_service_ready='s_atomic_mac_reply_ready',
        s_core_done='m_atomic_core_done',s_core_valid='m_atomic_core_done_valid',s_core_ready='s_atomic_core_done_ready',
        s_axis_ip_tdata='m_atomic_ip_data',s_axis_ip_tkeep='m_atomic_ip_keep',
        s_axis_ip_tvalid='m_atomic_ip_valid',s_axis_ip_tready='s_atomic_ip_ready',s_axis_ip_tlast='m_atomic_ip_last',
        s_axis_native_tdata='atomic_normal_mac_tdata',s_axis_native_tkeep='atomic_normal_mac_tkeep',
        s_axis_native_tvalid='atomic_normal_mac_tvalid',s_axis_native_tready='atomic_normal_mac_tready',
        s_axis_native_tlast='atomic_normal_mac_tlast',s_axis_native_tuser='atomic_normal_mac_tuser',
        m_retire_owner='s_atomic_retire_owner',m_retire_core='s_atomic_retire_core',
        m_retire_valid='s_atomic_retire_valid',m_retire_ready='m_atomic_retire_ready',
        queue_guard='atomic_mac_queue_guard',configuration_guard='atomic_mac_guard',
        fault='atomic_mac_fault',busy='atomic_mac_busy',tags_exhausted='atomic_tags_exhausted',
        fault_code='',active_tag='',frame_count='',receipt_count='',retired_count='',drop_retired_count='',
        m_retire_tag='',m_retire_timestamp='')
    for n in ['tdata','tkeep','tvalid','tready','tlast','tuser']:p['m_axis_mac_'+n]='m_axis_mac_tx_'+n
    for n in ['tag','ts','valid','ready']:
        p['s_mac_cpl_'+n]='s_axis_mac_cpl_'+n;p['m_native_cpl_'+n]='atomic_normal_cpl_'+n
    logic+=reserve+rx.instance(RTL/'rocev2_atomic_mac_tx.v','atomic_wire_lifetime',p)
    return once(t,'assign fault=native_fault ||',logic+'\nassign fault=native_fault ||')


def derive():
    out=rx.stage.derive()
    path=rx.stage.authority.base.responder.ORIGINAL
    out[path]=rx.protected(out[path])
    path=rx.stage.authority.base.duplex.ORIGINAL;out[path]=rx.shared(out[path])
    path=RTL/'rocev2_paged_responder.v';out[path]=memory(out[path])
    path=RTL/'rocev2_controlled_responder.v'
    t=ports(out[path],rx.FLOW)
    ctx=[('atomic_context_valid','atomic_admission_valid')]
    ctx +=[('atomic_context_'+n,'atomic_bound_'+n)for n in ['qpn','pd','epoch','cookie','peer_qpn','local_ip','peer_ip']]
    out[path]=connect(t,'endpoint',same(rx.FLOW)+ctx)
    for name,child in [('rocev2_dual_ethernet_endpoint','responder'),('rocev2_native_endpoint','datapath'),
        ('rocev2_native_sq_endpoint','network')]:
        path=RTL/(name+'.v');out[path]=connect(ports(out[path],rx.FLOW),child,same(rx.FLOW))
    path=RTL/'rocev2_native_rnic_endpoint.v'
    out[path]=connect(root(out[path]),'native',same(rx.FLOW))
    return out
