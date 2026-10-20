# SPDX-License-Identifier: BSD-2-Clause-Views
"""Observe the actual retained source, common DMA nonce and atomic CQ fanout.

No producer receipt, owner, retire, DMA or drain is driven by these observers.
Ordinary nonzero WRITE/SEND use the actual MAC/XGMII/FCS/SFD/CDC path, with
the second genuine MAC receipt withheld at its physical boundary. Physical
host/root/peer/PHY/PTP remain models. Native large admission is still closed.
"""
import json
import segmented_native_fixture as old

ROOT=old.ROOT;variant=old.variant;prelude=old.prelude;verify=old.verify
verify_nonce=old.verify_nonce


def bench():
    text=old.bench()
    # Same drained switch and actual receipt withholding as Atomic/zero.
    # Keep all original source-byte, wire/replay, CQ and timing assertions.
    text=old.old.once(text,'if(runtime_atomic || runtime_zero)begin\n if(mac_cpl_rd',
        'if(runtime_atomic || runtime_zero || observed_source_operation)begin\n if(mac_cpl_rd')
    text=old.old.once(text,'dut.ex_m_memory_command_tag!==1)',
        "dut.ex_m_memory_command_tag!==(observed_source_operation ? 16'hc001:16'd1))")
    return old.old.once(text,'module tb;','module tb;\n'+OBSERVER)


OBSERVER=r'''
wire observed_source_operation=!runtime_zero && (runtime_native_opcode==1 || runtime_native_opcode==3);
wire observed_local_CQ=dut.cq_retire_valid && !dut.receive_retire && dut.cq_retire_ready;
wire observed_HLS_retire=dut.native.s_local_retire_valid && dut.native.s_local_retire_ready;
wire observed_dispatcher_retire=dut.executor.s_retire_valid && dut.executor.s_retire_ready;
wire observed_source_retire=dut.executor.segmented.s_retire_valid && dut.executor.segmented.s_retire_ready;
integer observed_legacy_owners=0,observed_source_owners=0,observed_source_events=0,observed_source_retired=0;
integer observed_local_CQs=0,observed_HLS_retires=0,observed_dispatcher_retires=0;
reg observed_local_active=0,observed_source_active=0;
reg [747:0] observed_local_owner=0,observed_source_owner=0;
always @(posedge clk)begin
 if(rst)begin
  observed_legacy_owners=0;observed_source_owners=0;observed_source_events=0;observed_source_retired=0;
  observed_local_CQs=0;observed_HLS_retires=0;observed_dispatcher_retires=0;
  observed_local_active=0;observed_source_active=0;observed_local_owner=0;observed_source_owner=0;
 end else begin
  if(observed_local_CQ!==observed_HLS_retire || observed_local_CQ!==observed_dispatcher_retire)
   $fatal(1,"actual HLS/source CQ fanout did not consume the same genuine handshake");
  if(observed_source_active && (!dut.executor.segmented.active ||
   dut.executor.segmented.owner!==observed_source_owner || !dut.executor.queue_guard[2]))
   $fatal(1,"actual source lease/whole owner released before genuine CQ retirement");
  if(dut.executor.s_owner_valid && dut.executor.s_owner_ready)begin
   if(observed_local_active)$fatal(1,"overlapping actual local WR owner");
   observed_local_owner=dut.executor.s_owner_context;observed_local_active=1;
  end
  if(dut.executor.legacy.s_owner_valid && dut.executor.legacy.s_owner_ready)
   observed_legacy_owners=observed_legacy_owners+1;
  if(dut.executor.segmented.s_owner_valid && dut.executor.segmented.s_owner_ready)begin
   if(observed_source_active || !observed_source_operation || !observed_local_active ||
    dut.executor.segmented.s_owner_context!==observed_local_owner)
    $fatal(1,"actual retained source did not receive same trusted whole WR");
   observed_source_owner=dut.executor.segmented.s_owner_context;observed_source_active=1;
   observed_source_owners=observed_source_owners+1;
  end
  if(dut.executor.segmented.m_memory_event_valid && dut.executor.segmented.m_memory_event_ready)begin
   if(!observed_source_active || dut.executor.segmented.m_memory_event_context!==observed_source_owner ||
    dut.executor.segmented.m_memory_event_error!==0 || observed_source_events>=observed_source_owners)
    $fatal(1,"actual source aggregate memory event lost full WR owner");
   observed_source_events=observed_source_events+1;
  end
  if(observed_source_retire)begin
   if(!observed_source_active || !observed_local_CQ || !dut.executor.s_retire_offer_valid ||
    dut.executor.segmented.s_retire_context!==observed_source_owner ||
    observed_source_events!=observed_source_owners)
    $fatal(1,"actual source retired without same full WR CQ/HLS handshake");
   observed_source_retired=observed_source_retired+1;observed_source_active=0;
  end
  if(observed_local_CQ)begin
   if(!observed_local_active || dut.cq_retire_context!==observed_local_owner ||
    dut.native.s_local_retire_context!==observed_local_owner ||
    dut.executor.s_retire_context!==observed_local_owner ||
    (observed_source_operation && !observed_source_retire))
    $fatal(1,"actual whole WR CQ identity or atomic retained-source retirement");
   observed_local_CQs=observed_local_CQs+1;observed_local_active=0;
  end
  if(observed_HLS_retire)observed_HLS_retires=observed_HLS_retires+1;
  if(observed_dispatcher_retire)observed_dispatcher_retires=observed_dispatcher_retires+1;
 end
end
final begin
 $display("SEGMENTED_EXECUTOR_NATIVE_RESULT {\"legacy_owners\":%0d,\"source_owners\":%0d,\"source_events\":%0d,\"source_retired\":%0d,\"local_CQs\":%0d,\"HLS_retires\":%0d,\"dispatcher_retires\":%0d,\"local_active\":%0d,\"source_active\":%0d,\"DUT_source_active\":%0d,\"DUT_fault\":%0d,\"actual_native_SFD\":%0d,\"actual_all_SFD\":%0d,\"source_owner\":\"%0187h\"}",
  observed_legacy_owners,observed_source_owners,observed_source_events,observed_source_retired,
  observed_local_CQs,observed_HLS_retires,observed_dispatcher_retires,observed_local_active,observed_source_active,
  dut.executor.segmented.active,dut.executor.fault,actual_native_SFD_count,actual_SFD_count,observed_source_owner);
end
'''


