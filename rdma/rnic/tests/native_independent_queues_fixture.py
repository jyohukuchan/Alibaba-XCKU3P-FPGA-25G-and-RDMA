# SPDX-License-Identifier: BSD-2-Clause-Views
"""Separate coherent SQ/RQ: prepost receive, complete SEND, then receive.

Two pairs reuse the same registered buffer with independent WQE sequences
and distinct full queue cookies. Actual generated core/native RTL required;
only physical host/MAC and MMIO access are models. No production force.
"""
import json
import native_receive_cq_fixture as old


def encode_frame(frame):
    return [int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little') |
        (((1<<min(16,len(frame)-i))-1)<<128) | ((i+16>=len(frame))<<144)
        for i in range(0,len(frame),16)]


def case(base_case):
    m=old.old.qp.main
    tb,words,receive_records,ack=old.case(True,True)
    tb=m.sq.once(tb,'.RECV_CQ_ENABLE(1)',
        '.RECV_CQ_ENABLE(1),.REQUEST_CQ_ENABLE(1),.SEPARATE_RQ_ENABLE(1)')
    tb=m.sq.once(tb,'if(sq_value!==127)','if(sq_value!==511)')
    tb=tb.replace('[0:16511]','[0:16639]').replace('init_byte<16512','init_byte<16640')
    anchor=" if(address>=64'hfedcba9876543000"
    tb=m.sq.once(tb,anchor,
        " if(address>=64'hfedcba9876542000 && address<64'hfedcba9876542080)pcie_host_index=16512+address-64'hfedcba9876542000;\n"+anchor)
    anchor=' for(init_byte=0;init_byte<128;init_byte=init_byte+1)pcie_host[16384+init_byte]=sq_records[init_byte/64][(init_byte%64)*8+:8];'
    tb=m.sq.once(tb,anchor,anchor+'\n $readmemh("receive-records.hex",receive_records);\n'
        ' for(init_byte=0;init_byte<128;init_byte=init_byte+1)pcie_host[16512+init_byte]=receive_records[init_byte/64][(init_byte%64)*8+:8];')
    tb=m.sq.once(tb,"(64'hfedcba9876543000+(expected_recv_msn-1)*64)",
        "((dut.native.fetch_result_receive ? 64'hfedcba9876542000:64'hfedcba9876543000)+(expected_recv_msn-1)*64)")
    tb=m.sq.once(tb,'sq_command(1,0,0,7,0);','sq_command(1,0,0,7,0);rq_command(1,0);')
    # The actual owner's RRP policy is programmed through the existing real
    # SQC lookup/MMIO path, not injected into the retry or HLS state.
    policy_tb=base_case(True)[0]
    p=policy_tb.index('// Program through the ACTUAL main AXI decoder')
    policy=policy_tb[p:policy_tb.index('enable=1;sq_command(2,1,0,0,0);',p)]
    tb=m.sq.once(tb,'enable=1;read_reg(AS02_CTL_FEATURES',policy+'\nenable=1;read_reg(AS02_CTL_FEATURES')
    # Keep inherited original positive/RNR wire models; append two genuine
    # peer ACKs for independent local TX PSNs fffffe/ffffff.
    ack_start=len(words)
    for seq in (1,2):
        reply=bytearray(m.response.packet(write=True,mig=1,qpn=2,psn=0xfffffd+seq))
        reply[41:44]=seq.to_bytes(3,'big');reply=m.response.repair(reply)
        words+=encode_frame(bytes.fromhex('8af3fbb97531b8830367c5d00800')+reply)
    tb=m.sq.once(tb,f'stimulus[0:{ack_start-1}]',f'stimulus[0:{len(words)-1}]')
    a=tb.index('task receive_once;');b=tb.index('endtask',a)+len('endtask')
    tb=tb[:a]+TASKS.replace('ACK_START',str(ack_start))+tb[b:]
    # The inherited RECV-only test has never sent anything, hence flags0.
    # The actual sender deliberately RETAINS its last completed proof bits
    # until the next owner (wqe_lifetime.v). They are history, not busy or a
    # drain witness. Require all seven bits AND actual inactive TX guards.
    tb=m.sq.once(tb,'local_committed_count || local_proof_flags || fault)',
        "local_committed_count!=2 || local_proof_flags!==7'h7f || dut.tx_busy || dut.tx_queue_guard || fault)")
    tb=m.sq.once(tb,'check_ring();\nif(dut.rq_posted_count',
        'check_ring();rq_command(3,2);sq_command(3,2,0,31,2);\nif(dut.rq_posted_count')
    tb=m.sq.once(tb,r'\"receive_CQ_events\":2,\"same_buffer_reused\":true',
        r'\"receive_CQ_events\":2,\"send_CQ_events\":2,\"independent_physical_queues\":true,\"same_buffer_reused\":true')
    tb=m.sq.once(tb,r'\"proof_flags\":0',r'\"proof_flags\":%0d')
    tb=m.sq.once(tb,'",router_descriptor_count,read_tlps,write_tlps,fences);',
        '",local_proof_flags,router_descriptor_count,read_tlps,write_tlps,fences);')
    # Both actual commit families retain their own exact operation proofs.
    a=tb.index(' if(dut.cq_commit_valid && (!dut.rq_core_proved');b=tb.index(' if(dut.cq_busy',a)
    tb=tb[:a]+r'''
 if(dut.cq_commit_valid && (dut.cq_commit_context[339:324]==4 ?
    (!dut.rq_core_proved || !dut.receive_owners.owners.mac_proved ||
     dut.cq_commit_context!==expected_recv_owner || !dut.receive_ack_lifetime.ack_owner.proof_sent) :
    (!dut.wire_lifetime.request_proved || dut.cq_commit_context!==expected_send_owner || !dut.memory_drained)))
  $fatal(1,"independent CQ commit without exact direction/core/MAC/memory proofs");
 if(dut.cq_retire_valid && (dut.cq_retire_context[339:324]==4 ?
    (!dut.receive_owners.owners.committed || dut.cq_retire_context!==expected_recv_owner) :
    (local_committed_count!=expected_send_seq || dut.cq_retire_context!==expected_send_owner)))
  $fatal(1,"independent CQ retirement without exact committed owner");
 if(mac_tx_valid && tr && (mac_tx_user[16:1]&16'he000)==16'h2000)
  $display("NATIVE_SPLIT_SEND_MAC %032h %04h %0d %04h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user[16:1]);
 if(dut.h_request_done_valid && dut.h_request_done_ready &&
   (dut.h_request_done_data[587:0]!==expected_send_owner ||
    dut.h_request_done_data[611:588]!==expected_send_psn ||
    dut.h_request_done_data[635:612]!==(expected_send_psn+24'd1) ||
    dut.h_request_done_data[643:636]!==4 || dut.h_request_done_data[655:644]!==0))
  $fatal(1,"actual requester receipt lost independent SQ generation");
''' + tb[b:]
    tb=tb.replace('dut.ex_m_memory_command_tag!==1',
        'dut.ex_m_memory_command_tag!==dut.local_cq_context[355:340]')
    tb=tb.replace('if(fault && !expect_fault) $fatal(1,"unexpected fault %d",fc);',
        'if(fault && !expect_fault) $fatal(1,"split fault aggregate%h native%h ex%h tx%h shared%h rq%h",'
        'fault_code,dut.native_fault_code,dut.ex_fault_code,dut.tx_fault_code,dut.h_shared_hls_fault_code,dut.rq_fault_code);')
    tb=m.sq.once(tb,'if(fault)$fatal(1,"main native RNIC fault %h",fault_code);',
        'if(fault)$fatal(1,"split fault aggregate%h native%h ex%h tx%h shared%h rq%h ack%h",'
        'fault_code,dut.native_fault_code,dut.ex_fault_code,dut.tx_fault_code,dut.h_shared_hls_fault_code,dut.rq_fault_code,dut.recv_ack_fault_code);')
    declarations=r'''
reg [511:0] receive_records[0:1];
reg [587:0] expected_send_owner=0;
reg [23:0] expected_send_psn=24'hfffffe;
integer expected_send_seq=0,receive_control_sequence=0,split_word,split_file,split_deadline;
reg [31:0] receive_words[0:14];
'''
    tb=m.sq.once(tb,'reg [144:0] stimulus',declarations+'\nreg [144:0] stimulus')
    # Retain and check BOTH separate physical coherent buffers byte for byte.
    tb=m.sq.once(tb,'task check_ring;\n begin',r'''
task check_ring;
 begin
  for(sq_i=0;sq_i<128;sq_i=sq_i+1)
   if(pcie_host[16512+sq_i]!==receive_records[sq_i/64][(sq_i%64)*8+:8] || pcie_posted_valid[16512+sq_i])
    $fatal(1,"independent coherent RQ bytes modified");''')
    records=[]
    for seq in (1,2):
        w=m.shared.codec.candidate(wr_id=0xf223456789abc000+seq,sequence=seq,epoch=0x9123456700000001,
            local_address=0xfedcba9876543210,local_key=8,remote_address=0,remote_key=0,
            opcode=3,flags=1,length=65)
        records.append(m.shared.codec.oracle(w))
    if 'force ' in tb:raise ValueError('independent native queues cannot force production signals')
    return tb,words,records,receive_records,ack


