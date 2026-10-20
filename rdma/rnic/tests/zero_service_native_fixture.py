# SPDX-License-Identifier: BSD-2-Clause-Views
"""Whole-native ordinary zero WRITE/READ, real MAC/XGMII/SFD/CDC lifetime.

No SQ/RQ work is posted for the service. Actual privileged QP context, one
generated HLS, no-data owner, independent exact wire/core/sentinel checks.
Physical host/root/peer/PHY/PTP inputs remain models, not Linux/HW proof.
"""
import json
import struct
import zero_rq_native_fixture as old
import atomic_native_full_fixture as normal

ROOT=old.ROOT;once=old.once;link=old.link;fixtures=old.fixtures;GUARD=old.GUARD


def operations(mode):
    if mode not in [0,10,12,13]:raise ValueError('ordinary zero WRITE/READ mode')
    return [10,12]if mode in [0,13]else [mode,mode]


def variant(mode):
    packets=[];words=[]
    for seq,op in enumerate(operations(mode),1):
        p=bytearray(old.old.old.old.response.old.packet(write=True,length=1,mig=1,qpn=2,psn=0x987653+seq+(mode==13))[:40])
        p[28]=op;p[29]&=~0x30
        p+=struct.pack('!QII',(1<<64)-1 if seq==1 else 0xe23456789abcdef0,0xfedcba98 if seq==1 else 0x81234567,0)
        p=old.old.old.old.response.old.repair(p+bytes(4))
        frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+p;packets.append(frame)
        encoded=old.split.encode_frame(frame)
        if len(encoded)!=5:raise ValueError('exact ordinary zero60-byte IP')
        words+=encoded
    return words,packets


def prelude():
    # Genuine incoming normal WRITE through the unchanged MR/PTE/PCIe path.
    # Existing Atomic-mixed fixture already independently checks its8 bytes.
    frame=normal.packet(0x0a,0x987654,normal.BASE+0x220,struct.pack('<Q',normal.NORMAL_VALUE))
    return old.split.encode_frame(frame)


def bench():
    t=old.bench()
    t=once(t,'reg runtime_rq=0,hold_rq_mac=1;',DECLARATIONS+'\nreg runtime_rq=0,hold_rq_mac=1;')
    t=once(t," !(runtime_rq && hold_rq_mac && link_m_cpl_tag[15:13]==3'b011);",
        " !(runtime_rq && hold_rq_mac && link_m_cpl_tag[15:13]==3'b011) &&\n"
        " !(runtime_service && hold_service_legacy && link_m_cpl_tag==16'h4000) &&\n"
        " !(runtime_service && hold_service_receipt && link_m_cpl_tag[15:13]==3'b010 && link_m_cpl_tag!=16'h4000);")
    t=once(t,'enable=1;\nif(runtime_rq)begin',
        'enable=1;\nif(runtime_service)begin\n'
        ' if(mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)$fatal(1,"ordinary zero actual MAC switch not drained");\n'
        ' requester_wire_mode=1;run_zero_service();$finish;disable native_rnic_case;\nend\nif(runtime_rq)begin')
    t=once(t,'task run_zero_rq;',TASKS.replace('GUARD.',GUARD+'.')+'\ntask run_zero_rq;')
    t=once(t,'reg qp_model_allow=1;',MONITOR.replace('GUARD.',GUARD+'.')+'\nreg qp_model_allow=1;')
    # Standalone normal WRITE has no preceding Atomic update at4101..4108.
    # Keep the exact byte oracle for every location; select the real scenario
    # instead of assuming the earlier mixed-Atomic test's memory history.
    t=once(t,'  if(index>=4101 && index<4109)wanted=',
        '  if(!runtime_service && index>=4101 && index<4109)wanted=')
    if 'force 'in t:raise ValueError('no production force or fake service proof')
    return t


