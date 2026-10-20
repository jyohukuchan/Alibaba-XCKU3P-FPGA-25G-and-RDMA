# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual main SEND fixture: peer ACK/RNR and host/MAC are explicit models.

No fake CQ/core drain. Runtime evidence must contain the actual SEND frames
from transferred MAC pins, not just a descriptor/header construction oracle.
"""
import test_native_qp_tx_rtl as qp

def case(base_case):
    m=qp.main;tb,words,records,request=base_case(True)
    tb=m.sq.once(tb,'.RETRY_ENABLE(1)', '.RETRY_ENABLE(1),.SEND_ENABLE(1)')
    tb=m.sq.once(tb,'if(sq_value!==3)$fatal(1,"new QP TX capability missing");',
        'if(sq_value!==7)$fatal(1,"actual SEND capability missing");')
    # WRITE and SEND both source data from the same pinned/scattered MR.
    # SEND has BTH+payload, no RETH and no remote VA/rkey authorization.
    request=bytearray(request);request[28]=4;del request[40:56]
    # The ACTUAL frozen FNS IPv4/UDP producers set ECT(0), TTL100 and
    # source UDP=the configured4791. The generic WRITE wire-model defaults
    # (TOS0/TTL64/source49152) are not this generated transport's profile.
    # See ipv4_generate_ipv4/ipv4Header and tx_ipUdpMetaMerger in source002.
    request[1]=2;request[8]=100;request[20:22]=(4791).to_bytes(2,'big')
    request=m.response.repair(request)
    records=[]
    for i in range(2):
        w=m.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
            local_address=0xfedcba9876543210,local_key=8,remote_address=0,remote_key=0,
            opcode=3,flags=1,length=65)
        records.append(m.shared.codec.oracle(w))
    tb=tb.replace("m_work_remote_address!==64'hf123456789abc001",'m_work_remote_address!==0')
    tb=tb.replace('m_work_opcode!==1','m_work_opcode!==3')
    monitor=r'''
always @(posedge clk)if(!rst)begin
 if(dut.owner_take && (dut.sq_m_executor_context[339:324]!==16'd3 ||
    dut.sq_m_executor_context[115:52]!==0 || dut.sq_m_executor_context[51:20]!==0))
  $fatal(1,"SEND did not retain canonical full SQ owner");
 if(dut.rx_m_read_response_valid || dut.h_m_local_write_command_valid || dut.up_m_command_valid)
  $fatal(1,"SEND ACK incorrectly authorized READ placement or host writes");
 if(mac_tx_valid && tr && (mac_tx_user[16:1]&16'he000)==16'h2000)
  $display("NATIVE_SEND_MAC %032h %04h %0d %04h",mac_tx_data,mac_tx_keep,mac_tx_last,mac_tx_user[16:1]);
end
'''
    tb=m.sq.once(tb,'reg [144:0] stimulus',monitor+'\nreg [144:0] stimulus')
    return tb,words,records,request

def verify(output,request):
    expected=bytes.fromhex('b8830367c5d08af3fbb975310800')+request
    frames=[];frame=bytearray();tag=None;tags=[]
    for line in output.splitlines():
        if not line.startswith('NATIVE_SEND_MAC '):continue
        _,data,keep,last,raw_tag=line.split();value=int(raw_tag,16)
        if tag is None:tag=value
        if value!=tag:raise ValueError('actual SEND MAC tag changed within a frame')
        lanes=int(keep,16)
        if not lanes or lanes&(lanes+1):raise ValueError('actual SEND MAC keep has holes')
        frame.extend(int(data,16).to_bytes(16,'little')[:lanes.bit_count()])
        if last=='1':frames.append(bytes(frame));tags.append(tag);frame=bytearray();tag=None
    if frame or len(frames)!=2 or frames[0]!=expected or frames[1]!=expected or tags!=[0x2001,0x2002]:
        raise ValueError('actual SEND frame/payload/ICRC/replay/fresh tags mismatch: '+str(dict(
            lengths=list(map(len,frames)),expected_length=len(expected),tags=tags)))
    if request[28]!=4 or len(request)!=112 or request[40:105]!=bytes((((4093+i)*37)^0x5a)&255 for i in range(65)):
        raise ValueError('SEND fixture has a RETH or wrong source payload')
    return dict(actual_MAC_frames=2,byte_identical_replay=True,fresh_MAC_tags=tags,
        BTH_opcode=4,RETH_present=False,MAC_frame_bytes=len(expected),payload_bytes=65,
        full_payload_IP_UDP_BTH_padding_and_ICRC_match=True)
