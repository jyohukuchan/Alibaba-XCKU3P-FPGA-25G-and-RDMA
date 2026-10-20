#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""ONE live immutable HLS: protected WRITE, SAME-MR local READ/RX/unpad/MAC.

Actual C/UBSan WQE/shared MR/owner/SQ/issued PSN/guard/HLS/unpad/MAC RTL.
Memory/peer/MAC pins MODELS; NO coherent SQ/PCIe/CQ/provider/board or real
core-drain proof. Local role and MR lifetime intentionally HELD at finite end.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import shared_mr_fixture as fixture
import test_shared_mr_responder_rtl as shared
import test_wqe_response_guard_rtl as response
import native_executor_compiled_sim as compiled

ROOT=fixture.probe.ROOT
spec=importlib.util.spec_from_file_location('shared_derivation',ROOT/'rdma/rnic/fpga/derive_shared_responder.py')
derive=importlib.util.module_from_spec(spec);spec.loader.exec_module(derive)


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('finite bench anchor changed: '+old)
    return text.replace(old,new,1)


def ports(text):
    h=text.split(')(\n',1)[1]if ')(\n'in text else text.split('(\n',1)[1]
    return re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h.split('\n);',1)[0],re.M)


def instance(path,name,prefix,mapping):
    decl=[];conn=[]
    for direction,width,n in ports(path.read_text()):
        v=mapping.get(n,prefix+n);conn.append(f'.{n}({v})')
        if n not in mapping:decl.append(('reg 'if direction=='input'else'wire ')+(width or'')+v+('=0;'if direction=='input'else';'))
    return '\n'.join(decl)+'\n'+path.read_text().split('module ',1)[1].split()[0]+' '+name+'('+',\n'.join(conn)+');\n'


