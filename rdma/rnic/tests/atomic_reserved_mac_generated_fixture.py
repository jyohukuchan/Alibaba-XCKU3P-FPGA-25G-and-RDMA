# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owned core/Atomic/MR/MAC with ordered reservation before execution.

Full native admission/queues/PHY/physical host ordering remain unproven.
Small4-bit tag parameter reaches exhaustion in15 requests, not a long stress
test. Production/default width remains13. No force or test retirement.
"""
import re
import atomic_mac_generated_fixture as base
import derive_atomic_reserved_mac_bridge as bridge

ROOT=base.ROOT
once=base.once
EXTRA=['atomic_mac_tags_exhausted','atomic_mac_available','atomic_reservation_guard',
    'atomic_reservation_fault','atomic_reservation_queue_guard',
    'atomic_reservations','atomic_owner_deliveries']


def bench(directory,words):
    t,_=base.bench(directory,words)
    generated=directory/'rocev2_atomic_reserved_mac_integrity_transport.v'
    generated.write_text(bridge.derive())
    t=once(t,'rocev2_atomic_mac_integrity_transport #(',
        'rocev2_atomic_reserved_mac_integrity_transport #(.ATOMIC_MAC_TAG_SEQUENCE_WIDTH(4),')
    ports={name:(direction,width or '')for direction,width,name in base.prior.rtl.ports(generated)}
    declarations='\n'.join('wire '+ports[name][1]+'w_'+name+';'for name in EXTRA)
    t=once(t,'rocev2_atomic_reserved_mac_integrity_transport #(',declarations+'\nrocev2_atomic_reserved_mac_integrity_transport #(')
    t=once(t,'.atomic_parent_fault(',','.join('.'+name+'(w_'+name+')'for name in EXTRA)+',.atomic_parent_fault(')
    t=once(t,'assign quiet=!w_atomic_admission_guard && !w_atomic_mac_guard',
        'assign quiet=!w_atomic_reservation_guard && !w_atomic_admission_guard && !w_atomic_mac_guard')
    t=once(t,'w_atomic_admission_guard || w_atomic_mac_guard || token_held',
        'w_atomic_admission_guard || w_atomic_mac_guard || w_atomic_reservation_guard || token_held')
    t=once(t,'if(network_case==0 && (actual_Atomic_SFD_count',
        'if((network_case==0 || network_case==4) && (actual_Atomic_SFD_count')
    t=once(t,' if(network_case==3)begin',SPECIAL+'\n if(network_case==3)begin')
    # Previous branch selector becomes an else-if after our new special cases.
    t=once(t,'\n if(network_case==3)begin','\n else if(network_case==3)begin')
    tail=r'''
 if(network_case==4)begin
  // All15 tags are consumed within this short case. Requests12..15 replay
  // the actual cached FADD; no new execution or DMA. The16th post-integrity
  // packet must NOT gain a new owner or reach HLS/service/memory.
  run_frame(75,2,12);run_frame(75,2,13);run_frame(75,2,14);run_frame(75,2,15);
  if(!w_atomic_mac_tags_exhausted || w_atomic_mac_available || w_atomic_admission_accepted!=15 ||
    w_atomic_reservations!=15 || w_atomic_owner_deliveries!=15 || retirements!=15 ||
    a_executed_count!=7 || a_replay_count!=6 || a_dropped_count!=1 || commands!=12 ||
    w_atomic_admission_guard || w_atomic_mac_guard || w_atomic_reservation_guard || token_held)
   $fatal(1,"last finite tag lost genuine retirement or replay/side-effect semantics");
  input_frame(75);repeat(300)@(negedge clk);
  if(!network.checked_valid || network.checked_ready || w_atomic_admission_accepted!=15 ||
    services!=15 || replies!=15 || core_completions!=15 || retirements!=15 || commands!=12 ||
    w_atomic_reservations!=15 || w_atomic_owner_deliveries!=15 || a_executed_count!=7 ||
    w_atomic_mac_fault || w_atomic_reservation_fault || w_atomic_admission_fault)
   $fatal(1,"exhaustion admitted another side effect or invented retirement");
  // Pending input upstream of admission is NOT cancellation/unpin proof.
 end
'''
    t=once(t,' for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)',tail+'\n for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)')
    proof=r'''
 $display("ATOMIC_ADMISSION_PROOF {\"case\":%0d,\"tag_width\":4,\"reserved\":%0d,\"delivered\":%0d,\"accepted\":%0d,\"exhausted\":%0d,\"retired\":%0d,\"checked_pending\":%0d,\"checked_ready\":%0d,\"disable_cycle\":%0d}",
 network_case,w_atomic_reservations,w_atomic_owner_deliveries,w_atomic_admission_accepted,
 w_atomic_mac_tags_exhausted,w_atomic_mac_retired,network.checked_valid,network.checked_ready,disable_cycle);
'''
    t=once(t,' $display("ATOMIC_GENERATED ',proof+'\n $display("ATOMIC_GENERATED ')
    monitors=r'''
integer disable_cycle=0,reservation_events=0,delivery_events=0;
always @(posedge clk)if(!rst)begin
 if(network.reserved_mac_valid && network.reserved_mac_ready)begin
  reservation_events=reservation_events+1;
  $display("ATOMIC_MAC_RESERVED %082h",network.reserved_mac_owner);
 end
 if(network.reserved_hls_valid && network.reserved_hls_ready)begin
  if(!network.mac_owner.active || network.mac_owner.owner!==network.reserved_hls_owner ||
    reservation_events!=delivery_events+1 || w_atomic_reservation_fault)
   $fatal(1,"actual HLS owner released without matching actual MAC reservation");
  delivery_events=delivery_events+1;
  $display("ATOMIC_HLS_RELEASED %036h",network.reserved_hls_owner);
 end
end
'''
    t=once(t,'integer native_receipts=0,ni;',monitors+'\ninteger native_receipts=0,ni;')
    if 'force 'in t or 'w_s_atomic_retire_valid='in t:raise ValueError('no test release')
    return t,generated


SPECIAL=r'''
 if(network_case==5 || network_case==6)begin
  // Admission disable is deliberately AFTER a real packet-guard handshake.
  // Case5: first post-ICRC beat. Case6: full owner offered to actual MAC.
  fork
   input_frame(20);
   begin
    if(network_case==5)begin
     while(!(network.checked_valid && network.checked_ready))@(posedge clk);
     @(negedge clk);
    end else begin
     while(!network.reserved_mac_valid)@(negedge clk);
    end
    disable_cycle=cycles;w_atomic_admission_enable=0;
   end
  join
  expiry=cycles+3000;
  while((tx_frames!=1 || !core_seen) && cycles<expiry)@(negedge clk);
  if(tx_frames!=1 || services!=1 || replies!=1 || !core_seen || !disable_cycle)
   $fatal(1,"disabled admitted packet stranded before genuine core/MAC consumption");
  retire_wire();
  if(w_atomic_admission_enable || w_atomic_reservations!=1 || w_atomic_owner_deliveries!=1 || !quiet)
   $fatal(1,"disable dropped reservation or retained valid retired owner");
  @(negedge clk);w_atomic_admission_enable=1;
  run_frame(25,2,2);
  if(a_executed_count!=1 || a_replay_count!=1 || retirements!=2 || w_atomic_mac_frames!=2 ||
    w_atomic_reservations!=2 || w_atomic_owner_deliveries!=2)
   $fatal(1,"re-enable lost actual duplicate/cache ownership");
 end
'''