def verify(output,mode,run):
    result=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ZERO_SERVICE_NATIVE_RESULT ')]
    expected=dict(pass_test=True,services=2,mode=mode,MR_queries=0,data_commands=0,read_TLPs=0,write_TLPs=0,
        fences=0,SQ_work=0,RQ_work=0,CQ_events=0,host_bytes_preserved_by_zero_services=True,actual_MAC_receipts=True,
        zero_service_counters_only=True,normal_WRITE_prelude_bytes=8 if mode==13 else 0)
    if result!=[expected]:raise ValueError('whole-native ordinary zero summary or no-data authority')
    core=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('ZERO_SERVICE_NATIVE_CORE ')]
    retired=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('ZERO_SERVICE_NATIVE_RETIRE ')]
    owners=[];proofs=[];frames=[]
    if mode==13:
        p=bytearray(old.incoming.case(True,True)[-1]);p[37:40]=(0x987654).to_bytes(3,'big');p[41:44]=(1).to_bytes(3,'big')
        frames.append((0x4000,bytes.fromhex('b8830367c5d08af3fbb975310800')+old.incoming.qp.main.response.repair(p)))
    for seq,op in enumerate(operations(mode),1):
        psn=0x987653+seq+(mode==13);va=(1<<64)-1 if seq==1 else 0xe23456789abcdef0;key=0xfedcba98 if seq==1 else 0x81234567
        owner=2|(17<<24)|(0x9123456700000001<<40)|(0xfedcba9889abcdef<<104)|((seq+(mode==13))<<168)|\
            (psn<<184)|(op<<208)|(va<<216)|(key<<280)
        proof=owner|((psn+1)<<344)|((seq+(mode==13))<<368)|(15<<392);owners.append(owner);proofs.append(proof)
        p=bytearray(old.incoming.case(True,True)[-1]);p[28]=0x10 if op==12 else 0x11
        p[37:40]=psn.to_bytes(3,'big');p[41:44]=(seq+(mode==13)).to_bytes(3,'big')
        frames.append((0x4000+seq,bytes.fromhex('b8830367c5d08af3fbb975310800')+old.incoming.qp.main.response.repair(p)))
    if core!=proofs or retired!=proofs:raise ValueError('independent full344 owner/400 core/retire values')
    if link.frames(output)!=frames:raise ValueError('actual XGMII/FCS/SFD/CDC ordinary zero response bytes/tags')
    return dict(summary=result[0],full344_owners=[f'{o:086x}'for o in owners],full400_core_and_retire=[f'{o:0100x}'for o in proofs],
        actual_XGMII_frames=[dict(tag=tag,frame_hex=f.hex())for tag,f in frames],
        actual_generated_HLS_privileged_QP_MAC_lifetime=True,standard_Linux_or_physical_hardware=False)


DECLARATIONS=r'''
reg runtime_service=0,hold_service_receipt=1,hold_service_legacy=0,service_runtime_started=0;
integer service_mode=10,service_seq=0,service_op=0,service_i,service_deadline;
integer service_owner_count=0,service_hls_owner_count=0,service_core_count=0,service_retire_count=0,service_queries=0;
reg [144:0] service_input[0:9];
reg [144:0] service_prelude[0:5];
integer service_base_commands=0,service_base_statuses=0,service_base_descriptors=0;
integer service_base_reads=0,service_base_writes=0,service_base_fences=0;
reg [343:0] expected_service_owner=0;reg [399:0] expected_service_core=0;
initial begin
 runtime_service=$test$plusargs("ZERO_SERVICE");
 if($value$plusargs("SERVICE_OP=%d",service_mode))begin end
end
'''

