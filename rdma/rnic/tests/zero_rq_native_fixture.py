# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual coherent RQ128/zero RX/HLS/ACK/MAC/CQ in the full native graph.

Keep all previous requester/Atomic cases. Physical host/root/peer/PHY/PTP
remain models. RX uses real posted owners, never force or generated proof.
Only the actual MAC timestamp/CDC receipt may close the ACK lifetime.
"""
import ctypes as C
import hashlib
import json
import struct
import zero_native_fixture as old
import native_independent_queues_fixture as split
import native_receive_fixture as incoming

ROOT=old.ROOT;once=old.once;link=old.link;fixtures=old.fixtures
GUARD='dut.native.network.datapath.responder.endpoint.shared_hls.guard'


def variant(op=3,capacity=0):
    if op not in [3,5,6] or capacity not in [0,128]:raise ValueError('zero RQ profile')
    records=[];cls=old.codec.ZeroWQETests;cls.setUpClass()
    try:
        for seq in [1,2]:
            w=cls.zero(4);w.base.wr_id=0xf123456789abc000+seq;w.base.sequence=seq
            w.base.epoch=0x9123456700000001;w.base.length=capacity
            w.base.local_address=0xfedcba9876543210 if capacity else 0;w.base.local_key=8 if capacity else 0
            encoded=(C.c_uint8*128)()
            if cls.lib.as02_zero_wqe_encode(encoded,C.byref(w)) or bytes(encoded)!=old.codec.old.oracle(w):
                raise ValueError('actual C128 RQ codec/independent bytes')
            records.append(bytes(encoded))
    finally:cls.tearDownClass()
    packets=[];words=[]
    for seq in [1,2]:
        # Independent complete IPv4/UDP/BTH template; remove its AETH and
        # rebuild only the requested RQ operation, recomputing all integrity.
        p=bytearray(old.old.old.response.old.packet(write=True,length=1,mig=1,qpn=2,psn=0x987653+seq)[:40])
        p[28]={3:4,5:5,6:11}[op];p[29]&=~0x30
        if op==6:p+=struct.pack('!QII',(1<<64)-1,0xfedcba98,0)
        if op in [5,6]:p+=struct.pack('!I',0x89abcdef)
        p=old.old.old.response.old.repair(p+bytes(4))
        frame=(bytes.fromhex('8af3fbb97531b8830367c5d00800')+p).ljust(60,bytes(1))
        packets.append(frame);encoded=split.encode_frame(frame)
        if len(encoded)>5:raise ValueError('zero RX slot overflow')
        words+=encoded+[0]*(5-len(encoded))
    return words,records,packets


def bench():
    t=old.bench()
    t=once(t,'reg runtime_zero=0;',DECLARATIONS+'\nreg runtime_zero=0;')
    t=once(t,"wire allow_actual_receipt=!(requester_wire_mode && hold_request_mac_cpl && link_m_cpl_tag==16'h2002);",
        "wire allow_actual_receipt=!(requester_wire_mode && hold_request_mac_cpl && link_m_cpl_tag==16'h2002) &&\n"
        " !(runtime_rq && hold_rq_mac && link_m_cpl_tag[15:13]==3'b011);")
    t=t.replace('[0:16639]','[0:16895]').replace('init_byte<16640','init_byte<16896')
    t=once(t," if(address>=64'hfedcba9876543000", 
        " if(address>=64'hfedcba9876542000 && address<64'hfedcba9876542100)pcie_host_index=16640+address-64'hfedcba9876542000;\n"
        " if(address>=64'hfedcba9876543000")
    init=' for(init_byte=0;init_byte<256;init_byte=init_byte+1)pcie_host[16384+init_byte]=sq_records[init_byte/128][(init_byte%128)*8+:8];'
    t=once(t,init,init+'''
 if($test$plusargs("RQ"))begin
  $readmemh("receive-records.hex",rq_records);$readmemh("receive-input.hex",rq_stimulus);
  for(init_byte=0;init_byte<256;init_byte=init_byte+1)pcie_host[16640+init_byte]=rq_records[init_byte/128][(init_byte%128)*8+:8];
 end
''')
    t=once(t,"desc_address!==64'hfedcba9876543000)",
        "desc_address!==(runtime_rq ? 64'hfedcba9876542000+rq_dma_seen*128:64'hfedcba9876543000))")
    t=once(t,'  end else begin\n  if(desc_tag!=pcie_last_tag+1',
        '   if(runtime_rq)rq_dma_seen=rq_dma_seen+1;\n  end else begin\n  if(desc_tag!=pcie_last_tag+1')
    # Both directions keep exact, independent proof assertions. Do not
    # disable the global protocol/PCIe/MAC fault or backpressure monitors.
    t=once(t,'if(dut.cq_commit_valid && (!dut.wire_lifetime.request_proved ||',
        'if(!runtime_rq && dut.cq_commit_valid && (!dut.wire_lifetime.request_proved ||')
    t=once(t,'if(dut.cq_retire_valid && (local_committed_count!=1 ||',
        'if(!runtime_rq && dut.cq_retire_valid && (local_committed_count!=1 ||')
    t=once(t,'enable=1;\nif(!$test$plusargs("ATOMIC_ONLY"))begin',
        'enable=1;\nif(runtime_rq)begin\n'
        ' if(mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)$fatal(1,"RQ actual MAC switch not drained");\n'
        ' requester_wire_mode=1;run_zero_rq();$finish;disable native_rnic_case;\nend\n'
        'if(!$test$plusargs("ATOMIC_ONLY"))begin')
    control=split.TASKS[:split.TASKS.index('\ntask split_cq;')]
    t=once(t,'task send_frame;',control+'\n'+TASKS.replace('GUARD.',GUARD+'.')+'\ntask send_frame;')
    t=once(t,'reg qp_model_allow=1;',MONITOR.replace('GUARD.',GUARD+'.')+'\nreg qp_model_allow=1;')
    if 'force 'in t:raise ValueError('no production force')
    return t


def verify(output,records,op,capacity,rnr,run):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ZERO_RQ_NATIVE_RESULT ')]
    expected=dict(pass_test=True,receives=2,capacity=capacity,operation=op,
        local_MR_queries=2 if capacity else 0,posted_RQ_MR_queries=2 if capacity else 0,
        total_MR_table_queries=2 if capacity else 0,remote_MR_queries=0,data_commands=0,
        read_TLPs=2,write_TLPs=0,fences=0,host_bytes_unchanged=True,RNR=int(rnr),actual_MAC_receipt_model=False)
    if rows!=[expected]:raise ValueError('whole-native zero RX summary/actual no-data counts')
    receipts=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ZERO_RQ_NATIVE_RECEIPT ')]
    flags=0 if op==3 else 1 if op==5 else 3;imm=0 if op==3 else 0x89abcdef
    wanted=[dict(sequence=seq,capacity=capacity,operation=op,PSN=0x987653+seq,
        notification=imm,flags=flags,actual_HLS_MAC_CQ=True)for seq in [1,2]]
    if receipts!=wanted:raise ValueError('actual zero RX owner/PSN/notification receipts')
    template=incoming.case(True,True)[-1];frames=[]
    for seq in [1,2]:
        p=bytearray(template);p[37:40]=(0x987653+seq).to_bytes(3,'big');p[41:44]=seq.to_bytes(3,'big')
        frames.append((0x6000+seq,bytes.fromhex('b8830367c5d08af3fbb975310800')+incoming.qp.main.response.repair(p)))
    if rnr:
        p=bytearray(template);p[40]=0x20;p[41:44]=bytes(3)
        frames.insert(0,(0x4000,bytes.fromhex('b8830367c5d08af3fbb975310800')+incoming.qp.main.response.repair(p)))
    if link.frames(output)!=frames:raise ValueError('actual XGMII/FCS/SFD/CDC ACK/RNR full-frame mismatch')
    owners=[];snapshots={}
    for seq,r in enumerate(records,1):
        get=lambda n,w:int.from_bytes(r[n:n+w],'little')
        values=[(64,get(0,8)),(64,get(8,8)),(64,get(56,8)),(24,2),(16,17),(16,seq),
            (16,4),(16,1),(32,capacity),(32,get(36,4)),(64,get(16,8)),(64,0x210 if capacity else 0),
            (64,0),(32,0),(20,3)]
        owner=0
        for width,n in values:owner=(owner<<width)|n
        expected=[seq,15,0,0x89abcdf0,0xfedcba98]+[(owner>>(32*i))&0xffffffff for i in range(20)]+[0,flags,imm,15]+[0]*4
        p=run/f'zero-rq-event{seq}.hex';actual=[int(l,16)for l in p.read_text().splitlines()]
        if actual!=expected:raise ValueError('independent whole620-bit RX/CQ/cookie/notification snapshot')
        snapshots[p.name]=hashlib.sha256(p.read_bytes()).hexdigest();owners.append(f'{owner:0155x}')
    return dict(summary=rows[0],receipts=receipts,full620_CQ_owners=owners,CQ_snapshot_sha256=snapshots,
        actual_XGMII_frames=[dict(tag=tag,frame_hex=f.hex())for tag,f in frames],
        actual_C128_RQ_codec=True,actual_coherent_RQ_fetch=True,actual_HLS_EOF_PSN_ACK_MAC_CQ=True,
        standard_Linux_or_physical_hardware=False)


DECLARATIONS=r'''
reg runtime_rq=0,hold_rq_mac=1;
integer rq_op=3,rq_dma_seen=0,rq_local_queries=0,rq_remote_queries=0,rq_table_queries=0,rq_post_queries=0;
integer rq_capacity=0,rq_seq=0,rq_deadline,rq_word,rq_fp,rq_event_sequence=0;
integer receive_control_sequence=0,split_word,split_deadline;
reg [31:0] receive_words[0:14];
reg [1023:0] rq_records[0:1];reg [144:0] rq_stimulus[0:9];
reg [619:0] expected_rq_owner=0;
reg [751:0] expected_rq_core=0;
reg [23:0] expected_rq_psn=0;
wire [31:0] rq_notification=rq_op==3 ? 0:32'h89abcdef;
wire [7:0] rq_notification_flags=rq_op==3 ? 0:rq_op==5 ? 1:3;
initial begin
 runtime_rq=$test$plusargs("RQ");
 if($value$plusargs("RQ_OP=%d",rq_op))begin end
 if($test$plusargs("RQ_BUFFER"))rq_capacity=128;
end
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_rq)begin
 if(dut.native.s_local_mr_request_valid && dut.native.s_local_mr_request_ready)rq_local_queries=rq_local_queries+1;
 // The table output multiplexes LOCAL posted-buffer authorization and RX
 // data queries. Count the actual independent clients, not the merged bus
 // as though every request came from the wire. Preserve exact totals too.
 if(GUARD.table_request_valid && GUARD.table_request_ready)rq_table_queries=rq_table_queries+1;
 if(GUARD.state==GUARD.LOOKUP && !GUARD.fault && GUARD.mr_request_ready)rq_remote_queries=rq_remote_queries+1;
 if(dut.native.rq_mr_request_valid && dut.native.rq_mr_request_ready)begin
  if(rq_capacity!=128 || dut.native.rq_mr_request_pd!==17 || dut.native.rq_mr_request_key!==8 ||
     dut.native.rq_mr_request_address!==64'hfedcba9876543210 || dut.native.rq_mr_request_length!==128 ||
     dut.native.rq_mr_request_operation!==1)$fatal(1,"actual posted-buffer local MR authority");
  rq_post_queries=rq_post_queries+1;
 end
 if(dut.native.network.datapath.responder.endpoint.backend_command_valid ||
    dut.ex_m_memory_command_valid || dut.ex_s_memory_status_valid ||
    GUARD.m_memory_command_valid || GUARD.s_memory_status_valid ||
    GUARD.m_axis_memory_write_tvalid || GUARD.s_axis_memory_read_tvalid ||
    dut.owner_take || dut.m_work_handoff || dut.h_request_done_valid)
  $fatal(1,"zero RX invented data/SQ/status authority");
 if(dut.rq_post_valid && dut.rq_post_ready)begin
  if(dut.rq_post_context[587:524]!==64'hf123456789abc000+dut.rq_post_context[523:460] ||
   dut.rq_post_context[459:396]!==64'h9123456700000001 || dut.rq_post_context[395:372]!==2 ||
   dut.rq_post_context[371:356]!==17 || dut.rq_post_context[355:340]!==dut.rq_post_context[523:460] ||
   dut.rq_post_context[339:324]!==4 || dut.rq_post_context[323:308]!==1 ||
   dut.rq_post_context[307:276]!==rq_capacity || dut.rq_post_context[275:244]!==(rq_capacity ? 8:0) ||
   dut.rq_post_context[243:180]!==(rq_capacity ? 64'hfedcba9876543210:0) ||
   dut.rq_post_context[179:116]!==(rq_capacity ? 64'h210:0) ||
   dut.rq_post_context[115:20]!==0 || dut.rq_post_context[19:0]!==3 || dut.rq_post_context[619:588]!==0)
    $fatal(1,"actual coherent RQ128 owner/canonical local fields");
 end
 if(dut.rq_placement_valid && dut.rq_placement_ready &&
  (dut.rq_placement_context!==expected_rq_owner || dut.rq_placement_length!==0 ||
   dut.rq_placement_psn!==expected_rq_psn || dut.rq_placement_notification!==rq_notification ||
   dut.rq_placement_notification_flags!==rq_notification_flags))$fatal(1,"actual zero RX protected placement");
 if(dut.rq_core_valid && dut.rq_core_ready && dut.rq_core_data!==expected_rq_core)
  $fatal(1,"actual zero RX full HLS EOF/PSN/MSN receipt");
 if(dut.cq_commit_valid && (!dut.rq_core_proved || !dut.receive_owners.owners.mac_proved ||
    dut.cq_commit_context!=={128'd0,expected_rq_owner} || !dut.receive_ack_lifetime.ack_owner.proof_sent ||
    !dut.completion_memory_drained))$fatal(1,"zero RX CQ without exact HLS/MAC/physical-memory proofs");
 if(dut.cq_retire_valid && (!dut.receive_owners.owners.committed ||
    dut.cq_retire_context!=={128'd0,expected_rq_owner}))$fatal(1,"zero RX CQ without exact commit");
end
'''

TASKS=r'''
task rq_send;
 input integer seq;
 integer n,count;
 begin
  count=rq_op==6 ? 5:4;
  for(n=(seq-1)*5;n<(seq-1)*5+count;n=n+1)begin
   @(negedge clk);{il,ik,id}=rq_stimulus[n];iv=1;
   @(posedge clk);while(!ir)@(posedge clk);
  end
  @(negedge clk);iv=0;
 end
endtask

task rq_cq;
 input integer seq;
 begin
  rq_deadline=cycle+5000;sq_value=0;
  while(!(sq_value&1))begin
   if(cycle>rq_deadline)$fatal(1,"zero RX CQ deadline RQ%h ACK%h shared%h core%0d placed%0d",dut.rq_fault_code,dut.recv_ack_fault_code,dut.h_shared_hls_fault_code,dut.rq_core_proof_count,dut.rq_placement_count);
   read_reg(24'h40300c,sq_value);
  end
  if(sq_value!==3 || dut.rq_active || dut.rq_queue_guard || dut.recv_ack_busy || dut.h_local_hls_active ||
     local_execution_guard!==8'h04 || fault)$fatal(1,"zero RX exact CQ/RQ/ACK ownership handoff");
  rq_fp=$fopen(seq==1 ? "zero-rq-event1.hex":"zero-rq-event2.hex","w");
  for(rq_word=0;rq_word<5;rq_word=rq_word+1)begin
   case(rq_word)
    0:read_reg(24'h403018,sq_value);1:read_reg(24'h40301c,sq_value);2:read_reg(24'h403028,sq_value);
    3:read_reg(24'h403020,sq_value);4:read_reg(24'h403024,sq_value);
   endcase
   if(sq_value!==(rq_word==0 ? seq:rq_word==1 ? 15:rq_word==2 ? 0:rq_word==3 ? 32'h89abcdf0:32'hfedcba98))
    $fatal(1,"zero RX CQ prefix/owner/flags");
   $fdisplay(rq_fp,"%08h",sq_value);
  end
  for(rq_word=0;rq_word<20;rq_word=rq_word+1)begin
   read_reg(24'h403040+rq_word*4,sq_value);
   if(sq_value!==(({20'd0,expected_rq_owner}>>(rq_word*32))&32'hffffffff))$fatal(1,"zero RX immutable620-bit CQ snapshot");
   $fdisplay(rq_fp,"%08h",sq_value);
  end
  for(rq_word=0;rq_word<4;rq_word=rq_word+1)begin
   case(rq_word)
    0:read_reg(24'h403038,sq_value);1:read_reg(24'h40303c,sq_value);
    2:read_reg(24'h403090,sq_value);3:read_reg(24'h403008,sq_value);
   endcase
   if(sq_value!==(rq_word==0 ? 0:rq_word==1 ? rq_notification_flags:rq_word==2 ? rq_notification:15))
    $fatal(1,"zero RX actual byte count/notification ABI");
   $fdisplay(rq_fp,"%08h",sq_value);
  end
  for(rq_word=0;rq_word<4;rq_word=rq_word+1)begin
   read_reg(24'h4030a0+rq_word*4,sq_value);if(sq_value)$fatal(1,"zero RX forged Atomic operands");$fdisplay(rq_fp,"%08h",sq_value);
  end
  $fclose(rq_fp);
  if(seq>1)begin
   write_reg(24'h403010,seq-1,15,0,1);read_reg(24'h40300c,sq_value);
   if(sq_value!==3)$fatal(1,"stale CQ host ACK retired zero successor");
  end
  write_reg(24'h403010,seq,15,0,1);read_reg(24'h403014,sq_value);
  if(sq_value!==seq || local_execution_guard || dut.cq_busy || dut.rq_active || fault)
   $fatal(1,"exact zero RX CQ host ACK release");
 end
endtask

task run_zero_rq;
 integer seq,n,rnr_before;
 begin
  rq_command(1,0);
  if($test$plusargs("RQ_RNR"))begin
   reject_ready=0;rq_send(1);rq_deadline=cycle+5000;
   while(!reject_valid || GUARD.rnr_sent_count!=1 || !response_tx_quiescent)begin
    if(cycle>rq_deadline)$fatal(1,"real zero-RQ RNR/wire deadline");@(negedge clk);
   end
   if(reject_error!==38 || GUARD.expected_psn!==24'h987654 || dut.rq_posted_count || dut.rq_taken_count ||
      sq_fetch_count || dut.cq_busy || accepted || completed || rq_remote_queries || rq_local_queries ||
      actual_native_SFD_count!=1)$fatal(1,"empty RQ consumed WQE/PSN/memory or lost real RNR");
   reject_ready=1;@(posedge clk);@(negedge clk);reject_ready=0;
  end
  for(seq=1;seq<=2;seq=seq+1)begin
   rq_seq=seq;expected_rq_psn=24'h987653+seq;hold_rq_mac=1;
   rq_command(2,seq);rq_deadline=cycle+5000;
   while(dut.rq_posted_count!=seq)begin
    if(cycle>rq_deadline)$fatal(1,"actual zero RQ128 fetch/admission deadline");@(negedge clk);
   end
   if(dut.rq_active || dut.rq_taken_count!=seq-1 || dut.rq_queue_guard!==8'h04 || dut.h_local_hls_active)
    $fatal(1,"preposted zero RQ was consumed without peer packet");
   expected_rq_owner=dut.rq_head_context;
   expected_rq_core={8'd0,rq_notification_flags,rq_notification,24'(seq),4'd0,expected_rq_psn,32'd0,expected_rq_owner};
   rq_send(seq);rq_deadline=cycle+6000;
   while(dut.rq_placement_count!=seq || dut.rq_core_proof_count!=seq ||
     dut.receive_ack_lifetime.ack_owner.frame_count!=seq)begin
    if(cycle>rq_deadline)$fatal(1,"zero RX actual EOF/HLS/PSN/ACK deadline state%0d fault%h/%h core%0d placed%0d",GUARD.state,dut.rq_fault_code,dut.h_shared_hls_fault_code,dut.rq_core_proof_count,dut.rq_placement_count);
    @(negedge clk);
   end
   repeat(1100)begin
    @(negedge clk);
    if(dut.cq_busy || m_cq_valid || !dut.rq_active || dut.rq_queue_guard!==8'h04 ||
       dut.receive_ack_lifetime.ack_owner.receipt_count!=seq-1)$fatal(1,"zero RX retired without actual ACK MAC receipt");
   end
   hold_rq_mac=0;rq_cq(seq);
   $display("ZERO_RQ_NATIVE_RECEIPT {\"sequence\":%0d,\"capacity\":%0d,\"operation\":%0d,\"PSN\":%0d,\"notification\":%0d,\"flags\":%0d,\"actual_HLS_MAC_CQ\":true}",seq,rq_capacity,rq_op,expected_rq_psn,rq_notification,rq_notification_flags);
  end
  check_ring();
  for(n=0;n<256;n=n+1)if(pcie_host[16640+n]!==rq_records[n/128][(n%128)*8+:8] || pcie_posted_valid[16640+n])
   $fatal(1,"actual coherent RQ bytes changed");
  for(n=0;n<16384;n=n+1)if(pcie_host[n]!==(((n*37)^8'h5a)&255) || pcie_posted_valid[n])
   $fatal(1,"zero RX changed host/sentinel data");
  if(rq_dma_seen!=2 || router_descriptor_count!=2 || read_tlps!=2 || write_tlps || fences ||
     commands || statuses || rq_remote_queries || rq_local_queries!=(rq_capacity ? 2:0) ||
     rq_post_queries!=(rq_capacity ? 2:0) || rq_table_queries!=(rq_capacity ? 2:0) ||
     local_committed_count || dut.h_local_hls_active || dut.rq_active || local_execution_guard ||
     dut.rq_posted_count!=2 || dut.rq_taken_count!=2 || dut.rq_placement_count!=2 || dut.rq_core_proof_count!=2 ||
     dut.receive_ack_lifetime.ack_owner.receipt_count!=2 || GUARD.expected_psn!==24'h987656 ||
     actual_native_SFD_count!=2+($test$plusargs("RQ_RNR") ? 1:0) || fault)
    $fatal(1,"zero RX final actual coherent/data/owner/PSN/MAC counts");
  $display("ZERO_RQ_NATIVE_RESULT {\"pass_test\":true,\"receives\":2,\"capacity\":%0d,\"operation\":%0d,\"local_MR_queries\":%0d,\"posted_RQ_MR_queries\":%0d,\"total_MR_table_queries\":%0d,\"remote_MR_queries\":0,\"data_commands\":0,\"read_TLPs\":2,\"write_TLPs\":0,\"fences\":0,\"host_bytes_unchanged\":true,\"RNR\":%0d,\"actual_MAC_receipt_model\":false}",rq_capacity,rq_op,rq_local_queries,rq_post_queries,rq_table_queries,$test$plusargs("RQ_RNR"));
 end
endtask
'''
