# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated owned HLS/Atomic/MR/RAM/ICRC with core-done consumer.

Trusted config/physical memory ordering/descriptor and positive MAC boundary
are MODELS; drop core receipt is produced by the actual generated RX FSMs.
"""
import atomic_generated_fixture as base
import probe_atomic_owned as service
import derive_atomic_owned_bridge as bridge

ROOT=base.ROOT;once=base.once;prior=base.prior


def bench(directory,words):
    rtl=prior.rtl;t=service.service_bench();t=t[:t.index('integer fd,scanned,serial=0;')]
    generated=directory/'rocev2_atomic_owned_integrity_transport.v';generated.write_text(bridge.derive())
    mapping=dict(clk='clk',rst='rst',m_atomic_request_tdata='x_s_hls_request',
        m_atomic_request_tvalid='x_s_hls_request_valid',m_atomic_request_tready='x_s_hls_request_ready',
        s_atomic_reply_tdata='reply_to_core',s_atomic_reply_tvalid='x_m_hls_reply_valid',s_atomic_reply_tready='x_m_hls_reply_ready')
    for n in ['s_hls_request','s_hls_request_valid','m_hls_reply_ready']:
        t=base.re.sub(r'reg (\[[^]]+\]\s+)?x_'+n+r'=0;',lambda m:'wire '+(m[1]or'')+'x_'+n+';',t)
    t=once(t,'assign quiet=!x_configuration_guard',
        'assign quiet=!w_atomic_admission_guard && !x_configuration_guard')
    wrapper=rtl.instance(generated,'network','w_',mapping)
    wrapper=once(wrapper,'rocev2_atomic_owned_integrity_transport network(',
        'rocev2_atomic_owned_integrity_transport #(.LEGACY_QP_KEY(0),.REQUEST_CQ_ENABLE(1),.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1)) network(')
    n=base.NETWORK.replace('STIMULUS_LAST',str(words-1))
    n=n.replace('x_s_owner_', 'w_m_atomic_owner_')
    n=once(n,'reg token_held=0,reply_seen=0,wire_seen=0;reg [247:0] reply=0;',
        'reg token_held=0,reply_seen=0,wire_seen=0,core_seen=0;reg [391:0] reply=0;\n'
        'reg [223:0] core_receipt=0,held_core=0;reg core_stalled=0;integer core_completions=0;')
    n=once(n,'w_m_axis_tx_tready=random_state[2:0]!=0;',
        'w_m_axis_tx_tready=random_state[2:0]!=0;w_m_atomic_core_done_tready=random_state[4:3]!=0;')
    n=once(n,'reply_seen=0;wire_seen=0;', 'reply_seen=0;wire_seen=0;core_seen=0;')
    n=once(n,'$display("ATOMIC_JOB %092h"','$display("ATOMIC_JOB %0128h"')
    n=once(n,'$display("ATOMIC_RESULT_WORD %062h"','$display("ATOMIC_RESULT_WORD %098h"')
    n=once(n,'if(w_m_axis_tx_tvalid && w_m_axis_tx_tready)begin',r'''
 if(core_stalled && (!w_m_atomic_core_done_tvalid || w_m_atomic_core_done_tdata!==held_core))
  $fatal(1,"actual core receipt retracted under backpressure");
 core_stalled=w_m_atomic_core_done_tvalid&&!w_m_atomic_core_done_tready;held_core=w_m_atomic_core_done_tdata;
 if(w_m_atomic_core_done_tvalid && w_m_atomic_core_done_tready)begin
  core_receipt=w_m_atomic_core_done_tdata;
  if(!token_held || !reply_seen || core_seen || core_receipt[143:0]!=={owned_tag,owned_psn,owned_epoch,owned_qpn} ||
    core_receipt[223:208]!==0 || core_receipt[202:200]!==7 || core_receipt[207:206]!==0 ||
    core_receipt[205]!==reply[247] || core_receipt[204]!==reply[246] || core_receipt[203]===reply[247])
   $fatal(1,"actual core completion lost immutable ownership/consumed proof");
  core_seen=1;core_completions=core_completions+1;$display("ATOMIC_CORE_DONE %056h",core_receipt);
 end
 if(w_m_axis_tx_tvalid && w_m_axis_tx_tready)begin''')
    n=once(n,'if(!token_held || !reply_seen || !wire_seen)$fatal(1,"retirement without modeled owned wire EOF");',
        'if(!token_held || !reply_seen || !core_seen || (!wire_seen && !reply[247]))$fatal(1,"retirement without actual core receipt and required wire EOF");')
    n=once(n,'retirements=retirements+1;token_held=0;',
        'retirements=retirements+1;token_held=0;core_seen=0;')
    n=once(n,'if(!reply_seen || !wire_seen || !w_atomic_admission_guard || !token_held)$fatal(1,"missing exact owned packet EOF");',
        'if(!reply_seen || !core_seen || (!wire_seen && !reply[247]) || !w_atomic_admission_guard || !token_held)$fatal(1,"missing exact core/wire/no-packet receipt");')
    n=once(n,'while(tx_frames==last_tx && cycles<expiry)',
        'while((tx_frames==last_tx || !core_seen) && cycles<expiry)')
    n=once(n,'if(w_rnr_fault || w_recv_fault || w_request_fault || w_integrity_overflow_count || w_tx_integrity_drop_count)',
        'if(w_rnr_fault || w_recv_fault || (w_request_fault && network_case!=3) || w_integrity_overflow_count || w_tx_integrity_drop_count)')
    n=once(n,'if(network_case==1)begin',r'''
 if(network_case==3)begin
  // Explicit one-bit service-transport fault injection in the returned
  // immutable nonce. The actual RX consumer must reject it, not retire.
  input_frame(20);repeat(1200)@(negedge clk);
  if(!w_request_fault || services!=1 || replies!=1 || core_completions || tx_frames ||
    !w_atomic_admission_guard || !token_held || quiet || cfg_ready || mr_cfg_ready)
   $fatal(1,"stale echoed nonce fabricated a core receipt or released ownership");
 end else if(network_case==1)begin''')
    begin=n.index('  // Last evicted duplicate generates NO packet.')
    end=n.index('\n end\n for(k=0;k<16384;',begin)
    n=n[:begin]+r'''
  // Genuine no-packet branch completion: SAME real PSN/MSN readback and
  // immutable nonce, no fixed quiet delay or invented receive completion.
  choose(2);input_frame(65);expiry=cycles+3000;
  while(!core_seen && cycles<expiry)@(negedge clk);
  if(services!=10 || replies!=10 || tx_frames!=9 || !reply[247] || a_dropped_count!=1 || !core_seen ||
    !w_atomic_admission_guard || !token_held || quiet || cfg_ready || mr_cfg_ready)
   $fatal(1,"drop lacked genuine core consumption or fabricated wire");
  retire_wire();
  run_frame(75,2,11);
  if(a_executed_count!=7 || a_replay_count!=2 || retirements!=11 || core_completions!=11 ||
     load64(4096)!==64'hfedcba9876543211)$fatal(1,"drop failed later valid forward progress");'''+n[end:]
    n=n.replace('\\"drop_native_retirement_proven\\":false',
        '\\"drop_core_retirement_proven\\":true,\\"positive_MAC_retirement_model\\":true')
    # Not a replacement service result: only case3 flips one actual returned
    # owner bit to prove the downstream consumer checks immutable identity.
    injection="wire [391:0] reply_to_core=x_m_hls_reply ^ (network_case==3 ? (392'd1<<360):392'd0);\n"
    return t+injection+wrapper+n,generated