def bench(words,body,derived):
    tb=fixture.make_tb(words,body);tb=once(tb,'local_ready=0,','')
    tb=once(tb,'wire local_configuration_idle,','wire local_ready;\nwire local_configuration_idle,')
    for name in ['expect_local','release_local_lease']:
        start=tb.index('task '+name+';');end=tb.index('endtask',start)+len('endtask');tb=tb[:start]+tb[end:]
    tb=once(tb,'rocev2_protected_responder #(','rocev2_shared_protected_responder #(')
    tb=once(tb,'.local_work_guard(local_guard || executor_guard)',
        '.local_work_guard(local_guard || executor_guard || (|st_queue_guard) || (|tx_queue_guard) || (|rx_queue_guard) || (|up_queue_guard))')
    common=dict(clk='clk',rst='rst',enable="1'b1")
    shmap=dict(s_local_owner_context='st_m_owner_context',s_local_owner_valid='st_m_owner_valid && tx_s_owner_ready',
        s_local_sq_tdata='st_m_axis_sq_tdata',s_local_sq_tvalid='st_m_axis_sq_tvalid',s_local_sq_tready='st_m_axis_sq_tready',
        s_local_rx_tdata='rx_m_axis_hls_rx_tdata',s_local_rx_tkeep='rx_m_axis_hls_rx_tkeep',s_local_rx_tvalid='rx_m_axis_hls_rx_tvalid',
        s_local_rx_tready='rx_m_axis_hls_rx_tready',s_local_rx_tlast='rx_m_axis_hls_rx_tlast',s_local_rx_tuser="1'b0",
        m_local_tx_tready='tx_s_axis_ip_tready',m_local_ack_tready='tx_s_hls_ack_ready',
        m_local_write_command_ready='up_s_command_ready',m_local_write_tready='up_s_axis_tready')
    shdecl=[];shconn=[]
    for d,w,n in re.findall(r'\b(input|output) wire (\[[^]]+\] )?(\w+)',derive.LOCAL_PORTS):
        v=shmap.get(n,'sh_'+n);shconn.append(f'.{n}({v})')
        if n not in shmap:shdecl.append(('reg 'if d=='input'else'wire ')+(w or'')+v+('=0;'if d=='input'else';'))
    tb=once(tb,' .cfg_admission_pause(admission_pause),',','.join(shconn)+',\n .cfg_admission_pause(admission_pause),')
    stage=instance(ROOT/'rdma/rnic/rtl/rocev2_wqe_hls_sq.v','SQ_owner','st_',dict(common,halt="1'b0",
        s_work_context='full_work',s_work_valid='local_work_valid',s_work_ready='local_ready',
        m_owner_ready='sh_s_local_owner_ready && tx_s_owner_ready',
        downstream_queue_guard='sh_local_hls_queue_guard | tx_queue_guard'))
    tx=instance(ROOT/'rdma/rnic/rtl/rocev2_wqe_tx_lifetime.v','issued_MAC_lifetime','tx_',dict(common,
        parent_fault='sh_shared_hls_fault || rx_fault || up_fault || st_fault',
        s_owner_context='st_m_owner_context',s_owner_valid='st_m_owner_valid && sh_s_local_owner_ready',
        s_owner_local_ip="32'hc6120b02",s_owner_peer_ip="32'hc6120b01",s_owner_peer_qpn="24'd196",
        s_owner_local_mac="48'h8af3fbb97531",s_owner_peer_mac="48'hb8830367c5d0",
        s_axis_ip_tdata='sh_m_local_tx_tdata',s_axis_ip_tkeep='sh_m_local_tx_tkeep',s_axis_ip_tvalid='sh_m_local_tx_tvalid',
        s_axis_ip_tlast='sh_m_local_tx_tlast',s_axis_ip_tuser="1'b0",
        s_hls_ack='sh_m_local_ack_tdata',s_hls_ack_valid='sh_m_local_ack_tvalid',
        s_response_context='rx_m_response_event_context',s_response_psn='rx_m_response_event_psn',
        s_response_opcode='rx_m_response_event_opcode',s_response_syndrome='rx_m_response_event_syndrome',
        s_response_valid='rx_m_response_event_valid',s_response_ready='rx_m_response_event_ready'))
    rx=instance(ROOT/'rdma/rnic/rtl/rocev2_wqe_response_guard.v','protected_reply','rx_',dict(common,halt="1'b0",
        s_expect_context='tx_m_expect_context',s_expect_local_ip='tx_m_expect_local_ip',
        s_expect_peer_ip='tx_m_expect_peer_ip',s_expect_psn='tx_m_expect_psn',s_expect_valid='tx_m_expect_valid',
        s_expect_ready='tx_m_expect_ready',m_read_response_ready='up_s_context_ready',
        downstream_queue_guard='sh_local_hls_queue_guard | tx_queue_guard | up_queue_guard',
        m_response_event_ready='rx_m_response_event_ready'))
    up=instance(ROOT/'rdma/rnic/rtl/rocev2_wqe_read_unpad.v','checked_unpad','up_',dict(common,
        s_context='rx_m_read_response_context',s_context_valid='rx_m_read_response_valid',
        downstream_queue_guard='sh_local_hls_queue_guard | tx_queue_guard',
        s_command='sh_m_local_write_command',s_command_valid='sh_m_local_write_command_valid',
        s_axis_tdata='sh_m_local_write_tdata',s_axis_tkeep='sh_m_local_write_tkeep',
        s_axis_tvalid='sh_m_local_write_tvalid',s_axis_tlast='sh_m_local_write_tlast'))
    block=r'''
localparam MAX_QPS=8,TX_TAG_WIDTH=16,TS_WIDTH=96;
wire [587:0] full_work={local_id,local_seq,local_epoch,local_qpn,work_pd,work_tag,local_op,local_flags,local_length,local_key,local_address,local_offset,remote_address,remote_key,local_error,2'd0,8'd0,1'b1,local_authorized};
'''
    block+='\n'.join(shdecl)+'\n'+stage+tx+rx+up+MONITOR
    tb=once(tb,'reg [144:0] stimulus',block+'\nreg [144:0] stimulus')
    included=[derived]+[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_mr_table.v','rocev2_mr_query_arbiter.v','rocev2_wqe_admission.v',
        'rocev2_shared_hls_transport.v','rocev2_wqe_hls_sq.v','rocev2_wqe_tx_lifetime.v','rocev2_wqe_mac_tx.v',
        'rocev2_wqe_lifetime.v','rocev2_wqe_response_guard.v','rocev2_wqe_read_unpad.v']]
    return '\n'.join(chr(96)+'include "'+str(p)+'"'for p in included)+'\n'+tb,included


