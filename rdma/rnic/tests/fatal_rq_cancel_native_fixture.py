# SPDX-License-Identifier: BSD-2-Clause-Views
"""All FEC-native40 controls plus two genuine fatal RQC command4 scenarios.

Old task/raw inputs/oracles remain; new cases clone its pre-replay proofs,
then obtain a real full-owner/nonce/flags63 RQC receipt before replay probes.
No internal guard/context/proof force and no fake CQ/STOP/global-drain/unpin.
"""
import json
import fatal_event_native_fixture as parent
ROOT=parent.ROOT;once=parent.once
RQC='dut.native.independent_receive_frontend.receive_queue_control'


def __getattr__(name):return getattr(parent,name)


DECLARATIONS=r'''
reg runtime_fatal_rq_cancel=0;
initial runtime_fatal_rq_cancel=$test$plusargs("FATAL_RQ_CANCEL");
integer fatal_rqc_cancel_handshakes=0,fatal_rqc_fetch_retirements=0;
always @(posedge clk)if(!rst)begin
 if(!fec_joins && dut.fatal_rq_cancel_authorized!==0)
  $fatal(1,"FATAL_RQC VALID/mailbox/host ACK cannot authorize RQC before actual upstream join");
 if(runtime_fatal_rq_cancel && dut.rq_cancel_valid && dut.rq_cancel_ready)begin
  if(fatal_rqc_cancel_handshakes || fec_joins!=1 || wrfatal_selected_taken!=1 ||
   dut.rq_cancel_qpn!==2 || dut.rq_cancel_pd!==17 || dut.rq_cancel_epoch!==64'h9123456700000001 ||
   !dut.completion_memory_drained || dut.rq_taken_count || dut.rq_active || fault)
   $fatal(1,"FATAL_RQC actual posted-owner cancellation requires genuine completed fatal join and physical drain");
  fatal_rqc_cancel_handshakes=fatal_rqc_cancel_handshakes+1;
 end
 if(runtime_fatal_rq_cancel && RQC.cfg_valid && RQC.cfg_ready && RQC.snapshot[1]==4)begin
  if(fatal_rqc_fetch_retirements || fatal_rqc_cancel_handshakes!=1 ||
   dut.fatal_rq_cancel_authorized!==4 || !RQC.command_safe || !RQC.parent_dma_drained ||
   RQC.fetch_queue_guard[2] || RQC.work_queue_guard[2] || RQC.s_fatal_cancel_wire_guard[2] ||
   RQC.completion_queue_guard[2] || RQC.endpoint_fault || RQC.wire_queue_guard[2]!==1'b1 ||
   !dut.native.queue_control.owner_active[2] || fault)
   $fatal(1,"FATAL_RQC real fetch retirement needs all original active guards clear while permanent quarantine remains");
  fatal_rqc_fetch_retirements=fatal_rqc_fetch_retirements+1;
 end
end
task fatal_rqc_guards;
 begin
  if(dut.write_abort_quarantined!==4 || local_execution_guard!==4 ||
   dut.m_write_admission_ready || dut.m_write_rx_ready ||
   dut.native.queue_control.wire_queue_guard[2]!==1'b1 || RQC.wire_queue_guard[2]!==1'b1 ||
   !dut.native.local_work_guard || dut.fatal_rq_cancel_fault || fault || m_cq_valid || dut.cq_busy ||
   wrfatal_selected_taken!=1 || fec_joins!=1 || fec_captures!=1 ||
   dut.rq_posted_count!=1 || dut.rq_taken_count || dut.rq_active ||
   wrx_commits!=(wrfatal_partial ? 1:0) || dut.m_write_expected_psn!==wrfatal_psn)
   $fatal(1,"FATAL_RQC cancellation is never new work admission, PSN advancement, error CQ or whole-device STOP");
 end
endtask
task fatal_rqc_cancel;
 integer i,deadline,fp,stall,probe;
 reg [31:0] value;reg [31:0] expected[0:14];
 begin
  fatal_rqc_guards;
  if(dut.fatal_rq_cancel_authorized!==4 || dut.rq_cancelled_count ||
   dut.rq_queue_guard!==4 || dut.rq_head_context!==lrx_owner || !RQC.owner_active[2] ||
   RQC.owner_cookie[2]!==64'hfedcba9889abcdf0 || RQC.owner_epoch[2]!==64'h9123456700000001)
   $fatal(1,"FATAL_RQC full current posted-RQ/SQC authority must still be held before real cancellation");
  read_reg(24'h405008,value);if(value!==63)$fatal(1,"FATAL_RQC same original RQC profile63 required");
  read_reg(24'h40500c,value);if(value!==1)$fatal(1,"FATAL_RQC real RQC must be idle before command");
  receive_control_sequence=receive_control_sequence+1;
  expected[0]=receive_control_sequence;expected[1]=4;expected[2]=2;expected[3]=17;
  expected[4]=1;expected[5]=32'h91234567;expected[6]=32'h89abcdf0;expected[7]=32'hfedcba98;
  expected[8]=32'h76542000;expected[9]=32'hfedcba98;expected[10]=1;expected[11]=1;expected[12]=0;
  expected[13]=32'h89abcdf1;expected[14]=32'hfedcba98;
  for(i=0;i<15;i=i+1)write_reg(24'h405040+4*i,expected[i],15,i%3,(i+1)%4);
  write_reg(24'h405010,receive_control_sequence,15,2,7);deadline=cycle+4000;value=0;
  while(!(value&2))begin
   if(cycle>deadline)$fatal(1,"FATAL_RQC actual cancellation reply bounded deadline auth%h state%h guards%h wire%h fc%h",dut.fatal_rq_cancel_authorized,RQC.state,RQC.work_queue_guard,RQC.s_fatal_cancel_wire_guard,fc);
   read_reg(24'h40500c,value);if(value&60)$fatal(1,"FATAL_RQC real mailbox transport fault");fatal_rqc_guards;
  end
  fp=$fopen("fatal-rqc-reply.hex","w");if(!fp)$fatal(1,"FATAL_RQC actual reply capture");
  for(i=0;i<15;i=i+1)begin
   read_reg(24'h405100+4*i,value);$fdisplay(fp,"%08h",value);
   if(value!==expected[i])$fatal(1,"FATAL_RQC every full-width owner/layout/producer/nonce reply word");
  end
  read_reg(24'h40513c,value);$fdisplay(fp,"%08h",value);if(value!==0)$fatal(1,"FATAL_RQC real cancellation semantic success");
  read_reg(24'h405140,value);$fdisplay(fp,"%08h",value);if(value!==63)$fatal(1,"FATAL_RQC genuine cancel proof flags63");
  read_reg(24'h405144,value);$fdisplay(fp,"%08h",value);if(value!==1)$fatal(1,"FATAL_RQC genuine final producer equals fetch consumer");
  read_reg(24'h405148,value);$fdisplay(fp,"%08h",value);if(value!==0)$fatal(1,"FATAL_RQC full64 consumer");$fclose(fp);
  if(fatal_rqc_cancel_handshakes!=1 || fatal_rqc_fetch_retirements!=1 || dut.rq_cancelled_count!=1 ||
   dut.rq_queue_guard || dut.rq_active || dut.native.receive_fetch_guard || dut.native.receive_queue_active ||
   dut.native.receive_queue_pending || RQC.owner_active || RQC.owner_cookie[2] || RQC.owner_pd[2] ||
   RQC.owner_dma[2] || RQC.owner_producer[2] || RQC.owner_epoch[2]!==64'h9123456700000001 ||
   !dut.native.queue_control.owner_active[2] || dut.native.queue_control.owner_cookie[2]!==wrfatal_selected[591:528])
   $fatal(1,"FATAL_RQC only genuine never-consumed posted RQ and fetch ownership may retire; SQC/epoch/quarantine remain");
  read_reg(24'h40300c,value);if(value!==0)$fatal(1,"FATAL_RQC cancellation cannot fabricate a native CQ event");
  write_reg(24'h405014,receive_control_sequence,15,7,2);
  read_reg(24'h40500c,value);if(value!==1 || dut.rq_cancel_block)$fatal(1,"FATAL_RQC exact reply ACK ends only RQC command");
  probe=0;
  for(stall=0;stall<1100;stall=stall+1)begin
   @(negedge clk);if(probe<260)begin {il,ik,id}=wrx_stimulus[261+probe];iv=1;end else iv=0;
   @(posedge clk);if(iv && ir)probe=probe+1;
   fatal_rqc_guards;
   if(dut.rq_cancelled_count!=1 || dut.rq_queue_guard || dut.rq_taken_count ||
    fatal_rqc_cancel_handshakes!=1 || fatal_rqc_fetch_retirements!=1 || reject_valid || m_write_fatal_selected_valid)
    $fatal(1,"FATAL_RQC post-cancel real replay cannot reopen quarantine or duplicate cancellation/CQ");
  end
  $display("FATAL_RQC_NATIVE_RESULT {\"pass_test\":true,\"partial\":%0d,\"actual_RQC_flags\":63,\"reply_words\":19,\"cancelled_RQ\":1,\"RQ_taken\":0,\"retired_fetches\":1,\"CQ\":0,\"quarantine\":4,\"SQC_retained\":true,\"global_STOP\":false,\"replay_words_accepted\":%0d}",wrfatal_partial,probe);
 end
endtask
'''


