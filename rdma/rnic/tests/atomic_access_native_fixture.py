# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full Atomic128 fixture with real privileged QP/MR permission commands.

Keep the complete prior requester/responder tests. Add general WRITE on a
READ/WRITE-only QP before an Atomic RemoteAccess NAK, and separately deny MR
Atomic permission. No WQE, RQ, CQ or memory/retirement authority is invented.
Actual Atomic MAC/XGMII/FCS/SFD/CDC; physical host/root/peer/PHY/PTP modeled.
"""
import struct
import atomic128_native_fixture as old
import atomic_native_full_fixture as frames

ROOT=old.ROOT;link=old.link;once=old.once;variant=old.variant


def fixtures():
    extra=[frames.packet(0x0a,0x987654,frames.BASE+0x220,struct.pack('<Q',frames.NORMAL_VALUE)),
        frames.packet(0x14,0x987655,frames.BASE+0x218,struct.pack('!QQ',1,0))]
    words=[]
    for frame in extra:
        for off in range(0,len(frame),16):
            b=frame[off:off+16]
            words.append(int.from_bytes(b.ljust(16,bytes(1)),'little')|(((1<<len(b))-1)<<128)|(int(off+16>=len(frame))<<144))
    if len(words)!=12:raise ValueError('two whole six-beat permission stimulus frames')
    return frames.fixtures()+''.join(f'{w:037x}\n'for w in words)


def bench():
    t=once(old.bench(),'host_api(6,100,0,0,17,0,0,0,0,0);',
        'host_api(6,100,0,0,17,($test$plusargs("QP_DENIED") || $test$plusargs("NO_RX_ATOMIC")) ? 6:14,0,0,0,0);')
    t=once(t,'host_api(2,OWNER0,0,0,17,15,0,0,8,0);',
        'host_api(2,OWNER0,0,0,17,$test$plusargs("MR_DENIED") ? 7:15,0,0,8,0);')
    if t.count('if(sq_value!==1023)')!=2:raise ValueError('full RNC feature assertions changed')
    t=t.replace('if(sq_value!==1023)','if(sq_value!==2047)')
    t=once(t,'reg [144:0] atomic_inputs[0:23];','reg [144:0] atomic_inputs[0:35];\n'+OBSERVE)
    t=once(t,'task run_native_atomic;','task run_native_atomic_allowed;')
    t=once(t,'task run_native_atomic_allowed;',DENIED+'\ntask run_native_atomic_allowed;')
    return t.replace('ACCESS_FIRST_OLD',f"64'h{frames.FIRST_OLD:016x}").replace('ACCESS_NORMAL',f"64'h{frames.NORMAL_VALUE:016x}")


OBSERVE=r'''
integer denied_mr_queries=0;
always @(posedge clk)if(!rst && real_mac_mode &&
 dut.native.network.datapath.responder.endpoint.shared_hls.guard.atomic_execution_m_mr_valid &&
 dut.native.network.datapath.responder.endpoint.shared_hls.guard.atomic_execution_m_mr_ready)
 denied_mr_queries=denied_mr_queries+1;
'''

DENIED=r'''
task run_native_atomic;
 begin
  if($test$plusargs("QP_DENIED") || $test$plusargs("MR_DENIED"))run_native_atomic_denied();
  else run_native_atomic_allowed();
 end
endtask
task run_native_atomic_denied;
 integer n;
 begin
  $readmemh("atomic-input.hex",atomic_inputs);
  if(sq_fetch_count || local_committed_count || dut.cq_busy || dut.rq_active || !p_atomic_admission_valid ||
    dut.atomic_bound_access!==($test$plusargs("QP_DENIED") ? 4'h6:4'he) ||
    mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)
   $fatal(1,"permission test needs actual authorized general RX QP, no WQE/RQ/CQ or stale receipt");
  if(atomic_load(4101)!==ACCESS_FIRST_OLD)$fatal(1,"initial Atomic target");
  @(negedge clk);real_mac_mode=1;atomic_phase=3;expected_atomic_write=ACCESS_FIRST_OLD;
  // Normal WRITE must still traverse the SAME live QP and protected MR/PTE.
  atomic_input(4);atomic_deadline=cycle+5000;
  while(completed!=1 || !response_tx_quiescent || dut.atomic_lease_guard)begin
   if(cycle>atomic_deadline || fault)$fatal(1,"QP ordinary WRITE deadline before Atomic denial");@(negedge clk);
  end
  if(atomic_load(4109)!==ACCESS_NORMAL || atomic_load(4101)!==ACCESS_FIRST_OLD)
   $fatal(1,"ordinary WRITE failed on permission profile or clobbered Atomic target");
  atomic_phase=2;atomic_input(5);atomic_wait(1);
  if(denied_mr_queries!==($test$plusargs("QP_DENIED") ? 0:1) || atomic_load(4101)!==ACCESS_FIRST_OLD ||
    atomic_core_count!=1 || actual_Atomic_SFD_count!=1 || actual_native_SFD_count!=1 ||
    sq_fetch_count || local_committed_count || dut.cq_busy || dut.rq_active ||
    read_tlps!=1 || write_tlps!=1 || fences!=1 || actual_atomic_memory_commands!=1 ||
    actual_atomic_reads || actual_atomic_writes!=1)
   $fatal(1,"denied QP/MR Atomic gained memory/CQ authority or lost real NAK lifetime");
  for(n=0;n<16384;n=n+1)begin
   if(pcie_posted_valid[n])$fatal(1,"unfenced host bytes after QP/MR denial");
   if(n>=4109 && n<4117)begin
    if(pcie_host[n]!==((ACCESS_NORMAL>>((n-4109)*8))&255))$fatal(1,"normal WRITE byte after denial");
   end else if(pcie_host[n]!==(((n*37)^8'h5a)&255))$fatal(1,"denied Atomic/neighbor host-byte modification");
  end
  check_ring();
  $display("NATIVE_ACCESS_RESULT {\"pass_test\":true,\"QP_denied\":%0d,\"MR_queries\":%0d,\"normal_WRITEs\":1,\"retired\":%0d,\"core_receipts\":%0d,\"actual_Atomic_SFD\":%0d,\"actual_native_SFD\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"no_posted_WQE_RQ_CQ\":true}",
   $test$plusargs("QP_DENIED"),denied_mr_queries,atomic_retirements,atomic_core_count,
   actual_Atomic_SFD_count,actual_native_SFD_count,read_tlps,write_tlps,fences);
 end
endtask
'''