MONITOR=r'''
always @(posedge clk)if(!rst && service_runtime_started)begin
 if(GUARD.table_request_valid && GUARD.table_request_ready)service_queries=service_queries+1;
 if(dut.m_zero_packet_owner_valid && dut.s_zero_packet_owner_ready)begin
  if(dut.m_zero_packet_owner!=={48'h8af3fbb97531,48'hb8830367c5d0,32'hc6120b02,32'hc6120b01,24'd196,expected_service_owner})
   $fatal(1,"ordinary zero actual privileged route/owner snapshot");
  service_owner_count=service_owner_count+1;
 end
 if(dut.s_zero_hls_owner_valid && dut.m_zero_hls_owner_ready)begin
  if(dut.s_zero_hls_owner!==expected_service_owner || !dut.zero_wire_lifetime.active)
   $fatal(1,"ordinary HLS owner without matching real MAC reservation");
  service_hls_owner_count=service_hls_owner_count+1;
 end
 if(dut.m_zero_core_done_valid && dut.s_zero_core_done_ready)begin
  if(dut.m_zero_core_done!==expected_service_core)$fatal(1,"ordinary zero actual400-bit core receipt");
  service_core_count=service_core_count+1;$display("ZERO_SERVICE_NATIVE_CORE %0100h",dut.m_zero_core_done);
 end
 if(dut.s_zero_retire_valid && dut.m_zero_retire_ready)begin
  if(dut.s_zero_retire_owner!==expected_service_owner || dut.s_zero_retire_core!==expected_service_core ||
   !dut.zero_wire_lifetime.mac_done || !dut.zero_wire_lifetime.receipt_seen || dut.zero_wire_lifetime.tail_left ||
   dut.zero_wire_lifetime.active_tag!==16'h4000+service_seq)$fatal(1,"ordinary zero real MAC/SFD/EOF/tail retirement");
  service_retire_count=service_retire_count+1;$display("ZERO_SERVICE_NATIVE_RETIRE %0100h",dut.s_zero_retire_core);
 end
 if(dut.cq_commit_valid || dut.cq_retire_valid || dut.rq_post_valid || dut.rq_core_valid || dut.m_work_handoff || dut.owner_take ||
    dut.m_atomic_packet_owner_valid || dut.m_atomic_core_done_valid || dut.s_atomic_retire_valid ||
    GUARD.m_memory_command_valid || GUARD.s_memory_status_valid || GUARD.s_axis_memory_read_tvalid ||
    GUARD.core_write_valid || GUARD.core_read_valid || GUARD.core_write_data_valid)
   $fatal(1,"ordinary zero service invented SQ/RQ/Atomic/CQ/data authority");
end
'''