MONITOR=r'''
integer local_tx_frames=0,local_sq=0,local_ack=0,normalized_commands=0,normalized_bytes=0,local_mac_frames=0,mac_due=0,raw_bytes=0;
reg mac_scheduled=0;reg [127:0] reply_words[0:15];integer j,deadline,n,raw_lane;
function [7:0] reply_pattern;
 input integer pos;
 begin reply_pattern=(pos*149)^(pos>>4)^8'he7;end
endfunction
initial $readmemh("response.hex",reply_words);
always @(negedge clk)if(!rst)begin
 tx_m_axis_mac_tready=rng[11:9]!=0;
 up_m_command_ready=1;up_m_axis_tready=normalized_commands==1 && rng[14:12]!=0;
 if(tx_s_mac_cpl_valid && tx_s_mac_cpl_ready)tx_s_mac_cpl_valid=0;
 if(mac_scheduled && cycle>=mac_due)begin tx_s_mac_cpl_tag=16'h2001;tx_s_mac_cpl_ts=96'h123456789abcdef;tx_s_mac_cpl_valid=1;mac_scheduled=0;end
end
always @(posedge clk)if(!rst)begin
 if(sh_shared_hls_fault || rx_fault || up_fault || st_fault || tx_fault)$fatal(1,"shared local fault %h/%h/%h/%h/%h",sh_shared_hls_fault_code,rx_fault_code,up_fault_code,st_fault_code,tx_fault_code);
 if(st_m_axis_sq_tvalid && st_m_axis_sq_tready)local_sq=local_sq+1;
 if(sh_m_local_tx_tvalid && tx_s_axis_ip_tready)begin
  $display("LOCAL_IP %032h %04h %b",sh_m_local_tx_tdata,sh_m_local_tx_tkeep,sh_m_local_tx_tlast);
  if(sh_m_local_tx_tlast)local_tx_frames=local_tx_frames+1;
 end
 if(tx_m_axis_mac_tvalid && tx_m_axis_mac_tready)begin
  $display("LOCAL_MAC %032h %04h %b %h",tx_m_axis_mac_tdata,tx_m_axis_mac_tkeep,tx_m_axis_mac_tlast,tx_m_axis_mac_tuser);
  if(!mac_scheduled && !tx_receipt_count && !local_mac_frames)begin mac_scheduled=1;mac_due=cycle+17;end
  if(tx_m_axis_mac_tlast)local_mac_frames=local_mac_frames+1;
 end
 if(sh_m_local_ack_tvalid && tx_s_hls_ack_ready)begin
  if(sh_m_local_ack_tdata!==40'h07fffff004)$fatal(1,"same-core actual ACK metadata %h",sh_m_local_ack_tdata);
  local_ack=local_ack+1;
 end
 if(sh_m_local_read_command_valid)$fatal(1,"READ response became source READ");
 if(sh_m_local_write_command_valid && up_s_command_ready)begin
  if(sh_m_local_write_command!==96'h002cb0000044ba9876543210)$fatal(1,"same-core padded HLS ABI");
 end
 if(sh_m_local_write_tvalid && up_s_axis_tready)raw_bytes=raw_bytes+$countones(sh_m_local_write_tkeep);
 if(up_m_command_valid && up_m_command_ready)begin
  if(up_m_command!==96'h002cb0000041ba9876543210 || normalized_commands || !sh_local_hls_active ||
    sh_local_hls_queue_guard!==8'h04 || tx_queue_guard!==8'h04 || commands!=1)$fatal(1,"same-core normalized saved-WQE command");
  normalized_commands=normalized_commands+1;
 end
 if(up_m_axis_tvalid && up_m_axis_tready)begin
  for(raw_lane=0;raw_lane<64;raw_lane=raw_lane+1)if(up_m_axis_tkeep[raw_lane])begin
   if(normalized_bytes>=65 || up_m_axis_tdata[raw_lane*8+:8]!==reply_pattern(normalized_bytes))$fatal(1,"same-core actual READ data/pad");
   memory[16'h210+normalized_bytes]=up_m_axis_tdata[raw_lane*8+:8];normalized_bytes=normalized_bytes+1;
  end
  if(up_m_axis_tlast!==(normalized_bytes==65))$fatal(1,"same-core normalized last");
 end
 if(tx_m_cq_valid || tx_committed_count || tx_s_cq_commit_ready || sh_s_local_retire_ready)$fatal(1,"IO quiet mistaken for genuine core drain/memory/CQ");
end
task send_reply;
 input integer start;
 begin
  for(j=0;j<8;j=j+1)begin
   @(negedge clk);rx_s_axis_rx_tdata=reply_words[start+j];rx_s_axis_rx_tkeep=j==7 ? 16'h000f : 16'hffff;
   rx_s_axis_rx_tlast=j==7;rx_s_axis_rx_tvalid=1;
   @(posedge clk);while(!rx_s_axis_rx_tready)@(posedge clk);
  end
  @(negedge clk);rx_s_axis_rx_tvalid=0;
 end
endtask
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--verilator',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    obj=shared.SharedMRResponderRTLTests();obj.setUpClass()
    try:record,w=obj.record(local_key=8,opcode=2)
    finally:obj.directory.cleanup()
    words=fixture.packet();body=f'send_frame(0,{len(words)});allow();\n'
    body+=r'''
