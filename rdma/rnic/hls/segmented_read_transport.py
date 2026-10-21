#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private true segmented READ HLS source, one request/whole-WR receipt.

Extend the reviewed segmented WRITE/SEND source, never split READ into
independent READ_ONLY requests. Retain trusted response ownership, exact
payload extents and actual pointer/pool/timer/common-PSN consumers. Source
candidate only until execution/synthesis/native/kernel/timing qualification.
Expected REMOTE MSN wiring and mid-response retry recovery remain required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_request_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
JOIN=base.JOIN;RETRANS=base.RETRANS;once=base.once;change=base.change
NAME='rocev2_native_segmented_read_top'
PARENT=ROOT/'rdma/rnic/build/native-segmented-request-transport-003'

RX_BIND=r'''
            if(isResponse) {
                as02ReqRxOwner d=response_active ? response_owner:request_rx_owners.read();
                bool read=d.opcode==RC_RDMA_READ_REQUEST;
                bool atomic=d.opcode==RC_COMPARE_SWAP || d.opcode==RC_FETCH_ADD;
                ap_uint<32> span=read && d.bytes ? ap_uint<32>((d.bytes+PMTU-1)/PMTU):ap_uint<32>(1);
                ap_uint<8> expected=atomic ? ap_uint<8>(RC_ATOMIC_ACK):!read ? ap_uint<8>(RC_ACK):
                    span==1 ? ap_uint<8>(RC_RDMA_READ_RESP_ONLY):response_index==0 ? ap_uint<8>(RC_RDMA_READ_RESP_FIRST):
                    response_index+1==span ? ap_uint<8>(RC_RDMA_READ_RESP_LAST):ap_uint<8>(RC_RDMA_READ_RESP_MIDDLE);
                if(!as02_req_token_valid(d.token) || d.token(23,0)!=meta.dest_qp || emeta.isNak ||
                   d.bytes>1048576 || meta.op_code!=expected || (read && meta.psn!=qpState.epsn) || response_index>=span) {
                    fault=true;regRequestRxFault=1;return;
                }
                meta.request_owned=true;meta.request_token=d.token;
                response_owner=d;response_active=read && response_index+1<span;
                response_index=response_active ? ap_uint<16>(response_index+1):ap_uint<16>(0);
            }
'''

RX_READ_AETH=r'''
            if(meta.request_owned && meta.op_code!=RC_RDMA_READ_RESP_ONLY) {
                bool first=meta.op_code==RC_RDMA_READ_RESP_FIRST;
                ap_uint<32> left=first ? readReqInit.length:read_left;
                ap_uint<32> bytes=first ? ap_uint<32>(PMTU):left;
                ap_uint<32> padded=(bytes+3)&0xfffffffc;
                if(!readReqInit.request_owned || readReqInit.request_token!=meta.request_token ||
                   readReqInit.request_opcode!=RC_RDMA_READ_REQUEST || !readReqInit.lst ||
                   ackHeader.getSyndrome()(7,5)!=0 || payLoadLength!=padded ||
                   (first ? (read_active || left<=PMTU || left>1048576):
                    (!read_active || read_token!=meta.request_token || !left || left>PMTU))) {
                    request_fault=true;regRequestExhFault=1;return;
                }
                ap_uint<64> address=first ? readReqInit.laddr:ap_uint<64>(read_base+read_offset);
                pkgShift s(SHIFT_AETH,meta.dest_qp);s.request_owned=true;s.request_token=meta.request_token;
                s.request_psn=meta.psn;s.request_opcode=ap_uint<8>(meta.op_code);
                s.request_length_checked=true;s.request_bytes=padded;rx_pkgShiftTypeFifo.write(s);
                memoryWriteCmd.write(as02_duplex_command(memCmd(address,padded,!first,PKG_HOST,meta.dest_qp),true));
                if(first) {
                    read_active=true;read_token=meta.request_token;read_base=readReqInit.laddr;
                    read_left=left-PMTU;read_offset=PMTU;
                } else {read_active=false;read_left=0;read_offset=0;}
                // Owned READ uses its own saved address, not the inbound
                // responder MSN table's WRITE placement cursor.
                rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));pe_fsmState=META;break;
            }
'''

