# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full generated-native SEND/RECV followed by a real no-packet RQ cancel.

Physical host/MAC/drain delivery remain models. No production force, fake CQ
or receipt, queue-count drain substitution or changed HLS is allowed.
"""
import json
import native_independent_queues_fixture as split

def case(base_case):
    m=split.old.old.qp.main
    tb,words,records,receive_records,ack=split.case(base_case)
    tb=m.sq.once(tb,'.SEPARATE_RQ_ENABLE(1)',
        '.SEPARATE_RQ_ENABLE(1),.RECV_CANCEL_ENABLE(1)')
    w=m.shared.codec.candidate(wr_id=0xf123456789abc003,sequence=3,epoch=0x9123456700000001,
        local_address=0xfedcba9876543210,local_key=8,remote_address=0,remote_key=0,
        opcode=4,flags=1,length=128)
    encoded=m.shared.codec.oracle(w)
    literal=f"512'h{int.from_bytes(encoded,'little'):0128x}"
    tb=m.sq.once(tb,'task rq_command;\n input [1:0] op;input [63:0] producer;',
        'task rq_command;\n input [2:0] op;input [63:0] producer;')
    tb=m.sq.once(tb,'if(op==3)begin receive_words[13]=receive_control_sequence;receive_words[14]=32\'ha1234567;end',
        '''if(op==3)begin receive_words[13]=receive_control_sequence;receive_words[14]=32'ha1234567;end
  if(op==4)begin receive_words[13]=32'h89abcdf1;receive_words[14]=32'hfedcba98;end''')
    tb=m.sq.once(tb,'write_reg(24\'h405010,receive_control_sequence,15,0,1);split_deadline=cycle+4000;sq_value=0;',r'''
  write_reg(24'h405010,receive_control_sequence,15,0,1);
  if(op==4)begin
   repeat(60)begin
    @(negedge clk);
    if(!dut.rq_cancel_block || dut.rq_cancelled_count || parent_dma_drained ||
       dut.native.receive_fetch_guard!==8'h04 || dut.rq_posted_count!=2 ||
       dut.native.rq_control_response_valid || dut.native.rq_cfg_valid || fault)
     $fatal(1,"whole native cancelled without actual parent DMA drain");
   end
   hold_cancel_fetch=0;cancel_snapshot_file=$fopen("cancel-reply.hex","w");
   if(!cancel_snapshot_file)$fatal(1,"real native cancel reply snapshot");
  end
  split_deadline=cycle+4000;sq_value=0;''')
    tb=m.sq.once(tb,'if(sq_value!==receive_words[split_word])$fatal(1,"actual RQC1 full owner/layout/nonce");',
        'if(sq_value!==receive_words[split_word])$fatal(1,"actual RQC1 full owner/layout/nonce");\n'
        '   if(op==4)$fdisplay(cancel_snapshot_file,"%08h",sq_value);')
    tb=m.sq.once(tb,'read_reg(24\'h40513c,sq_value);if(sq_value)$fatal(1,"actual RQC1 semantic error%0d",sq_value);',
        'read_reg(24\'h40513c,sq_value);if(sq_value)$fatal(1,"actual RQC1 semantic error%0d",sq_value);\n'
        '  if(op==4)$fdisplay(cancel_snapshot_file,"%08h",sq_value);')
    tb=m.sq.once(tb,'if(sq_value!==(op==1 ? 7:op==3 ? 31:0))',
        'if(sq_value!==(op==1 ? 7:op==3 ? 31:op==4 ? 63:0))')
    tb=m.sq.once(tb,'if(op!=2)begin',
        'if(op==4)$fdisplay(cancel_snapshot_file,"%08h",sq_value);\n  if(op!=2)begin')
    tb=m.sq.once(tb,'if(sq_value!==(op==1 ? 0:producer))$fatal(1,"actual RQC1 consumer");',
        'if(sq_value!==(op==1 ? 0:producer))$fatal(1,"actual RQC1 consumer");\n'
        '   if(op==4)$fdisplay(cancel_snapshot_file,"%08h",sq_value);')
    tb=m.sq.once(tb,'if(sq_value)$fatal(1,"actual RQC1 consumer high");',
        'if(sq_value)$fatal(1,"actual RQC1 consumer high");\n'
        '   if(op==4)begin $fdisplay(cancel_snapshot_file,"%08h",sq_value);$fclose(cancel_snapshot_file);end')
    tb=m.sq.once(tb,'check_ring();rq_command(3,2);sq_command(3,2,0,31,2);',r'''
// Reuse coherent slot0 for an actual third receive, with NO peer packet.
expected_recv_msn=3;
hold_cancel_fetch=1;
receive_records[0]=CANCEL_RECORD;
cancel_snapshot_file=$fopen("cancel-record.hex","w");
if(!cancel_snapshot_file)$fatal(1,"third coherent receive record snapshot");
$fdisplay(cancel_snapshot_file,"%0128h",receive_records[0]);$fclose(cancel_snapshot_file);
for(split_word=0;split_word<64;split_word=split_word+1)
 pcie_host[16512+split_word]=receive_records[0][split_word*8+:8];
rq_command(2,3);split_deadline=cycle+5000;
while(!cancel_fetch_held)begin
 if(cycle>split_deadline)$fatal(1,"whole native third coherent fetch not issued");@(negedge clk);
end
if(dut.rq_taken_count!=2 || dut.rq_active || dut.rq_posted_count!=2 || parent_dma_drained ||
   dut.rq_placement_count!=2 || dut.rq_core_proof_count!=2 || dut.cq_busy ||
   dut.native.receive_fetch_guard!==8'h04 || cancel_owner_seen || fault)
 $fatal(1,"whole native cancellation input was not a genuine in-flight coherent fetch");
read_reg(24'h405008,sq_value);if(sq_value!==3)$fatal(1,"real optional RQC cancel capability");
rq_command(4,3);
if(dut.rq_cancelled_count!=1 || dut.rq_posted_count!=3 || !cancel_owner_seen || dut.rq_queue_guard || dut.rq_active ||
   dut.native.receive_queue_active || dut.native.receive_queue_pending || dut.native.receive_fetch_guard ||
   dut.native.rq_control_owner_active || dut.rq_taken_count!=2 || dut.rq_placement_count!=2 ||
   dut.rq_core_proof_count!=2 || dut.receive_ack_lifetime.ack_owner.frame_count!=2 ||
   dut.rq_cancel_block || dut.cq_busy || fault)
 $fatal(1,"whole native cancellation fabricated packet/CQ or retained queue authority");
read_reg(24'h403014,sq_value);if(sq_value!==4)$fatal(1,"cancel fabricated native CQ completion");
$display("NATIVE_RQ_CANCEL_RESULT {\"pass_test\":true,\"pending_WQE_sequence\":3,\"actual_RQC_features\":3,\"cancelled_posted\":1,\"actual_reply_flags\":63,\"native_CQ_events\":4,\"no_packet_or_fake_CQ\":true,\"parent_drain_withheld\":true}");
check_ring();sq_command(3,2,0,31,2);
'''.replace('CANCEL_RECORD',literal))
    tb=m.sq.once(tb,'if(dut.rq_posted_count!=2 || dut.rq_taken_count!=2',
        'if(dut.rq_posted_count!=3 || dut.rq_taken_count!=2')
    tb=m.sq.once(tb,'(expected_recv_msn-1)*64','((expected_recv_msn-1)%2)*64')
    monitor=r'''
integer cancel_snapshot_file;
reg cancel_owner_seen=0;
reg hold_cancel_fetch=0,cancel_fetch_held=0;
always @(posedge clk)if(!rst && dut.rq_post_valid && dut.rq_post_ready && dut.rq_post_context[523:460]==3)begin
 if(dut.rq_post_context[587:524]!==64'hf123456789abc003 ||
    dut.rq_post_context[459:396]!==64'h9123456700000001 || dut.rq_post_context[395:372]!==2 ||
    dut.rq_post_context[371:356]!==17 || dut.rq_post_context[355:340]!==5 ||
    dut.rq_post_context[339:324]!==4 || dut.rq_post_context[323:308]!==1 ||
    dut.rq_post_context[307:276]!==128 || dut.rq_post_context[275:244]!==8 ||
    dut.rq_post_context[243:180]!==64'hfedcba9876543210 || dut.rq_post_context[179:116]!==64'h210 ||
    dut.rq_post_context[115:20]!==0 || dut.rq_post_context[19:0]!==3 || cancel_owner_seen)
  $fatal(1,"third cancelled receive did not traverse real fetch/SAME-MR admission");
 cancel_owner_seen<=1;
end
'''
    tb=m.sq.once(tb,'reg [144:0] stimulus',monitor+'\nreg [144:0] stimulus')
    tb=m.sq.once(tb,'tlp_s_axis_rd_req_tx_seq_num=seq;tlp_s_axis_rd_req_tx_seq_num_valid=1;',r'''
  // Withhold only the physical root-complex completion/TX sequence for the
  // third real coherent fetch. The actual PCIe engine/parent guard must stay
  // busy; never assign or mask its derived drain/proof outputs.
  if(first_address==64'hfedcba9876542000 && hold_cancel_fetch)begin
   cancel_fetch_held=1;while(hold_cancel_fetch)@(negedge clk);cancel_fetch_held=0;
  end
  tlp_s_axis_rd_req_tx_seq_num=seq;tlp_s_axis_rd_req_tx_seq_num_valid=1;''')
    if 'force ' in tb:raise ValueError('no production force in whole native cancellation')
    return tb,words,records,receive_records,ack

def verify(output):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RQ_CANCEL_RESULT ')]
    if len(rows)!=1 or not rows[0]['pass_test'] or rows[0]['actual_reply_flags']!=63 or not rows[0]['no_packet_or_fake_CQ']:
        raise ValueError('missing whole native cancellation certificate')
    return rows[0]
