# SPDX-License-Identifier: BSD-2-Clause-Views
"""Whole native receive path: genuine fetched receive WQE and actual HLS.

Host/MAC/link are explicit physical models. No fake core drain, receive CQ,
unpin, standard registration or empty-RQ wire RNR claim is made.
"""
import json
import test_native_qp_tx_rtl as qp

def case(wire_rnr=False,core_receipts=False):
    if core_receipts and not wire_rnr:raise ValueError('receive receipts require matched actual RNR core')
    m=qp.main;tb,old_words=m.bench(True)
    n=len(m.sq.local.fixture.packet())
    payload=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65))
    # Derive only the no-RETH SEND shape from the established peer WRITE
    # fixture; recompute actual IP/UDP lengths/checksum/whole-frame ICRC.
    # The configured receive PSN is 0x987654; 0xfffffe belongs to the
    # independent local transmit stream and must not authorize this SEND.
    packet=bytearray(m.response.packet(write=False,mig=1,qpn=2,psn=0x987654))
    # READ_RESPONSE_ONLY has a4-byte AETH; SEND_ONLY has none.
    packet[28]=4;del packet[40:44]
    packet[40:105]=payload
    packet=m.response.repair(packet)
    frame=bytes.fromhex('8af3fbb97531b8830367c5d00800')+packet
    words=old_words[:n]+[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')|
        (((1<<min(16,len(frame)-i))-1)<<128)|((i+16>=len(frame))<<144)for i in range(0,len(frame),16)]
    tb=m.sq.once(tb,'rocev2_native_rnic_endpoint dut(',
        'rocev2_native_rnic_endpoint #(.QP_TX_ENABLE(1),.RETRY_ENABLE(1),.SEND_ENABLE(1),.RECV_ENABLE(1)'+
        (',.RNR_ENABLE(1)'if wire_rnr else'')+(', .RECV_RETIRE_ENABLE(1)'if core_receipts else'')+') dut(')
    tb=m.sq.once(tb,"expect_decerr(24'h404000);",
        "read_reg(24'h404000,sq_value);if(sq_value!==32'h52525031)$fatal(1,\"actual receive retry profile\");")
    tb=m.sq.once(tb,f'stimulus[0:{len(old_words)-1}]',f'stimulus[0:{len(words)-1}]')
    start=tb.index('enable=1;sq_command(2,1,0,0,0);')
    end=tb.index('disable native_rnic_case;',start)+len('disable native_rnic_case;')
    body=r'''
enable=1;read_reg(AS02_CTL_FEATURES,sq_value);if(sq_value!==15)$fatal(1,"actual RECV capability");
pcie_current_length=65;pcie_current_offset=64'h210;
if($test$plusargs("RNR"))begin
 m_reject_ready=0;send_frame(FRAME_START,FRAME_WORDS);
 sq_deadline=cycle+5000;
 while(!m_reject_valid)begin if(cycle>sq_deadline)$fatal(1,"empty RQ reject deadline");@(negedge clk);end
 if(m_reject_error!==38 || m_reject_qpn!==2 || m_reject_psn!==24'h987654 ||
    dut.rq_posted_count || dut.rq_taken_count || router_descriptor_count || write_tlps || m_cq_valid)
  $fatal(1,"empty receive queue authorized DMA/consumed descriptor/PSN");
 m_reject_ready=1;@(posedge clk);@(negedge clk);repeat(7)@(negedge clk);
end
sq_command(2,1,0,0,0);sq_deadline=cycle+5000;
while(dut.rq_posted_count!=1)begin
 if(cycle>sq_deadline)$fatal(1,"actual receive WQE fetch/admission deadline native%h rq%h",dut.native_fault_code,dut.rq_fault_code);
 @(negedge clk);
end
if(dut.rq_active || dut.rq_taken_count || dut.rq_queue_guard!==8'h04 ||
   sq_fetch_count!=1 || sq_result_count!=1 || sq_submission_owner_count || sq_submission_hls_count ||
   dut.h_local_hls_active || dut.ex_owner_count || dut.tx_busy || m_cq_valid)
 $fatal(1,"posted RECV was misrouted as local SEND/READ or released its owner");
send_frame(FRAME_START,FRAME_WORDS);sq_deadline=cycle+6000;
while(dut.rq_placement_count!=1)begin
 if(cycle>sq_deadline)$fatal(1,"receive placement deadline rq%h native%h reject%h accepted%0d completed%0d rxgood%0d rxbad%0d",dut.rq_fault_code,dut.native_fault_code,m_reject_error,accepted_count,completed_count,rxgood,rxbad);
 @(negedge clk);
end
repeat(1100)@(negedge clk);
if(!dut.rq_active || dut.rq_taken_count!=1 || dut.rq_received_bytes!==65 || dut.rq_queue_guard!==8'h04 ||
   accepted_count!=1 || completed_count!=1 || write_tlps!=2 || read_tlps!=2 || fences!=1 ||
   router_descriptor_count!=4 || m_cq_valid || local_committed_count || fault)
 $fatal(1,"real receive placement/PCIe/visibility/retained-owner evidence missing");
for(sq_i=0;sq_i<16384;sq_i=sq_i+1)begin
 if(pcie_posted_valid[sq_i])$fatal(1,"unfenced receive byte");
 if(sq_i>=4093 && sq_i<4158)begin
  if(pcie_host[sq_i]!==pcie_pattern(sq_i-4093))$fatal(1,"receive payload mismatch");
 end else if(pcie_host[sq_i]!==(((sq_i*37)^8'h5a)&255))$fatal(1,"receive changed sentinel/buffer tail");
end
check_ring();
host_stage(8,405,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(50)begin @(negedge clk);if(!control_busy || quiet || config_safe || m_cq_valid ||
 !dut.rq_active || dut.rq_queue_guard!==8'h04)$fatal(1,"unproved receive retirement released queue/MR");end
$display("NATIVE_RNIC_RESULT {\"pass_test\":true,\"operation\":\"RECV\",\"payload_bytes\":65,\"buffer_capacity\":128,\"proof_flags\":0,\"descriptors\":%0d,\"read_TLPs\":%0d,\"write_TLPs\":%0d,\"fences\":%0d,\"HLS_model\":true,\"CQ_committed\":false}",router_descriptor_count,read_tlps,write_tlps,fences);
$finish;disable native_rnic_case;
'''.replace('FRAME_START',str(n)).replace('FRAME_WORDS',str((len(frame)+15)//16))
    if wire_rnr:
        body=m.sq.once(body,'if(sq_value!==15)','if(sq_value!==31)')
        body=m.sq.once(body,' m_reject_ready=1;@(posedge clk);',r'''
 // RNR must travel through ACTUAL HLS/MSN/IP/ICRC/MAC and the existing
 // physical receipt/tail model while reject output remains backpressured.
 while(mac_response_cpls!=1 || !response_tx_quiescent)begin
  if(cycle>sq_deadline)$fatal(1,"empty-RQ actual RNR/MAC receipt deadline");@(negedge clk);
 end
 if(dut.rq_posted_count || dut.rq_taken_count || router_descriptor_count || write_tlps ||
    accepted_count || completed_count || m_cq_valid || fault)
  $fatal(1,"wire RNR consumed RX/WQE/PSN or authorized native DMA");
 m_reject_ready=1;@(posedge clk);''')
    if core_receipts:
        body=m.sq.once(body,'if(sq_value!==31)','if(sq_value!==63)')
        body=m.sq.once(body,'enable=1;read_reg',"force dut.rq_core_ready=1'b0;\nenable=1;read_reg")
        body=m.sq.once(body,'repeat(1100)@(negedge clk);',r'''
repeat(1100)@(negedge clk);sq_deadline=cycle+1000;
while(!dut.rq_core_valid)begin
 if(cycle>sq_deadline)$fatal(1,"actual internal HLS receive receipt deadline");@(negedge clk);
end
stalled_core_data=dut.rq_core_data;
repeat(17)begin
 @(negedge clk);
 if(dut.rq_core_data!==stalled_core_data || !dut.rq_core_valid || dut.rq_core_proved ||
    dut.rq_core_proof_count || !dut.rq_active || dut.rq_queue_guard!==8'h04 || m_cq_valid)
  $fatal(1,"withheld real HLS receipt consumer changed/released receive owner");
end
release dut.rq_core_ready;sq_deadline=cycle+100;
while(dut.rq_core_proof_count!=1)begin
 if(cycle>sq_deadline)$fatal(1,"actual full-owner receive proof handoff");@(negedge clk);
end
if(!dut.rq_core_proved || dut.rq_core_msn!==1 || fault)$fatal(1,"unproved or wrong-MSN internal receive proof");
''')
    for name in ['m_reject_valid','m_reject_error','m_reject_qpn','m_reject_psn','accepted_count','completed_count']:
        body=body.replace(name,'dut.'+name)
    body=body.replace('m_reject_ready','receive_reject_ready')
    tb=tb[:start]+body+tb[end:]
    tb=m.sq.once(tb,'.m_reject_ready(reject_ready)','.m_reject_ready(receive_reject_ready)')
    monitor=r'''
always @(posedge clk)if(!rst)begin
 if(dut.m_reject_valid && receive_reject_ready)
  $display("NATIVE_RECV_REJECT code%0d qpn%0d psn%h",dut.m_reject_error,dut.m_reject_qpn,dut.m_reject_psn);
 if(dut.rq_post_valid && dut.rq_post_ready &&
    (dut.rq_post_context[339:324]!==4 || dut.rq_post_context[307:276]!==128 ||
     dut.rq_post_context[275:244]!==8 || dut.rq_post_context[243:180]!==64'hfedcba9876543210))
  $fatal(1,"actual coherent receive owner lost full buffer/MR context");
 if(mac_tx_valid && tr && mac_tx_user[16:1]==16'h4000)
  $display("NATIVE_RECV_MAC %032h %04h %0d %04h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user[16:1]);
end
'''
    tb=m.sq.once(tb,'reg [144:0] stimulus','reg receive_reject_ready=1;\n'+monitor+'\nreg [144:0] stimulus')
    if core_receipts:
        proof=r'''
reg [679:0] stalled_core_data=0;
always @(posedge clk)if(!rst && dut.rq_core_valid && dut.rq_core_ready)begin
 if(dut.rq_core_data[587:0]!==dut.rq_placement_context || dut.rq_core_data[619:588]!==65 ||
    dut.rq_core_data[643:620]!==24'h987654 || dut.rq_core_data[647:644]!==0 ||
    dut.rq_core_data[671:648]!==1 || dut.rq_core_data[679:672]!==0)
  $fatal(1,"actual HLS data/ACK/MSN/PSN receipt lost full native owner");
 $display("NATIVE_RECV_CORE_PROOF {\"full_owner_match\":true,\"received_bytes\":%0d,\"PSN\":%0d,\"MSN\":%0d,\"error\":%0d}",dut.rq_core_data[619:588],dut.rq_core_data[643:620],dut.rq_core_data[671:648],dut.rq_core_data[679:672]);
end
'''
        tb=m.sq.once(tb,'reg [144:0] stimulus',proof+'\nreg [144:0] stimulus')
    records=[]
    for i in range(2):
        w=m.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
            local_address=0xfedcba9876543210,local_key=8,remote_address=0,remote_key=0,
            opcode=4,flags=1,length=128)
        records.append(m.shared.codec.oracle(w))
    # Actual FNS generate_exh RC_ACK uses syndrome0x00 (ACK, credit0),
    # not the generic peer fixture's0x1f. Keep exact full-frame comparison
    # and recompute ICRC; MSN comes from the SAME real HLS table.
    ack=bytearray(m.response.packet(write=True,mig=1,qpn=196,psn=0x987654))
    ack[1]=2;ack[8]=100;ack[12:16]=bytes.fromhex('c6120b02');ack[16:20]=bytes.fromhex('c6120b01')
    ack[20:22]=(4791).to_bytes(2,'big');ack[40]=0;ack[41:44]=(1).to_bytes(3,'big');ack=m.response.repair(ack)
    if wire_rnr:
        # The inherited positive responder observer requires memory status
        # before EVERY response. RNR has no memory command: allow ONLY the
        # exact four RNR beats, bound to authenticated reject38 and zero DMA.
        # Normal ACK still requires the original actual memory completion.
        negative=bytearray(ack);negative[40]=0x20;negative[41:44]=bytes(3);negative=m.response.repair(negative)
        frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+negative
        encoded=[int.from_bytes(frame[i:i+16].ljust(16,b'\0'),'little')|
            (((1<<min(16,len(frame)-i))-1)<<128)|((i+16>=len(frame))<<144)for i in range(0,len(frame),16)]
        if len(encoded)!=4:raise ValueError('expected exact62-byte RNR')
        checker='reg [144:0] expected_early_rnr[0:3];integer early_rnr_word=0;\ninitial begin\n'+\
            '\n'.join(f"expected_early_rnr[{i}]=145'h{w:x};"for i,w in enumerate(encoded))+'\nend\n'+r'''
wire permitted_early_rnr_beat=$test$plusargs("RNR") && early_rnr_word<4 &&
 dut.m_reject_valid===1'b1 && dut.m_reject_error===8'd38 &&
 dut.m_reject_qpn===24'd2 && dut.m_reject_psn===24'h987654 &&
 !dut.rq_posted_count && !dut.rq_taken_count && !router_descriptor_count &&
 !dut.accepted_count && !dut.completed_count && !m_cq_valid && !fault &&
 ({tl,tk,td}===expected_early_rnr[early_rnr_word]);
always @(posedge clk)if(!rst && tv && tr && !status_done)begin
 if(!permitted_early_rnr_beat)$fatal(1,"nonexact RNR or DMA before memory status");
 early_rnr_word<=early_rnr_word+1;
end
'''
        tb=m.sq.once(tb,'reg [144:0] stimulus',checker+'\nreg [144:0] stimulus')
        tb=m.sq.once(tb,'if(tv && !status_done) $fatal(1,"response visible before memory completion");',
            'if(tv && !status_done && !permitted_early_rnr_beat) $fatal(1,"response visible before memory completion");')
        tb=m.sq.once(tb,'if(dut.rq_posted_count || dut.rq_taken_count || router_descriptor_count || write_tlps ||\n    dut.accepted_count',
            'if(early_rnr_word!=4 || dut.rq_posted_count || dut.rq_taken_count || router_descriptor_count || write_tlps ||\n    dut.accepted_count')
    return tb,words,records,ack

def verify(output,ack,wire_rnr=False,empty=False):
    data=bytearray();frames=[]
    for line in output.splitlines():
        if not line.startswith('NATIVE_RECV_MAC '):continue
        _,word,keep,last,tag=line.split()
        if int(tag,16)!=0x4000:raise ValueError('wrong receive ACK MAC owner')
        mask=int(keep,16)
        if not mask or mask&(mask+1):raise ValueError('ACK keep holes')
        data.extend(int(word,16).to_bytes(16,'little')[:mask.bit_count()])
        if last=='1':frames.append(bytes(data));data=bytearray()
    expected=[bytes.fromhex('b8830367c5d08af3fbb975310800')+ack]
    if wire_rnr and empty:
        negative=bytearray(ack);negative[40]=0x20;negative[41:44]=bytes(3);negative=qp.main.response.repair(negative)
        expected.insert(0,expected[0][:14]+negative)
    if data or frames!=expected:raise ValueError('actual receive ACK/RNR full-frame mismatch: '+str(list(map(len,frames))))
    return dict(actual_ACK_MAC_frames=1,actual_RNR_MAC_frames=int(wire_rnr and empty),full_IP_UDP_BTH_AETH_MSN_ICRC_match=True,
        buffer_capacity=128,received_bytes=65,unchanged_tail_and_sentinels=True,
        CQ_published=False,internal_core_retirement=False,wire_RNR_for_empty_RQ=wire_rnr and empty,
        full_RNR_frame_and_current_MSN_match=wire_rnr and empty,RNR_advances_MSN_or_receive_PSN=False)
