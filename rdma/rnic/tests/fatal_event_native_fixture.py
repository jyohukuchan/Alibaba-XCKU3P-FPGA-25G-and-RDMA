# SPDX-License-Identifier: BSD-2-Clause-Views
"""Extend the exact native40 bench with real FEC AXI readback/ACK, not Linux IO.

All original419 assertions/inputs/oracles/stalls remain. Only the two fatal
cases gain new checks. Host ACK while the observer stalls cannot duplicate
the actual join event, clear native quarantine or release the queued RQ.
"""
import json
import write_abort_scheduled_mac_native_fixture as parent
ROOT=parent.ROOT;once=parent.once


def __getattr__(name):return getattr(parent,name)


DECLARATIONS=r'''
integer fec_captures=0,fec_joins=0;
always @(posedge clk)if(!rst && runtime_write_fatal)begin
 if(dut.fatal_mailbox_valid && dut.fatal_mailbox_ready)begin
  if(fec_captures || dut.fatal_mailbox_selected!==wrfatal_selected)
   $fatal(1,"FEC actual mailbox must accept exactly one full native1000");
  fec_captures=fec_captures+1;
 end
 if(dut.fatal_join_valid && dut.fatal_join_ready)begin
  if(fec_joins || dut.fatal_join_selected!==wrfatal_selected)
   $fatal(1,"FEC actual upstream lease retires once after both receivers");
  fec_joins=fec_joins+1;
 end
end
task fec_native_guards;
 begin
  wrfatal_counts;
  if(dut.write_abort_quarantined!==4 || local_execution_guard!==4 ||
   dut.m_write_admission_ready || dut.m_write_rx_ready ||
   dut.native.queue_control.wire_queue_guard[2]!==1'b1 ||
   dut.native.independent_receive_frontend.receive_queue_control.wire_queue_guard[2]!==1'b1 ||
   !dut.native.local_work_guard || dut.native.fatal_events.fault || fault)
   $fatal(1,"FEC host notification ACK cannot release native/SQC/RQC guards or retained RQ");
  if(dut.native.queue_control.owner_cookie[2]!==wrfatal_selected[591:528] ||
   dut.native.queue_control.owner_epoch[2]!==wrfatal_selected[527:464] ||
   dut.native.queue_control.owner_pd[2]!==wrfatal_selected[463:448] ||
   !dut.native.queue_control.owner_active[2])
   $fatal(1,"FEC record must bind actual still-live full SQC owner, not RNC/message cookie");
 end
endtask
task fec_read_and_ack;
 integer i,fp;reg [31:0] value;reg [1023:0] snapshot;
 begin
  snapshot=0;fec_native_guards;
  read_reg(24'h406000,value);if(value!==32'h46454331)$fatal(1,"FEC actual native aperture ID");
  read_reg(24'h406004,value);if(value!==32'h00010000)$fatal(1,"FEC actual native aperture ABI");
  read_reg(24'h406008,value);if(value!==15)$fatal(1,"FEC actual native aperture features");
  read_reg(24'h40600c,value);if(value!==1)$fatal(1,"FEC actual retained event status before ACK");
  read_reg(24'h406018,value);if(value!==1)$fatal(1,"FEC actual strictly sequenced first event");
  read_reg(24'h406014,value);if(value!==0)$fatal(1,"FEC cannot invent an earlier host ACK");
  read_reg(24'h40601c,value);if(value!==0)$fatal(1,"FEC actual native mailbox fault before ACK");
  fp=$fopen("write-fatal-mmio.hex","w");
  for(i=0;i<32;i=i+1)begin
   read_reg(24'h406040+4*i,value);snapshot[i*32+:32]=value;$fdisplay(fp,"%08h",value);
   fec_native_guards;
  end
  $fclose(fp);
  if(snapshot!=={24'd0,wrfatal_selected} || fec_captures!=1 || fec_joins || wrfatal_selected_taken ||
   !m_write_fatal_selected_valid || m_write_fatal_selected!==wrfatal_selected)
   $fatal(1,"FEC all32 actual AXI words must equal genuine selected1000 with observer still stalled");
  read_reg(24'h406018,value);if(value!==1)$fatal(1,"FEC snapshot sequence changed while held");
  read_reg(24'h40600c,value);if(value!==1)$fatal(1,"FEC snapshot status changed before host ACK");
  write_reg(24'h406010,1,15,7,2);
  read_reg(24'h40600c,value);if(value!==0)$fatal(1,"FEC host ACK must clear only mailbox visibility");
  read_reg(24'h406014,value);if(value!==1)$fatal(1,"FEC actual host ACK readback");
  read_reg(24'h406018,value);if(value!==1)$fatal(1,"FEC host ACK must not reset event sequence");
  for(i=0;i<32;i=i+1)begin
   read_reg(24'h406040+4*i,value);if(value!==0)$fatal(1,"FEC acknowledged aperture must not expose stale visible payload");
   fec_native_guards;
  end
  repeat(77)begin
   @(negedge clk);fec_native_guards;
   if(fec_captures!=1 || fec_joins || wrfatal_selected_taken || !m_write_fatal_selected_valid ||
    m_write_fatal_selected!==wrfatal_selected || dut.fatal_mailbox_valid ||
    !dut.fatal_event_split.mailbox_taken || dut.fatal_event_split.observer_taken)
    $fatal(1,"FEC independent host ACK during observer stall cannot redeliver or release upstream lease");
  end
  write_reg(24'h406010,1,15,2,7);
  read_reg(24'h40600c,value);if(value!==0)$fatal(1,"FEC exact duplicate host ACK is idempotent");
  read_reg(24'h406014,value);if(value!==1)$fatal(1,"FEC duplicate ACK readback remains exact");
  fec_native_guards;
 end
endtask
task fec_finish;
 reg [31:0] value;
 begin
  fec_native_guards;
  if(fec_captures!=1 || fec_joins!=1 || wrfatal_selected_taken!=1 ||
   dut.fatal_join_valid || dut.fatal_mailbox_valid || m_write_fatal_selected_valid)
   $fatal(1,"FEC observer completion must finish sole actual upstream event without duplicates");
  read_reg(24'h40600c,value);if(value!==0)$fatal(1,"FEC event must stay acknowledged after observer retirement");
  read_reg(24'h406018,value);if(value!==1)$fatal(1,"FEC no invented successor event after observer retirement");
  read_reg(24'h40601c,value);if(value!==0)$fatal(1,"FEC no actual native mailbox fault after ACK");
  $display("FATAL_NATIVE_FEC_RESULT {\"pass_test\":true,\"words\":32,\"sequence\":1,\"host_ACK\":1,\"duplicate_ACK\":1,\"observer_stall_after_ACK\":77,\"native_mailbox_captures\":%0d,\"native_join_retirements\":%0d,\"quarantine\":4,\"retained_RQ\":1,\"CQ\":0}",fec_captures,fec_joins);
 end
endtask
'''


