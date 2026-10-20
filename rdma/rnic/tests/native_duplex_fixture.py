# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native simultaneous RC: peer SEND before our SEND gets its ACK.

Preserve exact independent SQ/RQ, host memory/MAC/CQ proofs and wire checks.
Only peer scheduling changes; no internal state/drain assignment or fake CQ.
"""
import json
import native_independent_queues_fixture as split
import native_receive_cancel_fixture as cancel_fixture

def case(base_case,cancel=False):
    tb,words,records,receive_records,request=(cancel_fixture.case(base_case)if cancel else split.case(base_case))
    once=split.old.old.qp.main.sq.once
    tb=once(tb,'.SEPARATE_RQ_ENABLE(1)','.SEPARATE_RQ_ENABLE(1),.DUPLEX_ENABLE(1)')
    a=tb.index('task receive_once;');b=tb.index('endtask',a)+len('endtask')
    task=tb[a:b]
    first=task.index('  send_frame(')
    last=task.index('  send_frame(frame_start,8);',first)
    completed_send=task[first:last]
    # No local CQ may have completed before receiving the peer's independent
    # request. Its ACK is deliberately withheld until real peer placement and
    # HLS receive receipt/ACK generation have finished in the SAME engine.
    task=task[:first]+task[last:]
    anchor='  expected_recv_owner=dut.rq_held_context;'
    completed_send=once(completed_send,'dut.rq_taken_count!=seq-1 || dut.rq_active',
        'dut.rq_taken_count!=seq || !dut.rq_active')
    evidence=r'''
  if(!dut.h_local_hls_active || !dut.rq_active || dut.rq_taken_count!=seq ||
     local_committed_count!=seq-1 || dut.tx_receipt_count!=seq || dut.cq_busy || fault)
   $fatal(1,"peer request failed to progress while SAME local WR awaited peer ACK");
  $display("NATIVE_DUPLEX_PENDING {\"sequence\":%0d,\"local_SEND_unacknowledged\":true,\"peer_RECV_placement_and_core_proved\":true,\"both_owners_held\":true}",seq);
'''
    independent=r'''
  if(!dut.completion_memory_drained || dut.memory_drained || !parent_dma_drained ||
     !dut.native.router_drained || !dut.sq_dma_drained || !dut.rq_active ||
     dut.receive_ack_lifetime.ack_owner.receipt_count!=seq-1)
   $fatal(1,"local CQ needs real physical-memory proof and OWN MAC, not another owner's held MAC");
  $display("NATIVE_DUPLEX_LOCAL_CQ {\"sequence\":%0d,\"physical_memory_drained\":true,\"global_MAC_barrier_held\":true,\"other_RECV_owner_retained\":true}",seq);
'''
    task=once(task,anchor,evidence+completed_send+independent+anchor)
    tb=tb[:a]+task+tb[b:]
    # One direction's genuine completion must not wait for or retire the
    # other direction's MAC/core owner. All full-owner/proof checks remain.
    tb=once(tb,'if(sq_value!==3 || dut.h_local_hls_active || dut.rq_active || fault)',
        'if(sq_value!==3 || fault || (owner[339:324]==4 ? dut.rq_active:dut.h_local_hls_active))')
    tb=once(tb,'dut.cq_commit_context!==expected_send_owner || !dut.memory_drained)',
        'dut.cq_commit_context!==expected_send_owner || !dut.completion_memory_drained || '
        '!parent_dma_drained || !dut.native.router_drained || !dut.sq_dma_drained)')
    # Observation only. Preserve the exact original deadline/fatal; a held
    # peer receive is never permission to invent memory/core drain or a CQ.
    deadline='if(cycle>split_deadline)$fatal(1,"independent CQ deadline event%0d local%h RQ%0d shared%h SQ%h",event_sequence,local_proof_flags,dut.rq_active,dut.h_shared_hls_fault_code,dut.native_fault_code);'
    tb=once(tb,deadline,r'''
   if(cycle>split_deadline)begin
    $display("DUPLEX_CQ_WAIT req_valid%0d req_ready%0d match%0d memory%0d parent%0d router%0d SQ_DMA%0d net%0d local_mem%0d h_ack%0d shared%h",
     dut.h_request_done_valid,dut.h_request_done_ready,dut.wire_lifetime.request_match,
     dut.memory_drained,parent_dma_drained,dut.native.router_drained,dut.sq_dma_drained,
     dut.native.net_memory_drained,dut.sq_local_memory_busy,dut.h_m_local_ack_tvalid,dut.h_shared_hls_fault_code);
    '''+deadline+r'''
   end''')
    return tb,words,records,receive_records,request

def verify(output,request,empty=False):
    result=split.verify(output,request,empty)
    events=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_DUPLEX_PENDING ')]
    if len(events)!=2 or [x['sequence']for x in events]!=[1,2] or not all(
        x['local_SEND_unacknowledged']and x['peer_RECV_placement_and_core_proved']and x['both_owners_held']for x in events):
        raise ValueError('actual simultaneous pending local/remote ownership missing')
    completions=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_DUPLEX_LOCAL_CQ ')]
    if len(completions)!=2 or [x['sequence']for x in completions]!=[1,2] or not all(
        x['physical_memory_drained']and x['global_MAC_barrier_held']and x['other_RECV_owner_retained']for x in completions):
        raise ValueError('actual own-direction CQ/physical-memory versus other MAC proof missing')
    return dict(**result,simultaneous_native_request_receive_owners=events,
        independent_own_CQ_while_other_MAC_barrier_held=completions)