for(n=0;n<65;n=n+1)if(memory[16'h210+n]!==(((n*179)^(n>>7)^8'hd3)&255))$fatal(1,"remote WRITE not committed before local READ");
'''
    body+=f'offer_local({record});\n'
    body+=r'''
deadline=cycle+4000;while(!tx_response_admission_ready || local_tx_frames!=1)begin if(cycle>deadline)$fatal(1,"one-core local SQ/TX/issued expectation deadline");@(negedge clk);end
if(local_results!=1 || local_queries!=1 || local_sq!=1 || st_owner_handoff_count!=1 || st_HLS_SQ_handoff_count!=1 ||
 !sh_local_hls_active || sh_local_hls_queue_guard!==8'h04 || tx_queue_guard!==8'h04 || local_error || local_key!=8 || local_offset!=64'h210 ||
 local_address!==64'hfedcba9876543210 || remote_key || remote_address!==64'hf123456789abc001)$fatal(1,"same actual MR/full owner/SQ");
send_reply(0);deadline=cycle+1000;while(!rx_m_reject_valid)begin if(cycle>deadline)$fatal(1,"wrong-QP reject deadline");@(negedge clk);end
if(rx_m_reject_error!=8'h92 || up_context_count || normalized_commands || raw_bytes || local_ack)$fatal(1,"wrong-QP entered SAME HLS memory path");
rx_m_reject_ready=1;@(posedge clk);@(negedge clk);rx_m_reject_ready=0;
send_reply(8);deadline=cycle+4000;
while(normalized_bytes!=65 || local_ack!=1 || !tx_proof_flags[5] || rx_busy || up_busy)begin
 if(cycle>deadline)$fatal(1,"one-core protected READ/data/MAC proof deadline bytes%0d ack%0d flags%h",normalized_bytes,local_ack,tx_proof_flags);
 @(negedge clk);
end
if(raw_bytes!=68 || up_discarded_padding_bytes!=3 || up_context_count!=1 || up_command_count!=1 ||
 rx_accepted_count!=1 || rx_rejected_count!=1 || tx_proof_flags!==7'h3b || !tx_busy ||
 local_mac_frames!=1 || tx_frame_count!=1 || tx_receipt_count!=1 || tx_mac_proof_count!=1 || !tx_local_tx_drained ||
 commands!=1 || statuses!=1 || completed!=1 || accepted!=1 || rejected || !sh_local_hls_active)$fatal(1,"one-core role/data/ownership counts");
for(n=0;n<4096;n=n+1)begin
 if(memory[n] !== (n>=16'h210 && n<16'h251 ? reply_pattern(n-16'h210) : ((n*37)^8'h5a)&255))$fatal(1,"same MR memory/sentinel");
end
// Real core-drain and memory/CQ publication are absent: keep all owners and
// an offered MR invalidation blocked, not model/default-success completion.
admission_pause=1;cc=2;ci=0;ck=8;cv=1;car=0;
repeat(100)begin @(negedge clk);if(cr || cav || quiet || !sh_local_hls_active || tx_queue_guard!==8'h04 ||
 sh_local_hls_queue_guard!==8'h04 || tx_m_cq_valid || tx_committed_count)$fatal(1,"I/O alone released MR/core/CQ");end
$display("SHARED_CORE_RESULT {\"pass_test\":true,\"HLS_cores\":1,\"remote_WRITE_bytes\":65,\"local_READ_raw_bytes\":%0d,\"local_READ_payload_bytes\":%0d,\"discarded_pad\":%0d,\"actual_HLS_ACKs\":%0d,\"MAC_receipts\":%0d,\"role_and_MR_held\":true,\"actual_native_RDMA_completion\":false}",raw_bytes,normalized_bytes,up_discarded_padding_bytes,local_ack,tx_receipt_count);
'''
    run=Path(tempfile.mkdtemp(prefix='shared-core-',dir=ROOT/'rdma/rnic/build'))
    derived=run/'rocev2_shared_protected_responder.v';derived.write_text(derive.derive(derive.ORIGINAL.read_text()))
    tb,included=bench(words,body,derived)
    good=bytearray(response.packet(mig=1,qpn=2));good[44:109]=bytes(((i*149)^(i>>4)^0xe7)&255 for i in range(65));good=response.repair(good)
    bad=bytearray(good);bad[35]=3;bad=response.repair(bad)
    own=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(shared.__file__).resolve(),Path(shared.codec.__file__).resolve(),
        shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',Path(fixture.probe.__file__).resolve(),Path(response.__file__).resolve(),
        Path(response.read_wire.__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',Path(derive.__file__).resolve(),derive.ORIGINAL,*included]
    before={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in own}
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,board_integrated=False,hardware_verified=False,native_host_SQ_or_PCIe_DMA=False,
        actual_native_CQ_or_standard_verbs=False,actual_core_drain_verified=False,local_role_intentionally_held=True)
    try:
        output,identity=compiled.simulate(tb,{'input.hex':words,'response.hex':[int.from_bytes(v[n:n+16].ljust(16,b'\0'),'little')for v in [bad,good]for n in range(0,len(v),16)]},
            a.hls_build,a.verilator.resolve(),run)
        result['actual_HLS_identity']=identity
        counts=identity['hierarchy_module_counts'];required=['rocev2_top','rocev2_integrity_transport','rocev2_shared_hls_transport',
            'rocev2_shared_protected_responder','rocev2_mr_table','rocev2_mr_query_arbiter','rocev2_wqe_admission',
            'rocev2_wqe_hls_sq','rocev2_wqe_response_guard','rocev2_wqe_read_unpad','rocev2_wqe_tx_lifetime','rocev2_wqe_lifetime','rocev2_wqe_mac_tx']
        if any(counts.get(n)!=1 for n in required):raise ValueError('not exactly ONE shared actual HLS/MR graph '+str({n:counts.get(n)for n in required}))
        rows=[json.loads(l[len('SHARED_CORE_RESULT '):])for l in output.splitlines()if l.startswith('SHARED_CORE_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing one-core summary')
        import probe_wrkey_wire as wire
        remote=wire.packets(output)
        local=wire.packets('\n'.join(l.replace('LOCAL_IP ','OUT ',1)for l in output.splitlines()if l.startswith('LOCAL_IP ')))
        if len(remote)!=1 or len(local)!=1:raise ValueError('wrong shared role packet counts')
        for packet in remote+local:
            if wire.internet_checksum(packet[:20])or packet[-4:]!=wire.icrc_ipv4(packet):raise ValueError('actual shared-core IPv4/ICRC')
        if remote[0][28]!=17 or int.from_bytes(remote[0][37:40],'big')!=fixture.probe.PSN:raise ValueError('remote actual ACK')
        pkt=local[0]
        if len(pkt)!=60 or pkt[28]!=12 or int.from_bytes(pkt[33:36],'big')!=196 or int.from_bytes(pkt[37:40],'big')!=0xfffffe or int.from_bytes(pkt[40:48],'big')!=w.remote_address or int.from_bytes(pkt[48:52],'big')!=0 or int.from_bytes(pkt[52:56],'big')!=65:
            raise ValueError('actual same-QP local READ RETH/key/PSN')
        if before!={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('source changed')
        if derived.read_text()!=derive.derive(derive.ORIGINAL.read_text()):raise ValueError('derived controller changed')
        result.update(pass_test=True,terminal_exit_status=0,summary=rows[0],actual_module_counts={n:counts[n]for n in required},
            remote_ACK_IP_hex=remote[0].hex(),local_READ_request_IP_hex=pkt.hex(),source_sha256_before_after_equal=True)
    except Exception as e:
        result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