def bench():
    t=parent.bench()
    t=once(t,'module tb;','module tb;\n'+DECLARATIONS)
    t=once(t,'  wrx_fp=$fopen("write-fatal-selected.hex","w");',
        '  fec_read_and_ack;\n  wrx_fp=$fopen("write-fatal-selected.hex","w");')
    anchor='   $fatal(1,"FATAL real selected acknowledgment reopened native admission or duplicated owner/cancel/report");\n'
    return once(t,anchor,anchor+'  fec_finish;\n')


def verify_fatal(output,posted,partial,run):
    old=parent.verify_fatal(output,posted,partial,run)
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('FATAL_NATIVE_FEC_RESULT ')]
    wanted=dict(pass_test=True,words=32,sequence=1,host_ACK=1,duplicate_ACK=1,observer_stall_after_ACK=77,
        native_mailbox_captures=1,native_join_retirements=1,quarantine=4,retained_RQ=1,CQ=0)
    if rows!=[wanted]:raise ValueError('one exact actual native mailbox/ACK/quarantine proof required')
    words=[int(s,16)for s in (run/'write-fatal-mmio.hex').read_text().splitlines()]
    if len(words)!=32 or any(not 0<=v<2**32 for v in words):raise ValueError('actual32 full AXI readback words required')
    selected=int((run/'write-fatal-selected.hex').read_text(),16)
    if sum(v<<(32*i)for i,v in enumerate(words))!=selected:raise ValueError('every actual AXI/readback selected1000 bit must agree')
    old['fatal_event_mailbox']=wanted
    return old
