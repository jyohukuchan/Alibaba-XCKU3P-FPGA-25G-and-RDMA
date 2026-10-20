# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full native mixed Atomic/WRITE with actual MAC SFD/FCS/CDC after bootstrap.

Normal requester regression retains its old MAC-pin model. ATOMIC_ONLY posts
NO WQE/RQ/CQ and uses real XGMII/SFD/CDC. Physical root/host/peer/PHY/PTP input
remain models. Every host write/fence is checked against independent values.
"""
import struct
import sys
import atomic_native_full_sources as source
import atomic_native_owned_fixture as old
import atomic_mac_wire_fixture as link

ROOT=source.ROOT;once=source.candidate.once
sys.path.insert(0,str(ROOT/'rdma/host'))
import rocev2_wire as wire
BASE=64 if False else 0xfedcba9876543000
FIRST_OLD=int.from_bytes(bytes(((n*37)^0x5a)&255 for n in range(4101,4109)),'little')
NORMAL_VALUE=0x0123456789abcdef


def packet(op,psn,va,payload):
    bth=bytes([op,0])+struct.pack('!H',0xffff)+bytes([0])+int(2).to_bytes(3,'big')+bytes([0x80])+psn.to_bytes(3,'big')
    body=bth+struct.pack('!QI',va,8)+(struct.pack('!I',len(payload))if op==0x0a else b'')+payload
    length=32+len(body)
    ip=bytearray(struct.pack('!BBHHHBBHII',0x45,0,length,0,0x4000,64,17,0,0xc6120b01,0xc6120b02))
    ip[10:12]=wire.internet_checksum(ip).to_bytes(2,'big')
    p=bytes(ip)+struct.pack('!HHHH',4791,4791,length-20,0)+body+bytes(4)
    return bytes.fromhex('8af3fbb97531b8830367c5d00800')+p[:-4]+wire.icrc_ipv4(p)


def input_frames():
    first=packet(0x14,0x987654,BASE+0x218,struct.pack('!QQ',1,0))
    return [first,first,packet(0x0a,0x987655,BASE+0x220,struct.pack('<Q',NORMAL_VALUE)),
        packet(0x14,0x987656,BASE+0x218,struct.pack('!QQ',3,0))]


def fixtures():
    words=[]
    for frame in input_frames():
        for off in range(0,len(frame),16):
            b=frame[off:off+16]
            words.append(int.from_bytes(b.ljust(16,bytes(1)),'little')|(((1<<len(b))-1)<<128)|(int(off+16>=len(frame))<<144))
    return ''.join(f'{w:037x}\n'for w in words)


def bench():
    t=old.bench()
    t=once(t,".atomic_lease_guard(1'b0),",'')
    # This marker describes source selection, not Atomic execution in the
    # two unchanged ordinary requester regression cases.
    t=once(t,r'\"Atomic_RX_selected\":false',r'\"Atomic_RX_selected\":true')
    link_text=link.LINK.replace('always #1.28 mac_clk=~mac_clk;',
        'always #1.28 if(real_mac_mode || rst)mac_clk=~mac_clk;')
    t=once(t,'module tb;','module tb;\nreg real_mac_mode=0,hold_atomic_wire=0;\n'+link_text+CONNECTIONS+TASKS)
    t=once(t,'.m_axis_mac_tx_tready(tr),',
        '.m_axis_mac_tx_tready(real_mac_mode ? link_s_ready && !hold_atomic_wire:tr),')
    for name,signal in [('tag','link_m_cpl_tag'),('ts','link_m_cpl_ts'),('valid','link_m_cpl_valid')]:
        t=once(t,'.s_axis_mac_cpl_'+name+'(s_axis_mac_cpl_'+name+'),',
            '.s_axis_mac_cpl_'+name+'(real_mac_mode ? '+signal+':s_axis_mac_cpl_'+name+'),')
    t=once(t,"assign tv=mac_tx_valid && mac_tx_user[16:1]==16'h4000;",
        "assign tv=mac_tx_valid && mac_tx_user[16:1]==16'h4000 && !real_mac_mode;")
    t=once(t,'always @(posedge clk) if(!rst) begin\n if(mac_tx_valid && tr)',
        'always @(posedge clk) if(!rst && !real_mac_mode) begin\n if(mac_tx_valid && tr)')
    t=once(t,'always @(negedge clk) if(!rst) begin\n if(s_axis_mac_cpl_valid',
        'always @(negedge clk) if(!rst && !real_mac_mode) begin\n if(s_axis_mac_cpl_valid')
    # Real registration permission, not a bypass or manufactured MR result.
    t=once(t,'host_api(2,OWNER0,0,0,17,7,0,0,8,0);','host_api(2,OWNER0,0,0,17,15,0,0,8,0);')
    t=once(t,'if(idx<4093 || idx>=4158 || tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8]!==pcie_pattern(byte_pos))',
        'if(real_mac_mode ? !atomic_write_byte_ok(idx,tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8]) :\n'
        ' (idx<4093 || idx>=4158 || tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8]!==pcie_pattern(byte_pos)))')
    t=once(t,'if(bytes_count!=1 || first_address!==64\'h8123456789abcffd || posted_bytes!=65)',
        "if(real_mac_mode ? (bytes_count!=1 || posted_bytes!=8 || pcie_host_index(first_address)!=(atomic_phase==3 ? 4109:4101) || atomic_phase==2) :\n"
        " (bytes_count!=1 || first_address!==64'h8123456789abcffd || posted_bytes!=65))")
    first=t.index('enable=1;sq_command(2,1,0,0,0);')
    last=t.index(' $display("ATOMIC_NATIVE_OWNED_STAGE ',first)
    t=t[:first]+'enable=1;\nif(!$test$plusargs("ATOMIC_ONLY"))begin\n'+t[first+len('enable=1;'):last]+'end\n'+t[last:]
    first=t.index(' $display("ATOMIC_NATIVE_OWNED_STAGE ')
    finish=t.index('$finish;',first)
    t=t[:finish]+'end\n'+t[finish:]
    t=once(t,' $display("ATOMIC_NATIVE_OWNED_STAGE ',
        ' if($test$plusargs("ATOMIC_ONLY"))run_native_atomic();\n if(!$test$plusargs("ATOMIC_ONLY"))begin\n $display("ATOMIC_NATIVE_OWNED_STAGE ')
    if 'force 'in t or 's_atomic_retire_valid='in t:raise ValueError('no force/test retirement')
    return t.replace('FIRST_OLD_VALUE',f"64'h{FIRST_OLD:016x}").replace('NORMAL_VALUE',f"64'h{NORMAL_VALUE:016x}")


CONNECTIONS=r'''
assign link_s_data=mac_tx_data;assign link_s_keep=mac_tx_keep;
assign link_s_valid=real_mac_mode && !hold_atomic_wire && mac_tx_valid;
assign link_s_last=mac_tx_last;assign link_s_user=mac_tx_user;
assign link_m_cpl_ready=real_mac_mode && s_axis_mac_cpl_ready;
integer atomic_phase=0,atomic_input_i,atomic_deadline,atomic_retirements=0,atomic_core_count=0;
reg [63:0] expected_atomic_write=0;
reg [144:0] atomic_inputs[0:23];
always @(posedge clk)if(!rst && real_mac_mode)begin
 if(dut.m_atomic_core_done_valid && dut.s_atomic_core_done_ready)begin
  $display("NATIVE_ATOMIC_CORE %056h",dut.m_atomic_core_done);atomic_core_count=atomic_core_count+1;
 end
 if(dut.s_atomic_retire_valid && dut.m_atomic_retire_ready)begin
  $display("NATIVE_ATOMIC_RETIRE %036h %056h",dut.s_atomic_retire_owner,dut.s_atomic_retire_core);
  atomic_retirements=atomic_retirements+1;
 end
 if(fault)$display("NATIVE_ATOMIC_FAULT rx=%b guard=%h ctx=%b",dut.atomic_rx_guard,fc,p_atomic_admission_valid);
end
function atomic_write_byte_ok;
 input integer idx;input [7:0] value;
 begin
  atomic_write_byte_ok=0;
  if((atomic_phase==1 || atomic_phase==4) && idx>=4101 && idx<4109)
   atomic_write_byte_ok=value===((expected_atomic_write>>((idx-4101)*8))&255);
  if(atomic_phase==3 && idx>=4109 && idx<4117)
   atomic_write_byte_ok=value===((NORMAL_VALUE>>((idx-4109)*8))&255);
 end
endfunction
function [63:0] atomic_load;
 input integer offset;integer n;
 begin for(n=0;n<8;n=n+1)atomic_load[n*8+:8]=pcie_host[offset+n];end
endfunction
'''

TASKS=r'''
task atomic_input;
 input integer index;
 begin
  for(atomic_input_i=index*6;atomic_input_i<index*6+6;atomic_input_i=atomic_input_i+1)begin
   @(negedge clk);{il,ik,id}=atomic_inputs[atomic_input_i];iv=1;mac_rx_user=0;
   @(posedge clk);while(!ir)@(posedge clk);
  end
  @(negedge clk);iv=0;il=0;
 end
endtask
task atomic_wait;
 input integer wanted;
 begin
  atomic_deadline=cycle+5000;
  while(atomic_retirements!=wanted || dut.atomic_lease_guard || !response_tx_quiescent)begin
   if(cycle>atomic_deadline || fault)$fatal(1,"actual native Atomic service/core/MAC retirement deadline phase%0d fc%h",atomic_phase,fc);
   @(negedge clk);
  end
 end
endtask
task run_native_atomic;
 integer n;
 begin
  $readmemh("atomic-input.hex",atomic_inputs);
  if(sq_fetch_count || local_committed_count || dut.cq_busy || dut.rq_active || !p_atomic_admission_valid ||
    mac_cpl_rd!=mac_cpl_wr || mac_in_frame || s_axis_mac_cpl_valid)
   $fatal(1,"Atomic test requires actual live QP, NO posted WQE/RQ/CQ or stale MAC receipt");
  if(atomic_load(4101)!==FIRST_OLD_VALUE)$fatal(1,"actual host initial Atomic value");
  @(negedge clk);real_mac_mode=1;hold_atomic_wire=1;atomic_phase=1;expected_atomic_write=FIRST_OLD_VALUE+1;
  atomic_input(0);
  // True native SQC attempt while actual packet/core/MAC owner is retained.
  sq_command(3,0,35,0,0);
  if(sq_control_owner_active!==4 || !dut.atomic_lease_guard || p_atomic_bound_epoch!==64'h9123456700000001 ||
    atomic_retirements || dut.cq_busy)$fatal(1,"native Atomic lease allowed QP/SQC release");
  hold_atomic_wire=0;atomic_wait(1);
  if(atomic_load(4101)!==FIRST_OLD_VALUE+1)$fatal(1,"native FADD actual host value");
  atomic_phase=2;atomic_input(1);atomic_wait(2);
  if(atomic_load(4101)!==FIRST_OLD_VALUE+1)$fatal(1,"duplicate executed native RMW twice");
  atomic_phase=3;atomic_input(2);atomic_deadline=cycle+5000;
  while(completed!=1 || !response_tx_quiescent || dut.atomic_lease_guard)begin
   if(cycle>atomic_deadline || fault)$fatal(1,"mixed native WRITE completion deadline");@(negedge clk);
  end
  if(atomic_load(4109)!==NORMAL_VALUE)$fatal(1,"mixed normal native WRITE target");
  atomic_phase=4;expected_atomic_write=FIRST_OLD_VALUE+4;
  atomic_input(3);atomic_wait(3);
  if(atomic_load(4101)!==FIRST_OLD_VALUE+4 || atomic_core_count!=3 || actual_Atomic_SFD_count!=3 ||
    actual_native_SFD_count!=1 || sq_fetch_count || local_committed_count || dut.cq_busy || dut.rq_active ||
    read_tlps!=5 || write_tlps!=3 || fences!=3)
   $fatal(1,"native Atomic/common-MR/DMA/MAC/no-fake-WQE proof incomplete");
  for(n=0;n<16384;n=n+1)begin
   if(pcie_posted_valid[n])$fatal(1,"unfenced native host byte");
   if(n>=4101 && n<4109)begin
    if(pcie_host[n]!==(((FIRST_OLD_VALUE+4)>>((n-4101)*8))&255))$fatal(1,"native Atomic target byte");
   end else if(n>=4109 && n<4117)begin
    if(pcie_host[n]!==((NORMAL_VALUE>>((n-4109)*8))&255))$fatal(1,"mixed WRITE byte");
   end else if(pcie_host[n]!==(((n*37)^8'h5a)&255))$fatal(1,"native Atomic/WRITE neighbor clobber");
  end
  check_ring();
  $display("NATIVE_ATOMIC_RESULT {\"pass_test\":true,\"Atomic_requests\":3,\"normal_WRITEs\":1,\"retired\":%0d,\"core_receipts\":%0d,\"actual_Atomic_SFD\":%0d,\"actual_native_SFD\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"no_posted_WQE_RQ_CQ\":true,\"Atomic_MAC_receipt_model\":false,\"physical_host_PHY_peer_PTP_input_models\":true}",
   atomic_retirements,atomic_core_count,actual_Atomic_SFD_count,actual_native_SFD_count,read_tlps,write_tlps,fences);
 end
endtask
'''