TASKS=r'''
task run_zero_service;
 integer n;
 begin
  $readmemh("service-input.hex",service_input);
  if(service_mode==13)begin
   // Keep an actual older ordinary response outstanding. New zero service
   // must wait for the ORIGINAL response guard, not capture its4000 frame.
   real_mac_mode=1;atomic_phase=3;hold_service_legacy=1;
   $readmemh("service-prelude.hex",service_prelude);
   for(service_i=0;service_i<6;service_i=service_i+1)begin
    @(negedge clk);{il,ik,id}=service_prelude[service_i];iv=1;
    @(posedge clk);while(!ir)@(posedge clk);
   end
   @(negedge clk);iv=0;service_deadline=cycle+5000;
   while(GUARD.completed_count!=1 || GUARD.state!=GUARD.COLLECT || GUARD.lease)begin
    @(negedge clk);if(cycle>service_deadline)$fatal(1,"actual normal WRITE prelude did not hand off IP");
   end
   if(response_tx_quiescent || !response_pending_frames || pcie_host[4109]!==8'hef ||
      pcie_host[4116]!==8'h01)$fatal(1,"normal WRITE prelude did not retain actual pending response/data");
  end
  service_base_commands=commands;service_base_statuses=statuses;service_base_descriptors=router_descriptor_count;
  service_base_reads=read_tlps;service_base_writes=write_tlps;service_base_fences=fences;
  service_runtime_started=1;
  for(service_seq=1;service_seq<=2;service_seq=service_seq+1)begin
   service_op=(service_mode==0 || service_mode==13) ? (service_seq==1 ? 10:12):service_mode;
   expected_service_owner={32'd0,service_seq==1 ? 32'hfedcba98:32'h81234567,
    service_seq==1 ? 64'hffffffffffffffff:64'he23456789abcdef0,
    service_op[7:0],24'h987653+service_seq[23:0]+(service_mode==13 ? 24'd1:24'd0),
    service_seq[15:0]+(service_mode==13 ? 16'd1:16'd0),64'hfedcba9889abcdef,64'h9123456700000001,16'd17,24'd2};
   expected_service_core={8'h0f,service_seq[23:0]+(service_mode==13 ? 24'd1:24'd0),
    24'h987654+service_seq[23:0]+(service_mode==13 ? 24'd1:24'd0),expected_service_owner};
   hold_service_receipt=1;
   for(service_i=(service_seq-1)*5;service_i<service_seq*5;service_i=service_i+1)begin
    @(negedge clk);{il,ik,id}=service_input[service_i];iv=1;
    @(posedge clk);while(!ir)@(posedge clk);
   end
   @(negedge clk);iv=0;
   if(service_mode==13 && service_seq==1)begin
    repeat(100)begin
     @(negedge clk);if(service_owner_count || service_hls_owner_count || service_core_count ||
      GUARD.zero_service || GUARD.lease || dut.zero_mac_available || reject_valid || fault)
      $fatal(1,"ordinary zero did not wait for actual previous normal response");
    end
    hold_service_legacy=0;
   end
   service_deadline=cycle+5000;
   while(service_core_count<service_seq)begin
    @(negedge clk);if(cycle>service_deadline)$fatal(1,"ordinary zero real core timeout fc%h",fc);
   end
   repeat(1100)begin
    @(negedge clk);if(service_retire_count!=service_seq-1 || !GUARD.zero_service || !GUARD.lease ||
     !dut.zero_wire_lifetime.active || dut.cq_busy || local_execution_guard!==4 || fault)
      $fatal(1,"ordinary zero released without genuine own MAC receipt");
   end
   hold_service_receipt=0;service_deadline=cycle+4000;
   while(service_retire_count<service_seq || dut.zero_wire_lifetime.active || GUARD.zero_service)begin
    @(negedge clk);if(cycle>service_deadline)$fatal(1,"ordinary zero actual retirement deadline");
   end
   repeat(20)@(negedge clk);
   if(local_execution_guard || GUARD.lease || GUARD.expected_psn!==(24'h987654+service_seq[23:0]+(service_mode==13 ? 24'd1:24'd0)) || fault)
    $fatal(1,"ordinary zero actual lease/PSN after wire retirement");
  end
  for(n=0;n<16896;n=n+1)begin
   if(n>=16384 && n<16640)begin
    if(pcie_host[n]!==sq_records[(n-16384)/128][((n-16384)%128)*8+:8])$fatal(1,"ordinary zero altered SQ ring");
   end else if(service_mode==13 && n>=4109 && n<4117)begin
    if(pcie_host[n]!==((64'h0123456789abcdef>>((n-4109)*8))&255))$fatal(1,"zero service changed real normal prelude bytes");
   end else if(pcie_host[n]!==(((n*37)^8'h5a)&255))$fatal(1,"ordinary zero changed host/sentinel data");
   if(pcie_posted_valid[n])$fatal(1,"ordinary zero posted data write");
  end
  if(service_owner_count!=2 || service_hls_owner_count!=2 || service_core_count!=2 || service_retire_count!=2 ||
   service_queries || commands!=service_base_commands || statuses!=service_base_statuses ||
   router_descriptor_count!=service_base_descriptors || read_tlps!=service_base_reads || write_tlps!=service_base_writes || fences!=service_base_fences ||
   sq_fetch_count || local_committed_count || dut.rq_posted_count || dut.rq_taken_count || dut.cq_busy ||
   actual_native_SFD_count!=(service_mode==13 ? 3:2) || fault)$fatal(1,"ordinary zero final actual no-data/owner/packet counts");
  $display("ZERO_SERVICE_NATIVE_RESULT {\"pass_test\":true,\"services\":2,\"mode\":%0d,\"MR_queries\":0,\"data_commands\":0,\"read_TLPs\":0,\"write_TLPs\":0,\"fences\":0,\"SQ_work\":0,\"RQ_work\":0,\"CQ_events\":0,\"host_bytes_preserved_by_zero_services\":true,\"actual_MAC_receipts\":true,\"zero_service_counters_only\":true,\"normal_WRITE_prelude_bytes\":%0d}",service_mode,service_mode==13 ? 8:0);
 end
endtask
'''
