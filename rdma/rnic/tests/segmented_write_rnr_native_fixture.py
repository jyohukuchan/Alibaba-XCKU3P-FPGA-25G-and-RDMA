# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native empty-LAST-RQ RNR and SAME raw LAST/PSN retry.

Keep every36 old input/oracle. New case configures an empty genuine RQ before
FIRST, retains the real8192-byte WRITE/MR/HLS/PSN state through a negative
wire proof, posts a real zero-capacity RQ, then retries the identical LAST.
"""
import hashlib
import json
import segmented_write_profile_native_fixture as parent

ROOT=parent.ROOT;once=parent.once;GUARD=parent.GUARD


def __getattr__(name):return getattr(parent,name)


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR+TASK.replace('GUARD.',GUARD+'.'))
    t=once(t,"link_m_cpl_tag==16'h6003", "link_m_cpl_tag==(runtime_write_rnr ? 16'h6004:16'h6003)")
    for old,new in [
        ('wrx_queries>=4','wrx_queries>=(runtime_write_rnr ? 5:4)'),
        ('(wrx_queries<2 ? 0:(wrx_queries-1)*4096)','(wrx_queries<2 ? 0:wrx_queries==2 ? 4096:8192)'),
        ('(wrx_queries==0 ? 8193:wrx_queries==3 ? 1:4096)','(wrx_queries==0 ? 8193:wrx_queries>=3 ? 1:4096)'),
        ('dut.receive_ack_lifetime.ack_owner.receipt_count!=wrx_commits+1)',
         'dut.receive_ack_lifetime.ack_owner.receipt_count!=wrx_commits+1+(runtime_write_rnr && wrx_commits==2 ? 1:0))'),
        ('if(actual_native_SFD_count>fences)$fatal(1,"WRITE positive ACK SFD before real payload visibility fence");',
         'if(actual_native_SFD_count>fences+(runtime_write_rnr ? wrnr_events:0))$fatal(1,"WRITE positive ACK SFD before real payload visibility fence");'),
        ('   rq_command(1,0);rq_command(2,1);wrx_deadline=cycle+5000;',
         '   rq_command(1,0);\n   if(!runtime_write_rnr)begin\n   rq_command(2,1);wrx_deadline=cycle+5000;'),
        ('    $fatal(1,"WRITE notification RQ owner before peer data");\n  end',
         '    $fatal(1,"WRITE notification RQ owner before peer data");\n   end\n  end'),
        ('   wrx_send_packet(wrx_packet);wrx_deadline=cycle+10000;',
         '   if(runtime_write_rnr && wrx_packet==2)run_empty_write_rnr();\n   wrx_send_packet(wrx_packet);wrx_deadline=cycle+10000;'),
        ('dut.receive_ack_lifetime.ack_owner.frame_count!=3 || (wrx_immediate',
         'dut.receive_ack_lifetime.ack_owner.frame_count!=(runtime_write_rnr ? 4:3) || (wrx_immediate'),
        ('wrx_retired || dut.receive_ack_lifetime.ack_owner.receipt_count!=2 ||',
         'wrx_retired || dut.receive_ack_lifetime.ack_owner.receipt_count!=(runtime_write_rnr ? 3:2) ||'),
        ('if(wrx_queries!=4 || wrx_owners!=3','if(wrx_queries!=(runtime_write_rnr ? 5:4) || wrx_owners!=3'),
        ('pcie_write_bytes!=8193 || actual_native_SFD_count!=3 || dut.rq_taken_count!==(wrx_immediate',
         'pcie_write_bytes!=8193 || actual_native_SFD_count!=(runtime_write_rnr ? 4:3) || dut.rq_taken_count!==(wrx_immediate')]:t=once(t,old,new)
    anchor='  $display("SEGMENTED_WRITE_NATIVE_RESULT '
    a=t.index(anchor)
    t=t[:a]+'''  if(runtime_write_rnr)begin
   if(wrnr_owners!=1 || wrnr_events!=1 || wrnr_proofs!=1 || wrnr_retirements!=1 || wrnr_reports!=1 ||
    dut.write_rnr_requests!=1 || dut.write_rnr_proofs!=1 || dut.write_rnr_retirements!=1 || dut.write_rnr_reports!=1 ||
    dut.receive_ack_lifetime.ack_owner.frame_count!=4 || dut.receive_ack_lifetime.ack_owner.receipt_count!=4)
    $fatal(1,"WRITE exactly one real negative wire lifecycle and same-PSN recovery");
   $display("SEGMENTED_WRITE_RNR_NATIVE_RESULT {\\"pass_test\\":true,\\"bytes\\":8193,\\"packets\\":3,\\"MR_queries\\":5,\\"commands\\":3,\\"fences\\":3,\\"native_PSN_commits\\":3,\\"WRITE_Immediate\\":1,\\"notification_capacity\\":0,\\"RNR\\":1,\\"same_PSN_retry\\":1,\\"fresh_ACKs\\":4}");
  end else
'''+t[a:]
    if 'force 'in t:raise ValueError('no internal owner/proof/PSN/memory injection')
    return t


DECLARATIONS=r'''
reg runtime_write_rnr=0;
integer wrnr_owners=0,wrnr_events=0,wrnr_proofs=0,wrnr_retirements=0,wrnr_reports=0;
wire [367:0] wrnr_owner={24'd0,24'h987656,wrx_message};
initial runtime_write_rnr=$test$plusargs("WRITE_RNR_RETRY");
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_write_rnr)begin
 if(dut.write_rnr_ack_owner_valid && dut.write_rnr_ack_owner_ready)begin
  if(wrnr_owners || dut.write_rnr_ack_owner!==wrnr_owner || wrx_commits!=2 || wrx_owners!=2 ||
   dut.rq_posted_count || dut.rq_taken_count || dut.cq_busy)$fatal(1,"RNR actual retained368 owner without invented RQ/CQ");
  wrnr_owners=wrnr_owners+1;
 end
 if(dut.s_write_rnr_event_valid && dut.s_write_rnr_event_ready)begin
  if(wrnr_events || wrnr_owners!=1 || dut.s_write_rnr_event!=={8'h20,24'h987656,24'd2})
   $fatal(1,"RNR actual HLS event after unique real shared ACK owner");
  wrnr_events=wrnr_events+1;
 end
 if(dut.write_rnr_ack_done_valid && dut.write_rnr_ack_done_ready)begin
  if(wrnr_proofs || dut.write_rnr_ack_done!=={16'h6003,wrnr_owner} ||
   actual_native_SFD_count!=3 || dut.receive_ack_lifetime.ack_owner.receipt_count!=3)
   $fatal(1,"RNR actual fresh-tag384 negative EOF/SFD/tail receipt");
  wrnr_proofs=wrnr_proofs+1;
 end
 if(dut.write_rnr_ack_retire_valid && dut.write_rnr_ack_retire_ready)begin
  if(wrnr_retirements || wrnr_proofs!=1 || dut.write_rnr_ack_retire_owner!==wrnr_owner)
   $fatal(1,"RNR exact actual ACK retirement before local error consumer");
  wrnr_retirements=wrnr_retirements+1;
 end
 if(reject_valid && reject_ready)begin
  if(wrnr_reports || wrnr_retirements!=1 || reject_error!==38 || reject_qpn!==2 || reject_psn!==24'h987656)
   $fatal(1,"RNR actual independent local reject metadata/handshake");
  wrnr_reports=wrnr_reports+1;
 end
end
'''

TASK=r'''
task run_empty_write_rnr;
 begin
  if(!wrx_immediate || dut.rq_posted_count || dut.rq_taken_count || dut.rq_active || dut.cq_busy ||
   wrx_commits!=2 || wrx_done!=2 || wrx_owners!=2 || fences!=2 || pcie_write_bytes!=8192)
   $fatal(1,"RNR needs actual FIRST/MID payload with empty preconfigured notification RQ");
  reject_ready=0;wrx_send_packet(2);wrx_deadline=cycle+10000;
  while(!reject_valid || wrnr_proofs!=1 || wrnr_retirements!=1 || !response_tx_quiescent)begin
   if(cycle>wrx_deadline || fault)$fatal(1,"WRITE real RNR wire/local report deadline fc%h ACK%h RNR%h",fc,dut.recv_ack_fault_code,dut.write_rnr_fault_code);
   @(negedge clk);
  end
  repeat(71)begin
   @(negedge clk);
   if(reject_error!==38 || reject_qpn!==2 || reject_psn!==24'h987656 ||
    wrnr_owners!=1 || wrnr_events!=1 || wrnr_reports || wrx_queries!=4 || wrx_owners!=2 || wrx_done!=2 || wrx_commits!=2 ||
    GUARD.expected_psn!==24'h987656 || dut.write_ctl_message_context!==wrx_message || !dut.s_write_message_active ||
    !dut.s_write_held || !dut.s_write_mr_guard || dut.s_write_queue_guard!==4 || !dut.write_rnr_guard ||
    dut.rq_posted_count || dut.rq_taken_count || dut.rq_active || dut.cq_busy || m_cq_valid ||
    wrx_rq_owners || wrx_whole || wrx_committed || wrx_retired ||
    lrx_commands!=2 || lrx_statuses!=2 || commands!=2 || statuses!=2 || fences!=2 || pcie_write_bytes!=8192 ||
    actual_native_SFD_count!=3 || dut.receive_ack_lifetime.ack_owner.frame_count!=3 ||
    dut.receive_ack_lifetime.ack_owner.receipt_count!=3 ||
    pcie_host[12285]!==(((12285*37)^8'h5a)&255) || pcie_posted_valid[12285] || fault)
    $fatal(1,"RNR advanced real message/MR/PSN/DMA/RQ/CQ or lost negative proof while local report blocked");
  end
  reject_ready=1;@(posedge clk);if(!reject_valid)$fatal(1,"RNR true local report handshake");
  @(negedge clk);reject_ready=0;wrx_deadline=cycle+5000;
  while(dut.write_rnr_guard || dut.write_reject_valid || !dut.m_write_rx_ready)begin
   if(cycle>wrx_deadline || fault)$fatal(1,"RNR genuine reject retirement/input retry deadline");@(negedge clk);
  end
  if(wrnr_reports!=1 || dut.write_rnr_reports!=1 || GUARD.expected_psn!==24'h987656 ||
   dut.write_ctl_message_context!==wrx_message || !dut.s_write_mr_guard || !dut.s_write_message_active)
   $fatal(1,"RNR local report must not release actual message/MR or advance PSN");
  // Only the genuine producer advances. Do not reconfigure a guarded QP/RQ.
  rq_command(2,1);wrx_deadline=cycle+5000;
  while(dut.rq_posted_count!=1)begin
   if(cycle>wrx_deadline || fault)$fatal(1,"RNR genuine zero-capacity RQ producer/fetch deadline");@(negedge clk);
  end
  if(dut.rq_head_context!==lrx_owner || dut.rq_active || dut.rq_taken_count || dut.rq_queue_guard!==4 ||
   GUARD.expected_psn!==24'h987656 || wrx_commits!=2 || dut.write_ctl_message_context!==wrx_message)
   $fatal(1,"RNR actual posted RQ before identical LAST/PSN retry");
 end
endtask
'''


def verify_large_write_rnr(output,posted,run):
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('SEGMENTED_WRITE_RNR_NATIVE_RESULT ')]
    wanted=dict(pass_test=True,bytes=8193,packets=3,MR_queries=5,commands=3,fences=3,native_PSN_commits=3,
        WRITE_Immediate=1,notification_capacity=0,RNR=1,same_PSN_retry=1,fresh_ACKs=4)
    if rows!=[wanted]:raise ValueError('actual complete native RNR/retry cardinality')
    original=parent.parent.parent
    ack=bytearray(original.incoming.case(True,True)[-1]);frames=[]
    for index,(packet,syndrome,msn)in enumerate([(0,0,0),(1,0,0),(2,0x20,0),(2,0,1)]):
        p=bytearray(ack);p[37:40]=(original.FIRST+packet).to_bytes(3,'big');p[40]=syndrome;p[41:44]=msn.to_bytes(3,'big')
        frames.append((0x6001+index,bytes.fromhex('b8830367c5d08af3fbb975310800')+original.packet_tool.repair(p)))
    if original.rq.link.frames(output)!=frames:raise ValueError('independent every actual negative/positive ACK byte, fresh tag, PSN/MSN/FCS/SFD/CDC')
    host=bytes(int(s,16)for s in(run/'large-write-receive-host.hex').read_text().splitlines())
    expected=bytearray(((i*37)^0x5a)&255 for i in range(16384));expected[4093:12286]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(8193))
    if host!=expected:raise ValueError('independent every RNR/retry host payload/pad/sentinel byte')
    owner=0;r=posted[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little')
    for width,value in [(32,0),(64,get(0,8)),(64,1),(64,0x9123456700000001),(24,2),(16,17),(16,1),
        (16,4),(16,1),(32,0),(32,0),(64,0),(64,0),(64,0),(32,0),(20,3)]:owner=(owner<<width)|value
    snapshot=[int(s,16)for s in(run/'large-write-receive-event.hex').read_text().splitlines()]
    if snapshot!=[1,15,0,0x89abcdf0,0xfedcba98]+[(owner>>(32*i))&0xffffffff for i in range(20)]+[8193,3,0x89abcdef,511]+[0]*4:
        raise ValueError('independent one whole8193 flags3 CQ/full620 zero-capacity owner after RNR/retry')
    return dict(summary=rows[0],every_payload_and_sentinel_byte=True,actual_native_RNR_and_same_PSN_retry=True,
        zero_capacity_genuine_RQ=True,whole_received_bytes=8193,full620_CQ_owner=f'{owner:0155x}',
        actual_XGMII_frames=[dict(tag=tag,frame_hex=frame.hex())for tag,frame in frames],
        host_snapshot_sha256=hashlib.sha256(host).hexdigest(),actual_Linux_or_physical_hardware=False)
