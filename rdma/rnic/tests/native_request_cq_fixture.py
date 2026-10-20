# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated requester SEND/READ/WRITE -> native memory/MAC -> CQ.

One compiled testbench selects three real WQE/peer-wire stimuli at runtime.
Only physical PCIe/host/MAC pins and software MMIO are models. Withhold the
second physical MAC receipt; never force any producer proof or drain.
"""
import json
import native_send_fixture as send
import test_native_qp_tx_rtl as qp


def variant(base_case, opcode):
    if opcode == 3:
        tb, words, records, request = send.case(base_case)
    else:
        tb, words, records, request = base_case(opcode == 1)
    prefix = len(qp.main.sq.local.fixture.packet())
    positive_words = len(words)-prefix-4
    # Fixed array offsets allow the same executable to read all three peer
    # packets. Padding is NOT delivered to the RX interface.
    words = words[:-4] + [0]*(9-positive_words) + words[-4:]
    request = bytearray(request)
    request[1] = 2; request[8] = 100
    request[20:22] = (4791).to_bytes(2, 'big')
    request = qp.main.response.repair(request)
    return words, records, request


def case(base_case):
    m = qp.main
    tb, _, _, _ = base_case(False)
    tb = m.sq.once(tb, '.RETRY_ENABLE(1)', '.RETRY_ENABLE(1),.SEND_ENABLE(1),.RECV_ENABLE(1),'
        '.RNR_ENABLE(1),.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.REQUEST_CQ_ENABLE(1)')
    tb = m.sq.once(tb, 'if(sq_value!==3)$fatal(1,"new QP TX capability missing");',
        'if(sq_value!==255)$fatal(1,"actual requester CQ capability missing");')
    tb = tb.replace('m_work_opcode!==1', 'm_work_opcode!==runtime_native_opcode')
    tb = tb.replace("m_work_remote_address!==64'hf123456789abc001",
        "m_work_remote_address!==(runtime_native_opcode==3 ? 64'd0 : 64'hf123456789abc001)")
    first = len(m.sq.local.fixture.packet())
    tb = m.sq.once(tb, f'send_frame({first},9);',
        f'send_frame({first},runtime_native_opcode==2 ? 9 : 4);')
    tb = m.sq.once(tb, 'if(mac_cpl_rd<mac_cpl_wr && cycle>=mac_cpl_due[mac_cpl_rd%32])',
        "if(mac_cpl_rd<mac_cpl_wr && cycle>=mac_cpl_due[mac_cpl_rd%32] && "
        "(!hold_request_mac_cpl || mac_cpl_tags[mac_cpl_rd%32]!=16'h2002))")
    tb = m.sq.once(tb, r''' if(dut.cq_commit_valid || dut.cq_retire_valid || dut.cq_busy || dut.cq_fault)
  $fatal(1,"main invented a CQ event without genuine internal HLS drain");''', r'''
 if(dut.cq_commit_valid && (!dut.wire_lifetime.request_proved ||
    dut.cq_commit_context!==expected_request_owner || !dut.memory_drained))
  $fatal(1,"request CQ commit without exact producer/native proofs");
 if(dut.cq_retire_valid && (local_committed_count!=1 || dut.cq_retire_context!==expected_request_owner))
  $fatal(1,"request CQ retirement without actual commit");
 if(dut.cq_busy && !local_execution_guard[2])$fatal(1,"request CQ handoff lost owner guard");
 if(mac_tx_valid && tr && (mac_tx_user[16:1]&16'he000)==16'h2000)
  $display("NATIVE_REQUEST_MAC %032h %04h %0d %04h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user[16:1]);
 if(dut.h_request_done_valid && dut.h_request_done_ready)
  $display("NATIVE_REQUEST_CORE_PROOF {\"opcode\":%0d,\"PSN\":%0d,\"next_PSN\":%0d,\"full_owner_match\":%s}",
   runtime_native_opcode,dut.h_request_done_data[611:588],dut.h_request_done_data[635:612],
   dut.h_request_done_data[587:0]===expected_request_owner ? "true":"false");''')
    declarations = r'''
integer runtime_native_opcode=2,request_event_file,request_word;
reg hold_request_mac_cpl=1;
reg [587:0] expected_request_owner=0;
reg [655:0] held_request_proof=0;
initial begin
 if($test$plusargs("WRITE"))runtime_native_opcode=1;
 if($test$plusargs("SEND"))runtime_native_opcode=3;
end
'''
    tb = m.sq.once(tb, 'reg [144:0] stimulus', declarations+'\nreg [144:0] stimulus')
    start = tb.index('sq_deadline=cycle+5000;\nwhile(local_proof_flags!==7\'h3f)')
    end = tb.index('disable native_rnic_case;', start)+len('disable native_rnic_case;')
    body = r'''
sq_deadline=cycle+5000;
while(!dut.h_request_done_valid)begin
 if(cycle>sq_deadline)$fatal(1,"actual requester core receipt deadline flags%h nativefault%h",local_proof_flags,dut.native_fault_code);
 @(negedge clk);
end
expected_request_owner=dut.local_cq_context;held_request_proof=dut.h_request_done_data;
if(expected_request_owner[587:524]!==64'hf123456789abc001 || expected_request_owner[523:460]!==1 ||
 expected_request_owner[459:396]!==64'h9123456700000001 || expected_request_owner[395:372]!==2 ||
 expected_request_owner[371:356]!==17 || expected_request_owner[339:324]!==runtime_native_opcode ||
 expected_request_owner[323:308]!==1 || expected_request_owner[307:276]!==65 ||
 expected_request_owner[275:244]!==8 || expected_request_owner[243:180]!==64'hfedcba9876543210 ||
 expected_request_owner[179:116]!==64'h210 || expected_request_owner[51:20]!==0 ||
 expected_request_owner[115:52]!==(runtime_native_opcode==3 ? 64'd0 : 64'hf123456789abc001) ||
 expected_request_owner[19:0]!==3 || held_request_proof[587:0]!==expected_request_owner ||
 held_request_proof[611:588]!==24'h89abcd || held_request_proof[635:612]!==24'h89abce ||
 held_request_proof[643:636]!==(runtime_native_opcode==2 ? 8'h0c : runtime_native_opcode==1 ? 8'h0a : 8'h04) ||
 held_request_proof[655:644]!==0)$fatal(1,"actual full requester receipt identity");
// The producer receipt alone cannot complete: the second real MAC receipt
// is withheld at the physical interface for longer than the tail window.
repeat(1100)begin
 @(negedge clk);
 if(!dut.h_request_done_valid || dut.h_request_done_data!==held_request_proof ||
    dut.h_request_done_ready || dut.wire_lifetime.request_proved || m_cq_valid || dut.cq_busy ||
    local_committed_count || !dut.h_local_hls_active || local_execution_guard!==8'h04 ||
    dut.tx_receipt_count!=1 || dut.tx_mac_proof_count!=1)
  $fatal(1,"request owner/CQ escaped missing real MAC receipt");
end
hold_request_mac_cpl=0;sq_deadline=cycle+5000;sq_value=0;
while(!(sq_value&1))begin
 if(cycle>sq_deadline)$fatal(1,"request CQ publication deadline flags%h proof%0d ready%0d commit%0d retire%0d",local_proof_flags,dut.h_request_done_valid,dut.h_request_done_ready,dut.cq_commit_valid,dut.cq_retire_valid);
 read_reg(24'h40300c,sq_value);
end
if(sq_value!==3 || local_committed_count!=1 || dut.h_local_hls_active ||
 local_execution_guard!==8'h04 || fault || dut.ex_command_count!=1 ||
 dut.ex_memory_status_count!=1 || dut.ex_owner_count!=1 || sq_fetch_count!=1 || sq_result_count!=1 ||
 sq_submission_owner_count!=1 || sq_submission_hls_count!=1 ||
 dut.rx_accepted_count!=($test$plusargs("RNR") ? 2 : 1) || dut.tx_receipt_count!=2 ||
 dut.tx_mac_proof_count!=2 || dut.native_retry_count!=1 || dut.native_rnr_count!=($test$plusargs("RNR") ? 1 : 0))
 $fatal(1,"actual native requester CQ ownership handoff");
if(router_descriptor_count!==(runtime_native_opcode==2 ? 4 : 3) ||
 read_tlps!==(runtime_native_opcode==2 ? 2 : 3) || write_tlps!==(runtime_native_opcode==2 ? 2 : 0) ||
 fences!==(runtime_native_opcode==2 ? 1 : 0))$fatal(1,"request native DMA/READ fence coverage");
for(sq_i=0;sq_i<16384;sq_i=sq_i+1)begin
 if(pcie_posted_valid[sq_i])$fatal(1,"unfenced host byte");
 if(runtime_native_opcode==2 && sq_i>=4093 && sq_i<4158)begin
  if(pcie_host[sq_i]!==((((sq_i-4093)*179)^((sq_i-4093)>>7)^8'hd3)&255))$fatal(1,"request READ placement byte");
 end else if(pcie_host[sq_i]!==(((sq_i*37)^8'h5a)&255))$fatal(1,"request changed source/sentinel");
end
check_ring();request_event_file=$fopen("request-event.hex","w");
read_reg(24'h403018,sq_value);if(sq_value!==1)$fatal(1,"request CQ sequence");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h40301c,sq_value);if(sq_value!==15)$fatal(1,"request CQ actual proofs");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403028,sq_value);if(sq_value)$fatal(1,"request CQ status");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403020,sq_value);if(sq_value!==32'h89abcdef)$fatal(1,"request CQ cookie low");$fdisplay(request_event_file,"%08h",sq_value);
read_reg(24'h403024,sq_value);if(sq_value!==32'hfedcba98)$fatal(1,"request CQ cookie high");$fdisplay(request_event_file,"%08h",sq_value);
for(request_word=0;request_word<19;request_word=request_word+1)begin
 read_reg(24'h403040+request_word*4,sq_value);
 if(sq_value!==(({20'd0,expected_request_owner}>>(request_word*32))&32'hffffffff))$fatal(1,"request CQ full context word");
 $fdisplay(request_event_file,"%08h",sq_value);
end
read_reg(24'h403038,sq_value);if(sq_value)$fatal(1,"request CQ fabricated receive byte count");$fdisplay(request_event_file,"%08h",sq_value);$fclose(request_event_file);
repeat(17)@(negedge clk);
write_reg(24'h403010,1,15,0,1);read_reg(24'h403014,sq_value);
if(sq_value!==1 || dut.cq_busy || local_execution_guard || dut.h_local_hls_active || fault)
 $fatal(1,"request CQ host ACK did not release owner");
$display("NATIVE_RNIC_RESULT {\"pass_test\":true,\"opcode\":%0d,\"payload_bytes\":65,\"proof_flags\":0,\"descriptors\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"HLS_model\":false,\"CQ_committed\":true}",runtime_native_opcode,router_descriptor_count,read_tlps,write_tlps,fences);
$finish;disable native_rnic_case;
'''
    tb = tb[:start]+body+tb[end:]
    tb = tb.replace('if(fault && !expect_fault) $fatal(1,"unexpected fault %d",fc);',
        'if(fault && !expect_fault) $fatal(1,"request fault aggregate%h native%h ex%h rx%h up%h tx%h shared%h cq%h rq%h",'
        'fault_code,dut.native_fault_code,dut.ex_fault_code,dut.rx_fault_code,dut.up_fault_code,'
        'dut.tx_fault_code,dut.h_shared_hls_fault_code,dut.cq_fault_code,dut.rq_fault_code);')
    if 'force ' in tb:
        raise ValueError('request CQ fixture cannot force production signals')
    words, records, request = variant(base_case, 2)
    return tb, words, records, request


def verify(output, request, opcode):
    frames=[]; data=bytearray(); tags=[]
    for line in output.splitlines():
        if not line.startswith('NATIVE_REQUEST_MAC '):continue
        _,word,keep,last,tag=line.split(); mask=int(keep,16)
        if not mask or mask & (mask+1):raise ValueError('request MAC keep holes')
        if not data:tags.append(int(tag,16))
        elif int(tag,16)!=tags[-1]:raise ValueError('request MAC tag changed mid-frame')
        data.extend(int(word,16).to_bytes(16,'little')[:mask.bit_count()])
        if last=='1':frames.append(bytes(data));data=bytearray()
    expected=bytes.fromhex('b8830367c5d08af3fbb975310800')+request
    if data or frames!=[expected,expected] or tags!=[0x2001,0x2002]:
        raise ValueError('request actual wire/payload/ICRC/replay mismatch: '+str(dict(
            lengths=list(map(len,frames)),expected_length=len(expected),tags=tags,
            actual_first=frames[0].hex() if frames else None,expected=expected.hex())))
    proofs=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_REQUEST_CORE_PROOF ')]
    if proofs!=[dict(opcode=opcode,PSN=qp.PSN,next_PSN=qp.PSN+1,full_owner_match=True)]:
        raise ValueError('missing actual same-HLS requester receipt: '+str(proofs))
    return dict(actual_MAC_frames=2,byte_identical_replay=True,fresh_MAC_tags=tags,
        BTH_opcode=request[28],MAC_frame_bytes=len(expected),payload_bytes=65,
        full_wire_and_ICRC_match=True,actual_HLS_request_proofs=proofs)