TASKS=r'''
task rq_command;
 input [1:0] op;input [63:0] producer;
 begin
  read_reg(24'h405000,sq_value);if(sq_value!==32'h52514331)$fatal(1,"actual distinct RQC1 window");
  read_reg(24'h40500c,sq_value);if(sq_value!==1)$fatal(1,"RQC1 not independently ready");
  for(split_word=0;split_word<15;split_word=split_word+1)receive_words[split_word]=0;
  receive_control_sequence=receive_control_sequence+1;
  receive_words[0]=receive_control_sequence;receive_words[1]=op;receive_words[2]=2;receive_words[3]=17;
  receive_words[4]=1;receive_words[5]=32'h91234567;
  receive_words[6]=32'h89abcdf0;receive_words[7]=32'hfedcba98;
  receive_words[8]=32'h76542000;receive_words[9]=32'hfedcba98;receive_words[10]=1;
  receive_words[11]=producer;receive_words[12]=producer>>32;
  if(op==3)begin receive_words[13]=receive_control_sequence;receive_words[14]=32'ha1234567;end
  for(split_word=0;split_word<15;split_word=split_word+1)
   write_reg(24'h405040+split_word*4,receive_words[split_word],15,0,1);
  write_reg(24'h405010,receive_control_sequence,15,0,1);split_deadline=cycle+4000;sq_value=0;
  while(!(sq_value&2))begin
   if(cycle>split_deadline)$fatal(1,"actual independent RQC1 reply deadline");
   read_reg(24'h40500c,sq_value);if(sq_value&60)$fatal(1,"actual RQC1 transport fault");
  end
  for(split_word=0;split_word<15;split_word=split_word+1)begin
   read_reg(24'h405100+split_word*4,sq_value);
   if(sq_value!==receive_words[split_word])$fatal(1,"actual RQC1 full owner/layout/nonce");
  end
  read_reg(24'h40513c,sq_value);if(sq_value)$fatal(1,"actual RQC1 semantic error%0d",sq_value);
  read_reg(24'h405140,sq_value);if(sq_value!==(op==1 ? 7:op==3 ? 31:0))$fatal(1,"actual RQC1 proof flags");
  if(op!=2)begin
   read_reg(24'h405144,sq_value);if(sq_value!==(op==1 ? 0:producer))$fatal(1,"actual RQC1 consumer");
   read_reg(24'h405148,sq_value);if(sq_value)$fatal(1,"actual RQC1 consumer high");
  end
  write_reg(24'h405014,receive_control_sequence,15,0,1);
  read_reg(24'h40500c,sq_value);if(sq_value!==1)$fatal(1,"RQC1 exact reply ACK");
 end
endtask

task split_cq;
 input integer event_sequence;input [587:0] owner;input integer received_bytes;
 reg [63:0] cookie;
 begin
  cookie=owner[339:324]==4 ? 64'hfedcba9889abcdf0:64'hfedcba9889abcdef;
  split_deadline=cycle+5000;sq_value=0;
  while(!(sq_value&1))begin
   if(cycle>split_deadline)$fatal(1,"independent CQ deadline event%0d local%h RQ%0d shared%h SQ%h",event_sequence,local_proof_flags,dut.rq_active,dut.h_shared_hls_fault_code,dut.native_fault_code);
   read_reg(24'h40300c,sq_value);
  end
  if(sq_value!==3 || dut.h_local_hls_active || dut.rq_active || fault)
   $fatal(1,"independent CQ did not retire actual core operation");
  case(event_sequence)
   1:split_file=$fopen("send-event1.hex","w");
   2:split_file=$fopen("receive-event1.hex","w");
   3:split_file=$fopen("send-event2.hex","w");
   4:split_file=$fopen("receive-event2.hex","w");
   default:$fatal(1,"unexpected split CQ event");
  endcase
  if(!split_file)$fatal(1,"native CQ snapshot file");
  read_reg(24'h403018,sq_value);if(sq_value!==event_sequence)$fatal(1,"independent global CQ sequence");$fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h40301c,sq_value);if(sq_value!==15)$fatal(1,"independent actual CQ proofs");$fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h403028,sq_value);if(sq_value)$fatal(1,"independent CQ status");$fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h403020,sq_value);if(sq_value!==cookie[31:0])$fatal(1,"independent direction-specific cookie low");$fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h403024,sq_value);if(sq_value!==cookie[63:32])$fatal(1,"independent full queue cookie high");$fdisplay(split_file,"%08h",sq_value);
  for(split_word=0;split_word<19;split_word=split_word+1)begin
   read_reg(24'h403040+split_word*4,sq_value);
   if(sq_value!==(({20'd0,owner}>>(split_word*32))&32'hffffffff))$fatal(1,"independent CQ complete context word");
   $fdisplay(split_file,"%08h",sq_value);
  end
  read_reg(24'h403038,sq_value);if(sq_value!==received_bytes)$fatal(1,"independent CQ actual byte count");$fdisplay(split_file,"%08h",sq_value);$fclose(split_file);
  if(event_sequence>1)begin
   write_reg(24'h403010,event_sequence-1,15,0,1);read_reg(24'h40300c,sq_value);
   if(sq_value!==3)$fatal(1,"previous direction ACK consumed successor CQ");
  end
  write_reg(24'h403010,event_sequence,15,0,1);read_reg(24'h403014,sq_value);
  if(sq_value!==event_sequence || dut.cq_busy || fault)$fatal(1,"independent exact host CQ ACK");
  $display("NATIVE_SPLIT_CQ_EVENT {\"event_sequence\":%0d,\"WQE_sequence\":%0d,\"opcode\":%0d,\"received_bytes\":%0d}",event_sequence,owner[523:460],owner[339:324],received_bytes);
 end
endtask

task receive_once;
 input integer seq;input integer frame_start;input [23:0] psn;
 begin
  expected_recv_msn=seq;expected_recv_psn=psn;expected_send_seq=seq;
  expected_send_psn=24'hfffffd+seq;hold_receive_mac_cpl=1;
  rq_command(2,seq);split_deadline=cycle+5000;
  while(dut.rq_posted_count!=seq)begin
   if(cycle>split_deadline)$fatal(1,"separate physical RQ fetch/admission deadline");@(negedge clk);
  end
  if(dut.rq_taken_count!=seq-1 || dut.rq_active || dut.h_local_hls_active || dut.rq_queue_guard!==8'h04 ||
     dut.native.sq.fetch.producer_table[2]!==seq-1 || dut.native.sq.fetch.producer_table[10]!==seq)
   $fatal(1,"preposted RQ did not retain independent physical producer");
  sq_command(2,seq,0,0,0);split_deadline=cycle+5000;
  while(!dut.tx_response_admission_ready || dut.tx_frame_count!=seq)begin
   if(cycle>split_deadline)$fatal(1,"preposted RQ blocked independent SEND flags%h shared%h SQ%h",local_proof_flags,dut.h_shared_hls_fault_code,dut.native_fault_code);
   @(negedge clk);
  end
  expected_send_owner=dut.local_cq_context;
  if(expected_send_owner[587:524]!==64'hf223456789abc000+seq || expected_send_owner[523:460]!==seq ||
     expected_send_owner[459:396]!==64'h9123456700000001 || expected_send_owner[395:372]!==2 ||
     expected_send_owner[371:356]!==17 || expected_send_owner[355:340]!==2*seq ||
     expected_send_owner[339:324]!==3 || expected_send_owner[323:308]!==1 || expected_send_owner[307:276]!==65 ||
     expected_send_owner[275:244]!==8 || expected_send_owner[243:180]!==64'hfedcba9876543210 ||
     expected_send_owner[179:116]!==64'h210 || expected_send_owner[115:20]!==0 || expected_send_owner[19:0]!==3)
   $fatal(1,"independent SEND full native owner");
  send_frame(ACK_START+(seq-1)*4,4);split_cq(2*seq-1,expected_send_owner,0);
  if(dut.rq_taken_count!=seq-1 || dut.rq_active || dut.rq_queue_guard!==8'h04 ||
     local_committed_count!=seq || dut.tx_receipt_count!=seq || dut.tx_mac_proof_count!=seq ||
     dut.native_retry_count || dut.h_local_hls_active || dut.ex_busy)
   $fatal(1,"SEND completion consumed/released preposted receive");
  send_frame(frame_start,8);split_deadline=cycle+6000;
  while(dut.rq_placement_count!=seq || dut.rq_core_proof_count!=seq ||
        dut.receive_ack_lifetime.ack_owner.frame_count!=seq)begin
   if(cycle>split_deadline)$fatal(1,"independent actual RECV placement/core/ACK deadline rq%h shared%h",dut.rq_fault_code,dut.h_shared_hls_fault_code);
   @(negedge clk);
  end
  expected_recv_owner=dut.rq_held_context;
  if(expected_recv_owner[587:524]!==64'hf123456789abc000+seq || expected_recv_owner[523:460]!==seq ||
     expected_recv_owner[459:396]!==64'h9123456700000001 || expected_recv_owner[395:372]!==2 ||
     expected_recv_owner[371:356]!==17 || expected_recv_owner[355:340]!==2*seq-1 ||
     expected_recv_owner[339:324]!==4 || expected_recv_owner[323:308]!==1 || expected_recv_owner[307:276]!==128 ||
     expected_recv_owner[275:244]!==8 || expected_recv_owner[243:180]!==64'hfedcba9876543210 ||
     expected_recv_owner[179:116]!==64'h210 || expected_recv_owner[115:20]!==0 || expected_recv_owner[19:0]!==3)
   $fatal(1,"independent RECV full native owner");
  repeat(1100)begin
   @(negedge clk);if(m_cq_valid || dut.cq_busy || !dut.rq_active ||
      dut.receive_ack_lifetime.ack_owner.receipt_count!=seq-1)
    $fatal(1,"independent receive released without actual ACK MAC receipt");
  end
  hold_receive_mac_cpl=0;split_cq(2*seq,expected_recv_owner,65);
  if(dut.rq_active || dut.rq_queue_guard || local_execution_guard || dut.h_local_hls_active || fault)
   $fatal(1,"independent SQ/RQ lifecycle not reusable");
  $display("NATIVE_RECV_CQ_EVENT {\"sequence\":%0d,\"capacity\":128,\"received_bytes\":65,\"owner_retired\":true,\"MAC_tag\":%0d}",seq,16'h6000+seq);
 end
endtask
'''


