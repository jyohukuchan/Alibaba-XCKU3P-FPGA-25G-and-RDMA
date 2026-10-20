# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated-HLS native receive -> per-WR ACK -> CQ -> next receive.

Only physical host/PCIe/MAC and software register access are modeled. Never
force a drain, proof, MAC completion, producer result or CQ-valid high.
"""
import json
import native_receive_fixture as old


def case(wire_rnr=True, core_receipts=True):
    if not wire_rnr or not core_receipts:
        raise ValueError('receive CQ test requires matched RNR/receive-receipt HLS')
    m = old.qp.main
    tb, words, records, ack = old.case(True, True)
    tb = m.sq.once(tb, '.RECV_RETIRE_ENABLE(1)', '.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1)')
    first = len(m.sq.local.fixture.packet())
    # Same registered buffer, different genuine receive PSN/MSN and WQE seq.
    packet = bytearray(m.response.packet(write=False, mig=1, qpn=2, psn=0x987655))
    packet[28] = 4
    del packet[40:44]
    packet[40:105] = bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65))
    packet = m.response.repair(packet)
    frame = bytes.fromhex('8af3fbb97531b8830367c5d00800') + packet
    second = len(words)
    extra = [int.from_bytes(frame[i:i+16].ljust(16, b'\0'), 'little') |
        (((1 << min(16, len(frame)-i))-1) << 128) | ((i+16 >= len(frame)) << 144)
        for i in range(0, len(frame), 16)]
    tb = m.sq.once(tb, f'stimulus[0:{len(words)-1}]', f'stimulus[0:{len(words)+len(extra)-1}]')
    # The inherited host observer covered only the first coherent ring slot.
    # Keep every size/RAM/direction/fresh-tag check; bind the exact second
    # descriptor address to its already-programmed in-order producer slot.
    tb = m.sq.once(tb, "desc_address!==64'hfedcba9876543000)$fatal(1,\"actual coherent SQ descriptor/address/size/tag\");",
        "desc_address!==(64'hfedcba9876543000+(expected_recv_msn-1)*64))$fatal(1,\"actual coherent SQ descriptor/address/size/tag\");")
    start = tb.index("force dut.rq_core_ready=1'b0;")
    end = tb.index('disable native_rnic_case;', start) + len('disable native_rnic_case;')
    body = r'''
enable=1;read_reg(AS02_CTL_FEATURES,sq_value);if(sq_value!==127)$fatal(1,"actual receive CQ capability");
read_reg(24'h403008,sq_value);if(sq_value!==3)$fatal(1,"actual CQC message/byte-count ABI");
pcie_current_length=65;pcie_current_offset=64'h210;
if($test$plusargs("RNR"))begin
 receive_reject_ready=0;send_frame(FIRST,FRAME_WORDS);sq_deadline=cycle+5000;
 while(!dut.m_reject_valid)begin if(cycle>sq_deadline)$fatal(1,"CQ empty RQ rejection");@(negedge clk);end
 while(mac_response_cpls!=1 || !response_tx_quiescent)begin
  if(cycle>sq_deadline)$fatal(1,"actual RNR wire completion");@(negedge clk);
 end
 if(early_rnr_word!=4 || dut.rq_posted_count || dut.rq_taken_count || router_descriptor_count ||
    dut.accepted_count || dut.completed_count || m_cq_valid || fault)$fatal(1,"RNR consumed work/PSN");
 receive_reject_ready=1;@(posedge clk);@(negedge clk);
end
receive_once(1,FIRST,24'h987654);
receive_once(2,SECOND,24'h987655);
check_ring();
if(dut.rq_posted_count!=2 || dut.rq_taken_count!=2 || dut.rq_placement_count!=2 ||
   dut.rq_core_proof_count!=2 || dut.receive_ack_lifetime.ack_owner.frame_count!=2 ||
   dut.receive_ack_lifetime.ack_owner.receipt_count!=2 || dut.rq_active || dut.rq_queue_guard ||
   dut.h_local_hls_active || local_committed_count || local_proof_flags || fault)
 $fatal(1,"native receive CQ/next-owner lifecycle incomplete");
for(sq_i=0;sq_i<16384;sq_i=sq_i+1)begin
 if(pcie_posted_valid[sq_i])$fatal(1,"unfenced receive byte");
 if(sq_i>=4093 && sq_i<4158)begin
  if(pcie_host[sq_i]!==pcie_pattern(sq_i-4093))$fatal(1,"receive/reused payload mismatch");
 end else if(pcie_host[sq_i]!==(((sq_i*37)^8'h5a)&255))$fatal(1,"receive changed sentinel/buffer tail");
end
$display("NATIVE_RNIC_RESULT {\"pass_test\":true,\"operation\":\"RECV\",\"payload_bytes\":65,\"buffer_capacity\":128,\"proof_flags\":0,\"descriptors\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"HLS_model\":true,\"CQ_committed\":true,\"receive_CQ_events\":2,\"same_buffer_reused\":true}",router_descriptor_count,read_tlps,write_tlps,fences);
$finish;disable native_rnic_case;
'''.replace('FIRST', str(first)).replace('SECOND', str(second)).replace('FRAME_WORDS', str((len(frame)+15)//16))
    tb = tb[:start] + body + tb[end:]
    # The old fixture intentionally forbids CQ publication. Replace that
    # observer with exact actual per-WR joins, not a blanket assertion removal.
    tb = m.sq.once(tb, r''' if(dut.cq_commit_valid || dut.cq_retire_valid || dut.cq_busy || dut.cq_fault)
  $fatal(1,"main invented a CQ event without genuine internal HLS drain");''', r'''
 if(dut.cq_commit_valid && (!dut.rq_core_proved || !dut.receive_owners.owners.mac_proved ||
    dut.cq_commit_context!==expected_recv_owner || !dut.receive_ack_lifetime.ack_owner.proof_sent))
  $fatal(1,"CQ commit without exact core/MAC owner proofs");
 if(dut.cq_retire_valid && (!dut.receive_owners.owners.committed || dut.cq_retire_context!==expected_recv_owner))
  $fatal(1,"CQ retirement without actual receive commit");
 if(dut.cq_busy && !local_execution_guard[2])$fatal(1,"CQ handoff lost queue guard");''')
    tb = m.sq.once(tb, "assign tv=mac_tx_valid && mac_tx_user[16:1]==16'h4000;",
        "assign tv=mac_tx_valid && (mac_tx_user[16:1]==16'h4000 || mac_tx_user[16:14]==3'b011);")
    tb = m.sq.once(tb, "&& mac_tx_user[16:1]!=16'h4000)$fatal(1,\"wrong native TX class\");",
        "&& mac_tx_user[16:1]!=16'h4000 && mac_tx_user[16:14]!=3'b011)$fatal(1,\"wrong native TX class\");")
    tb = m.sq.once(tb, 'if(mac_cpl_rd<mac_cpl_wr && cycle>=mac_cpl_due[mac_cpl_rd%32])',
        "if(mac_cpl_rd<mac_cpl_wr && cycle>=mac_cpl_due[mac_cpl_rd%32] && (!hold_receive_mac_cpl || mac_cpl_tags[mac_cpl_rd%32][15:13]!=3'b011))")
    tb = m.sq.once(tb, "if(s_axis_mac_cpl_tag==16'h4000)mac_response_cpls=mac_response_cpls+1;",
        "if(s_axis_mac_cpl_tag==16'h4000 || s_axis_mac_cpl_tag[15:13]==3'b011)mac_response_cpls=mac_response_cpls+1;")
    tb = m.sq.once(tb, "if(mac_tx_valid && tr && mac_tx_user[16:1]==16'h4000)",
        "if(mac_tx_valid && tr && (mac_tx_user[16:1]==16'h4000 || mac_tx_user[16:14]==3'b011))")
    tb = tb.replace("dut.rq_core_data[643:620]!==24'h987654", 'dut.rq_core_data[643:620]!==expected_recv_psn')
    tb = tb.replace('dut.rq_core_data[671:648]!==1', 'dut.rq_core_data[671:648]!==expected_recv_msn')
    tasks = r'''
reg hold_receive_mac_cpl=1;
reg [587:0] expected_recv_owner=0;
reg [23:0] expected_recv_psn=24'h987654,expected_recv_msn=1;
integer receive_event_file,receive_word,receive_deadline;
task receive_once;
 input integer seq;input integer frame_start;input [23:0] psn;
 begin
  expected_recv_psn=psn;expected_recv_msn=seq;hold_receive_mac_cpl=1;
  sq_command(2,seq,0,0,0);receive_deadline=cycle+5000;
  while(dut.rq_posted_count!=seq)begin if(cycle>receive_deadline)$fatal(1,"receive WQE posting");@(negedge clk);end
  send_frame(frame_start,FRAME_WORDS);
  while(dut.rq_placement_count!=seq || dut.rq_core_proof_count!=seq ||
        dut.receive_ack_lifetime.ack_owner.frame_count!=seq)begin
   if(cycle>receive_deadline)$fatal(1,"actual receive/ACK/proof deadline state%0d core%0d place%0d rq%h ack%h",dut.receive_ack_lifetime.ack_owner.state,dut.rq_core_proof_count,dut.rq_placement_count,dut.rq_fault_code,dut.recv_ack_fault_code);
   @(negedge clk);
  end
  expected_recv_owner=dut.rq_held_context;
  if(expected_recv_owner[587:524]!==64'hf123456789abc000+seq || expected_recv_owner[523:460]!==seq ||
     expected_recv_owner[459:396]!==64'h9123456700000001 || expected_recv_owner[395:372]!==2 ||
     expected_recv_owner[371:356]!==17 || expected_recv_owner[339:324]!==4 ||
     expected_recv_owner[323:308]!==1 || expected_recv_owner[307:276]!==128 ||
     expected_recv_owner[275:244]!==8 || expected_recv_owner[243:180]!==64'hfedcba9876543210 ||
     expected_recv_owner[179:116]!==64'h210 || expected_recv_owner[115:20]!==0 || expected_recv_owner[19:0]!==3)
   $fatal(1,"genuine received full WQE identity/capacity");
  // Withhold only physical MAC receipt delivery, not any production proof.
  repeat(1100)begin
   @(negedge clk);
   if(m_cq_valid || dut.cq_busy || !dut.rq_active || dut.rq_queue_guard!==8'h04 ||
      dut.receive_ack_lifetime.ack_owner.receipt_count!=seq-1)
    $fatal(1,"receive CQ/owner released without actual ACK receipt");
  end
  hold_receive_mac_cpl=0;receive_deadline=cycle+2500;sq_value=0;
  while(!(sq_value&1))begin
   if(cycle>receive_deadline)$fatal(1,"native receive CQ deadline status%h rqactive%0d macstate%0d ticket%0d commit%0d retire%0d rqs%0d acks%0d hlss%0d mem%0d",sq_value,dut.rq_active,dut.receive_ack_lifetime.ack_owner.state,dut.rq_ticket_valid,dut.cq_commit_valid,dut.cq_retire_valid,dut.rq_retire_ready,dut.recv_ack_retire_ready,dut.recv_hls_retire_ready,dut.memory_drained);
   read_reg(24'h40300c,sq_value);
  end
  if(sq_value!==3 || dut.rq_active || dut.rq_queue_guard || dut.recv_ack_busy ||
     local_execution_guard!==8'h04 || dut.h_local_hls_active || fault)
   $fatal(1,"native CQ/RQ/HLS/ACK ownership handoff");
  receive_event_file=$fopen(seq==1 ? "receive-event1.hex":"receive-event2.hex","w");
  read_reg(24'h403018,sq_value);if(sq_value!==seq)$fatal(1,"native CQ sequence");$fdisplay(receive_event_file,"%08h",sq_value);
  read_reg(24'h40301c,sq_value);if(sq_value!==15)$fatal(1,"native CQ actual proofs");$fdisplay(receive_event_file,"%08h",sq_value);
  read_reg(24'h403028,sq_value);if(sq_value)$fatal(1,"native CQ status");$fdisplay(receive_event_file,"%08h",sq_value);
  read_reg(24'h403020,sq_value);if(sq_value!==32'h89abcdef)$fatal(1,"native CQ exact cookie low");$fdisplay(receive_event_file,"%08h",sq_value);
  read_reg(24'h403024,sq_value);if(sq_value!==32'hfedcba98)$fatal(1,"native CQ exact cookie high");$fdisplay(receive_event_file,"%08h",sq_value);
  for(receive_word=0;receive_word<19;receive_word=receive_word+1)begin
   read_reg(24'h403040+receive_word*4,sq_value);
   if(sq_value!==(({20'd0,expected_recv_owner}>>(receive_word*32))&32'hffffffff))$fatal(1,"native CQ full context word");
   $fdisplay(receive_event_file,"%08h",sq_value);
  end
  read_reg(24'h403038,sq_value);if(sq_value!==65)$fatal(1,"native actual bytes versus capacity");$fdisplay(receive_event_file,"%08h",sq_value);$fclose(receive_event_file);
  repeat(17)@(negedge clk);
  if(seq>1)begin
   write_reg(24'h403010,seq-1,15,0,1);read_reg(24'h40300c,sq_value);
   if(sq_value!==3)$fatal(1,"old ACK consumed next receive CQ");
  end
  write_reg(24'h403010,seq,15,0,1);read_reg(24'h403014,sq_value);
  if(sq_value!==seq || dut.cq_busy || local_execution_guard || dut.rq_active || fault)
   $fatal(1,"native CQ host ACK did not release completed owner");
  $display("NATIVE_RECV_CQ_EVENT {\"sequence\":%0d,\"capacity\":128,\"received_bytes\":65,\"owner_retired\":true,\"MAC_tag\":%0d}",seq,16'h6000+seq);
 end
endtask
'''.replace('FRAME_WORDS', str((len(frame)+15)//16))
    tb = m.sq.once(tb, 'reg [144:0] stimulus', tasks + '\nreg [144:0] stimulus')
    if 'force ' in tb:
        raise ValueError('native CQ test cannot force any production signal')
    return tb, words+extra, records, ack


def verify(output, ack, wire_rnr=False, empty=False):
    data = bytearray()
    frames = []
    tags = []
    for line in output.splitlines():
        if not line.startswith('NATIVE_RECV_MAC '):
            continue
        _, word, keep, last, tag = line.split()
        mask = int(keep, 16)
        if not mask or mask & (mask+1):
            raise ValueError('receive ACK keep holes')
        if not data:
            tags.append(int(tag, 16))
        elif int(tag, 16) != tags[-1]:
            raise ValueError('ACK tag changed mid-frame')
        data.extend(int(word, 16).to_bytes(16, 'little')[:mask.bit_count()])
        if last == '1':
            frames.append(bytes(data)); data = bytearray()
    expected = []
    if empty:
        rnr = bytearray(ack);rnr[40] = 0x20;rnr[41:44] = bytes(3)
        expected.append(bytes.fromhex('b8830367c5d08af3fbb975310800')+old.qp.main.response.repair(rnr))
    for seq in (1, 2):
        packet = bytearray(ack)
        packet[37:40] = (0x987653+seq).to_bytes(3, 'big')
        packet[41:44] = seq.to_bytes(3, 'big')
        expected.append(bytes.fromhex('b8830367c5d08af3fbb975310800')+old.qp.main.response.repair(packet))
    if data or frames != expected or tags != ([0x4000] if empty else [])+[0x6001, 0x6002]:
        raise ValueError('actual consecutive receive ACK/RNR frames, MSN, ICRC or tags differ')
    events = [json.loads(l.split(' ', 1)[1]) for l in output.splitlines() if l.startswith('NATIVE_RECV_CQ_EVENT ')]
    if len(events) != 2 or any(not e['owner_retired'] or e['received_bytes'] != 65 for e in events):
        raise ValueError('two exact native receive CQ events required')
    return dict(actual_ACK_MAC_frames=2, actual_RNR_MAC_frames=int(empty),
        full_IP_UDP_BTH_AETH_MSN_ICRC_match=True, distinct_ACK_tags=tags,
        buffer_capacity=128, received_bytes=65, CQ_published=True,
        receive_owner_reused=True, whole_core_drain=False, events=events)
