#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Whole checked-frame WRITE controller/MR/RQ/backend/ACK real RTL coupling.

Exact C++ HLS traces, native shadow PSN endpoint, descriptor/host order and
CQ consumer remain boundary models. No live generated-HLS/native/TLP/board
claim. Positive ACK cannot pass before actual backend EOF/fence status;
frontend DONE and modeled native PSN commit must transfer on the SAME edge.
"""
import ast
from pathlib import Path
import struct
import sys
import tempfile
import probe_remote_write_memory as prior

ROOT=prior.ROOT;once=prior.authorization.queue.once
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_controller_leaves as leaves
sys.path.insert(0,str(ROOT/'rdma/host'))
from rocev2_wire import internet_checksum,icrc_ipv4

CTRL=ROOT/'rdma/rnic/rtl/rocev2_segmented_write_controller.v'
ICRC=ROOT/'rdma/rtl/rocev2_ipv4_icrc.v'
FIFO=ROOT/'external/corundum/fpga/lib/axis/rtl/axis_fifo.v'


def raw_packet(payload,index,imm):
    count=len(payload)if index<2 else 1;psn=2+index;pad=(-count)&3
    opcode=6 if index==0 else 9 if index==2 and imm else 8 if index==2 else 7
    body=bytes([opcode,0x40|(pad<<4)])+b'\xff\xff\x00\x00\x00\x02\x80'+psn.to_bytes(3,'big')
    if index==0:body+=struct.pack('!QII',0xe23456789abcdef0,0x81234567,8193)
    if index==2 and imm:body+=struct.pack('!I',0x89abcdf1)
    body+=payload
    ip=bytearray(struct.pack('!BBHHHBBHII',0x45,0,32+len(body),1,0x4000,64,17,0,0xc6120b01,0xc6120b02))
    ip[10:12]=internet_checksum(ip).to_bytes(2,'big')
    packet=bytes(ip)+struct.pack('!HHHH',49152,4791,len(body)+12,0)+body+bytes(4)
    return packet[:-4]+icrc_ipv4(packet)


RAW=r'''
reg [127:0] raw_data=0;reg [15:0] raw_keep=0;reg raw_valid=0,raw_last=0;
wire raw_ready,checked_valid,checked_ready,checked_last;
wire [127:0] checked_data,replay_data;wire [15:0] checked_keep,replay_keep;
wire replay_valid,replay_last;reg replay_ready=0;
wire crc_good,crc_bad,crc_overflow,ctrl_tx_release;
wire [7:0] ctrl_queue_guard;wire ctrl_configuration_guard,ctrl_fault;
reg [144:0] input_words[0:259];integer raw_words=0,raw_index=0,replay_index=0,replayed_frames=0,replayed_bytes=0,CRC_frames=0;
reg replay_complete=0;
integer actual_hls_rq_owners=0;
wire [355:0] native_context={4'd7,48'h020000000001,48'h020000000002,32'hc6120b01,32'hc6120b02,
 24'd196,64'h8000000000000001,g_trusted_epoch,g_trusted_pd,g_trusted_qpn};
assign done_ready=e_m_done_token[39:16]===g_trusted_expected_psn && e_m_done_proofs===8'h0f &&
 e_m_done_token[423:400]===g_trusted_qpn && e_m_done_token[399:384]===g_trusted_pd && e_m_done_token[383:320]===g_trusted_epoch;
assign e_busy=controller.memory_busy;assign e_fault=controller.memory_fault;assign e_fault_code=controller.memory_fault_code;
assign e_configuration_guard=controller.memory_guard;assign e_queue_guard=controller.memory_queue_guard;
assign e_done_count=controller.packet_memory.done_count;assign e_retired_count=controller.packet_memory.retired_count;
assign g_fault=controller.front_fault;assign g_fault_code=controller.front_fault_code;
assign g_configuration_guard=controller.front_guard;assign g_queue_guard=controller.front_queue_guard;
always @(negedge clk)if(!rst)replay_ready=(cycles%7)!=0;
always @(posedge clk)if(!rst)begin
 if(ctrl_hls_rq_valid)begin
  if(ctrl_hls_rq_owner!=={4'd0,token[39:16],token[71:40],rq} || mode!=1 || packet_index!=2)
   $fatal(1,"independent full680 genuine LAST-only HLS RQ owner oracle");
  actual_hls_rq_owners=actual_hls_rq_owners+1;
 end
 if(crc_good)CRC_frames=CRC_frames+1;
 if(crc_bad || crc_overflow)$fatal(1,"actual input CRC drop/overflow");
 if(replay_valid && replay_ready)begin
  if({replay_last,replay_keep,replay_data}!==input_words[replay_index])$fatal(1,"exact whole checked frame replay byte/KEEP/EOF oracle");
  replay_index=replay_index+1;replayed_bytes=replayed_bytes+$countones(replay_keep);
  if(replay_last)begin if(replay_index!=raw_words)$fatal(1,"whole replay extent");replay_complete=1;replayed_frames=replayed_frames+1;end
 end
 if(e_m_done_valid && done_ready && done_allow)g_trusted_expected_psn<=e_m_done_token[39:16]+24'd1;
end
rocev2_ipv4_icrc #(.TX_MODE(0)) actual_input_integrity(
 .clk(clk),.rst(rst),.s_axis_tdata(raw_data),.s_axis_tkeep(raw_keep),.s_axis_tvalid(raw_valid),.s_axis_tready(raw_ready),
 .s_axis_tlast(raw_last),.s_axis_tuser(1'b0),.m_axis_tdata(checked_data),.m_axis_tkeep(checked_keep),
 .m_axis_tvalid(checked_valid),.m_axis_tready(checked_ready),.m_axis_tlast(checked_last),
 .status_good_frame(crc_good),.status_bad_frame(crc_bad),.status_overflow(crc_overflow));
'''


def bench(ack,queue):
    t=prior.bench(ack,queue)
    for anchor in ['rocev2_remote_write_message_guard #(', 'rocev2_remote_write_memory packet_memory(']:
        a=t.index(anchor);b=t.index(');',a)+2;t=t[:a]+t[b:]
    mapping=dict(clk='clk',rst='rst',enable='enable',parent_fault='fault || a_fault || q_fault || n_fault',
        trusted_valid='g_trusted_valid',trusted_context='native_context',trusted_expected_psn='g_trusted_expected_psn',
        s_rx_data='checked_data',s_rx_keep='checked_keep',s_rx_valid='checked_valid',s_rx_ready='checked_ready',s_rx_last='checked_last',
        m_hls_rx_data='replay_data',m_hls_rx_keep='replay_keep',m_hls_rx_valid='replay_valid',m_hls_rx_ready='replay_ready',m_hls_rx_last='replay_last',
        **{'m_mr_'+n:'g_m_mr_'+n for n in ['pd','key','address','length','operation','tag','valid','ready']},
        **{'s_mr_'+n:'g_s_mr_'+n for n in ['tag','error','offset','address','length','valid','ready']},
        s_rq_context='q_m_notice_head_context',s_rq_valid='q_m_notice_head_valid',m_notice_context='g_m_notice_context',
        m_notice_last_psn='g_m_notice_last_psn',m_notice_valid='g_m_notice_valid',m_notice_ready='q_s_write_notice_ready',
        s_notice_retire_context='q_m_write_retire_context',s_notice_retire_valid='q_m_write_retire_valid',s_notice_retire_ready='q_m_write_retire_ready',
        m_hls_owner='e_m_hls_owner',m_hls_owner_valid='e_m_hls_owner_valid',m_hls_owner_ready='e_m_hls_owner_ready',
        s_hls_done='e_s_hls_done',s_hls_done_valid='e_s_hls_done_valid',s_hls_done_ready='e_s_hls_done_ready',
        m_hls_rq_owner='ctrl_hls_rq_owner',m_hls_rq_owner_valid='ctrl_hls_rq_valid',m_hls_rq_owner_ready="1'b1",
        m_rq_placement_context='q_s_placement_context',m_rq_placement_length='q_s_placement_length',
        m_rq_placement_notification='q_s_placement_notification',m_rq_placement_psn='q_s_placement_psn',
        m_rq_placement_valid='q_s_placement_valid',m_rq_placement_ready='q_s_placement_ready',
        **{'s_hls_'+n:'e_s_hls_'+n for n in ['command','command_valid','command_ready','data','keep','last','valid','ready']},
        **{'m_command_'+n:'e_m_command_'+n for n in ['write','offset','length','key','tag','valid','ready']},
        **{'m_'+n:'e_m_'+n for n in ['data','keep','last','valid','ready']},
        **{'s_status_'+n:'n_m_status_'+n for n in ['tag','error','valid','ready']},
        **{'m_ack_owner'+n:'a_s_write_owner'+n for n in ['','_notify','_rq_context','_valid','_ready']},
        m_ack_core='a_s_write_core_data',m_ack_core_valid='a_s_write_core_valid',m_ack_core_ready='a_s_write_core_ready',
        s_ack_done='a_m_write_done_data',s_ack_done_valid='a_m_write_done_valid',s_ack_done_ready='a_m_write_done_ready',
        m_ack_retire_token='retire_token',m_ack_retire_valid='retire_valid',m_ack_retire_ready='a_s_write_retire_ready && retire_allow',
        m_packet_commit_token='e_m_done_token',m_packet_commit_msn='e_m_done_msn',m_packet_commit_proofs='e_m_done_proofs',
        m_packet_commit_valid='e_m_done_valid',m_packet_commit_ready='done_ready && done_allow',m_tx_release='ctrl_tx_release',
        m_reject_ready="1'b0",message_context='g_message_context',message_active='g_message_active',
        configuration_guard='ctrl_configuration_guard',queue_guard='ctrl_queue_guard',fault='ctrl_fault',
        accepted_packets='g_accepted_packets',completed_packets='g_completed_packets',completed_messages='g_completed_messages')
    block=prior.instance(CTRL.read_text(),'rocev2_segmented_write_controller','controller','ctrl_',mapping,
        ".INITIAL_MESSAGE_COOKIE(64'hfedcba9876543212),.INITIAL_PACKET_TAG(16'd4)")
    # Genuine RQ placement now comes from the actual controller, not a fixture
    # copy of its parsed data. Remove only the old boundary MODEL drivers.
    for n in ['q_s_placement_context','q_s_placement_length','q_s_placement_notification','q_s_placement_psn','q_s_placement_valid']:
        t,count=__import__('re').subn(r'\breg (\[[^]]+\]\s+)?'+n+r'=0;',lambda m:'wire '+(m[1]or'')+n+';',t)
        if count!=1:raise ValueError('exact old placement model declaration required:'+n)
    t=once(t,'reg q_s_placement_notification_flags=0;','wire [7:0] q_s_placement_notification_flags=3;')if 'reg q_s_placement_notification_flags=0;'in t else once(t,'reg [7:0] q_s_placement_notification_flags=0;','wire [7:0] q_s_placement_notification_flags=3;')
    t=once(t,'wire done_ready,retire_valid,actual_cpl_ready;',
        'wire done_ready,retire_valid,actual_cpl_ready;wire [679:0] ctrl_hls_rq_owner;wire ctrl_hls_rq_valid;')
    t=once(t,'always #2 clk=~clk;',block+'\n'+RAW+'\nalways #2 clk=~clk;')
    t=__import__('re').sub(r'(?<!controller\.)packet_memory\.', 'controller.packet_memory.',t)
    # The producer may offer an ACK early. The native visibility gate holds
    # BOTH VALID and producer READY until the real controller releases it.
    t=once(t,'.s_axis_tvalid(a_s_axis_tvalid),','.s_axis_tvalid(a_s_axis_tvalid && ctrl_tx_release),')
    t=once(t,'while(!a_s_axis_tready && !any_fault)','while(!(a_s_axis_tready && ctrl_tx_release) && !any_fault)')
    a=t.index('task metadata;');b=t.index('endtask',a)+len('endtask')
    t=t[:a]+r'''
task metadata;
 begin
  replay_index=0;replay_complete=0;
  raw_words=(packet_index==0 ? 4160:packet_index==1 ? 4144:mode==1 ? 52:48)+15;
  raw_words=raw_words/16;
  $readmemh($sformatf("raw%0d-%0d.hex",mode==1,packet_index),input_words,0,raw_words-1);
  for(raw_index=0;raw_index<raw_words;raw_index=raw_index+1)begin
   {raw_last,raw_keep,raw_data}=input_words[raw_index];raw_valid=1;
   @(posedge clk);while(!raw_ready)@(posedge clk);@(negedge clk);raw_valid=0;
  end
  limit=cycles+4000;
  while(!e_busy || !replay_complete)begin if(cycles>limit)$fatal(1,"actual CRC/frontend/MR/owned replay missing");tick;end
  if(controller.packet_memory.owner!==token || controller.packet_memory.mr_offset!==528+offset_value ||
     e_m_command_valid || e_m_done_valid)$fatal(1,"actual checked frame/MR full424 owner");
  no_revoke;
 end
endtask
'''+t[b:]
    # Preserve the actual-HLS RQ proof MODEL, but actual controller must
    # supply real placement first. No old modeled placement field remains.
    a=t.index('      q_s_placement_context=rq;');b=t.index('      q_s_core_data=',a)
    t=t[:a]+'''      limit=cycles+100;while(!controller.placement_sent)begin
       if(cycles>limit)$fatal(1,"real parsed-RQ placement missing");tick;end
'''+t[b:]
    t=once(t,'g_trusted_epoch=64\'h9123456700000001;',"g_trusted_epoch=64'h9123456700000001;g_trusted_expected_psn=2;")
    t=once(t,'     ack_frame;tick;','     fork ack_frame;join_none\n     tick;')
    t=once(t,'$fatal(1,"HLS/SFD/quiet without actual data DMA/fence advanced packet");end',
        '$fatal(1,"HLS/SFD/quiet without actual data DMA/fence advanced packet");\n'
        '      if(actual_SFD_count!=packet_index || ctrl_tx_release)$fatal(1,"positive ACK passed before actual visibility fence");end')
    # A mismatched MSN faults only after the true visibility gate allows
    # capture/check. Do not turn that fail-stop into a wait-for-DONE oracle.
    t=once(t,'      finish_packet;','      if(mode==13)repeat(31)tick;else finish_packet;')
    t=once(t,' $display("WRITE_MEMORY_RESULT ',r'''
 if(!expect_fault && (CRC_frames!=3 || replayed_frames!=3 || g_trusted_expected_psn!=5 || actual_done!=3 || actual_hls_rq_owners!=(mode==1 ? 1:0)))
  $fatal(1,"whole raw integrity/replay/atomic native PSN commit cardinality");
 $display("WRITE_CONTROLLER_RESULT {\"pass_test\":true,\"raw_frames\":%0d,\"replayed_frames\":%0d,\"replayed_bytes\":%0d,\"PSN\":%0d,\"commits\":%0d,\"genuine_HLS_RQ_owners\":%0d,\"ACK_after_actual_fence\":true}",CRC_frames,replayed_frames,replayed_bytes,g_trusted_expected_psn,actual_done,actual_hls_rq_owners);
 $display("WRITE_MEMORY_RESULT ''')
    return t


def runner_source():
    t=Path(prior.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import argparse','import probe_segmented_write_controller as controller\nimport argparse')
    t=once(t,"prefix='remote-write-memory-'","prefix='segmented-write-controller-'")
    t=once(t,"prefix='as02-remote-write-memory-'","prefix='as02-segmented-write-controller-'")
    t=once(t,'sources=[MEMORY,NONCE,','sources=[controller.CTRL,controller.ICRC,controller.FIFO,MEMORY,NONCE,')
    t=once(t,'inputs=list(dict.fromkeys([*sources,Path(__file__).resolve(),',
        'inputs=list(dict.fromkeys([*sources,Path(controller.__file__).resolve(),Path(controller.leaves.__file__).resolve(),controller.leaves.FRONT,Path(__file__).resolve(),')
    t=once(t,"(run/'tb.v').write_text(bench(ack,q))", "(run/'tb.v').write_text(controller.bench(ack,q))\n        (run/'native-front.v').write_text(controller.leaves.frontend())")
    t=once(t,"payload=data[v['offset']];(run/f'payload{i}.hex')", "payload=data[v['offset']]\n            for imm in [0,1]:\n                raw=controller.raw_packet(payload,i,imm)\n                (run/f'raw{imm}-{i}.hex').write_text(''.join(f'{int.from_bytes(raw[n:n+16].ljust(16,bytes(1)),\"little\") | (((1<<min(16,len(raw)-n))-1)<<128) | (int(n+16>=len(raw))<<144):037x}\\n'for n in range(0,len(raw),16)))\n            (run/f'payload{i}.hex')")
    t=once(t,"actual_sources=[run/'tb.v',run/'ack.v',run/'rq.v',", "actual_sources=[run/'tb.v',run/'ack.v',run/'rq.v',run/'native-front.v',")
    t=once(t,"            item['summary']=rows[0]",r'''
            item['summary']=rows[0]
            extra=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_CONTROLLER_RESULT ')]
            if len(extra)!=1 or not extra[0]['pass_test']:raise ValueError('actual controller full assertions missing')
            item['controller']=extra[0]''')
    t=once(t,'actual_MR_guard_RQ=True,','actual_checked_frame_controller=True,native_shadow_PSN_endpoint_modeled=True,ACK_TX_waits_actual_backend_visibility=True,actual_MR_guard_RQ=True,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-controller-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