RX_READ_MIDDLE=r'''
            if(meta.request_owned) {
                payLoadLength=udpLength-(8+12+4);
                if(!read_active || read_token!=meta.request_token || read_left<=PMTU || payLoadLength!=PMTU) {
                    request_fault=true;regRequestExhFault=1;return;
                }
                pkgShift s(SHIFT_NONE,meta.dest_qp);s.request_owned=true;s.request_token=meta.request_token;
                s.request_psn=meta.psn;s.request_opcode=RC_RDMA_READ_RESP_MIDDLE;
                s.request_length_checked=true;s.request_bytes=PMTU;rx_pkgShiftTypeFifo.write(s);
                memoryWriteCmd.write(as02_duplex_command(memCmd(read_base+read_offset,PMTU,PKG_NF,PKG_HOST,meta.dest_qp),true));
                read_left-=PMTU;read_offset+=PMTU;
                rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));pe_fsmState=META;break;
            }
'''

PAYLOAD_HELPER=r'''
template<int WIDTH> bool as02_read_payload_extent(pkgShift shift,net_axis<WIDTH> word,ap_uint<32>& copied) {
#pragma HLS inline
    if(!shift.request_length_checked)return true;
    ap_uint<16> count=0;
    for(unsigned b=0;b<WIDTH/8;b++)count+=word.keep[b];
    ap_uint<WIDTH/8+1> mask=(ap_uint<WIDTH/8+1>(1)<<count)-1;
    ap_uint<33> next=ap_uint<33>(copied)+count;
    if(!shift.request_owned || !count || word.keep!=mask || next>shift.request_bytes ||
       bool(word.last)!=(next==shift.request_bytes))return false;
    copied=next;return true;
}
'''


