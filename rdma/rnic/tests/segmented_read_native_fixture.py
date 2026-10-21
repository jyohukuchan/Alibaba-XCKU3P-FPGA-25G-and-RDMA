# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native8193 READ plus all29 original cases, physical endpoints models.

No work/MR/status/core/CQ/retire injection. Only normal CSR/host/peer/physical
root/PHY/PTP interfaces are driven. All original checks remain in old modes.
"""
import ctypes as C
import json
from pathlib import Path
import segmented_profile_native_fixture as parent
import zero_rq_native_fixture as rq
import test_segmented_read_wqe as codec
import test_wqe_response_guard_rtl as packets

ROOT=parent.ROOT;once=parent.once;LENGTH=8193;FIRST=0xfffffe


def __getattr__(name):return getattr(parent,name)


verify_large=parent.clone(parent.parent.verify_large,'[0,0,0,15,748,0xa0]','[0,0,0,63,748,0xa0]')
verify_rq=parent.clone(parent.rq.verify,'[0,flags,imm,15]','[0,flags,imm,63]')
verify_atomic=parent.clone(parent.atomic.verify,'[0,0,0,15,748,0xa0]','[0,0,0,63,748,0xa0]')
verify_zero=parent.clone(parent.zero.verify_zero,'[0,0,0,15,748,0xa0]','[0,0,0,63,748,0xa0]')


def large_read_variant():
    words,records,request=rq.old.variant(2,0,False);actual=[]
    cls=codec.SegmentedReadWQE;cls.setUpClass()
    try:
        for raw in records:
            raw=bytearray(raw);raw[32:36]=LENGTH.to_bytes(4,'little')
            w=codec.AtomicWQE();data=(C.c_uint8*128).from_buffer_copy(raw);out=(C.c_uint8*128)()
            if cls.lib.as02_segmented_read_wqe_decode(C.byref(w),data)or cls.lib.as02_segmented_read_wqe_encode(out,C.byref(w))or \
               bytes(out)!=raw or codec.old.old.old.oracle(w)!=raw:raise ValueError('actual READ C128/independent bytes mismatch')
            actual.append(bytes(out))
    finally:cls.tearDownClass()
    p=bytearray(request);p[37:40]=FIRST.to_bytes(3,'big');p[52:56]=LENGTH.to_bytes(4,'big');request=packets.repair(p)
    payload=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(LENGTH))
    frames=packets.read_wire.responses(payload,initial_psn=FIRST,msn=1,source_ip='198.18.11.1',
        destination_ip='198.18.11.2',destination_qpn=2)
    beats=[];sizes=[]
    for frame in frames:
        packets.read_wire.decode(frame);items=rq.split.encode_frame(frame);sizes.append(len(items));beats+=items
    if sizes!=[260,260,5]:raise ValueError('full READ response byte/beat geometry mismatch')
    return words,actual,request,beats


def bench():
    t=parent.bench()
    if t.count('if(sq_value!==8191)')!=2:raise ValueError('both genuine RNC reads required')
    t=t.replace('if(sq_value!==8191)','if(sq_value!==16383)')
    if t.count("read_reg(24'h403008,sq_value);if(sq_value!==31)")!=3:raise ValueError('all actual CQ ABI reads required')
    t=t.replace("read_reg(24'h403008,sq_value);if(sq_value!==31)","read_reg(24'h403008,sq_value);if(sq_value!==63)")
    t=once(t,'rq_word==2 ? rq_notification:31','rq_word==2 ? rq_notification:63')
    # Only hierarchy changed by the already-qualified READ routing wrapper.
    t=t.replace('dut.executor.segmented.','dut.executor.source_and_legacy.segmented.')
    t=t.replace('dut.executor.legacy.','dut.executor.source_and_legacy.legacy.')
    start=t.index('check_ring();request_event_file=');end=t.index('  $display("SEGMENTED_NATIVE_RESULT ',start)
    cq=t[start:end]
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS+MONITOR+TASKS.replace('// CQ_SNAPSHOT',cq))
    t=once(t,'runtime_zero ? 0:runtime_segmented ? 8193:runtime_atomic ? 8:65',
        'runtime_zero ? 0:(runtime_segmented || runtime_large_read) ? 8193:runtime_atomic ? 8:65')
    t=once(t,'host_words[10]=runtime_segmented ? 8721:4096;',
        'host_words[10]=(runtime_segmented || runtime_large_read) ? 8721:4096;')
    t=once(t,'if(runtime_segmented)host_api(3,owner,entry,key,0,0,2,',
        'if(runtime_segmented || runtime_large_read)host_api(3,owner,entry,key,0,0,2,')
    t=once(t,"host_words[20]=runtime_segmented ? 24'hfffffe:24'h89abcd;",
        "host_words[20]=(runtime_segmented || runtime_large_read) ? 24'hfffffe:24'h89abcd;")
    t=once(t,"link_m_cpl_tag==(runtime_segmented ? 16'h2003:16'h2002)",
        "link_m_cpl_tag==(runtime_large_read ? 16'h2001:runtime_segmented ? 16'h2003:16'h2002)")
    t=once(t,'if(runtime_atomic || runtime_zero || observed_source_operation)begin',
        'if(runtime_atomic || runtime_zero || observed_source_operation || runtime_large_read)begin')
    t=once(t,'if(runtime_segmented)begin run_segmented_native();',
        'if(runtime_large_read)begin run_large_read();$finish;disable native_rnic_case;end\nif(runtime_segmented)begin run_segmented_native();')
    t=once(t,'if(runtime_segmented ? !big_source_tuple_ok:',
        'if(runtime_large_read ? !lr_tuple_ok:runtime_segmented ? !big_source_tuple_ok:')
    t=once(t,'if(runtime_segmented ? (m_dma_write_valid || !big_page_shape(',
        'if(runtime_large_read ? !lr_page_shape(desc_ram,desc_length,m_dma_write_valid):runtime_segmented ? (m_dma_write_valid || !big_page_shape(')
    # Exact low sealed page may use real3DW READ or WRITE headers. Keep all
    # original strict requester/type/TC/attr/address/byte-enable checks.
    t=once(t,"if(runtime_segmented && h[127:125]===3'b000)",
        "if((runtime_segmented || runtime_large_read) && h[127:125]===3'b000 || runtime_large_read && h[127:125]===3'b010)")
    t=once(t,"if(runtime_segmented && !is_write && h[127:125]===3'b000)begin",
        "if((runtime_segmented || runtime_large_read) && !is_write && h[127:125]===3'b000 ||\n"
        "     runtime_large_read && is_write && h[127:125]===3'b010)begin")
    t=once(t,"base={h[63:2],2'b0};dwords=",'base=segmented_read_address(h);dwords=')
    t=once(t,'always @(posedge clk)if(!rst && runtime_segmented)begin\n if(m_dma_read_valid',
        'always @(posedge clk)if(!rst && (runtime_segmented || runtime_large_read))begin\n if(m_dma_read_valid')
    t=once(t,'  if(runtime_segmented)begin\n   if(!read_outstanding',
        '  if(runtime_segmented || runtime_large_read)begin\n   if(!read_outstanding')
    t=once(t,"(bytes_count!=1 || first_address!==64'h8123456789abcffd || posted_bytes!=runtime_length))",
        "(runtime_large_read ? (bytes_count!=1 || first_address!==pcie_expected_dma(pcie_current_offset) ||\n"
        "  posted_bytes!=pcie_current_length || lr_fenced_bytes!==pcie_current_offset-16'h210):\n"
        " (bytes_count!=1 || first_address!==64'h8123456789abcffd || posted_bytes!=runtime_length)))")
    t=once(t,'   fences=fences+1;',r'''
   if(runtime_large_read)begin
    for(n=0;n<16384;n=n+1)begin
     if(pcie_posted_valid[n]!==((n>=4093+lr_fenced_bytes) && (n<4093+lr_fenced_bytes+pcie_current_length)))
      $fatal(1,"READ fence missing/extra enabled destination byte");
     if(pcie_posted_valid[n] && pcie_posted[n]!==pcie_pattern(n-4093))$fatal(1,"READ fence actual payload byte");
    end
    lr_fenced_bytes=lr_fenced_bytes+pcie_current_length;
   end
   fences=fences+1;''')
    t=once(t,'guard_byte<4093+runtime_length) ? pcie_pattern',
        'guard_byte<4093+(runtime_large_read ? lr_fenced_bytes:runtime_length)) ? pcie_pattern')
    if 'force 'in t:raise ValueError('no force/internal grant/completion injection')
    return t


DECLARATIONS=r'''
reg runtime_large_read=0;initial runtime_large_read=$test$plusargs("LARGE_READ");
reg [144:0] lr_inputs[0:524];
integer lr_commands=0,lr_statuses=0,lr_events=0,lr_tokens=0,lr_rx=0,lr_MR_queries=0,lr_MR_responses=0,lr_receipts=0;
integer lr_fenced_bytes=0,lr_i,lr_p,lr_start,lr_count,lr_deadline,lr_dump;
wire [15:0] lr_tag=dut.ex_m_memory_command_tag;
wire lr_tuple_ok=dut.ex_m_memory_command_write && dut.ex_m_memory_command_key==8 &&
 lr_tag>=16'ha001 && lr_tag<=16'ha003 &&
 dut.ex_m_memory_command_offset==(64'h210+((lr_tag-16'ha001)<<12)) &&
 dut.ex_m_memory_command_length==(lr_tag==16'ha003 ? 1:4096);
function lr_page_shape;input integer ram,bytes,is_write;
 begin lr_page_shape=ram==8128 ? (!is_write && bytes==1):
  is_write && (pcie_current_offset==16'h2210 ? (ram==0 && bytes==1):
   ((ram==0 && bytes==3)||(ram==3 && bytes==4093)));end
endfunction
'''

MONITOR=r'''
always @(posedge clk)if(!rst && runtime_large_read)begin
 if(dut.owner_take)expected_request_owner=dut.sq_m_executor_context;
 if(dut.native.s_local_mr_request_valid && dut.native.s_local_mr_request_ready)begin
  if(lr_MR_queries || dut.native.s_local_mr_request_pd!==17 || dut.native.s_local_mr_request_key!==8 ||
   dut.native.s_local_mr_request_address!==64'hfedcba9876543210 || dut.native.s_local_mr_request_length!==8193 ||
   dut.native.s_local_mr_request_operation!==1 || dut.native.s_local_mr_request_tag!==1)$fatal(1,"large READ full actual MR authority");
  lr_MR_queries=lr_MR_queries+1;
 end
 if(dut.native.m_local_mr_response_valid && dut.native.m_local_mr_response_ready)begin
  if(lr_MR_responses || dut.native.m_local_mr_response_tag!==1 || dut.native.m_local_mr_response_error!==0 ||
   dut.native.m_local_mr_response_offset!==64'h210 || dut.native.m_local_mr_response_length!==8193)$fatal(1,"large READ actual MR grant");
  lr_MR_responses=lr_MR_responses+1;
 end
 if(dut.ex_m_memory_command_valid && dut.ex_m_memory_command_ready)begin
  if(!lr_tuple_ok || lr_tag!==16'ha001+lr_commands || lr_commands>=3)$fatal(1,"large READ exact child DMA command");
  lr_commands=lr_commands+1;
 end
 if(dut.ex_s_memory_status_valid && dut.ex_s_memory_status_ready)begin
  if(dut.ex_s_memory_status_tag!==16'ha001+lr_statuses || dut.ex_s_memory_status_error ||
   lr_statuses>=3 || lr_fenced_bytes!==(lr_statuses==2 ? 8193:(lr_statuses+1)*4096))$fatal(1,"large READ status before exact host fence");
  lr_statuses=lr_statuses+1;
 end
 if(dut.read_token_take)begin
  if(lr_tokens || dut.rx_m_read_response_context!==expected_request_owner)$fatal(1,"large READ one whole placement token");
  lr_tokens=lr_tokens+1;
 end
 if(dut.rx_m_response_event_valid && dut.rx_m_response_event_ready)begin
  if(lr_rx>=3 || dut.rx_m_response_event_context!==expected_request_owner ||
   dut.rx_m_response_event_psn!==((24'hfffffe+lr_rx)&24'hffffff) ||
   dut.rx_m_response_event_opcode!==(lr_rx==0 ? 8'h0d:lr_rx==1 ? 8'h0e:8'h0f) ||
   dut.expected_remote_msn!==1 || dut.remote_msn.message_count!==1)$fatal(1,"large READ actual RX/PSN/class/trusted MSN");
  if(lr_rx<2 && (dut.wire_lifetime.retained_replay.replay.acked || dut.wire_lifetime.proof_flags[3]))
   $fatal(1,"nonterminal READ released actual request cache/RX lease");
  lr_rx=lr_rx+1;
 end
 if(dut.executor.m_memory_event_valid && dut.executor.m_memory_event_ready)begin
  if(lr_events || lr_commands!=3 || lr_statuses!=3 || lr_fenced_bytes!=8193 ||
   dut.ex_m_memory_event_context!==expected_request_owner || dut.ex_m_memory_event_error)$fatal(1,"large READ aggregate event before real data/status");
  lr_events=lr_events+1;
 end
 if(dut.h_request_done_valid && dut.h_request_done_ready)begin
  if(lr_receipts || dut.h_request_done_data[747:0]!==expected_request_owner ||
   dut.h_request_done_data[771:748]!==24'hfffffe || dut.h_request_done_data[795:772]!==24'h000001 ||
   dut.h_request_done_data[803:796]!==8'h0c || dut.h_request_done_data[815:804]!==0)$fatal(1,"large READ real HLS whole receipt");
  lr_receipts=lr_receipts+1;
 end
end
'''

TASKS=r'''
task run_large_read;
 begin
  $readmemh("large-read-input.hex",lr_inputs);
  if(runtime_native_opcode!=2 || runtime_segmented || !requester_wire_mode)$fatal(1,"large READ actual mode setup");
  sq_command(2,1,0,0,0);lr_deadline=cycle+10000;
  while(!dut.tx_response_admission_ready || dut.tx_frame_count!=1 || board_wire_eofs!=1)begin
   if(cycle>lr_deadline)$fatal(1,"large READ genuine issued request deadline flags%h",local_proof_flags);@(negedge clk);
  end
  if(dut.remote_msn.message_count!==1 || dut.expected_remote_msn!==1)$fatal(1,"large READ missing real SQ MSN source");
  for(lr_p=0;lr_p<3;lr_p=lr_p+1)begin
   lr_start=lr_p*260;lr_count=lr_p==2 ? 5:260;
   for(lr_i=lr_start;lr_i<lr_start+lr_count;lr_i=lr_i+1)begin
    @(negedge clk);{il,ik,id}=lr_inputs[lr_i];iv=1;mac_rx_user=0;
    @(posedge clk);while(!ir)begin if(cycle>lr_deadline)$fatal(1,"large READ peer input deadline");@(posedge clk);end
    @(negedge clk);iv=0;
   end
  end
  lr_deadline=cycle+15000;
  while(!dut.h_request_done_valid)begin
   if(cycle>lr_deadline)$fatal(1,"large READ HLS/payload/DMA receipt deadline flags%h cmds%0d statuses%0d events%0d RX%0d fences%0d",local_proof_flags,lr_commands,lr_statuses,lr_events,lr_rx,fences);
   @(negedge clk);
  end
  held_request_proof=dut.h_request_done_data;
  repeat(1100)begin
   @(negedge clk);
   if(!dut.h_request_done_valid || dut.h_request_done_data!==held_request_proof || dut.h_request_done_ready ||
    dut.wire_lifetime.request_proved || m_cq_valid || dut.cq_busy || local_committed_count ||
    !dut.h_local_hls_active || local_execution_guard!==4 || dut.tx_receipt_count || dut.tx_mac_proof_count ||
    !dut.executor.read_fragments.active || !dut.remote_msn.busy)$fatal(1,"large READ escaped missing real MAC receipt");
  end
  hold_request_mac_cpl=0;lr_deadline=cycle+5000;sq_value=0;
  while(!(sq_value&1))begin if(cycle>lr_deadline)$fatal(1,"large READ actual CQ deadline");read_reg(24'h40300c,sq_value);end
  if(sq_value!==3 || fault || local_committed_count!=1 || dut.h_local_hls_active || local_execution_guard!==4 ||
   sq_fetch_count!=1 || sq_result_count!=1 || sq_submission_owner_count!=1 || sq_submission_hls_count!=1 ||
   lr_MR_queries!=1 || lr_MR_responses!=1 || lr_commands!=3 || lr_statuses!=3 || lr_events!=1 || lr_rx!=3 || lr_tokens!=1 || lr_receipts!=1 ||
   dut.rx_accepted_count!=3 || dut.tx_frame_count!=1 || dut.tx_receipt_count!=1 || dut.tx_mac_proof_count!=1 ||
   dut.native_retry_count || dut.native_rnr_count || router_descriptor_count!=9 ||
   pcie_physical_reads!=4 || pcie_physical_writes!=5 || read_tlps!=4 || write_tlps!=67 || fences!=3 || pcie_write_bytes!=8193 ||
   actual_native_SFD_count!=1 || actual_SFD_count!=1 || actual_Atomic_SFD_count || board_wire_eofs!=1 ||
   dut.remote_msn.message_count!=1 || dut.remote_msn.retired_count!=1 || dut.remote_msn.busy)
    $fatal(1,"large READ actual full path cardinality");
  lr_dump=$fopen("large-read-host.hex","w");if(!lr_dump)$fatal(1,"large READ host capture");
  for(lr_i=0;lr_i<16384;lr_i=lr_i+1)begin
   if(pcie_posted_valid[lr_i] || pcie_host[lr_i]!==((lr_i>=4093 && lr_i<12286) ? pcie_pattern(lr_i-4093):(((lr_i*37)^8'h5a)&255)))
    $fatal(1,"large READ every host payload/pad/sentinel byte");
   $fdisplay(lr_dump,"%02h",pcie_host[lr_i]);
  end
  $fclose(lr_dump);
  // CQ_SNAPSHOT
  $display("LARGE_READ_NATIVE_RESULT {\"pass_test\":true,\"bytes\":8193,\"MR_queries\":%0d,\"MR_responses\":%0d,\"commands\":%0d,\"statuses\":%0d,\"memory_events\":%0d,\"RX_packets\":%0d,\"placement_tokens\":%0d,\"HLS_receipts\":%0d,\"fenced_bytes\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"actual_SFD\":%0d,\"CQ_commits\":%0d}",
   lr_MR_queries,lr_MR_responses,lr_commands,lr_statuses,lr_events,lr_rx,lr_tokens,lr_receipts,lr_fenced_bytes,read_tlps,write_tlps,fences,actual_native_SFD_count,local_committed_count);
 end
endtask
'''


def verify_large_read(output,records,request,run):
    def row(prefix):
        r=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith(prefix+' ')]
        if len(r)!=1:raise ValueError('one actual '+prefix+' required')
        return r[0]
    summary=row('LARGE_READ_NATIVE_RESULT')
    want=dict(pass_test=True,bytes=8193,MR_queries=1,MR_responses=1,commands=3,statuses=3,memory_events=1,
        RX_packets=3,placement_tokens=1,HLS_receipts=1,fenced_bytes=8193,read_TLPs=4,write_TLPs=67,fences=3,actual_SFD=1,CQ_commits=1)
    if summary!=want:raise ValueError('actual large READ full-path counts mismatch:'+str(summary))
    frames=rq.link.frames(output)
    if frames!=[(0x2001,bytes.fromhex('b8830367c5d08af3fbb975310800')+request)]:raise ValueError('one exact real READ XGMII/FCS/SFD/CDC request required')
    host=bytes(int(l,16)for l in(run/'large-read-host.hex').read_text().splitlines())
    wanted=bytes((((i-4093)*179)^((i-4093)>>7)^0xd3)&255 if 4093<=i<12286 else((i*37)^0x5a)&255 for i in range(16384))
    if host!=wanted:raise ValueError('independent every-byte READ host/sentinel/padding oracle')
    r=records[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little');owner=0
    for bits,value in [(64,get(0,8)),(64,get(8,8)),(64,get(56,8)),(24,2),(16,17),(16,1),(16,2),(16,get(46,2)),
        (32,LENGTH),(32,get(36,4)),(64,get(16,8)),(64,0x210),(64,get(24,8)),(32,get(40,4)),(20,3)]:owner=(owner<<bits)|value
    event=[int(l,16)for l in(run/'request-event.hex').read_text().splitlines()]
    expected=[1,15,0,0x89abcdef,0xfedcba98]+[(owner>>(32*i))&0xffffffff for i in range(20)]+[0,0,0,63,748,0xa0]+[0]*4
    if event!=expected:raise ValueError('independent whole748 READ CQ owner/status/ABI')
    nonce=parent.verify_nonce(output)
    if nonce!=dict(admitted=3,issued=3,backend_completed=3,logical_completed=3,translated=3,active=0,fault=0):raise ValueError('READ physical nonce/status joins')
    core=row('NATIVE_REQUEST_CORE_PROOF')
    if core!=dict(opcode=2,PSN=FIRST,next_PSN=1,full_owner_match=True):raise ValueError('READ actual HLS whole response-span receipt')
    dispatcher=row('SEGMENTED_EXECUTOR_NATIVE_RESULT')
    for k,v in dict(legacy_owners=0,source_owners=0,source_events=0,source_retired=0,local_CQs=1,HLS_retires=1,
        dispatcher_retires=1,local_active=0,source_active=0,DUT_source_active=0,DUT_fault=0,actual_native_SFD=1,actual_all_SFD=1).items():
        if dispatcher.get(k)!=v:raise ValueError('actual whole READ dispatcher/CQ:'+k)
    return dict(summary=summary,full748_bit_CQ_owner=f'{owner:0187x}',actual_HLS_request_receipt=core,
        actual_common_nonce_backend=nonce,actual_READ_dispatcher_CQ=dispatcher,all16384_host_bytes_verified=True,
        actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],physical_MAC_receipt_model=False)
