# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real8193-byte incoming SEND/Immediate on one8194-byte posted receive.

Physical host/root/peer/PHY/PTP only are models. Every MR/PTE/scattered DMA,
nonce/status/fence/HLS/ACK-MAC/whole-CQ producer is actual RTL. All old32
mode assertions remain; new receive-only assertions replace requester-only
assumptions solely in the explicit LARGE_RX mode. Not a1MiB/native release.
"""
import ctypes as C
import hashlib
import json
import segmented_receive_native_fixture as parent
import zero_rq_native_fixture as rq
import native_receive_fixture as incoming
import test_segmented_receive_wqe as codec
import test_wqe_response_guard_rtl as packet_tool

ROOT=parent.ROOT;once=parent.once;LENGTH=8193;CAPACITY=8194;FIRST=0x987654
GUARD=rq.GUARD


def __getattr__(name):return getattr(parent,name)


def large_receive_variant(opcode,immediate):
    if (opcode,immediate)not in [(3,0),(5,0x89abcdef)]:raise ValueError('explicit segmented incoming SEND/Immediate required')
    words,records,_=rq.old.variant(2,0,False);received=[]
    codec.SegmentedReceiveWQE.setUpClass()
    try:
        for seq in [1,2]:
            w=codec.SegmentedReceiveWQE.receive(CAPACITY,wr_id=0xf123456789abc000+seq,sequence=seq,
                epoch=0x9123456700000001,local_key=8,local_address=0xfedcba9876543210)
            out=(C.c_uint8*128)()
            if codec.SegmentedReceiveWQE.lib.as02_segmented_receive_wqe_encode(out,C.byref(w))or bytes(out)!=codec.old.old.old.old.old.oracle(w):
                raise ValueError('actual full128 RECV C codec/independent byte oracle')
            received.append(bytes(out))
    finally:codec.SegmentedReceiveWQE.directory.cleanup()
    payload=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(LENGTH));frames=[];encoded=[]
    for packet,offset in enumerate(range(0,LENGTH,4096)):
        count=min(4096,LENGTH-offset);last=offset+count==LENGTH
        p=bytearray(incoming.qp.main.response.packet(write=False,mig=1,qpn=2,psn=FIRST+packet)[:40])
        p[28]=0 if packet==0 else (3 if opcode==5 else 2)if last else 1
        p[29]=(p[29]&~0x30)|(((-count)&3)<<4)
        if last and opcode==5:p+=immediate.to_bytes(4,'big')
        p+=payload[offset:offset+count]+bytes((-count)&3)+bytes(4)
        frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+packet_tool.repair(p)
        beats=rq.split.encode_frame(frame)
        if len(beats)not in ([260]if not last else[5 if opcode==5 else 4]):raise ValueError('independent incoming frame extent')
        frames.append(frame);encoded+=beats+[0]*(260-len(beats))
    return words,records,received,encoded,frames


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR.replace('GUARD.',GUARD+'.')+TASKS)
    t=once(t,'(runtime_segmented || runtime_large_read) ? 8193:',
        '(runtime_segmented || runtime_large_read || runtime_receive_segmented) ? 8193:')
    t=once(t,'host_words[10]=(runtime_segmented || runtime_large_read) ? 8721:4096;',
        'host_words[10]=runtime_receive_segmented ? 8722:(runtime_segmented || runtime_large_read) ? 8721:4096;')
    t=once(t,'if(runtime_segmented || runtime_large_read)host_api(3,owner,entry,key,0,0,2,',
        'if(runtime_segmented || runtime_large_read || runtime_receive_segmented)host_api(3,owner,entry,key,0,0,2,')
    t=once(t,'if($test$plusargs("RQ"))begin','if($test$plusargs("RQ") || $test$plusargs("LARGE_RX"))begin')
    t=once(t,'$readmemh("receive-records.hex",rq_records);$readmemh("receive-input.hex",rq_stimulus);',
        '$readmemh("receive-records.hex",rq_records);if(!$test$plusargs("LARGE_RX"))$readmemh("receive-input.hex",rq_stimulus);')
    t=once(t,"runtime_rq ? 64'hfedcba9876542000+rq_dma_seen*128:",
        "(runtime_rq || runtime_receive_segmented) ? 64'hfedcba9876542000+rq_dma_seen*128:")
    t=once(t,'if(runtime_rq)rq_dma_seen=rq_dma_seen+1;',
        'if(runtime_rq || runtime_receive_segmented)rq_dma_seen=rq_dma_seen+1;')
    t=once(t,'if(!runtime_rq && dut.cq_commit_valid','if(!runtime_rq && !runtime_receive_segmented && dut.cq_commit_valid')
    t=once(t,'if(!runtime_rq && dut.cq_retire_valid','if(!runtime_rq && !runtime_receive_segmented && dut.cq_retire_valid')
    t=once(t,'if(runtime_large_read)begin run_large_read();',r'''
if(runtime_receive_segmented)begin
 if(mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)$fatal(1,"large RX actual MAC switch not drained");
 requester_wire_mode=1;run_large_receive_native();$finish;disable native_rnic_case;
end
if(runtime_large_read)begin run_large_read();''')
    t=once(t,"!(runtime_rq && hold_rq_mac && link_m_cpl_tag[15:13]==3'b011) &&",
        "!(runtime_rq && hold_rq_mac && link_m_cpl_tag[15:13]==3'b011) &&\n"
        " !(runtime_receive_segmented && lrx_hold_final_MAC && link_m_cpl_tag==16'h6003) &&")
    t=once(t,'if(mk!==pcie_expected_key || (real_mac_mode ?',
        'if(runtime_receive_segmented ? !lrx_tuple_ok : mk!==pcie_expected_key || (real_mac_mode ?')
    t=once(t,'if(real_mac_mode ? (atomic_phase!=3 || !mw || ma!==64\'h220 || ml!==8 || mt!==16\'d1) :',
        'if(runtime_receive_segmented ? (!mw || ma!==(64\'h210+32\'(commands)*4096) ||\n'
        ' ml!==(commands==2 ? 1:4096) || mt!==commands+1 || commands>=3) :\n'
        ' real_mac_mode ? (atomic_phase!=3 || !mw || ma!==64\'h220 || ml!==8 || mt!==16\'d1) :')
    t=once(t,'if(runtime_large_read ? !lr_page_shape(desc_ram,desc_length,m_dma_write_valid):',
        'if(runtime_receive_segmented ? !lrx_page_shape(desc_ram,desc_length,m_dma_write_valid):\n'
        ' runtime_large_read ? !lr_page_shape(desc_ram,desc_length,m_dma_write_valid):')
    t=once(t,'(runtime_large_read ? lr_fenced_bytes:runtime_length)',
        '(runtime_receive_segmented ? lrx_fenced_bytes:runtime_large_read ? lr_fenced_bytes:runtime_length)')
    # The third actually sealed page is low DMA32; retain every original
    # request-format/address/TC/attribute/byte-enable assertion on both forms.
    t=once(t,"if((runtime_segmented || runtime_large_read) && h[127:125]===3'b000 || runtime_large_read && h[127:125]===3'b010)",
        "if((runtime_segmented || runtime_large_read || runtime_receive_segmented) && h[127:125]===3'b000 ||\n"
        " (runtime_large_read || runtime_receive_segmented) && h[127:125]===3'b010)")
    t=once(t,"if((runtime_segmented || runtime_large_read) && !is_write && h[127:125]===3'b000 ||\n     runtime_large_read && is_write && h[127:125]===3'b010)begin",
        "if((runtime_segmented || runtime_large_read || runtime_receive_segmented) && !is_write && h[127:125]===3'b000 ||\n"
        "     (runtime_large_read || runtime_receive_segmented) && is_write && h[127:125]===3'b010)begin")
    t=once(t,'if(!rst && (runtime_segmented || runtime_large_read))begin\n if(m_dma_read_valid',
        'if(!rst && (runtime_segmented || runtime_large_read || runtime_receive_segmented))begin\n if(m_dma_read_valid')
    t=once(t,'if(runtime_segmented || runtime_large_read)begin\n   if(!read_outstanding',
        'if(runtime_segmented || runtime_large_read || runtime_receive_segmented)begin\n   if(!read_outstanding')
    t=once(t,'(runtime_large_read ? (bytes_count!=1 || first_address!==pcie_expected_dma(pcie_current_offset) ||',
        "(runtime_receive_segmented ? (bytes_count!=1 || first_address!==pcie_expected_dma(pcie_current_offset) ||\n"
        " posted_bytes!=pcie_current_length || lrx_fenced_bytes!==pcie_current_offset-16'h210) :\n"
        '(runtime_large_read ? (bytes_count!=1 || first_address!==pcie_expected_dma(pcie_current_offset) ||')
    t=once(t,'posted_bytes!=runtime_length))) $fatal(1,"readback fence identity/data");',
        'posted_bytes!=runtime_length)))) $fatal(1,"readback fence identity/data");')
    t=once(t,'   fences=fences+1;',r'''
   if(runtime_receive_segmented)begin
    for(n=0;n<16384;n=n+1)begin
     if(pcie_posted_valid[n]!==((n>=4093+lrx_fenced_bytes) && (n<4093+lrx_fenced_bytes+pcie_current_length)))
      $fatal(1,"large RX readback fence missing/extra posted byte");
     if(pcie_posted_valid[n] && pcie_posted[n]!==pcie_pattern(n-4093))$fatal(1,"large RX fenced payload byte");
    end
    lrx_fenced_bytes=lrx_fenced_bytes+pcie_current_length;
   end
   fences=fences+1;''')
    if 'force 'in t:raise ValueError('no internal owner/receipt/status/MR/retirement injection')
    return t


DECLARATIONS=r'''
reg runtime_receive_segmented=0,lrx_hold_final_MAC=1;
integer lrx_op=3,lrx_packet,lrx_i,lrx_deadline,lrx_fp,lrx_commands=0,lrx_statuses=0,lrx_fenced_bytes=0;
integer lrx_post_queries=0,lrx_data_queries=0,lrx_placements=0,lrx_core=0,lrx_whole=0,lrx_packet_releases=0;
integer lrx_CQ_commits=0,lrx_CQ_retires=0;
reg [144:0] lrx_stimulus[0:779];reg [619:0] lrx_owner=0;
wire lrx_tuple_ok=mw && mk==8 && ((mt==1 && mo==64'h210 && ml==4096) ||
 (mt==2 && mo==64'h1210 && ml==4096) || (mt==3 && mo==64'h2210 && ml==1));
wire [31:0] lrx_immediate=lrx_op==5 ? 32'h89abcdef:0;
wire [7:0] lrx_flags=lrx_op==5 ? 1:0;
initial begin runtime_receive_segmented=$test$plusargs("LARGE_RX");if($value$plusargs("LARGE_RX_OP=%d",lrx_op))begin end end
function lrx_page_shape;input integer ram,bytes,is_write;
 begin lrx_page_shape=ram==8128 ? (!is_write && bytes==1):
  is_write && (pcie_current_offset==16'h2210 ? (ram==0 && bytes==1):
   ((ram==0 && bytes==3)||(ram==3 && bytes==4093)));end
endfunction
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_receive_segmented)begin
 if(dut.native.rq_mr_request_valid && dut.native.rq_mr_request_ready)begin
  if(lrx_post_queries || dut.native.rq_mr_request_pd!==17 || dut.native.rq_mr_request_key!==8 ||
   dut.native.rq_mr_request_address!==64'hfedcba9876543210 || dut.native.rq_mr_request_length!==8194 ||
   dut.native.rq_mr_request_operation!==1)$fatal(1,"large RX full posted-capacity MR authority");
  lrx_post_queries=lrx_post_queries+1;
 end
 if(GUARD.state==GUARD.LOOKUP && !GUARD.fault && GUARD.mr_request_ready)begin
  if(lrx_data_queries>=3 || GUARD.request_key!==8 || GUARD.request_va!==(64'hfedcba9876543210+lrx_data_queries*4096) ||
   GUARD.request_length!==(lrx_data_queries==2 ? 1:4096) || GUARD.table_request_operation!==1)
   $fatal(1,"large RX actual packet MR saved full key/VA/offset/range");
  lrx_data_queries=lrx_data_queries+1;
 end
 if(mv && mr)begin if(!lrx_tuple_ok)$fatal(1,"large RX full actual write authority tuple");lrx_commands=lrx_commands+1;end
 if(sv && sr)begin
  if(lrx_statuses>=3 || lrx_fenced_bytes!==(lrx_statuses==2 ? 8193:(lrx_statuses+1)*4096))
   $fatal(1,"large RX status before exact real host fence");
  lrx_statuses=lrx_statuses+1;
 end
 if(dut.rq_post_valid && dut.rq_post_ready && dut.rq_post_context!==lrx_owner)
  $fatal(1,"large RX actual C128/trusted full620 posted owner");
 if(dut.rq_placement_valid && dut.rq_placement_ready)begin
  if(lrx_placements>=3 || dut.rq_placement_context!==lrx_owner ||
   dut.rq_placement_length!==(lrx_placements==2 ? 1:4096) || dut.rq_placement_psn!==(24'h987654+lrx_placements) ||
   dut.rq_placement_notification!==(lrx_placements==2 ? lrx_immediate:0) ||
   dut.rq_placement_notification_flags!==(lrx_placements==0 ? 4:lrx_placements==1 ? 8:lrx_op==5 ? 17:16))
   $fatal(1,"large RX protected placement/phase/notification/full owner");
  lrx_placements=lrx_placements+1;
 end
 if(dut.rq_core_valid && dut.rq_core_ready)begin
  if(lrx_core>=3 || dut.rq_core_data[619:0]!==lrx_owner || dut.rq_core_data[651:620]!==(lrx_core==2 ? 1:4096) ||
   dut.rq_core_data[675:652]!==(24'h987654+lrx_core) || dut.rq_core_data[679:676]!==0 ||
   dut.rq_core_data[703:680]!==(lrx_core==2 ? 1:0) || dut.rq_core_data[735:704]!==(lrx_core==2 ? lrx_immediate:0) ||
   dut.rq_core_data[743:736]!==(lrx_core==0 ? 4:lrx_core==1 ? 8:lrx_op==5 ? 17:16) || dut.rq_core_data[751:744]!==0)
   $fatal(1,"large RX actual HLS full packet EOF/PSN/MSN/phase receipt");
  lrx_core=lrx_core+1;
 end
 if(dut.rq_message_valid && dut.rq_message_ready)begin
  if(lrx_whole || dut.rq_message_data!=={4'd0,8'd0,lrx_flags,lrx_immediate,24'd1,24'h987656,24'h987654,32'd8193,lrx_owner})
   $fatal(1,"large RX actual HLS whole receipt/capacity-vs-length");
  lrx_whole=lrx_whole+1;
 end
 if(dut.rq_packet_retire_valid && dut.rq_packet_retire_ready)begin
  if(lrx_packet_releases>=3 || dut.rq_packet_retire_context!==lrx_owner || !dut.rq_active ||
   !dut.receive_owners.owners.mac_proved || !dut.rq_core_proved || !dut.completion_memory_drained)
   $fatal(1,"large RX packet release without real data/HLS/ACK-MAC authority");
  lrx_packet_releases=lrx_packet_releases+1;
 end
 if(dut.cq_commit_valid && dut.s_cq_commit_ready)begin
  if(lrx_CQ_commits || lrx_packet_releases!=3 || lrx_whole!=1 || !dut.receive_owners.owners.mac_proved ||
   !dut.receive_owners.owners.message_proved || !dut.completion_memory_drained ||
   dut.cq_commit_context!=={128'd0,lrx_owner})$fatal(1,"large RX whole CQ without final real packet/whole proofs");
  lrx_CQ_commits=lrx_CQ_commits+1;
 end
 if(dut.cq_retire_valid && dut.cq_retire_ready)begin
  if(lrx_CQ_retires || lrx_CQ_commits!=1 || !dut.receive_owners.owners.committed ||
   dut.cq_retire_context!=={128'd0,lrx_owner})$fatal(1,"large RX exact whole CQ retirement");
  lrx_CQ_retires=lrx_CQ_retires+1;
 end
end
'''

TASKS=r'''
task lrx_send_packet;
 input integer packet_index;integer b,last_word;
 begin
  last_word=packet_index<2 ? 260:lrx_op==5 ? 5:4;
  for(b=packet_index*260;b<packet_index*260+last_word;b=b+1)begin
   @(negedge clk);{il,ik,id}=lrx_stimulus[b];iv=1;@(posedge clk);while(!ir)@(posedge clk);
  end
  @(negedge clk);iv=0;
 end
endtask

task run_large_receive_native;
 begin
  $readmemh("large-receive-input.hex",lrx_stimulus);
  lrx_owner={32'd0,rq_records[0][63:0],64'd1,64'h9123456700000001,24'd2,16'd17,16'd1,
   16'd4,16'd1,32'd8194,32'd8,64'hfedcba9876543210,64'h210,64'd0,32'd0,20'd3};
  rq_command(1,0);rq_command(2,1);lrx_deadline=cycle+5000;
  while(dut.rq_posted_count!=1)begin if(cycle>lrx_deadline)$fatal(1,"large RX real coherent posting deadline");@(negedge clk);end
  if(dut.rq_head_context!==lrx_owner || dut.rq_active || dut.rq_taken_count || dut.rq_queue_guard!==4 || lrx_post_queries!=1)
   $fatal(1,"large RX full admitted queued owner before peer data");
  for(lrx_packet=0;lrx_packet<3;lrx_packet=lrx_packet+1)begin
   lrx_send_packet(lrx_packet);lrx_deadline=cycle+10000;
   if(lrx_packet<2)begin
    while(lrx_packet_releases!=lrx_packet+1)begin
     if(cycle>lrx_deadline)$fatal(1,"large RX real per-packet data/HLS/MAC release deadline packet%0d",lrx_packet);
     @(negedge clk);
    end
    if(!dut.rq_active || dut.rq_taken_count!=1 || dut.rq_held_context!==lrx_owner || dut.rq_queue_guard!==4 ||
     dut.rq_received_bytes!==(lrx_packet+1)*4096 || dut.cq_busy || m_cq_valid || lrx_CQ_commits || lrx_whole)
     $fatal(1,"large RX FIRST/MIDDLE popped/unpinned owner or fabricated whole completion");
   end else begin
    while(lrx_core!=3 || lrx_whole!=1 || dut.receive_ack_lifetime.ack_owner.frame_count!=3)begin
     if(cycle>lrx_deadline)$fatal(1,"large RX actual LAST HLS/whole/ACK deadline core%0d whole%0d",lrx_core,lrx_whole);
     @(negedge clk);
    end
    repeat(1100)begin
     @(negedge clk);
     if(!dut.rq_active || dut.rq_held_context!==lrx_owner || dut.rq_queue_guard!==4 || dut.cq_busy || m_cq_valid ||
      lrx_CQ_commits || lrx_CQ_retires || lrx_packet_releases!=2 || dut.receive_ack_lifetime.ack_owner.receipt_count!=2)
      $fatal(1,"large RX whole owner/CQ escaped missing final actual ACK MAC receipt");
    end
   end
  end
  lrx_hold_final_MAC=0;lrx_deadline=cycle+5000;sq_value=0;
  while(!(sq_value&1))begin if(cycle>lrx_deadline)$fatal(1,"large RX actual whole CQ publication deadline");read_reg(24'h40300c,sq_value);end
  if(sq_value!==3 || dut.rq_active || dut.rq_queue_guard || dut.recv_ack_busy || local_execution_guard!==4 ||
   lrx_CQ_commits!=1 || lrx_CQ_retires!=1 || lrx_packet_releases!=3 || lrx_whole!=1 || lrx_core!=3 ||
   lrx_post_queries!=1 || lrx_data_queries!=3 || lrx_commands!=3 || lrx_statuses!=3 || lrx_fenced_bytes!=8193 ||
   dut.rq_taken_count!=1 || dut.rq_posted_count!=1 || dut.rq_placement_count!=3 || dut.rq_core_proof_count!=3 ||
   sq_fetch_count!=1 || sq_result_count!=1 || sq_submission_owner_count || sq_submission_hls_count ||
   dut.ex_owner_count || dut.ex_command_count || local_committed_count || dut.h_local_hls_active ||
   router_descriptor_count!=9 || pcie_physical_reads!=4 || pcie_physical_writes!=5 || read_tlps!=4 ||
   read_completions!=4 || write_tlps!=67 || fences!=3 || pcie_write_bytes!=8193 || actual_native_SFD_count!=3 || fault)
   $fatal(1,"large RX actual payload/MR/PTE/DMA/HLS/ACK/wholeCQ coverage");
  lrx_fp=$fopen("large-receive-host.hex","w");
  for(lrx_i=0;lrx_i<16384;lrx_i=lrx_i+1)begin
   if(pcie_posted_valid[lrx_i] || pcie_host[lrx_i]!==((lrx_i>=4093 && lrx_i<12286) ? pcie_pattern(lrx_i-4093):(((lrx_i*37)^8'h5a)&255)))
    $fatal(1,"large RX every host payload/pad/sentinel byte");
   $fdisplay(lrx_fp,"%02h",pcie_host[lrx_i]);
  end
  $fclose(lrx_fp);check_ring();
  for(lrx_i=0;lrx_i<256;lrx_i=lrx_i+1)if(pcie_posted_valid[16640+lrx_i] || pcie_host[16640+lrx_i]!==rq_records[lrx_i/128][(lrx_i%128)*8+:8])
   $fatal(1,"large RX coherent receive ring changed");
  lrx_fp=$fopen("large-receive-event.hex","w");
  read_reg(24'h403018,sq_value);if(sq_value!==1)$fatal(1,"large RX CQ sequence");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h40301c,sq_value);if(sq_value!==15)$fatal(1,"large RX CQ real proofs");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h403028,sq_value);if(sq_value!==0)$fatal(1,"large RX CQ error");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h403020,sq_value);if(sq_value!==32'h89abcdf0)$fatal(1,"large RX CQ cookie low");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h403024,sq_value);if(sq_value!==32'hfedcba98)$fatal(1,"large RX CQ cookie high");$fdisplay(lrx_fp,"%08h",sq_value);
  for(lrx_i=0;lrx_i<20;lrx_i=lrx_i+1)begin
   read_reg(24'h403040+lrx_i*4,sq_value);
   if(sq_value!==(({20'd0,lrx_owner}>>(lrx_i*32))&32'hffffffff))$fatal(1,"large RX CQ full620 owner");
   $fdisplay(lrx_fp,"%08h",sq_value);
  end
  read_reg(24'h403038,sq_value);if(sq_value!==8193)$fatal(1,"large RX CQ used capacity instead of actual bytes");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h40303c,sq_value);if(sq_value!==lrx_flags)$fatal(1,"large RX CQ notification flags");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h403090,sq_value);if(sq_value!==lrx_immediate)$fatal(1,"large RX CQ wire Immediate");$fdisplay(lrx_fp,"%08h",sq_value);
  read_reg(24'h403008,sq_value);if(sq_value!==255)$fatal(1,"large RX CQ exact profile");$fdisplay(lrx_fp,"%08h",sq_value);
  for(lrx_i=0;lrx_i<4;lrx_i=lrx_i+1)begin read_reg(24'h4030a0+lrx_i*4,sq_value);if(sq_value)$fatal(1,"large RX CQ invented Atomic operands");$fdisplay(lrx_fp,"%08h",sq_value);end
  $fclose(lrx_fp);write_reg(24'h403010,1,15,0,1);read_reg(24'h403014,sq_value);
  if(sq_value!==1 || dut.cq_busy || local_execution_guard || dut.rq_active || fault)$fatal(1,"large RX exact host ACK/guard release");
  $display("SEGMENTED_RECEIVE_NATIVE_RESULT {\"pass_test\":true,\"opcode\":%0d,\"bytes\":8193,\"capacity\":8194,\"packets\":3,\"posted\":1,\"taken\":1,\"MR_queries\":4,\"commands\":3,\"fences\":3,\"write_TLPs\":67,\"read_TLPs\":4,\"packet_releases\":3,\"whole_receipts\":1,\"CQ_commits\":1,\"CQ_retires\":1,\"notification\":%0d}",lrx_op,lrx_immediate);
 end
endtask
'''


def verify_large_receive(output,records,opcode,immediate,run):
    summaries=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('SEGMENTED_RECEIVE_NATIVE_RESULT ')]
    wanted=dict(pass_test=True,opcode=opcode,bytes=8193,capacity=8194,packets=3,posted=1,taken=1,MR_queries=4,
        commands=3,fences=3,write_TLPs=67,read_TLPs=4,packet_releases=3,whole_receipts=1,CQ_commits=1,CQ_retires=1,notification=immediate)
    if summaries!=[wanted]:raise ValueError('actual whole native large receive cardinality')
    ack=bytearray(incoming.case(True,True)[-1]);frames=[]
    for packet in range(3):
        p=bytearray(ack);p[37:40]=(FIRST+packet).to_bytes(3,'big');p[41:44]=(1 if packet==2 else 0).to_bytes(3,'big')
        frames.append((0x6001+packet,bytes.fromhex('b8830367c5d08af3fbb975310800')+packet_tool.repair(p)))
    if rq.link.frames(output)!=frames:raise ValueError('independent every actual XGMII/FCS/SFD/CDC ACK/PSN/MSN/ICRC byte')
    host=bytes(int(line,16)for line in(run/'large-receive-host.hex').read_text().splitlines())
    expected=bytearray(((i*37)^0x5a)&255 for i in range(16384))
    expected[4093:12286]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(LENGTH))
    if host!=expected:raise ValueError('independent every received payload/pad/sentinel byte')
    get=lambda off,size:int.from_bytes(records[0][off:off+size],'little');owner=0
    for width,value in [(32,0),(64,get(0,8)),(64,1),(64,0x9123456700000001),(24,2),(16,17),(16,1),
        (16,4),(16,1),(32,CAPACITY),(32,8),(64,0xfedcba9876543210),(64,0x210),(64,0),(32,0),(20,3)]:owner=(owner<<width)|value
    snapshot=[int(line,16)for line in(run/'large-receive-event.hex').read_text().splitlines()]
    expected_snapshot=[1,15,0,0x89abcdf0,0xfedcba98]+[(owner>>(32*i))&0xffffffff for i in range(20)]+[LENGTH,int(opcode==5),immediate,255]+[0]*4
    if snapshot!=expected_snapshot:raise ValueError('independent complete actual wholeCQ/owner/bytes/Immediate snapshot')
    return dict(summary=summaries[0],full620_CQ_owner=f'{owner:0155x}',actual_received_bytes=LENGTH,posted_capacity=CAPACITY,
        every_payload_and_sentinel_byte=True,per_packet_ACK_MSN_only_LAST=True,one_whole_CQ_and_host_ACK=True,
        actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],
        CQ_snapshot_sha256=hashlib.sha256((run/'large-receive-event.hex').read_bytes()).hexdigest(),
        host_snapshot_sha256=hashlib.sha256(host).hexdigest(),actual_Linux_or_physical_hardware=False)
