# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full native duplex Immediate receive, independent RQ and remote-MR data.

WRITE_IMM uses a1-byte posted RQ at a different VA/offset from the65-byte
RETH destination. Source/received bytes and ALL untouched sentinels remain
checked by the real parent fixture. Core/CQ/drain proofs are never injected.
"""
import re
import native_duplex_fixture as old
import native_independent_queues_fixture as split
import probe_native_retry as base
import check_immediate_native_elaboration as elaboration
from native_immediate_request_fixture import audit_profile

matched=elaboration.matched
once=matched.once


def _base():return old.case(base.case)


def case():
    tb,words,records,receive_records,ack=_base()
    prefix=len(base.qp.main.sq.local.fixture.packet())
    tb=matched.widths(tb)
    tb=once(tb,'.DUPLEX_ENABLE(1)', '.DUPLEX_ENABLE(1),.RECV_CANCEL_ENABLE(1)')
    fields={'611:588':'643:620','635:612':'667:644','643:636':'675:668','655:644':'687:676',
        '619:588':'651:620','643:620':'675:652','647:644':'679:676','671:648':'703:680','679:672':'751:744'}
    tb=re.sub(r'\[('+ '|'.join(fields)+r')\]',lambda m:'['+fields[m[1]]+']',tb)
    declarations=r'''
reg runtime_write_immediate=0;
reg [31:0] runtime_notification=0;
wire [7:0] runtime_notification_flags=runtime_write_immediate ? 3:1;
wire [31:0] runtime_RQ_capacity=runtime_write_immediate ? 1:128;
wire [63:0] runtime_RQ_address=runtime_write_immediate ? 64'hfedcba9876543410:64'hfedcba9876543210;
wire [63:0] runtime_RQ_offset=runtime_write_immediate ? 64'h410:64'h210;
wire [31:0] runtime_peer_words=runtime_write_immediate ? 10:9;
initial begin
 if($test$plusargs("WRITE_IMM"))runtime_write_immediate=1;
 if($value$plusargs("IMM=%h",runtime_notification))begin end
end
'''
    tb=once(tb,'reg [144:0] stimulus',declarations+'\nreg [144:0] stimulus')
    tb=once(tb,f'stimulus[0:{len(words)-1}]',f'stimulus[0:{len(words)+4-1}]')
    # Fixed10-word slots for peer SEND_IMM/WRITE_IMM, only actual words sent.
    tb=once(tb,f'send_frame({prefix},8);',f'send_frame({prefix},runtime_peer_words);')
    tb=once(tb,f'receive_once(2,{prefix+8},',f'receive_once(2,{prefix+10},')
    tb=once(tb,f'send_frame({prefix+16}+(seq-1)*4,4);',f'send_frame({prefix+20}+(seq-1)*4,4);')
    tb=once(tb,'send_frame(frame_start,8);','send_frame(frame_start,runtime_peer_words);')
    tb=once(tb,'if(sq_value!==3)$fatal(1,"actual CQC message/byte-count ABI");',
        'if(sq_value!==7)$fatal(1,"actual CQC Immediate completion format");')
    tb=tb.replace('dut.rq_post_context[307:276]!==128',
        'dut.rq_post_context[307:276]!==runtime_RQ_capacity')
    tb=tb.replace("dut.rq_post_context[243:180]!==64'hfedcba9876543210",
        'dut.rq_post_context[243:180]!==runtime_RQ_address')
    tb=tb.replace('expected_recv_owner[307:276]!==128',
        'expected_recv_owner[307:276]!==runtime_RQ_capacity')
    tb=tb.replace("expected_recv_owner[243:180]!==64'hfedcba9876543210",
        'expected_recv_owner[243:180]!==runtime_RQ_address')
    tb=tb.replace("expected_recv_owner[179:116]!==64'h210",
        'expected_recv_owner[179:116]!==runtime_RQ_offset')
    tb=once(tb,'dut.rq_core_data[751:744]!==0)',
        'dut.rq_core_data[751:744]!==0 || dut.rq_core_data[735:704]!==runtime_notification ||\n'
        '    dut.rq_core_data[743:736]!==runtime_notification_flags || dut.rq_core_data[619:588]!==0)')
    # No posted receive context ever acquires a wire notification value.
    tb=once(tb,'$fatal(1,"independent RECV full native owner");',
        '$fatal(1,"independent RECV full native owner");\n'
        '  if(expected_recv_owner[619:588]!==0)$fatal(1,"wire Immediate overwrote posted RQ context");')
    tb=once(tb,'split_word<19;','split_word<20;')
    tb=once(tb,'$fdisplay(split_file,"%08h",sq_value);$fclose(split_file);',r'''$fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h40303c,sq_value);
  if(sq_value!==(owner[339:324]==4 ? runtime_notification_flags:0))$fatal(1,"actual native notification flags");
  $fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h403090,sq_value);
  if(sq_value!==(owner[339:324]==4 ? runtime_notification:0))$fatal(1,"actual native wire notification value");
  $fdisplay(split_file,"%08h",sq_value);
  read_reg(24'h403008,sq_value);if(sq_value!==7)$fatal(1,"actual native Immediate CQ format");
  $fdisplay(split_file,"%08h",sq_value);$fclose(split_file);''')
    tb=tb.replace(r'\"capacity\":128',r'\"capacity\":%0d')
    tb=once(tb,',seq,16\'h6000+seq);',',seq,runtime_RQ_capacity,16\'h6000+seq);')
    tb=once(tb,r'\"buffer_capacity\":128',r'\"buffer_capacity\":%0d')
    tb=once(tb,'",local_proof_flags,router_descriptor_count,read_tlps,write_tlps,fences);',
        '",runtime_RQ_capacity,local_proof_flags,router_descriptor_count,read_tlps,write_tlps,fences);')
    tb=once(tb,r'\"HLS_model\":true',r'\"HLS_model\":false')
    # Actual wire/MR admission metadata must agree with actual HLS and RQ.
    monitor=r'''
always @(posedge clk)if(!rst && dut.rq_placement_valid && dut.rq_placement_ready)begin
 if(dut.rq_placement_notification!==runtime_notification ||
    dut.rq_placement_notification_flags!==runtime_notification_flags || dut.rq_placement_length!==65)
  $fatal(1,"actual protected wire notification/placement metadata");
end
'''
    tb=once(tb,'reg [144:0] stimulus',monitor+'\nreg [144:0] stimulus')
    tb=re.sub(r'^\s*`include "[^\"]+\.v"\s*$', '',tb,flags=re.M)
    if 'force 'in tb:raise ValueError('no internal production force')
    return audit_profile(tb)


def variant(write,immediate):
    _,words,records,receive_records,ack=_base()
    prefix=len(base.qp.main.sq.local.fixture.packet())
    output=words[:prefix]
    for seq in (1,2):
        raw=words[prefix+(seq-1)*8:prefix+seq*8]
        frame=bytearray()
        for w in raw:
            keep=(w>>128)&0xffff;frame.extend((w&((1<<128)-1)).to_bytes(16,'little')[:keep.bit_count()])
        p=bytearray(frame[14:])
        if write:
            p[28]=11
            reth=(0xfedcba9876543210).to_bytes(8,'big')+(8).to_bytes(4,'big')+(65).to_bytes(4,'big')
            p[40:40]=reth+immediate.to_bytes(4,'big')
        else:p[28]=5;p[40:40]=immediate.to_bytes(4,'big')
        p=base.qp.main.response.repair(p)
        encoded=split.encode_frame(frame[:14]+p)
        if len(encoded)!=(10 if write else 9):raise ValueError('actual peer frame shape')
        output+=encoded+[0]*(10-len(encoded))
    output+=words[prefix+16:]
    if write:
        new=[]
        for raw in receive_records:
            r=bytearray(raw);r[16:24]=(0xfedcba9876543410).to_bytes(8,'little');r[32:36]=(1).to_bytes(4,'little')
            new.append(bytes(r))
        receive_records=new
    return output,records,receive_records,ack


def verify(output,ack,write,empty):
    result=old.verify(output,ack,empty)
    # Parent verifier fixes128 in its returned description (but actual event
    # values are checked above). Do not misreport WRITE notification capacity.
    for recv in [result.get('actual_receive'),result.get('actual_independent_queues',{}).get('actual_receive')]:
        if isinstance(recv,dict):recv['buffer_capacity']=1 if write else 128
    return result
