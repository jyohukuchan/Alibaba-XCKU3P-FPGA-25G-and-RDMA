# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native fatal access62/partial semantic61; every38 old case retained.

Only host/root/peer/PHY/PTP are models. Actual HLS/MR/backend/MAC/PSN/cancel
and real queued zero-RQ ownership must run; no fake error CQ/STOP/unpin.
"""
import hashlib
import json
import write_psn_control_native_fixture as parent
ROOT=parent.ROOT;once=parent.once;GUARD=parent.GUARD;CONTEXT=parent.CONTEXT


def __getattr__(name):return getattr(parent,name)


def fatal_input(partial):
    _,_,_,_,frames=parent.large_write_variant(True)
    original=frames[1 if partial else 0];body=bytearray(original[14:])
    if partial:
        body=body[:40+4080]+bytes(4)
        if body[28]!=7 or int.from_bytes(body[37:40],'big')!=0x987655:raise ValueError('actual expected-PSN MID required')
    else:body[48:52]=(9).to_bytes(4,'big')
    frame=original[:14]+parent.payload.parent.packet_tool.repair(body)
    if partial:
        if frame[14+40:-4]!=original[14+40:14+40+4080]:raise ValueError('exact authored MID payload prefix required')
    elif frame[14+56:-4]!=original[14+56:-4]:raise ValueError('invalid-key FIRST must retain every payload byte')
    words=parent.payload.parent.rq.split.encode_frame(frame)
    if len(words)!=(259 if partial else 261):raise ValueError('exact authored fatal Ethernet extent required')
    return words,frame


DECLARATIONS=r'''
reg runtime_write_fatal=0,wrfatal_partial=0;
initial begin runtime_write_fatal=$test$plusargs("WRITE_FATAL_ACCESS") || $test$plusargs("WRITE_FATAL_PARTIAL");
 wrfatal_partial=$test$plusargs("WRITE_FATAL_PARTIAL");end
reg [144:0] wrfatal_input[0:260];
wire [999:0] m_write_fatal_selected;wire m_write_fatal_selected_valid;
reg m_write_fatal_selected_ready=0;
integer wrfatal_owners=0,wrfatal_events=0,wrfatal_hls=0,wrfatal_mac=0,wrfatal_retired=0;
integer wrfatal_abort_owners=0,wrfatal_abort_done=0,wrfatal_reports=0,wrfatal_cancels=0,wrfatal_selected_taken=0;
wire [23:0] wrfatal_psn=wrfatal_partial ? 24'h987655:24'h987654;
wire [479:0] wrfatal_owner={4'd0,wrfatal_partial ? 8'h61:8'h62,wrfatal_psn,wrfatal_psn,64'd1,wrpsn_context};
wire [959:0] wrfatal_abort={8'd0,wrfatal_partial ? 8'h0f:8'd0,wrfatal_partial ? 16'h6001:16'd0,
 24'd0,wrfatal_owner,wrfatal_partial ? wrx_token(0):424'd0};
wire [999:0] wrfatal_selected={8'h07,8'd0,24'd0,wrfatal_abort};
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_write_fatal)begin
 if(dut.write_control_ack_owner_valid && dut.write_control_ack_owner_ready)begin
  if(wrfatal_owners || dut.write_control_ack_owner!==wrfatal_owner || dut.m_write_native_context!==wrpsn_context ||
   wrx_commits!=(wrfatal_partial ? 1:0) || GUARD.expected_psn!==wrfatal_psn ||
   dut.s_write_abort_guard!==4 || dut.m_write_admission_ready)
   $fatal(1,"FATAL genuine full480 native admission/current frontier and pre-wire quarantine");
  $display("FATAL_NATIVE_OWNER %0120h",dut.write_control_ack_owner);wrfatal_owners=wrfatal_owners+1;
 end
 if(dut.s_control_owner_valid && dut.s_control_owner_ready)begin
  if(wrfatal_events || wrfatal_owners!=1 || dut.s_control_owner!==wrfatal_owner)$fatal(1,"FATAL real480 HLS event must follow actual shared ACK owner");
  wrfatal_events=wrfatal_events+1;
 end
 if(dut.m_control_done_valid && dut.m_control_done_ready)begin
  if(wrfatal_hls || wrfatal_events!=1 || dut.m_control_done!=={8'd0,24'd0,wrfatal_owner})$fatal(1,"FATAL actual512 shared-MSN header receipt");
  $display("FATAL_NATIVE_HLS %0128h",dut.m_control_done);wrfatal_hls=wrfatal_hls+1;
 end
 if(dut.write_control_ack_done_valid && dut.write_control_ack_done_ready)begin
  if(wrfatal_mac || wrfatal_hls!=1 || dut.write_control_ack_done!=={wrfatal_partial ? 16'h6002:16'h6001,8'd0,24'd0,wrfatal_owner} ||
   actual_native_SFD_count!=(wrfatal_partial ? 2:1) || dut.receive_ack_lifetime.ack_owner.receipt_count!=(wrfatal_partial ? 2:1))
   $fatal(1,"FATAL actual fresh528 MAC EOF/SFD/tail proof, never fabricated header completion");
  $display("FATAL_NATIVE_MAC %0132h",dut.write_control_ack_done);wrfatal_mac=wrfatal_mac+1;
 end
 if(dut.write_control_ack_retire_valid && dut.write_control_ack_retire_ready)begin
  if(wrfatal_retired || wrfatal_mac!=1 || dut.write_control_ack_retire_owner!==wrfatal_owner || reject_valid)
   $fatal(1,"FATAL real480 ACK retirement must precede abort and local report release");
  wrfatal_retired=wrfatal_retired+1;
 end
 if(dut.s_write_abort_owner_valid && dut.s_write_abort_owner_ready)begin
  if(wrfatal_abort_owners || wrfatal_retired!=1 || wrfatal_reports || dut.s_write_abort_owner!==wrfatal_abort)
   $fatal(1,"FATAL actual full960 last real positive/fatal ownership before HLS abort");
  $display("FATAL_NATIVE_ABORT_OWNER %0240h",dut.s_write_abort_owner);wrfatal_abort_owners=wrfatal_abort_owners+1;
 end
 if(dut.m_write_abort_done_valid && dut.m_write_abort_done_ready)begin
  if(wrfatal_abort_done || wrfatal_abort_owners!=1 || wrfatal_reports || wrfatal_cancels ||
   dut.m_write_abort_done!=={8'd0,24'd0,wrfatal_abort} || dut.s_write_message_active!==wrfatal_partial)
   $fatal(1,"FATAL actual992 HLS table/checkpoint/state-clear receipt before local report/native cancel");
  $display("FATAL_NATIVE_ABORT_DONE %0248h",dut.m_write_abort_done);wrfatal_abort_done=wrfatal_abort_done+1;
 end
 if(reject_valid && reject_ready)begin
  if(wrfatal_reports || wrfatal_abort_done!=1 || wrfatal_cancels || reject_error!==(wrfatal_partial ? 16:1) ||
   reject_qpn!==2 || reject_psn!==wrfatal_psn)$fatal(1,"FATAL exact independent local reject after actual HLS abort");
  wrfatal_reports=wrfatal_reports+1;
 end
 if(dut.s_error_cancel_valid && dut.s_error_cancel_ready)begin
  if(!wrfatal_partial || wrfatal_cancels || wrfatal_reports!=1 || !dut.s_error_cancel_certified ||
   dut.s_error_cancel_context!==wrx_message || !dut.s_write_message_active)$fatal(1,"FATAL genuine selected native message cancellation after all proofs");
  wrfatal_cancels=wrfatal_cancels+1;
 end
 if(m_write_fatal_selected_valid && m_write_fatal_selected_ready)begin
  if(wrfatal_selected_taken || wrfatal_abort_done!=1 || wrfatal_reports!=1 || wrfatal_cancels!=(wrfatal_partial ? 1:0) ||
   m_write_fatal_selected!==wrfatal_selected || dut.s_write_message_active || dut.write_abort_quarantined!==4 ||
   dut.m_write_admission_ready)$fatal(1,"FATAL selected1000 is real cancel readback, not quarantine release/global drain/unpin");
  $display("FATAL_NATIVE_SELECTED %0250h",m_write_fatal_selected);wrfatal_selected_taken=wrfatal_selected_taken+1;
 end
end
'''

TASKS=r'''
task wrfatal_send_bad;
 integer b,count;
 begin
  count=wrfatal_partial ? 259:261;
  for(b=0;b<count;b=b+1)begin
   @(negedge clk);{il,ik,id}=wrfatal_input[b];iv=1;@(posedge clk);
   while(!ir)begin if(cycle>wrx_deadline || fault)$fatal(1,"FATAL bounded genuine peer input backpressure");@(posedge clk);end
  end
  @(negedge clk);iv=0;
 end
endtask
task wrfatal_counts;
 begin
  if(wrx_queries!=(wrfatal_partial ? 2:1) || wrx_owners!=(wrfatal_partial ? 1:0) || wrx_done!=(wrfatal_partial ? 1:0) ||
   wrx_commits!=(wrfatal_partial ? 1:0) || GUARD.expected_psn!==wrfatal_psn ||
   commands!=(wrfatal_partial ? 1:0) || statuses!=(wrfatal_partial ? 1:0) ||
   lrx_commands!=(wrfatal_partial ? 1:0) || lrx_statuses!=(wrfatal_partial ? 1:0) ||
   lrx_fenced_bytes!=(wrfatal_partial ? 4096:0) || fences!=(wrfatal_partial ? 1:0) || pcie_write_bytes!=(wrfatal_partial ? 4096:0) ||
   router_descriptor_count!=(wrfatal_partial ? 4:1) || pcie_physical_reads!=(wrfatal_partial ? 2:1) ||
   pcie_physical_writes!=(wrfatal_partial ? 2:0) || read_tlps!=(wrfatal_partial ? 2:1) ||
   read_completions!=(wrfatal_partial ? 2:1) || write_tlps!=(wrfatal_partial ? 33:0) ||
   dut.rq_posted_count!=1 || dut.rq_taken_count || dut.rq_active || dut.rq_head_context!==lrx_owner ||
   wrx_rq_owners || wrx_whole || wrx_committed || wrx_retired || dut.cq_busy || m_cq_valid ||
   dut.write_ctl_completed_messages || fault)
   $fatal(1,"FATAL rejected data changed actual MR/DMA/fence/PSN/queued-RQ/CQ/cardinality or invented whole completion");
 end
endtask
task run_write_fatal_native;
 integer wait_until,stall,b,probe_index;
 begin
  if(!wrx_immediate)$fatal(1,"FATAL real zero-SGE notification RQ fixture required");
  $readmemh("large-write-receive-input.hex",wrx_stimulus);
  $readmemh("write-fatal-input.hex",wrfatal_input,0,wrfatal_partial ? 258:260);
  lrx_owner={32'd0,rq_records[0][63:0],64'd1,64'h9123456700000001,24'd2,16'd17,16'd1,16'd4,16'd1,
   32'd0,32'd0,64'd0,64'd0,64'd0,32'd0,20'd3};
  rq_command(1,0);rq_command(2,1);wait_until=cycle+5000;
  while(dut.rq_posted_count!=1)begin if(cycle>wait_until || fault)$fatal(1,"FATAL genuine queued zero-RQ posting");@(negedge clk);end
  if(dut.rq_head_context!==lrx_owner || dut.rq_active || dut.rq_taken_count || dut.rq_queue_guard!==4)
   $fatal(1,"FATAL genuine retained queued zero-RQ context");
  reject_ready=0;m_write_fatal_selected_ready=0;lrx_hold_final_MAC=1;
  if(wrfatal_partial)begin
   wrx_send_packet(0);wait_until=cycle+10000;
   while(wrx_done!=1 || dut.receive_ack_lifetime.ack_owner.frame_count!=1)begin
    if(cycle>wait_until || fault)$fatal(1,"FATAL actual FIRST HLS/MAC frame deadline");@(negedge clk);
   end
   wrx_deadline=cycle+10000;
   fork
    begin wrfatal_send_bad();end
    begin
     repeat(1100)begin
      @(negedge clk);
      if(wrx_commits || GUARD.expected_psn!==24'h987654 || dut.receive_ack_lifetime.ack_owner.receipt_count ||
       wrfatal_owners || wrfatal_events || wrfatal_hls || wrfatal_abort_owners || wrfatal_reports ||
       wrfatal_cancels || m_write_fatal_selected_valid || m_cq_valid || fault)
       $fatal(1,"FATAL old positive actual MAC receipt withholding cannot become PSN/fatal/abort proof");
     end
     lrx_hold_final_MAC=0;
    end
   join
  end else begin wrx_deadline=cycle+10000;wrfatal_send_bad();end
  wait_until=cycle+10000;
  while(!reject_valid || wrfatal_abort_done!=1 || wrfatal_retired!=1 || !response_tx_quiescent)begin
   if(cycle>wait_until || fault)$fatal(1,"FATAL real NAK/HLS abort/local reject deadline fc%h ctl%h abort%h",fc,dut.write_control_fault_code,dut.write_abort_fault_code);
   @(negedge clk);
  end
  repeat(71)begin
   @(negedge clk);wrfatal_counts;
   if(reject_error!==(wrfatal_partial ? 16:1) || reject_psn!==wrfatal_psn || reject_qpn!==2 ||
    wrfatal_reports || wrfatal_cancels || m_write_fatal_selected_valid || wrfatal_owners!=1 || wrfatal_events!=1 ||
    wrfatal_hls!=1 || wrfatal_mac!=1 || wrfatal_retired!=1 || wrfatal_abort_owners!=1 || wrfatal_abort_done!=1 ||
    dut.s_write_message_active!==wrfatal_partial || !dut.s_write_held || !dut.s_write_mr_guard ||
    dut.s_write_queue_guard!==4 || !dut.s_control_held || dut.s_control_queue_guard!==4 ||
    dut.write_abort_quarantined!==4 || dut.m_write_admission_ready)
    $fatal(1,"FATAL independent local report withholding lost message/RQ/quarantine or canceled early");
  end
  reject_ready=1;@(posedge clk);if(!reject_valid)$fatal(1,"FATAL actual independent local reject consumption");
  @(negedge clk);reject_ready=0;wait_until=cycle+5000;
  while(!m_write_fatal_selected_valid)begin
   if(cycle>wait_until || fault)$fatal(1,"FATAL actual native selected cancel/readback deadline");@(negedge clk);
  end
  repeat(71)begin
   @(negedge clk);wrfatal_counts;
   if(m_write_fatal_selected!==wrfatal_selected || wrfatal_reports!=1 || wrfatal_cancels!=(wrfatal_partial ? 1:0) ||
    dut.s_write_message_active || dut.s_write_held || dut.write_abort_quarantined!==4 ||
    !dut.s_control_held || dut.s_control_queue_guard!==4 || local_execution_guard!==4 ||
    dut.m_write_admission_ready || dut.m_write_rx_ready || wrfatal_selected_taken)
    $fatal(1,"FATAL full1000 notification held independently; selected cancel is NOT global drain/unpin/quarantine release");
  end
  wrx_fp=$fopen("write-fatal-selected.hex","w");$fdisplay(wrx_fp,"%0250h",m_write_fatal_selected);$fclose(wrx_fp);
  wrx_fp=$fopen("write-fatal-rq-owner.hex","w");$fdisplay(wrx_fp,"%0155h",dut.rq_head_context);$fclose(wrx_fp);
  read_reg(24'h40300c,sq_value);if(sq_value)$fatal(1,"FATAL must not invent a standard success/error CQ");
  m_write_fatal_selected_ready=1;@(posedge clk);if(!m_write_fatal_selected_valid)$fatal(1,"FATAL real selected notification handshake");
  @(negedge clk);m_write_fatal_selected_ready=0;repeat(71)@(negedge clk);
  wrfatal_counts;
  if(wrfatal_selected_taken!=1 || m_write_fatal_selected_valid || dut.write_abort_quarantined!==4 ||
   dut.m_write_admission_ready || dut.m_write_rx_ready || local_execution_guard!==4 ||
   dut.write_abort_requests!=1 || dut.write_abort_HLS_completions!=1 || dut.write_abort_cancels!=(wrfatal_partial ? 1:0) ||
   dut.write_abort_completions!=1 || dut.write_control_requests!=1 || dut.write_control_proofs!=1 ||
   dut.write_control_retirements!=1 || dut.write_control_reports!=1 || dut.write_control_suppressed)
   $fatal(1,"FATAL real selected acknowledgment reopened native admission or duplicated owner/cancel/report");
  wrx_fp=$fopen("large-write-receive-host.hex","w");
  for(b=0;b<16384;b=b+1)begin
   if(pcie_posted_valid[b] || pcie_host[b]!==((wrfatal_partial && b>=4093 && b<8189) ? pcie_pattern(b-4093):(((b*37)^8'h5a)&255)))
    $fatal(1,"FATAL every real host FIRST-only payload and unchanged rejected-data/pad/sentinel byte");
   $fdisplay(wrx_fp,"%02h",pcie_host[b]);
  end
  $fclose(wrx_fp);check_ring;
  for(b=0;b<256;b=b+1)if(pcie_posted_valid[16640+b] || pcie_host[16640+b]!==rq_records[b/128][(b%128)*8+:8])
   $fatal(1,"FATAL queued coherent RQ descriptor changed without a real RQ/CQ transfer");
  // Offer the complete authored correct MID for up to1100 clocks. If raw
  // ingress backpressures, keep VALID/data stable until simulation ends;
  // otherwise the real checker/router must hold it before native authority.
  // A pending raw RX reference is NOT asserted to be a global drain.
  probe_index=0;
  for(stall=0;stall<1100;stall=stall+1)begin
   @(negedge clk);
   if(probe_index<260)begin {il,ik,id}=wrx_stimulus[261+probe_index];iv=1;end else iv=0;
   @(posedge clk);if(iv && ir)probe_index=probe_index+1;
   if(dut.m_write_admission_ready || dut.m_write_rx_ready || dut.write_abort_quarantined!==4 ||
    local_execution_guard!==4 || m_write_fatal_selected_valid || reject_valid || m_cq_valid || fault)
    $fatal(1,"FATAL actual new peer replay escaped permanent native ingress quarantine");
   wrfatal_counts;
  end
  $display("WRITE_FATAL_NATIVE_RESULT {\"pass_test\":true,\"partial\":%0d,\"MR_queries\":%0d,\"bytes\":%0d,\"commands\":%0d,\"fences\":%0d,\"native_PSN_commits\":%0d,\"NAK\":1,\"HLS_aborts\":1,\"native_cancels\":%0d,\"selected_proofs\":1,\"retained_RQ\":1,\"CQ\":0,\"quarantine\":4,\"replay_words_accepted\":%0d}",
   wrfatal_partial,wrx_queries,pcie_write_bytes,commands,fences,wrx_commits,wrfatal_cancels,probe_index);
 end
endtask
'''


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR.replace('GUARD.',GUARD+'.')+TASKS.replace('GUARD.',GUARD+'.'))
    t=once(t,'dut.s_write_mr_request_key!==8',
        "dut.s_write_mr_request_key!==(runtime_write_fatal && !wrfatal_partial ? 32'd9:32'd8)")
    t=once(t,'if(actual_native_SFD_count>fences+(runtime_write_rnr ? wrnr_events:0)+(runtime_write_psn ? wrpsn_events:0))',
        'if(actual_native_SFD_count>fences+(runtime_write_rnr ? wrnr_events:0)+(runtime_write_psn ? wrpsn_events:0)+(runtime_write_fatal ? wrfatal_events:0))')
    t=once(t,"link_m_cpl_tag==(runtime_write_psn ? 16'h6005:runtime_write_rnr ? 16'h6004:16'h6003)",
        "link_m_cpl_tag==(runtime_write_fatal ? 16'h6001:runtime_write_psn ? 16'h6005:runtime_write_rnr ? 16'h6004:16'h6003)")
    t=once(t,'requester_wire_mode=1;run_large_write_native();',
        'requester_wire_mode=1;if(runtime_write_fatal)run_write_fatal_native();else run_large_write_native();')
    a=t.index('rocev2_native_rnic_endpoint #(');b=t.index(');',a)+2;inst=t[a:b]
    inst=once(inst,'dut(', 'dut(.m_write_fatal_selected(m_write_fatal_selected),.m_write_fatal_selected_valid(m_write_fatal_selected_valid),.m_write_fatal_selected_ready(m_write_fatal_selected_ready),')
    t=t[:a]+inst+t[b:]
    if 'force 'in t:raise ValueError('no internal owner/proof/PSN/MR/DMA injection')
    return t


def verify_fatal(output,posted,partial,run):
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('WRITE_FATAL_NATIVE_RESULT ')]
    if len(rows)!=1:raise ValueError('one actual complete fatal native result required')
    summary=rows[0]
    wanted=dict(pass_test=True,partial=int(partial),MR_queries=2 if partial else 1,bytes=4096 if partial else 0,
        commands=int(partial),fences=int(partial),native_PSN_commits=int(partial),NAK=1,HLS_aborts=1,
        native_cancels=int(partial),selected_proofs=1,retained_RQ=1,CQ=0,quarantine=4)
    if any(summary.get(n)!=v for n,v in wanted.items())or not 0<=summary['replay_words_accepted']<=260:
        raise ValueError('independent fatal native cardinalities/retained ownership/quarantine required')
    psn=0x987655 if partial else 0x987654;syndrome=0x61 if partial else 0x62
    owner=(syndrome<<468)|(psn<<444)|(psn<<420)|(1<<356)|CONTEXT
    packet=0
    if partial:
        for w,v in [(24,2),(16,17),(64,0x9123456700000001),(64,1),(32,8),(64,0xfedcba9876543210),
            (32,8193),(24,0x987654),(32,0),(32,4096),(24,0x987654),(16,1)]:packet=(packet<<w)|v
    abort=packet|(owner<<424)|((0x6001 if partial else 0)<<928)|((15 if partial else 0)<<944)
    selected=abort|(7<<992)
    expected={'OWNER':owner,'HLS':owner,'MAC':owner|((0x6002 if partial else 0x6001)<<512),
        'ABORT_OWNER':abort,'ABORT_DONE':abort,'SELECTED':selected}
    for label,value in expected.items():
        observed=[int(s.split()[1],16)for s in output.splitlines()if s.startswith('FATAL_NATIVE_'+label+' ')]
        if observed!=[value]:raise ValueError('independent every full480/512/528/960/992/1000 bit:'+label)
    if int((run/'write-fatal-selected.hex').read_text(),16)!=selected:raise ValueError('unedited actual selected1000 snapshot required')
    original=parent.payload.parent;ack=bytearray(original.incoming.case(True,True)[-1]);frames=[]
    for index,(wire_psn,syn)in enumerate(([(0x987654,0)]if partial else[])+[(psn,syndrome)]):
        p=bytearray(ack);p[37:40]=wire_psn.to_bytes(3,'big');p[40]=syn;p[41:44]=bytes(3)
        frames.append((0x6001+index,bytes.fromhex('b8830367c5d08af3fbb975310800')+original.packet_tool.repair(p)))
    if original.rq.link.frames(output)!=frames:raise ValueError('independent every fatal/positive ACK byte/PSN/MSN/fresh tag/FCS/SFD/CDC')
    host=bytes(int(s,16)for s in(run/'large-write-receive-host.hex').read_text().splitlines())
    expected_host=bytearray(((i*37)^0x5a)&255 for i in range(16384))
    if partial:expected_host[4093:8189]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(4096))
    if host!=expected_host:raise ValueError('independent actual host payload/pad/sentinel/rejected-byte snapshot')
    r=posted[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little');rq=0
    for w,v in [(32,0),(64,get(0,8)),(64,1),(64,0x9123456700000001),(24,2),(16,17),(16,1),(16,4),(16,1),
        (32,0),(32,0),(64,0),(64,0),(64,0),(32,0),(20,3)]:rq=(rq<<w)|v
    if int((run/'write-fatal-rq-owner.hex').read_text(),16)!=rq:raise ValueError('genuine unconsumed full620 zero-RQ snapshot required')
    return dict(summary=summary,actual_native_fatal61_62=True,actual_HLS_abort=True,actual_native_selected_cancel=partial,
        full_control_owner480=f'{owner:0120x}',full_abort_owner960=f'{abort:0240x}',full_selected1000=f'{selected:0250x}',
        full_retained_RQ620=f'{rq:0155x}',retained_RQ_not_error_CQ_or_unpin=True,global_drain_or_STOP=False,
        actual_XGMII_frames=[dict(tag=tag,frame_hex=frame.hex())for tag,frame in frames],
        host_snapshot_sha256=hashlib.sha256(host).hexdigest(),every_host_payload_pad_sentinel_byte=True,
        physical_peer_or_live_Linux=False)