def additions(base):
    a=base.index('task run_write_fatal_native;');b=base.index('endtask',a)+len('endtask')
    task=once(base[a:b],'task run_write_fatal_native;','task run_write_fatal_rq_cancel;')
    a=task.index('  // Offer the complete authored correct MID');b=task.index('  $display("WRITE_FATAL_NATIVE_RESULT',a)
    task=task[:a]+'  probe_index=0;\n'+task[b:]
    task=once(task,' end\nendtask','  fatal_rqc_cancel;\n end\nendtask')
    return DECLARATIONS.replace('RQC.',RQC+'.')+'\n'+task+'\n'


def bench():
    base=parent.bench();t=once(base,'module tb;','module tb;\n'+additions(base))
    t=once(t,' run_write_fatal_native();',' if(runtime_fatal_rq_cancel)run_write_fatal_rq_cancel();else run_write_fatal_native();')
    # Explicit feature31 image, not a relaxed version/feature probe.
    old='if(value!==15)$fatal(1,"FEC actual native aperture features");'
    # The old task and its cloned sibling both call the same original FEC routine.
    t=once(t,old,old.replace('value!==15','value!==31'))
    if 'force 'in t:raise ValueError('no DUT context, guard, CQ, drain or proof injection')
    return t


def verify_fatal_cancel(output,posted,partial,run):
    old=parent.verify_fatal(output,posted,partial,run)
    if old['summary']['replay_words_accepted']!=0:raise ValueError('new scenario must snapshot old retained-RQ proofs before its own cancel/replay')
    rows=[json.loads(s.split(' ',1)[1])for s in output.splitlines()if s.startswith('FATAL_RQC_NATIVE_RESULT ')]
    wanted=dict(pass_test=True,partial=int(partial),actual_RQC_flags=63,reply_words=19,cancelled_RQ=1,
        RQ_taken=0,retired_fetches=1,CQ=0,quarantine=4,SQC_retained=True,global_STOP=False)
    if len(rows)!=1 or any(rows[0].get(k)!=v for k,v in wanted.items())or not 0<=rows[0]['replay_words_accepted']<=260:
        raise ValueError('actual per-RQ receipt/cardinality/permanent quarantine required')
    words=[int(l,16)for l in(run/'fatal-rqc-reply.hex').read_text().splitlines()]
    expected=[3,4,2,17,1,0x91234567,0x89abcdf0,0xfedcba98,0x76542000,0xfedcba98,1,1,0,0x89abcdf1,0xfedcba98,0,63,1,0]
    if words!=expected:raise ValueError('all19 actual AXI reply words must equal independent immutable full-owner/nonce/producer/flags oracle')
    old['fatal_RQC_cancellation']=rows[0]
    old['retained_RQ_snapshot_is_before_command4']=True
    old['never_consumed_RQ_retired_by_real_cancel']=True
    return old
