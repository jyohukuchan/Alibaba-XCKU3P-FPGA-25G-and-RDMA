# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owned HLS/Atomic/MR/RAM/ICRC + automatic real-MAC retirement.

Host descriptors/order/PHY pins remain models. MAC XGMII/SFD/FCS and receipt
CDC, framer/native mux/owner join/packet retirement are actual connected RTL.
"""
import re
import atomic_owned_generated_fixture as old
import atomic_mac_wire_fixture as link
import derive_atomic_mac_bridge as bridge

ROOT=old.ROOT;once=old.once;prior=old.prior
NATIVE=bytes.fromhex('02000000000102000000000288b5')+bytes(range(46))


def bench(directory,words):
    original,_=old.bench(directory,words)
    n=original[original.index('reg [145:0] stimulus'):]
    t=old.service.service_bench();t=t[:t.index('integer fd,scanned,serial=0;')]
    generated=directory/'rocev2_atomic_mac_integrity_transport.v';generated.write_text(bridge.derive())
    mapping=dict(clk='clk',rst='rst',m_atomic_request_tdata='x_s_hls_request',
        m_atomic_request_tvalid='x_s_hls_request_valid',m_atomic_request_tready='x_s_hls_request_ready',
        s_atomic_reply_tdata='reply_to_core',s_atomic_reply_tvalid='x_m_hls_reply_valid',s_atomic_reply_tready='x_m_hls_reply_ready',
        m_mac_data='link_s_data',m_mac_keep='link_s_keep',m_mac_valid='link_s_valid',m_mac_ready='link_s_ready',m_mac_last='link_s_last',m_mac_user='link_s_user',
        s_mac_cpl_tag='link_m_cpl_tag',s_mac_cpl_ts='link_m_cpl_ts',s_mac_cpl_valid='link_m_cpl_valid',s_mac_cpl_ready='link_m_cpl_ready',
        atomic_parent_fault='a_fault || b_fault || fault || x_fault')
    for name in ['s_hls_request','s_hls_request_valid','m_hls_reply_ready']:
        t=re.sub(r'reg (\[[^]]+\]\s+)?x_'+name+r'=0;',lambda m:'wire '+(m[1]or'')+'x_'+name+';',t)
    t=once(t,'assign quiet=!x_configuration_guard',
        'assign quiet=!w_atomic_admission_guard && !w_atomic_mac_guard && !x_configuration_guard')
    wrapper=prior.rtl.instance(generated,'network','w_',mapping)
    wrapper=once(wrapper,'rocev2_atomic_mac_integrity_transport network(',
        'rocev2_atomic_mac_integrity_transport #(.LEGACY_QP_KEY(0),.REQUEST_CQ_ENABLE(1),.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1)) network(')
    n=once(n,'w_m_axis_tx_tready=random_state[2:0]!=0;w_m_atomic_core_done_tready=random_state[4:3]!=0;',
        '// BOTH ready signals are driven by actual MAC lifecycle, not the test.')
    n=once(n,'a_fault || b_fault || fault || x_fault || w_atomic_admission_fault',
        'a_fault || b_fault || fault || x_fault || w_atomic_admission_fault || w_atomic_mac_fault')
    n=once(n,'if(network_case!=2)$fatal','if(network_case!=2 && network_case!=3)$fatal')
    n=once(n,'w_atomic_admission_guard || token_held || x_busy || a_busy || b_busy',
        'w_atomic_admission_guard || w_atomic_mac_guard || token_held || x_busy || a_busy || b_busy')
    n=once(n,'w_atomic_trusted_qpn=q;',"w_atomic_trusted_qpn=q;w_atomic_trusted_peer_qpn=24'hf12345+q;")
    a=n.index('task retire_wire;');b=n.index('endtask',a)+len('endtask')
    n=n[:a]+r'''
task retire_wire;
 begin
  // OBSERVE automatic hardware handoff. No CPU/test-driven release signal.
  expiry=cycles+2200;
  while(token_held || w_atomic_admission_guard || w_atomic_mac_guard)begin
   if(cycles>expiry)$fatal(1,"missing actual MAC SFD/EOF/tail automatic retirement");@(negedge clk);
  end
  if(!quiet)$fatal(1,"unreleased actual guarded memory/packet owner");
 end
endtask
'''+n[b:]
    n=once(n,'w_atomic_trusted_local_ip=32\'hc6120b02;w_atomic_trusted_peer_ip=32\'hc6120b01;',
        "w_atomic_trusted_local_ip=32'hc6120b02;w_atomic_trusted_peer_ip=32'hc6120b01;\n"
        " w_atomic_trusted_local_mac=48'h020000000002;w_atomic_trusted_peer_mac=48'h020000000001;\n"
        " w_atomic_trusted_peer_qpn=24'hf12347;w_m_native_cpl_ready=1;")
    n=once(n,'run_frame(20,2,1);run_frame(25,2,2);',
        'fork run_frame(20,2,1);native_frame();join\n  run_frame(25,2,2);')
    a=n.index('  // Genuine no-packet branch completion:');b=n.index('  run_frame(75,2,11);',a)
    n=n[:a]+r'''
  choose(2);input_frame(65);expiry=cycles+2200;
  while(retirements!=10 && cycles<expiry)@(negedge clk);
  if(services!=10 || replies!=10 || tx_frames!=9 || a_dropped_count!=1 || retirements!=10 || token_held || !quiet)
   $fatal(1,"drop not genuinely/automatically retired by consumed-core proof");
'''+n[b:]
    n=once(n,' for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)',r'''
 if(network_case==0 && (actual_Atomic_SFD_count!=10 || actual_native_SFD_count!=1 || native_receipts!=1 ||
   w_atomic_mac_frames!=10 || w_atomic_mac_receipts!=10 || w_atomic_mac_retired!=11 || w_atomic_mac_fault))
  $fatal(1,"actual MAC/native classes/receipts/automatic lifetimes incomplete");
 for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)''')
    # Prior nested fixture contains escaped quotes. Require one replacement,
    # preserving its quote escaping without weakening the scope verifier.
    for key in ['MAC_boundary_model','positive_MAC_retirement_model']:
        n,count=re.subn('('+key+r'\\*":)true',r'\1false',n)
        if count!=1:raise ValueError('MAC scope label anchor changed: '+key)
    native=r'''
integer native_receipts=0,ni;
reg [479:0] native_packet=480'hNATIVE;
always @(posedge clk)if(!rst && w_m_native_cpl_valid && w_m_native_cpl_ready)begin
 if(w_m_native_cpl_tag!==16'h9234)$fatal(1,"private Atomic receipt escaped to normal/native owner");
 native_receipts=native_receipts+1;
end
task native_frame;
 begin
  for(ni=0;ni<4;ni=ni+1)begin
   @(negedge clk);w_s_native_data=(native_packet>>(ni*128));w_s_native_keep=ni==3 ? 16'h0fff:16'hffff;
   w_s_native_last=ni==3;w_s_native_user={16'h9234,1'b0};w_s_native_valid=1;
   @(posedge clk);while(!w_s_native_ready)@(posedge clk);
  end
  @(negedge clk);w_s_native_valid=0;
 end
endtask
'''.replace('NATIVE',f'{int.from_bytes(NATIVE,"little"):0120x}')
    injection="wire [391:0] reply_to_core=x_m_hls_reply ^ (network_case==3 ? (392'd1<<360):392'd0);\n"
    return t+injection+link.LINK+wrapper+native+n,generated
