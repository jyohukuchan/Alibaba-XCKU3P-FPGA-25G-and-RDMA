# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual8193 incoming WRITE/Immediate added to the unchanged34 native cases.

Only host/root/peer/PHY/PTP inputs are modeled. New WRITE must traverse the
actual generated HLS, native MR/PTE/PCIe/nonce/fence/ACK/PSN and genuine CQ.
The zero-capacity RQ is notification ownership, NEVER WRITE DMA authority.
"""
import hashlib
import json
import struct
import segmented_receive_payload_native_fixture as parent

ROOT=parent.ROOT;once=parent.once;GUARD=parent.GUARD


def __getattr__(name):return getattr(parent,name)


def large_write_variant(immediate):
    words,records,_=parent.rq.old.variant(2,0,False)
    _,posted,_=parent.rq.variant(6,0)
    payload=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(8193));frames=[];encoded=[]
    for packet,offset in enumerate(range(0,8193,4096)):
        count=min(4096,8193-offset);last=offset+count==8193
        p=bytearray(parent.incoming.qp.main.response.packet(write=False,mig=1,qpn=2,psn=parent.FIRST+packet)[:40])
        p[28]=6 if packet==0 else (9 if immediate else 8)if last else 7
        p[29]=(p[29]&~0x30)|(((-count)&3)<<4)
        if not packet:p+=struct.pack('!QII',0xfedcba9876543210,8,8193)
        if last and immediate:p+=struct.pack('!I',0x89abcdef)
        frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+parent.packet_tool.repair(p+payload[offset:offset+count]+bytes((-count)&3)+bytes(4))
        beats=parent.rq.split.encode_frame(frame)
        if len(beats)!=(261 if not packet else 260 if packet==1 else 5 if immediate else 4):
            raise ValueError('independent full Ethernet WRITE frame extent')
        frames.append(frame);encoded+=beats+[0]*(261-len(beats))
    return words,records,posted,encoded,frames


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR.replace('GUARD.',GUARD+'.')+TASKS.replace('GUARD.',GUARD+'.'))
    t=once(t,'runtime_receive_segmented=$test$plusargs("LARGE_RX");',
        'runtime_receive_segmented=$test$plusargs("LARGE_RX") || $test$plusargs("LARGE_WRITE_RX");')
    t=once(t,'always @(posedge clk)if(!rst && runtime_receive_segmented)begin',
        'always @(posedge clk)if(!rst && runtime_receive_segmented && !runtime_write_segmented)begin')
    t=once(t,'if($test$plusargs("RQ") || $test$plusargs("LARGE_RX"))begin',
        'if($test$plusargs("RQ") || $test$plusargs("LARGE_RX") || $test$plusargs("LARGE_WRITE_RX"))begin')
    t=once(t,'if(!$test$plusargs("LARGE_RX"))$readmemh("receive-input.hex",rq_stimulus);',
        'if(!$test$plusargs("LARGE_RX") && !$test$plusargs("LARGE_WRITE_RX"))$readmemh("receive-input.hex",rq_stimulus);')
    t=once(t,'if(runtime_receive_segmented)begin\n if(mac_cpl_rd!=mac_cpl_wr',
        'if(runtime_write_segmented)begin\n'
        ' if(mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)$fatal(1,"WRITE actual MAC switch not drained");\n'
        ' requester_wire_mode=1;run_large_write_native();$finish;disable native_rnic_case;\nend\n'
        'if(runtime_receive_segmented)begin\n if(mac_cpl_rd!=mac_cpl_wr')
    if 'force 'in t:raise ValueError('no internal owner/proof/PSN/MR/DMA injection')
    return t


DECLARATIONS=r'''
reg runtime_write_segmented=0;
reg [144:0] wrx_stimulus[0:782];
integer wrx_queries=0,wrx_owners=0,wrx_done=0,wrx_commits=0,wrx_rq_owners=0,wrx_whole=0,wrx_committed=0,wrx_retired=0;
integer wrx_packet,wrx_word,wrx_deadline,wrx_count,wrx_fp;
wire wrx_immediate=lrx_op==5;
wire [319:0] wrx_message={24'd2,16'd17,64'h9123456700000001,64'd1,32'd8,64'hfedcba9876543210,32'd8193,24'h987654};
function [423:0] wrx_token;input integer packet_index;
 begin wrx_token={wrx_message,32'(packet_index*4096),32'(packet_index==2 ? 1:4096),24'(24'h987654+packet_index),16'(packet_index+1)};end
endfunction
initial runtime_write_segmented=$test$plusargs("LARGE_WRITE_RX");
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_write_segmented)begin
 if(dut.s_write_mr_request_valid && dut.s_write_mr_request_ready)begin
  if(wrx_queries>=4 || dut.s_write_mr_request_pd!==17 || dut.s_write_mr_request_key!==8 || dut.s_write_mr_request_operation!==3 ||
   dut.s_write_mr_request_address!==(64'hfedcba9876543210+(wrx_queries<2 ? 0:(wrx_queries-1)*4096)) ||
   dut.s_write_mr_request_length!==(wrx_queries==0 ? 8193:wrx_queries==3 ? 1:4096))
   $fatal(1,"WRITE actual whole and per-packet full64 MR authority");
  wrx_queries=wrx_queries+1;
 end
 if(dut.s_write_owner_valid && dut.s_write_owner_ready)begin
  if(wrx_owners>=3 || dut.s_write_owner!==wrx_token(wrx_owners))$fatal(1,"WRITE complete actual424 HLS owner");
  wrx_owners=wrx_owners+1;
 end
 if(dut.m_write_done_valid && dut.m_write_done_ready)begin
  if(wrx_done>=3 || dut.m_write_done!=={8'd0,24'(wrx_done==2 ? 1:0),wrx_token(wrx_done)})
   $fatal(1,"WRITE actual generated HLS owner/PSN/MSN/EOF receipt");
  wrx_done=wrx_done+1;
 end
 if(dut.s_write_commit_valid && dut.s_write_commit_ready)begin
  if(wrx_commits>=3 || dut.s_write_commit_token!==wrx_token(wrx_commits) || dut.s_write_commit_proofs!==15 ||
   dut.s_write_commit_msn!==(wrx_commits==2 ? 1:0) || GUARD.expected_psn!==(24'h987654+wrx_commits) ||
   fences!=wrx_commits+1 || dut.receive_ack_lifetime.ack_owner.receipt_count!=wrx_commits+1)
   $fatal(1,"WRITE real fenced/HLS/MAC/native PSN atomic commit");
  wrx_commits=wrx_commits+1;
 end
 if(mv && mr)begin if(!lrx_tuple_ok)$fatal(1,"WRITE actual MR-relative backend tuple");lrx_commands=lrx_commands+1;end
 if(sv && sr)begin
  if(lrx_statuses>=3 || lrx_fenced_bytes!==(lrx_statuses==2 ? 8193:(lrx_statuses+1)*4096))$fatal(1,"WRITE status before host fence");
  lrx_statuses=lrx_statuses+1;
 end
 if(dut.s_write_rq_owner_valid && dut.s_write_rq_owner_ready)begin
  if(!wrx_immediate || wrx_rq_owners || dut.s_write_rq_owner!=={4'd0,24'h987656,32'd1,lrx_owner})
   $fatal(1,"WRITE genuine LAST-only680 RQ owner");
  wrx_rq_owners=wrx_rq_owners+1;
 end
 if(dut.rq_message_valid && dut.rq_message_ready)begin
  if(!wrx_immediate || wrx_whole || dut.rq_message_data!=={4'd0,8'd0,8'd3,32'h89abcdef,24'd1,24'h987656,24'h987654,32'd8193,lrx_owner})
   $fatal(1,"WRITE actual whole8193 notification receipt, not zero capacity/LAST1");
  wrx_whole=wrx_whole+1;
 end
 if(dut.cq_commit_valid && dut.s_cq_commit_ready)begin
  if(!wrx_immediate || wrx_committed || wrx_whole!=1 || wrx_commits!=3 || dut.cq_commit_context!=={128'd0,lrx_owner} ||
   !dut.completion_memory_drained)$fatal(1,"WRITE genuine whole CQ before real proofs");
  wrx_committed=wrx_committed+1;
 end
 if(dut.cq_retire_valid && dut.cq_retire_ready)begin
  if(wrx_retired || wrx_committed!=1 || dut.cq_retire_context!=={128'd0,lrx_owner})$fatal(1,"WRITE actual exact CQ retirement");
  wrx_retired=wrx_retired+1;
 end
 if(actual_native_SFD_count>fences)$fatal(1,"WRITE positive ACK SFD before real payload visibility fence");
end
'''

TASKS=r'''
task wrx_send_packet;input integer packet_index;integer b,count;
 begin
  count=packet_index==0 ? 261:packet_index==1 ? 260:wrx_immediate ? 5:4;
  for(b=packet_index*261;b<packet_index*261+count;b=b+1)begin
   @(negedge clk);{il,ik,id}=wrx_stimulus[b];iv=1;@(posedge clk);while(!ir)@(posedge clk);
  end
  @(negedge clk);iv=0;
 end
endtask
task run_large_write_native;
 begin
  $readmemh("large-write-receive-input.hex",wrx_stimulus);
  lrx_owner={32'd0,rq_records[0][63:0],64'd1,64'h9123456700000001,24'd2,16'd17,16'd1,16'd4,16'd1,
   32'd0,32'd0,64'd0,64'd0,64'd0,32'd0,20'd3};
  if(wrx_immediate)begin
   rq_command(1,0);rq_command(2,1);wrx_deadline=cycle+5000;
   while(dut.rq_posted_count!=1)begin if(cycle>wrx_deadline)$fatal(1,"WRITE genuine zero-capacity RQ posting");@(negedge clk);end
   if(dut.rq_head_context!==lrx_owner || dut.rq_active || dut.rq_taken_count || dut.rq_queue_guard!==4)
    $fatal(1,"WRITE notification RQ owner before peer data");
  end
  for(wrx_packet=0;wrx_packet<3;wrx_packet=wrx_packet+1)begin
   wrx_send_packet(wrx_packet);wrx_deadline=cycle+10000;
   if(wrx_packet<2)begin
    while(wrx_commits!=wrx_packet+1 || dut.write_controller.packet_memory.busy)begin
     if(cycle>wrx_deadline)$fatal(1,"WRITE native packet completion deadline packet%0d",wrx_packet);@(negedge clk);
    end
    if(dut.rq_taken_count || wrx_rq_owners || wrx_whole || dut.cq_busy || wrx_committed ||
     !dut.s_write_message_active || !dut.s_write_held || GUARD.expected_psn!==(24'h987655+wrx_packet))
     $fatal(1,"WRITE FIRST/MIDDLE lost real message/MR/PSN or consumed invented RQ/CQ");
   end else begin
    while(wrx_done!=3 || dut.receive_ack_lifetime.ack_owner.frame_count!=3 || (wrx_immediate && wrx_whole!=1))begin
     if(cycle>wrx_deadline)$fatal(1,"WRITE actual LAST HLS/ACK/whole deadline");@(negedge clk);
    end
    repeat(1100)begin
     @(negedge clk);
     if(wrx_commits!=2 || GUARD.expected_psn!==24'h987656 || !dut.s_write_held ||
      dut.cq_busy || m_cq_valid || wrx_committed || wrx_retired || dut.receive_ack_lifetime.ack_owner.receipt_count!=2 ||
      (wrx_immediate && (!dut.rq_active || dut.rq_held_context!==lrx_owner)))
      $fatal(1,"WRITE escaped missing LAST actual MAC receipt");
    end
   end
  end
  lrx_hold_final_MAC=0;wrx_deadline=cycle+5000;
  if(wrx_immediate)begin
   sq_value=0;while(!(sq_value&1))begin
    if(cycle>wrx_deadline)$fatal(1,"WRITE actual whole CQ publication deadline");read_reg(24'h40300c,sq_value);
   end
   if(sq_value!==3 || wrx_committed!=1 || wrx_retired!=1)$fatal(1,"WRITE whole CQ exact commit/retire");
  end else begin
   while(dut.s_write_held || dut.recv_ack_busy)begin
    if(cycle>wrx_deadline)$fatal(1,"WRITE plain final real retirement deadline");@(negedge clk);
   end
  end
  if(wrx_queries!=4 || wrx_owners!=3 || wrx_done!=3 || wrx_commits!=3 || GUARD.expected_psn!==24'h987657 ||
   lrx_commands!=3 || lrx_statuses!=3 || lrx_fenced_bytes!=8193 || commands!=3 || statuses!=3 ||
   router_descriptor_count!=(wrx_immediate ? 9:8) || pcie_physical_reads!=(wrx_immediate ? 4:3) || pcie_physical_writes!=5 ||
   read_tlps!=(wrx_immediate ? 4:3) || read_completions!=(wrx_immediate ? 4:3) || write_tlps!=67 || fences!=3 ||
   pcie_write_bytes!=8193 || actual_native_SFD_count!=3 || dut.rq_taken_count!==(wrx_immediate ? 1:0) || fault)
   $fatal(1,"WRITE complete actual MR/PCIe/HLS/MAC/PSN/CQ coverage");
  wrx_fp=$fopen("large-write-receive-host.hex","w");
  for(wrx_word=0;wrx_word<16384;wrx_word=wrx_word+1)begin
   if(pcie_posted_valid[wrx_word] || pcie_host[wrx_word]!==((wrx_word>=4093 && wrx_word<12286) ? pcie_pattern(wrx_word-4093):(((wrx_word*37)^8'h5a)&255)))
    $fatal(1,"WRITE every actual host payload/pad/sentinel byte");
   $fdisplay(wrx_fp,"%02h",pcie_host[wrx_word]);
  end
  $fclose(wrx_fp);check_ring();
  for(wrx_word=0;wrx_word<256;wrx_word=wrx_word+1)
   if(pcie_posted_valid[16640+wrx_word] || pcie_host[16640+wrx_word]!==rq_records[wrx_word/128][(wrx_word%128)*8+:8])
    $fatal(1,"WRITE coherent notification RQ changed");
  if(wrx_immediate)begin
   wrx_fp=$fopen("large-write-receive-event.hex","w");
   read_reg(24'h403018,sq_value);if(sq_value!==1)$fatal(1,"WRITE CQ sequence");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h40301c,sq_value);if(sq_value!==15)$fatal(1,"WRITE CQ real proofs");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h403028,sq_value);if(sq_value)$fatal(1,"WRITE CQ error");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h403020,sq_value);if(sq_value!==32'h89abcdf0)$fatal(1,"WRITE CQ cookie low");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h403024,sq_value);if(sq_value!==32'hfedcba98)$fatal(1,"WRITE CQ cookie high");$fdisplay(wrx_fp,"%08h",sq_value);
   for(wrx_word=0;wrx_word<20;wrx_word=wrx_word+1)begin
    read_reg(24'h403040+wrx_word*4,sq_value);
    if(sq_value!==(({20'd0,lrx_owner}>>(wrx_word*32))&32'hffffffff))$fatal(1,"WRITE CQ full620 owner");$fdisplay(wrx_fp,"%08h",sq_value);
   end
   read_reg(24'h403038,sq_value);if(sq_value!==8193)$fatal(1,"WRITE CQ used capacity/LAST1 instead of whole bytes");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h40303c,sq_value);if(sq_value!==3)$fatal(1,"WRITE CQ flags");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h403090,sq_value);if(sq_value!==32'h89abcdef)$fatal(1,"WRITE CQ Immediate");$fdisplay(wrx_fp,"%08h",sq_value);
   read_reg(24'h403008,sq_value);if(sq_value!==255)$fatal(1,"WRITE CQ candidate profile");$fdisplay(wrx_fp,"%08h",sq_value);
   for(wrx_word=0;wrx_word<4;wrx_word=wrx_word+1)begin read_reg(24'h4030a0+wrx_word*4,sq_value);if(sq_value)$fatal(1,"WRITE invented Atomic operands");$fdisplay(wrx_fp,"%08h",sq_value);end
   $fclose(wrx_fp);write_reg(24'h403010,1,15,0,1);read_reg(24'h403014,sq_value);
   if(sq_value!==1)$fatal(1,"WRITE exact host CQ ACK");
  end
  if(dut.s_write_held || dut.rq_active || dut.cq_busy || local_execution_guard || fault)$fatal(1,"WRITE final genuine lifetime guard");
  $display("SEGMENTED_WRITE_NATIVE_RESULT {\"pass_test\":true,\"bytes\":8193,\"packets\":3,\"MR_queries\":4,\"commands\":3,\"fences\":3,\"native_PSN_commits\":3,\"WRITE_Immediate\":%0d,\"notification_capacity\":0}",wrx_immediate);
 end
endtask
'''


def verify_large_write(output,posted,immediate,run):
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('SEGMENTED_WRITE_NATIVE_RESULT ')]
    wanted=dict(pass_test=True,bytes=8193,packets=3,MR_queries=4,commands=3,fences=3,native_PSN_commits=3,
        WRITE_Immediate=int(immediate),notification_capacity=0)
    if rows!=[wanted]:raise ValueError('actual complete native WRITE cardinality')
    ack=bytearray(parent.incoming.case(True,True)[-1]);frames=[]
    for packet in range(3):
        p=bytearray(ack);p[37:40]=(parent.FIRST+packet).to_bytes(3,'big');p[41:44]=(1 if packet==2 else 0).to_bytes(3,'big')
        frames.append((0x6001+packet,bytes.fromhex('b8830367c5d08af3fbb975310800')+parent.packet_tool.repair(p)))
    if parent.rq.link.frames(output)!=frames:raise ValueError('independent every native ACK/MAC/FCS/SFD/CDC/PSN/MSN byte')
    host=bytes(int(s,16)for s in(run/'large-write-receive-host.hex').read_text().splitlines())
    expected=bytearray(((i*37)^0x5a)&255 for i in range(16384));expected[4093:12286]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(8193))
    if host!=expected:raise ValueError('independent every WRITE host byte/pad/sentinel')
    result=dict(summary=rows[0],every_payload_and_sentinel_byte=True,actual_Linux_or_physical_hardware=False,
        actual_XGMII_frames=[dict(tag=tag,frame_hex=frame.hex())for tag,frame in frames],host_snapshot_sha256=hashlib.sha256(host).hexdigest())
    if immediate:
        owner=0;r=posted[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little')
        for width,value in [(32,0),(64,get(0,8)),(64,1),(64,0x9123456700000001),(24,2),(16,17),(16,1),
            (16,4),(16,1),(32,0),(32,0),(64,0),(64,0),(64,0),(32,0),(20,3)]:owner=(owner<<width)|value
        snapshot=[int(s,16)for s in(run/'large-write-receive-event.hex').read_text().splitlines()]
        if snapshot!=[1,15,0,0x89abcdf0,0xfedcba98]+[(owner>>(32*i))&0xffffffff for i in range(20)]+[8193,3,0x89abcdef,255]+[0]*4:
            raise ValueError('independent whole WRITE/Immediate CQ/full620 owner snapshot')
        result.update(full620_CQ_owner=f'{owner:0155x}',zero_capacity_genuine_RQ=True,whole_received_bytes=8193)
    return result