def verify(output,ack,empty=False):
    receive=old.verify(output,ack,True,empty)
    m=old.old.qp.main
    actual=[];data=bytearray();tags=[]
    for line in output.splitlines():
        if not line.startswith('NATIVE_SPLIT_SEND_MAC '):continue
        _,word,keep,last,tag=line.split();mask=int(keep,16)
        if not mask or mask&(mask+1):raise ValueError('split SEND MAC keep holes')
        if not data:tags.append(int(tag,16))
        elif tags[-1]!=int(tag,16):raise ValueError('split SEND MAC tag changed mid-frame')
        data.extend(int(word,16).to_bytes(16,'little')[:mask.bit_count()])
        if last=='1':actual.append(bytes(data));data=bytearray()
    expected=[]
    for seq in (1,2):
        p=bytearray(m.request(True));p[28]=4;del p[40:56]
        p[1]=2;p[8]=100;p[20:22]=(4791).to_bytes(2,'big');p[37:40]=(0xfffffd+seq).to_bytes(3,'big')
        if seq==2:p[40:105]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65))
        expected.append(bytes.fromhex('b8830367c5d08af3fbb975310800')+m.response.repair(p))
    if data or actual!=expected or tags!=[0x2001,0x2002]:
        raise ValueError('independent SEND full wire/changed received buffer/PSN/tags mismatch')
    events=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_SPLIT_CQ_EVENT ')]
    if [(e['event_sequence'],e['WQE_sequence'],e['opcode'])for e in events]!=[(1,1,3),(2,1,4),(3,2,3),(4,2,4)]:
        raise ValueError('CQ did not demonstrate independent send/receive sequences and completion order')
    return dict(actual_receive=receive,actual_SEND_MAC_frames=2,SEND_tags=tags,
        second_SEND_sources_actual_received_buffer=True,full_SEND_wire_and_ICRC_match=True,
        independent_physical_SQ_RQ=True,distinct_queue_cookies=True,events=events)