def verify_executor(output,name,request=None,owner=None):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('SEGMENTED_EXECUTOR_NATIVE_RESULT ')]
    if len(rows)!=1:raise ValueError('missing actual retained-source/CQ observer')
    row=rows[0];retained=int(name in ['WRITE','SEND'])
    local=int(name in ['WRITE','SEND','CAS','FADD','READ','SEND_IMM','CAS_NO_RX_ATOMIC']or name.startswith('ZERO_'))
    expected=dict(legacy_owners=local-retained,source_owners=retained,source_events=retained,source_retired=retained,
        local_CQs=local,HLS_retires=local,dispatcher_retires=local,local_active=0,source_active=0,DUT_source_active=0,DUT_fault=0)
    if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('actual source/CQ ownership/counts:'+str(row))
    if retained:
        if request is None or owner is None or int(row['source_owner'],16)!=int(owner,16):
            raise ValueError('independent full748 CQ/source owner differs')
        expected_frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+request
        frames=old.old.link.frames(output)
        if frames!=[(0x2001,expected_frame),(0x2002,expected_frame)]or \
           (row['actual_native_SFD'],row['actual_all_SFD'])!=(2,2):
            raise ValueError('two genuine exact source XGMII/FCS/SFD/CDC/replay receipts required')
        row['actual_XGMII_frames']=[dict(tag=t,frame_hex=f.hex())for t,f in frames]
        row['physical_MAC_receipt_model']=False
    elif int(row['source_owner'],16):raise ValueError('legacy/RQ/service invented retained source authority')
    return row