def derive():
    out=base.derive()
    t=out[HPP]
    t=once(t,'(op==1 || op==3) ? 1048576U:4096U','(op==1 || op==2 || op==3) ? 1048576U:4096U')
    t=once(t,'struct as02ReqStep {',r'''
struct as02ReqRxOwner {
    as02ReqToken token=0;ap_uint<8> opcode=0;ap_uint<32> bytes=0;
    as02ReqRxOwner() {}
    as02ReqRxOwner(as02ReqToken t,ap_uint<8> o,ap_uint<32> n):token(t),opcode(o),bytes(n) {}
};
inline ap_uint<32> as02_read_response_span(ap_uint<748> n) {
    return n(339,324)==2 && n(307,276)>PMTU ? ap_uint<32>((ap_uint<32>(n(307,276))+PMTU-1)/PMTU):ap_uint<32>(1);
}
struct as02ReqStep {''')
    t=once(t,'as02ReqToken token=0;ap_uint<24> psn=0;ap_uint<8> opcode=0;',
        'as02ReqToken token=0;ap_uint<24> psn=0;ap_uint<8> opcode=0;ap_uint<32> bytes=0;')
    t=once(t,'struct as02ReqReclaim {',r'''
inline as02ReqStep as02_read_release_step(ap_uint<748> owner,as02ReqStep issued) {
    if(owner(339,324)==2)issued.psn+=as02_read_response_span(owner)-1;
    return issued;
}
struct as02ReqReclaim {''')
    t=once(t,'struct pkgShift\n{','struct pkgShift\n{\n    bool request_length_checked=false;ap_uint<32> request_bytes=0;')
    out[HPP]=t
    t=out[CPP]
    if t.count('stream<as02ReqToken>& request_rx_owners')!=2:raise ValueError('two actual RX owner consumers required')
    t=t.replace('stream<as02ReqToken>& request_rx_owners','stream<as02ReqRxOwner>& request_rx_owners')
    t=once(t,'stream<as02ReqToken>& rx_owners)', 'stream<as02ReqRxOwner>& rx_owners)')
    t=once(t,'if(add_rx_owner)rx_owners.write(token);',
        'if(add_rx_owner)rx_owners.write(as02ReqRxOwner(token,ap_uint<8>(op),bytes));')
    t=once(t,'request_admitted.write(n);request_rx_owners.write(token);',
        'request_admitted.write(n);request_rx_owners.write(as02ReqRxOwner(token,as02_req_opcode(n),ap_uint<32>(n(307,276))));')
    t=once(t,'static stream<as02ReqToken> request_rx_owners("request_rx_owners");',
        'static stream<as02ReqRxOwner> request_rx_owners("request_rx_owners");')
    def ibh(t):
        marker='static bool fault=false;regRequestRxFault=fault;if(fault)return;'
        t=once(t,marker,marker+'\n    static as02ReqRxOwner response_owner;\n    static bool response_active=false;static ap_uint<16> response_index=0;')
        t=once(t,'(!isResponse || !request_rx_owners.empty())','(!isResponse || response_active || !request_rx_owners.empty())')
        a=t.index('            if(isResponse) {');b=t.index('\n\t\t\t//ap_uint<24> oldest_outstanding_psn',a)
        return t[:a]+RX_BIND+t[b:]
    t=change(t,'void rx_ibh_fsm(',ibh)
    def exh(t):
        marker='static bool request_fault=false;regRequestExhFault=request_fault;if(request_fault)return;'
        t=once(t,marker,marker+'\n    static bool read_active=false;static as02ReqToken read_token=0;\n    static ap_uint<64> read_base=0;static ap_uint<32> read_left=0,read_offset=0;')
        marker='\t\t\tif(meta.request_owned && (!readReqInit.request_owned || readReqInit.request_token!=meta.request_token ||'
        t=once(t,marker,RX_READ_AETH+marker)
        marker='            pkgShift s(SHIFT_AETH,meta.dest_qp);s.request_owned=meta.request_owned;s.request_token=meta.request_token;'
        t=once(t,marker,marker+r'''
            if(meta.request_owned) {
                ap_uint<32> expected=(readReqInit.length+3)&0xfffffffc;
                if(read_active || readReqInit.length>PMTU || payLoadLength!=expected) {
                    request_fault=true;regRequestExhFault=1;return;
                }
                s.request_length_checked=true;s.request_bytes=expected;
            }
''')
        marker='\t\tcase RC_RDMA_READ_RESP_MIDDLE:\n'
        return once(t,marker,marker+RX_READ_MIDDLE)
    t=change(t,'void rx_exh_fsm(',exh)
    def merge(t):
        marker='static bool fault=false;regRequestPayloadFault=fault;if(fault)return;'
        t=once(t,marker,marker+'\n    static ap_uint<32> copied=0;')
        t=once(t,'rx_pkgShiftTypeFifo.read(shift);','rx_pkgShiftTypeFifo.read(shift);copied=0;')
        marker='\t\t\tm_axis_mem_write_data.write(currWord);'
        if t.count(marker)!=3:raise ValueError('all three actual payload branches required')
        t=t.replace(marker,'            if(!as02_read_payload_extent<WIDTH>(shift,currWord,copied)){\n'
            '                fault=true;regRequestPayloadFault=1;state=QUARANTINE;return;\n            }\n'+marker)
        return once(t,'request_read_consumed.write(as02ReqStep(shift.request_token,shift.request_psn,shift.request_opcode));',
            'as02ReqStep receipt(shift.request_token,shift.request_psn,shift.request_opcode);\n'
            '        receipt.bytes=shift.atomic_result ? ap_uint<32>(8):copied;request_read_consumed.write(receipt);')
    t=change(t,'void merge_rx_pkgs(',merge)
    t=once(t,'template <int WIDTH, int INSTID = 0>\n\n// STREAM MERGE',PAYLOAD_HELPER+'\ntemplate <int WIDTH, int INSTID = 0>\n\n// STREAM MERGE')
    out[CPP]=t
    t=out[RETRANS]
    t=once(t,'struct retransMetaReq\n{','struct retransMetaReq\n{\n    bool request_progress=false;')
    t=once(t,'if(req.entry.request_owned){receipt_index=req.idx;receipt_phase=1;}',
        'if(req.entry.request_owned && !req.request_progress){receipt_index=req.idx;receipt_phase=1;}')
    t=once(t,'(meta.opCode==RC_RDMA_READ_REQUEST && update.op_code==RC_RDMA_READ_RESP_ONLY)',
        '(meta.opCode==RC_RDMA_READ_REQUEST && ((meta.length>PMTU &&\n'
        '                  (update.op_code==RC_RDMA_READ_RESP_FIRST || update.op_code==RC_RDMA_READ_RESP_MIDDLE)) ||\n'
        '                  (meta.length<=PMTU && (update.op_code==RC_RDMA_READ_RESP_LAST || update.op_code==RC_RDMA_READ_RESP_ONLY))))')
    t=once(t,'metaReqFifo.write(retransMetaReq(ptrMeta.head, retransMetaEntry(meta)));',
        'retransMetaReq progress(ptrMeta.head,retransMetaEntry(meta));progress.request_progress=update.request_owned;\n'
        '                    metaReqFifo.write(progress);')
    t=once(t,'pointerUpdate p(update.qpn,ptrMeta);p.request_release=meta.request_owned;',
        'pointerUpdate p(update.qpn,ptrMeta);p.request_release=meta.request_owned &&\n'
        '                update.op_code!=RC_RDMA_READ_RESP_FIRST && update.op_code!=RC_RDMA_READ_RESP_MIDDLE;')
    out[RETRANS]=t
    t=out[JOIN]
    t=once(t,'PACKET,POINTER,','PACKET,READ_RX_TIMER,POINTER,')
    t=once(t,'static ap_uint<32> segment_offset=0;static ap_uint<24> first_psn=0;',
        'static ap_uint<32> segment_offset=0;static ap_uint<24> first_psn=0;\n    static ap_uint<16> read_packets=0;')
    t=once(t,'segment_offset=0;phase=ISSUE;','segment_offset=0;read_packets=0;phase=ISSUE;')
    a=t.index('            if(r.token!=issued_step.token || r.psn!=issued_step.psn ||');b=t.index('\n        }\n    } else if(phase==POINTER',a)
    t=t[:a]+r'''
            ap_uint<32> span=as02_read_response_span(owner);
            ap_uint<8> expected=atomic ? ap_uint<8>(RC_ATOMIC_ACK):!read ? ap_uint<8>(RC_ACK):
                span==1 ? ap_uint<8>(RC_RDMA_READ_RESP_ONLY):read_packets==0 ? ap_uint<8>(RC_RDMA_READ_RESP_FIRST):
                read_packets+1==span ? ap_uint<8>(RC_RDMA_READ_RESP_LAST):ap_uint<8>(RC_RDMA_READ_RESP_MIDDLE);
            ap_uint<32> remaining=ap_uint<32>(owner(307,276))-ap_uint<32>(read_packets)*PMTU;
            ap_uint<32> count=remaining>PMTU ? ap_uint<32>(PMTU):remaining;
            ap_uint<32> bytes=atomic ? ap_uint<32>(8):ap_uint<32>((count+3)&0xfffffffc);
            if(r.token!=issued_step.token || r.psn!=ap_uint<24>(issued_step.psn+(read ? read_packets:ap_uint<16>(0))) ||
               r.opcode!=expected || (read && r.bytes!=bytes)) {fault=true;return;}
            if(read && !atomic)read_packets++;
            phase=(read && !atomic && span>1 && read_packets==1) ? READ_RX_TIMER:
                (read && !atomic && read_packets<span) ? PACKET:POINTER;
'''+t[b:]
    marker='    } else if(phase==POINTER && !pointer_released.empty()) {'
    t=once(t,marker,'''    } else if(phase==READ_RX_TIMER && !rx_timer_consumed.empty()) {
        as02ReqStep r=rx_timer_consumed.read();
        if(r.token!=issued_step.token || r.psn!=issued_step.psn){fault=true;return;}
        phase=PACKET;
'''+marker)
    old='!as02_req_step_equal(r.step,issued_step)'
    if t.count(old)!=2:raise ValueError('actual pointer AND pool receipt joins required')
    t=t.replace(old,'!as02_req_step_equal(r.step,as02_read_release_step(owner,issued_step))')
    t=once(t,'if(r.token!=issued_step.token || r.psn!=issued_step.psn){fault=true;return;}phase=QUERY;',
        'if(r.token!=issued_step.token || r.psn!=as02_read_release_step(owner,issued_step).psn){fault=true;return;}phase=QUERY;')
    t=once(t,'ap_uint<24> next=ap_uint<25>(issued_step.psn)+1;',
        'ap_uint<24> next=ap_uint<24>(issued_step.psn+as02_read_response_span(owner));')
    t=once(t,'r.next=ap_uint<24>(issued_step.psn+1);','r.next=ap_uint<24>(issued_step.psn+as02_read_response_span(owner));')
    out[JOIN]=t;out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=base.NAME:raise ValueError('reviewed full segmented parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h:raise ValueError('parent derived body changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(scope=__doc__,HLS_top=NAME,source_only=True,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},original_unchanged=True,
        large_READ_max_bytes=1048576,large_WRITE_SEND_max_bytes=1048576,Immediate_max_bytes=4096,
        packet_payload_bytes=4096,whole_WR_owner_bits=748,request_done_bits=816,SQ_bits=408,MAX_QPS=8,metadata_entries=2000,
        trusted_REMOTE_MSN_source_implemented=False,mid_READ_retry_recovery_qualified=False,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
