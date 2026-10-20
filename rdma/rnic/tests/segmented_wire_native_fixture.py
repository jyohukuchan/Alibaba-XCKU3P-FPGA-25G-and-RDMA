# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual8193-byte ordinary WRITE/SEND on generated HLS/MR/PTE/PCIe/MAC/CQ.

All prior27 cases remain unchanged when SEGMENTED is absent. Physical
host/root/peer/PHY/PTP are models, never internal owner/core/CQ receipts.
"""
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
import test_segmented_wqe as codec
import segmented_executor_native_fixture as old
import zero_rq_native_fixture as prior
import test_wqe_response_guard_rtl as packet_tool

ROOT=old.ROOT;once=prior.once
variant=old.variant;prelude=old.prelude;verify=old.verify
verify_nonce=old.verify_nonce;verify_executor=old.verify_executor
CODEC_REPORT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-wqe-002.json'
LENGTH=8193;FIRST=0xfffffe


def large_variant(opcode):
    if opcode not in [1,3]:raise ValueError('only ordinary WRITE/SEND large native cases')
    proof=json.loads(CODEC_REPORT.read_text())
    if not proof.get('pass_test')or proof.get('methods')!=15:raise ValueError('matched actual private C128 codec evidence required')
    for n,h in proof['source_sha256'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h:
            raise ValueError('codec evidence changed:'+n)
    words,records,request=prior.old.variant(opcode,0,False);actual=[]
    cls=codec.SegmentedWQETests;cls.setUpClass()
    try:
        for raw in records:
            raw=bytearray(raw);raw[32:36]=LENGTH.to_bytes(4,'little')
            w=codec.AtomicWQE();data=(C.c_uint8*128).from_buffer_copy(raw);out=(C.c_uint8*128)()
            if cls.lib.as02_segmented_wqe_decode(C.byref(w),data)or cls.lib.as02_segmented_wqe_encode(out,C.byref(w))or \
               bytes(out)!=raw or codec.old.old.oracle(w)!=raw:raise ValueError('actual full-range C128 codec/independent byte oracle')
            actual.append(bytes(out))
    finally:cls.tearDownClass()
    frames=[]
    for offset in range(0,LENGTH,4096):
        count=min(4096,LENGTH-offset);first=offset==0;last=offset+count==LENGTH
        bth=(0 if first else 2 if last else 1)if opcode==3 else(6 if first else 8 if last else 7)
        p=bytearray(request[:28]);p+=bytes([bth,0x40|(((-count)&3)<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+((FIRST+offset//4096)&0xffffff).to_bytes(3,'big')
        if opcode==1 and first:p+=struct.pack('!QII',int.from_bytes(actual[0][24:32],'little'),int.from_bytes(actual[0][40:44],'little'),LENGTH)
        p+=bytes(((((4093+offset+i)*37)^0x5a)&255)for i in range(count))+bytes((-count)&3)+bytes(4)
        frames.append(bytes.fromhex('b8830367c5d08af3fbb975310800')+packet_tool.repair(p))
    template=b''.join((w&((1<<128)-1)).to_bytes(16,'little')[:((w>>128)&0xffff).bit_count()]for w in words[8:12]);acks=[]
    for index in range(3):
        p=bytearray(template[14:]);p[37:40]=((FIRST+index)&0xffffff).to_bytes(3,'big')
        frame=template[:14]+packet_tool.repair(p)
        acks+=prior.split.encode_frame(frame)
    if len(acks)!=12:raise ValueError('three whole four-beat peer ACK packets required')
    return words,actual,frames,acks


def bench():
    t=old.bench()
    cq_start=t.index('check_ring();request_event_file=');cq_end=t.index('\nend\n if($test$plusargs("ATOMIC_ONLY"))',cq_start)
    cq=t[cq_start:cq_end]
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+'\n'+MONITOR+'\n'+TASKS.replace('// CQ_SNAPSHOT',cq))
    t=once(t,'runtime_zero ? 0:runtime_atomic ? 8:65','runtime_zero ? 0:runtime_segmented ? 8193:runtime_atomic ? 8:65')
    t=once(t,"requester_wire_mode && hold_request_mac_cpl && link_m_cpl_tag==16'h2002",
        "requester_wire_mode && hold_request_mac_cpl && link_m_cpl_tag==(runtime_segmented ? 16'h2003:16'h2002)")
    t=once(t,'host_words[10]=4096;host_words[11]=3565;',
        'host_words[10]=runtime_segmented ? 8721:4096;host_words[11]=3565;')
    t=once(t,'  if(!admission_pause) $fatal(1,"last page reopened admission before seal");',
        "  if(runtime_segmented)host_api(3,owner,entry,key,0,0,2,64'h0000000012345000,key,0);\n"
        '  if(!admission_pause) $fatal(1,"last page reopened admission before seal");')
    t=once(t,"host_words[6]=17;host_words[15]=2;host_words[20]=24'h89abcd;",
        "host_words[6]=17;host_words[15]=2;host_words[20]=runtime_segmented ? 24'hfffffe:24'h89abcd;")
    t=once(t,'enable=1;\nif(runtime_service)begin',
        'enable=1;\nif(runtime_segmented)begin run_segmented_native();$finish;disable native_rnic_case;end\nif(runtime_service)begin')
    predicate="dut.ex_m_memory_command_key!==8 || dut.ex_m_memory_command_offset!==64'h210 ||\n   dut.ex_m_memory_command_length!==runtime_length || dut.ex_m_memory_command_tag!==(observed_source_operation ? 16'hc001:16'd1)"
    t=once(t,'if('+predicate+')$fatal(1,"main-path authority tuple");',
        'if(runtime_segmented ? !big_source_tuple_ok:('+predicate+'))$fatal(1,"main-path authority tuple");')
    predicate="real_mac_mode ? !((desc_ram==8128 && desc_length==1)||(desc_ram==0 && desc_length==8)) :\n ((desc_ram==8128 && desc_length!=1) || (desc_ram!=8128 && !((desc_ram==0 && desc_length==3)||(desc_ram==3 && desc_length==(runtime_atomic ? 5:62)))))"
    t=once(t,'if('+predicate+')',
        'if(runtime_segmented ? (m_dma_write_valid || !big_page_shape(pcie_current_offset,desc_ram,desc_length)):('+predicate+'))')
    if 'force 'in t:raise ValueError('no internal proof/owner/retire injection')
    return t


DECLARATIONS=r'''
reg runtime_segmented=0;
initial runtime_segmented=$test$plusargs("SEGMENTED");
reg [144:0] big_acks[0:11];
integer big_source_commands=0,big_MR_queries=0,big_MR_responses=0,big_expectations=0,big_advances=0,big_core_receipts=0;
integer big_packet,big_deadline,big_i;
wire [15:0] big_source_tag=dut.ex_m_memory_command_tag;
wire big_source_tuple_ok=!dut.ex_m_memory_command_write && dut.ex_m_memory_command_key==8 &&
 big_source_tag>=16'hc001 && big_source_tag<=16'hc003 &&
 dut.ex_m_memory_command_offset==(64'h210+((big_source_tag-16'hc001)<<12)) &&
 dut.ex_m_memory_command_length==(big_source_tag==16'hc003 ? 1:4096);
function big_page_shape;
 input integer off,ram,bytes;
 begin big_page_shape=((off==16'h210 || off==16'h1210) && ((ram==0 && bytes==3)||(ram==3 && bytes==4093))) ||
  (off==16'h2210 && ram==0 && bytes==1);end
endfunction
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_segmented)begin
 if(dut.owner_take)expected_request_owner=dut.sq_m_executor_context;
 if(dut.native.s_local_mr_request_valid && dut.native.s_local_mr_request_ready)begin
  if(big_MR_queries || dut.native.s_local_mr_request_pd!==17 || dut.native.s_local_mr_request_key!==8 ||
   dut.native.s_local_mr_request_address!==64'hfedcba9876543210 || dut.native.s_local_mr_request_length!==8193 ||
   dut.native.s_local_mr_request_operation!==0 || dut.native.s_local_mr_request_tag!==1)
   $fatal(1,"large actual full-range MR request");
  big_MR_queries=big_MR_queries+1;
 end
 if(dut.native.m_local_mr_response_valid && dut.native.m_local_mr_response_ready)begin
  if(big_MR_responses || dut.native.m_local_mr_response_tag!==1 || dut.native.m_local_mr_response_error!==0 ||
   dut.native.m_local_mr_response_offset!==64'h210 || dut.native.m_local_mr_response_length!==8193)
   $fatal(1,"large actual full-range MR grant");
  big_MR_responses=big_MR_responses+1;
 end
 if(dut.ex_m_memory_command_valid && dut.ex_m_memory_command_ready)begin
  if(!big_source_tuple_ok || big_source_tag!==16'hc001+big_source_commands || big_source_commands>=3)
   $fatal(1,"large saved-owner child range/sequence");
  big_source_commands=big_source_commands+1;
 end
 if(dut.wire_lifetime.m_expect_valid && dut.wire_lifetime.m_expect_ready)begin
  if(big_expectations>=3 || dut.wire_lifetime.m_expect_context!==expected_request_owner ||
   dut.wire_lifetime.m_expect_psn!==((24'hfffffe+big_expectations)&24'hffffff))$fatal(1,"large actual issued packet PSN/owner");
  big_expectations=big_expectations+1;
 end
 if(dut.wire_lifetime.packet_advance_valid && dut.wire_lifetime.packet_advance_ready)begin
  if(big_advances>=2 || dut.wire_lifetime.packet_advance_context!==expected_request_owner ||
   dut.wire_lifetime.packet_advance_psn!==((24'hfffffe+big_advances)&24'hffffff) ||
   dut.wire_lifetime.packet_index!==big_advances || !dut.wire_lifetime.local_tx_drained || !dut.executor.segmented.active)
   $fatal(1,"large genuine per-packet owner/cache advance");
  big_advances=big_advances+1;
 end
 if(dut.h_request_done_valid && dut.h_request_done_ready)begin
  if(big_core_receipts || dut.h_request_done_data[747:0]!==expected_request_owner ||
   dut.h_request_done_data[771:748]!==24'hfffffe || dut.h_request_done_data[795:772]!==24'h000001 ||
   dut.h_request_done_data[803:796]!==(runtime_native_opcode==1 ? 8'h0a:8'h04) || dut.h_request_done_data[815:804]!==0)
   $fatal(1,"large actual one full-WR HLS receipt/PSN span");
  big_core_receipts=big_core_receipts+1;
 end
end
'''

TASKS=r'''
task big_ack;
 input integer index;integer a;
 begin
  for(a=0;a<4;a=a+1)begin
   @(negedge clk);id=big_acks[index*4+a][127:0];ik=big_acks[index*4+a][143:128];il=big_acks[index*4+a][144];iv=1;
   @(posedge clk);while(!ir)@(posedge clk);@(negedge clk);iv=0;
  end
 end
endtask
task run_segmented_native;
 begin
  $readmemh("large-acks.hex",big_acks);
  if(runtime_native_opcode!=1 && runtime_native_opcode!=3)$fatal(1,"large ordinary source opcode");
  sq_command(2,1,0,0,0);
  for(big_packet=0;big_packet<3;big_packet=big_packet+1)begin
   big_deadline=cycle+10000;
   while(!dut.tx_response_admission_ready || dut.tx_frame_count!=big_packet+1 ||
    dut.wire_lifetime.m_expect_psn!==((24'hfffffe+big_packet)&24'hffffff))begin
    if(cycle>big_deadline)$fatal(1,"large actual packet issue deadline packet%0d flags%h fault%h",big_packet,local_proof_flags,fc);
    @(negedge clk);
   end
   big_ack(big_packet);
  end
  big_deadline=cycle+5000;
  while(!dut.h_request_done_valid)begin if(cycle>big_deadline)$fatal(1,"large genuine HLS receipt deadline");@(negedge clk);end
  held_request_proof=dut.h_request_done_data;
  if(held_request_proof[747:0]!==expected_request_owner || held_request_proof[771:748]!==24'hfffffe ||
   held_request_proof[795:772]!==24'h000001)$fatal(1,"large full-WR producer PSN/owner");
  repeat(1100)begin
   @(negedge clk);
   if(!dut.h_request_done_valid || dut.h_request_done_data!==held_request_proof || dut.h_request_done_ready ||
    dut.wire_lifetime.request_proved || m_cq_valid || dut.cq_busy || local_committed_count ||
    !dut.h_local_hls_active || local_execution_guard!==4 || dut.tx_receipt_count!=2 || dut.tx_mac_proof_count!=2 ||
    !dut.executor.segmented.active)$fatal(1,"large WR escaped missing final real MAC receipt");
  end
  hold_request_mac_cpl=0;big_deadline=cycle+5000;sq_value=0;
  while(!(sq_value&1))begin if(cycle>big_deadline)$fatal(1,"large actual CQ publication deadline");read_reg(24'h40300c,sq_value);end
  if(sq_value!==3 || local_committed_count!=1 || dut.h_local_hls_active || local_execution_guard!==4 || fault ||
   dut.ex_owner_count!=1 || dut.ex_command_count!=3 || dut.ex_memory_status_count!=3 ||
   sq_fetch_count!=1 || sq_result_count!=1 || sq_submission_owner_count!=1 || sq_submission_hls_count!=1 ||
   big_MR_queries!=1 || big_MR_responses!=1 || big_source_commands!=3 || big_expectations!=3 || big_advances!=2 ||
   big_core_receipts!=1 || dut.rx_accepted_count!=3 || dut.tx_frame_count!=3 || dut.tx_receipt_count!=3 ||
   dut.tx_mac_proof_count!=3 || dut.native_retry_count || dut.native_rnr_count ||
   router_descriptor_count!=6 || pcie_physical_reads!=6 || read_tlps!=68 || write_tlps || fences ||
   actual_native_SFD_count!=3 || actual_SFD_count!=3 || actual_Atomic_SFD_count)
   $fatal(1,"large actual memory/packet/PSN/CQ cardinality");
  for(big_i=0;big_i<16384;big_i=big_i+1)begin
   if(pcie_posted_valid[big_i] || pcie_host[big_i]!==(((big_i*37)^8'h5a)&255))$fatal(1,"large source/sentinel byte altered");
  end
  // CQ_SNAPSHOT
  $display("SEGMENTED_NATIVE_RESULT {\"pass_test\":true,\"opcode\":%0d,\"bytes\":8193,\"MR_queries\":%0d,\"MR_responses\":%0d,\"source_commands\":%0d,\"packet_expectations\":%0d,\"packet_advances\":%0d,\"core_receipts\":%0d,\"read_descriptors\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"actual_SFD\":%0d,\"CQ_commits\":%0d}",
   runtime_native_opcode,big_MR_queries,big_MR_responses,big_source_commands,big_expectations,big_advances,big_core_receipts,router_descriptor_count,read_tlps,write_tlps,fences,actual_native_SFD_count,local_committed_count);
 end
endtask
'''


def verify_large(output,records,frames,opcode,run):
    def row(prefix):
        r=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith(prefix+' ')]
        if len(r)!=1:raise ValueError('one actual '+prefix+' observation required')
        return r[0]
    expected=dict(pass_test=True,opcode=opcode,bytes=8193,MR_queries=1,MR_responses=1,source_commands=3,
        packet_expectations=3,packet_advances=2,core_receipts=1,read_descriptors=6,read_TLPs=68,write_TLPs=0,fences=0,actual_SFD=3,CQ_commits=1)
    summary=row('SEGMENTED_NATIVE_RESULT')
    if summary!=expected:raise ValueError('large full-native cardinality/authority:'+str(summary))
    actual=prior.link.frames(output)
    if actual!=[(0x2001+i,f)for i,f in enumerate(frames)]:raise ValueError('actual large XGMII/FCS/SFD/CDC/ICRC/full payload bytes')
    r=records[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little');owner=0
    for bits,value in [(64,get(0,8)),(64,get(8,8)),(64,get(56,8)),(24,2),(16,17),(16,1),(16,opcode),(16,get(46,2)),
        (32,8193),(32,get(36,4)),(64,get(16,8)),(64,0x210),(64,get(24,8)),(32,get(40,4)),(20,3)]:owner=(owner<<bits)|value
    wanted=[1,15,0,0x89abcdef,0xfedcba98]+[(owner>>(i*32))&0xffffffff for i in range(20)]+[0,0,0,15,748,0xa0]+[0]*4
    event=[int(l,16)for l in(run/'request-event.hex').read_text().splitlines()]
    if event!=wanted:raise ValueError('large independent full748 CQ context/notification/operand bytes')
    source=row('SEGMENTED_EXECUTOR_NATIVE_RESULT')
    for key,value in dict(legacy_owners=0,source_owners=1,source_events=1,source_retired=1,local_CQs=1,HLS_retires=1,
        dispatcher_retires=1,local_active=0,source_active=0,DUT_source_active=0,DUT_fault=0,actual_native_SFD=3,actual_all_SFD=3).items():
        if source.get(key)!=value:raise ValueError('large retained source/atomic CQ:'+key)
    if int(source['source_owner'],16)!=owner:raise ValueError('large actual trusted source owner differs from independent CQ owner')
    nonce=verify_nonce(output)
    if nonce!=dict(admitted=3,issued=3,backend_completed=3,logical_completed=3,translated=3,active=0,fault=0):raise ValueError('large actual physical nonce/status lifetimes')
    core=row('NATIVE_REQUEST_CORE_PROOF')
    if core!=dict(opcode=opcode,PSN=FIRST,next_PSN=1,full_owner_match=True):raise ValueError('large real HLS first/next common-PSN receipt')
    return dict(summary=summary,full748_bit_CQ_owner=f'{owner:0187x}',actual_source_and_atomic_CQ=source,
        actual_common_nonce_backend=nonce,actual_HLS_request_receipt=core,
        actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in actual],physical_MAC_receipt_model=False)
