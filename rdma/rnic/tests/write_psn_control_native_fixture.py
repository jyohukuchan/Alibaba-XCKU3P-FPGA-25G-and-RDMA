# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native NAK/suppression/retry/duplicate, retaining every37 old case.

Genuine8193 WRITE Immediate, one real zero-SGE notification RQ/CQ; future MID
NAK, suppressed repeat, correct MID retry, identical MID and post-LAST replay.
No rewritten observed output, internal injection or invented success proof.
"""
import hashlib
import json
import segmented_write_rnr_native_fixture as parent
import segmented_write_payload_native_fixture as payload

ROOT=parent.ROOT;once=parent.once;GUARD=parent.GUARD
CONTEXT=(14<<352)|(0xb8830367c5d0<<304)|(0x8af3fbb97531<<256)|(0xc6120b01<<224)|(0xc6120b02<<192)|\
    (196<<168)|(0xfedcba9889abcdef<<104)|(0x9123456700000001<<40)|(17<<24)|2


def __getattr__(name):return getattr(parent,name)


def future_input():
    _,_,_,_,frames=parent.large_write_variant(True)
    frame=frames[1];body=bytearray(frame[14:]);body[37:40]=(payload.parent.FIRST+4).to_bytes(3,'big')
    future=frame[:14]+payload.parent.packet_tool.repair(body)
    if future[14+40:-4]!=frame[14+40:-4]or len(future)!=len(frame):
        raise ValueError('future MID must retain full authored payload/extent')
    words=payload.parent.rq.split.encode_frame(future)
    if len(words)!=260:raise ValueError('actual full Ethernet MID260 required')
    return words,future


DECLARATIONS=r'''
reg runtime_write_psn=0;
initial runtime_write_psn=$test$plusargs("WRITE_PSN_CONTROL");
reg [144:0] wrpsn_future[0:259];
integer wrpsn_owners=0,wrpsn_events=0,wrpsn_hls=0,wrpsn_mac=0,wrpsn_retired=0,wrpsn_reports=0;
wire [355:0] wrpsn_context={4'he,48'hb8830367c5d0,48'h8af3fbb97531,32'hc6120b01,32'hc6120b02,
 24'd196,64'hfedcba9889abcdef,64'h9123456700000001,16'd17,24'd2};
function [479:0] wrpsn_owner;input integer n;
 begin wrpsn_owner={4'd0,n==0 ? 8'h60:8'h1f,n==0 ? 24'h987658:n==1 ? 24'h987655:24'h987656,
 n==2 ? 24'h987656:24'h987655,64'(n+1),wrpsn_context};end
endfunction
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_write_psn)begin
 if(dut.write_control_ack_owner_valid && dut.write_control_ack_owner_ready)begin
  if(wrpsn_owners>=3 || dut.write_control_ack_owner!==wrpsn_owner(wrpsn_owners) ||
   wrx_commits!=wrpsn_owners+1 || dut.m_write_native_context!==wrpsn_context)
   $fatal(1,"PSN genuine full native356 plus480 type/received/response/serial owner");
  $display("PSN_NATIVE_OWNER %0d %0120h",wrpsn_owners,dut.write_control_ack_owner);wrpsn_owners=wrpsn_owners+1;
 end
 if(dut.s_control_owner_valid && dut.s_control_owner_ready)begin
  if(wrpsn_events>=3 || wrpsn_owners!=wrpsn_events+1 || dut.s_control_owner!==wrpsn_owner(wrpsn_events))
   $fatal(1,"PSN same full480 actual HLS event after shared ACK admission");
  wrpsn_events=wrpsn_events+1;
 end
 if(dut.m_control_done_valid && dut.m_control_done_ready)begin
  if(wrpsn_hls>=3 || wrpsn_events!=wrpsn_hls+1 ||
   dut.m_control_done!=={8'd0,24'(wrpsn_hls==2 ? 1:0),wrpsn_owner(wrpsn_hls)})
   $fatal(1,"PSN actual shared-MSN full512 HLS receipt, never local fake MSN");
  $display("PSN_NATIVE_HLS %0d %0128h",wrpsn_hls,dut.m_control_done);wrpsn_hls=wrpsn_hls+1;
 end
 if(dut.write_control_ack_done_valid && dut.write_control_ack_done_ready)begin
  if(wrpsn_mac>=3 || wrpsn_hls!=wrpsn_mac+1 ||
   dut.write_control_ack_done!=={16'(16'h6002+2*wrpsn_mac),8'd0,24'(wrpsn_mac==2 ? 1:0),wrpsn_owner(wrpsn_mac)} ||
   actual_native_SFD_count!=2+2*wrpsn_mac || dut.receive_ack_lifetime.ack_owner.receipt_count!=2+2*wrpsn_mac ||
   wrx_commits!=wrpsn_mac+1)
   $fatal(1,"PSN actual fresh528 MAC proof/SFD/EOF/tail without data PSN commit");
  $display("PSN_NATIVE_MAC %0d %0132h",wrpsn_mac,dut.write_control_ack_done);wrpsn_mac=wrpsn_mac+1;
 end
 if(dut.write_control_ack_retire_valid && dut.write_control_ack_retire_ready)begin
  if(wrpsn_retired>=3 || wrpsn_mac!=wrpsn_retired+1 ||
   dut.write_control_ack_retire_owner!==wrpsn_owner(wrpsn_retired))
   $fatal(1,"PSN exact full480 ACK retirement after actual MAC proof");
  wrpsn_retired=wrpsn_retired+1;
 end
 if(reject_valid && reject_ready)begin
  if(wrpsn_reports>=4 || reject_error!==18 || reject_qpn!==2 ||
   reject_psn!==(wrpsn_reports<2 ? 24'h987658:wrpsn_reports==2 ? 24'h987655:24'h987656) ||
   wrpsn_retired!=(wrpsn_reports<2 ? 1:wrpsn_reports) ||
   wrpsn_events!=(wrpsn_reports<2 ? 1:wrpsn_reports))
   $fatal(1,"PSN independent local error or suppressed repeat fabricated wire lifecycle");
  wrpsn_reports=wrpsn_reports+1;
 end
end
'''

TASKS=r'''
task wrpsn_send_future;
 integer b;
 begin
  for(b=0;b<260;b=b+1)begin
   @(negedge clk);{il,ik,id}=wrpsn_future[b];iv=1;@(posedge clk);while(!ir)@(posedge clk);
  end
  @(negedge clk);iv=0;
 end
endtask
task run_psn_reject;
 input integer kind;
 integer limit,base_commits,base_queries,base_reads,base_writes,base_descriptors,base_sfd,expected_controls;
 reg [23:0] native_psn;
 begin
  base_commits=kind<2 ? 1:kind==2 ? 2:3;base_queries=base_commits+1;
  native_psn=24'h987654+base_commits;base_sfd=kind<2 ? 2:kind==2 ? 4:6;
  expected_controls=kind<2 ? 1:kind;
  if(wrx_commits!=base_commits || wrx_owners!=base_commits || wrx_done!=base_commits ||
   wrx_queries!=base_queries || GUARD.expected_psn!==native_psn ||
   fences!=base_commits || pcie_write_bytes!=(kind<2 ? 4096:kind==2 ? 8192:8193) ||
   kind<3 && (!dut.s_write_message_active || dut.write_ctl_message_context!==wrx_message) ||
   kind==3 && (dut.s_write_message_active || dut.s_write_held || wrx_whole!=1 || wrx_committed!=1 || wrx_retired!=1 || dut.cq_busy))
   $fatal(1,"PSN rejected packet needs genuine prior native payload/frontier and exact message lifetime");
  base_reads=read_tlps;base_writes=write_tlps;base_descriptors=router_descriptor_count;
  reject_ready=0;
  if(kind<2)wrpsn_send_future;else wrx_send_packet(kind==2 ? 1:2);
  limit=cycle+10000;
  while(!reject_valid || wrpsn_retired!=expected_controls || !response_tx_quiescent)begin
   if(cycle>limit || fault)$fatal(1,"PSN actual negative wire/local report deadline kind%0d fc%h ACK%h control%h",kind,fc,dut.recv_ack_fault_code,dut.write_control_fault_code);
   @(negedge clk);
  end
  repeat(71)begin
   @(negedge clk);
   if(reject_error!==18 || reject_qpn!==2 || reject_psn!==(kind<2 ? 24'h987658:kind==2 ? 24'h987655:24'h987656) ||
    wrpsn_reports!=kind || wrpsn_owners!=expected_controls || wrpsn_events!=expected_controls ||
    wrpsn_hls!=expected_controls || wrpsn_mac!=expected_controls || wrpsn_retired!=expected_controls ||
    wrx_queries!=base_queries || wrx_owners!=base_commits || wrx_done!=base_commits || wrx_commits!=base_commits ||
    GUARD.expected_psn!==native_psn || !dut.s_control_held || dut.s_control_queue_guard!==4 ||
    !dut.s_write_held || dut.s_write_queue_guard!==4 || dut.write_ctl_m_control_context!==wrpsn_context ||
    !dut.write_ctl_m_control_certified || kind<3 && (!dut.s_write_message_active || dut.write_ctl_message_context!==wrx_message) ||
    kind==3 && dut.s_write_message_active ||
    dut.rq_taken_count!=(kind==3 ? 1:0) || wrx_rq_owners!=(kind==3 ? 1:0) || wrx_whole!=(kind==3 ? 1:0) ||
    wrx_committed!=(kind==3 ? 1:0) || wrx_retired!=(kind==3 ? 1:0) || dut.cq_busy || m_cq_valid ||
    commands!=base_commits || statuses!=base_commits || lrx_commands!=base_commits || lrx_statuses!=base_commits || fences!=base_commits ||
    pcie_write_bytes!=(kind<2 ? 4096:kind==2 ? 8192:8193) || read_tlps!=base_reads || write_tlps!=base_writes ||
    router_descriptor_count!=base_descriptors || actual_native_SFD_count!=base_sfd ||
    dut.receive_ack_lifetime.ack_owner.frame_count!=base_sfd || dut.receive_ack_lifetime.ack_owner.receipt_count!=base_sfd || fault)
    $fatal(1,"PSN NAK/duplicate/suppression changed native MR/data/PSN/RQ/CQ or synthesized wire completion");
  end
  reject_ready=1;@(posedge clk);if(!reject_valid)$fatal(1,"PSN genuine local error consumption");
  @(negedge clk);reject_ready=0;limit=cycle+5000;
  while(dut.s_control_held || dut.control_reject_valid || !dut.m_write_rx_ready || !response_tx_quiescent)begin
   if(cycle>limit || fault)$fatal(1,"PSN actual negative retire/input retry deadline");@(negedge clk);
  end
  if(wrpsn_reports!=kind+1 || GUARD.expected_psn!==native_psn || wrx_commits!=base_commits ||
   dut.write_control_requests!=expected_controls || dut.write_control_proofs!=expected_controls ||
   dut.write_control_retirements!=expected_controls || dut.write_control_reports!=expected_controls ||
   dut.write_control_suppressed!=(kind==0 ? 0:1))
   $fatal(1,"PSN local completion/suppression incorrectly advanced positive execution");
 end
endtask
'''


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR+TASKS.replace('GUARD.',GUARD+'.'))
    changes=[
        ("link_m_cpl_tag==(runtime_write_rnr ? 16'h6004:16'h6003)",
         "link_m_cpl_tag==(runtime_write_psn ? 16'h6005:runtime_write_rnr ? 16'h6004:16'h6003)"),
        ('receipt_count!=wrx_commits+1+(runtime_write_rnr && wrx_commits==2 ? 1:0))',
         'receipt_count!=wrx_commits+1+(runtime_write_rnr && wrx_commits==2 ? 1:0)+(runtime_write_psn ? wrpsn_mac:0))'),
        ('if(actual_native_SFD_count>fences+(runtime_write_rnr ? wrnr_events:0))',
         'if(actual_native_SFD_count>fences+(runtime_write_rnr ? wrnr_events:0)+(runtime_write_psn ? wrpsn_events:0))'),
        ('  $readmemh("large-write-receive-input.hex",wrx_stimulus);',
         '  $readmemh("large-write-receive-input.hex",wrx_stimulus);\n  if(runtime_write_psn)$readmemh("write-psn-future-input.hex",wrpsn_future);'),
        ('   if(runtime_write_rnr && wrx_packet==2)run_empty_write_rnr();',
         '   if(runtime_write_psn && wrx_packet==1)begin run_psn_reject(0);run_psn_reject(1);end\n'
         '   if(runtime_write_psn && wrx_packet==2)run_psn_reject(2);\n'
         '   if(runtime_write_rnr && wrx_packet==2)run_empty_write_rnr();'),
        ('frame_count!=(runtime_write_rnr ? 4:3) || (wrx_immediate',
         'frame_count!=(runtime_write_psn ? 5:runtime_write_rnr ? 4:3) || (wrx_immediate'),
        ('receipt_count!=(runtime_write_rnr ? 3:2) ||',
         'receipt_count!=(runtime_write_psn ? 4:runtime_write_rnr ? 3:2) ||'),
        ('actual_native_SFD_count!=(runtime_write_rnr ? 4:3) || dut.rq_taken_count',
         'actual_native_SFD_count!=(runtime_write_psn ? 5:runtime_write_rnr ? 4:3) || dut.rq_taken_count'),
        ('  if(dut.s_write_held || dut.rq_active || dut.cq_busy || local_execution_guard || fault)$fatal(1,"WRITE final genuine lifetime guard");',
         '  if(runtime_write_psn)run_psn_reject(3);\n'
         '  if(dut.s_write_held || dut.rq_active || dut.cq_busy || local_execution_guard || fault)$fatal(1,"WRITE final genuine lifetime guard");')]
    for old,new in changes:t=once(t,old,new)
    anchor='  if(runtime_write_rnr)begin\n   if(wrnr_owners!=1'
    summary=r'''  if(runtime_write_psn)begin
   if(wrpsn_owners!=3 || wrpsn_events!=3 || wrpsn_hls!=3 || wrpsn_mac!=3 || wrpsn_retired!=3 || wrpsn_reports!=4 ||
    dut.write_control_requests!=3 || dut.write_control_proofs!=3 || dut.write_control_retirements!=3 ||
    dut.write_control_reports!=3 || dut.write_control_suppressed!=1 ||
    dut.receive_ack_lifetime.ack_owner.frame_count!=6 || dut.receive_ack_lifetime.ack_owner.receipt_count!=6 ||
    actual_native_SFD_count!=6 || wrx_queries!=4 || wrx_commits!=3 || wrx_whole!=1 || wrx_committed!=1 || wrx_retired!=1)
    $fatal(1,"PSN exactly three real control lifecycles/one suppressed drop and one data/RQ/CQ execution");
   $display("WRITE_PSN_NATIVE_RESULT {\"pass_test\":true,\"bytes\":8193,\"packets\":3,\"MR_queries\":4,\"commands\":3,\"fences\":3,\"native_PSN_commits\":3,\"WRITE_Immediate\":1,\"notification_capacity\":0,\"NAK\":1,\"NAK_suppressed\":1,\"duplicate_ACKs\":2,\"fresh_ACKs\":6,\"local_rejects\":4,\"whole_CQ\":1}");
  end else
'''
    t=once(t,anchor,summary+anchor)
    if 'force 'in t:raise ValueError('no internal owner/proof/PSN/MR/DMA injection')
    return t


def verify_large_write_psn(output,posted,run):
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('WRITE_PSN_NATIVE_RESULT ')]
    wanted=dict(pass_test=True,bytes=8193,packets=3,MR_queries=4,commands=3,fences=3,native_PSN_commits=3,
        WRITE_Immediate=1,notification_capacity=0,NAK=1,NAK_suppressed=1,duplicate_ACKs=2,fresh_ACKs=6,local_rejects=4,whole_CQ=1)
    if rows!=[wanted]:raise ValueError('actual complete native PSN-control cardinality')
    original=payload.parent;ack=bytearray(original.incoming.case(True,True)[-1]);frames=[]
    for i,(packet,syndrome,msn)in enumerate([(0,0,0),(1,0x60,0),(1,0,0),(1,0x1f,0),(2,0,1),(2,0x1f,1)]):
        p=bytearray(ack);p[37:40]=(original.FIRST+packet).to_bytes(3,'big');p[40]=syndrome;p[41:44]=msn.to_bytes(3,'big')
        frames.append((0x6001+i,bytes.fromhex('b8830367c5d08af3fbb975310800')+original.packet_tool.repair(p)))
    if original.rq.link.frames(output)!=frames:raise ValueError('independent every actual positive/control wire byte/PSN/MSN/FCS/SFD/fresh tag')
    owners=[]
    for n,(syndrome,received,response)in enumerate([(0x60,0x987658,0x987655),(0x1f,0x987655,0x987655),(0x1f,0x987656,0x987656)]):
        owners.append((syndrome<<468)|(received<<444)|(response<<420)|((n+1)<<356)|CONTEXT)
    for label,expected in [('OWNER',owners),('HLS',[o|((1 if i==2 else 0)<<480)for i,o in enumerate(owners)]),
        ('MAC',[o|((1 if i==2 else 0)<<480)|((0x6002+2*i)<<512)for i,o in enumerate(owners)])]:
        actual=[(int(s.split()[1]),int(s.split()[2],16))for s in output.splitlines()if s.startswith('PSN_NATIVE_'+label+' ')]
        if actual!=list(enumerate(expected)):raise ValueError('independent full native control '+label+' ownership')
    host=bytes(int(s,16)for s in(run/'large-write-receive-host.hex').read_text().splitlines())
    expected=bytearray(((i*37)^0x5a)&255 for i in range(16384));expected[4093:12286]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(8193))
    if host!=expected:raise ValueError('independent every PSN-retry/duplicate host payload/pad/sentinel byte')
    rq=0;r=posted[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little')
    for width,value in [(32,0),(64,get(0,8)),(64,1),(64,0x9123456700000001),(24,2),(16,17),(16,1),
        (16,4),(16,1),(32,0),(32,0),(64,0),(64,0),(64,0),(32,0),(20,3)]:rq=(rq<<width)|value
    snapshot=[int(s,16)for s in(run/'large-write-receive-event.hex').read_text().splitlines()]
    if snapshot!=[1,15,0,0x89abcdf0,0xfedcba98]+[(rq>>(32*i))&0xffffffff for i in range(20)]+[8193,3,0x89abcdef,511]+[0]*4:
        raise ValueError('independent one whole8193/CQ/flags3/real620 owner despite replay and retry')
    return dict(summary=rows[0],every_payload_and_sentinel_byte=True,actual_native_PSN_control=True,
        suppressed_repeat_has_no_wire_proof=True,duplicate_has_no_second_DMA_RQ_CQ=True,zero_capacity_genuine_RQ=True,
        full620_CQ_owner=f'{rq:0155x}',whole_received_bytes=8193,
        actual_XGMII_frames=[dict(tag=tag,frame_hex=frame.hex())for tag,frame in frames],
        host_snapshot_sha256=hashlib.sha256(host).hexdigest(),actual_Linux_or_physical_hardware=False)
